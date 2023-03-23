# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
BofhdRequests database abstraction.
"""
import datetime

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Errors
from Cerebrum.utils import date_compat
from Cerebrum.utils import date as date_utils

# TODO: Move to __init__
__version__ = "1.0"


def _get_batch_time(now):
    """
    Get time for batch commands.

    - If we are past 22:00 this day, schedule for tomorrow evening
    - Otherwise, schedule this evening at 22:00
    """
    batch_time = datetime.time(22)

    # We use get_datetime_tz to
    #  1. validate the value
    #  2. make sure it's in our local tz
    now = date_compat.get_datetime_tz(now, allow_none=False)

    curr_time = now.time()
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)

    batch_dt = datetime.datetime.combine(
        tomorrow if curr_time > batch_time else today,
        batch_time,
    )
    # We lost the (local) tzinfo from splitting and combining the date and time
    return date_utils.apply_timezone(batch_dt)


class BofhdRequests(object):

    def __init__(self, db, const):
        self._db = db
        self.co = const

        self.now = now = date_utils.now()
        self.batch_time = _get_batch_time(now)

        # "None" means _no_ conflicts, there can even be several of
        # that op pending.  All other ops implicitly conflict with
        # themselves, so there can only be one of each op.
        self.conflicts = {
            int(const.bofh_move_user): [
                const.bofh_move_student,
                const.bofh_move_user_now,
                const.bofh_move_request,
                const.bofh_delete_user,
            ],
            int(const.bofh_move_student): [
                const.bofh_move_user,
                const.bofh_move_user_now,
                const.bofh_move_request,
                const.bofh_delete_user,
            ],
            int(const.bofh_move_user_now): [
                const.bofh_move_student,
                const.bofh_move_user,
                const.bofh_move_request,
                const.bofh_delete_user,
            ],
            int(const.bofh_move_request): [
                const.bofh_move_user,
                const.bofh_move_user_now,
                const.bofh_move_student,
                const.bofh_delete_user,
            ],
            int(const.bofh_move_give): None,
            int(const.bofh_archive_user): [
                const.bofh_move_user,
                const.bofh_move_user_now,
                const.bofh_move_student,
                const.bofh_delete_user,
            ],
            int(const.bofh_delete_user): [
                const.bofh_move_user,
                const.bofh_move_user_now,
                const.bofh_move_student,
                const.bofh_email_create,
            ],
            int(const.bofh_email_create): [
                const.bofh_email_delete,
                const.bofh_delete_user,
            ],
            int(const.bofh_email_delete): [
                const.bofh_email_create,
            ],
            int(const.bofh_email_convert): [
                const.bofh_email_delete,
            ],
            int(const.bofh_sympa_create): [
                const.bofh_sympa_remove,
            ],
            int(const.bofh_sympa_remove): [
                const.bofh_sympa_create,
            ],
            int(const.bofh_quarantine_refresh): None,
            int(const.bofh_email_restore): [
                const.bofh_email_create,
            ],
            int(const.bofh_homedir_restore): [
                const.bofh_move_user,
                const.bofh_move_user_now,
                const.bofh_move_student,
                const.bofh_delete_user,
            ],
        }

    def get_conflicts(self, op):
        """
        Returns a list of conflicting operation types.

        :param op: operation type constant, or constant int value
        """
        conflicts = self.conflicts[int(op)]

        if conflicts is None:
            conflicts = []
        else:
            conflicts = list(conflicts)
            conflicts.append(op)
        # Make sure all elements in the returned list are integers
        return [int(c) for c in conflicts]

    def add_request(self, operator, when, op_code, entity_id,
                    destination_id, state_data=None):

        conflicts = self.get_conflicts(op_code)

        if entity_id is not None:
            # No need to check for conflicts when no entity is given
            for r in self.get_requests(entity_id=entity_id):
                if int(r['operation']) in conflicts:
                    conflict_op = self.co.BofhdRequestOp(r['operation'])
                    raise CerebrumError("Conflicting request exists (%s)"
                                        % (conflict_op.description,))

        reqid = int(self._db.nextval('request_id_seq'))
        cols = {
            'requestee_id': operator,
            'run_at': when,
            'operation': int(op_code),
            'entity_id': entity_id,
            'destination_id': destination_id,
            'state_data': state_data,
            'request_id': reqid,
        }

        order = tuple(sorted(cols.keys()))
        self._db.execute(
            """
              INSERT INTO [:table schema=cerebrum name=bofhd_request]
                ({tcols})
              VALUES
                ({binds})
            """.format(
                tcols=", ".join(order),
                binds=", ".join(":{}".format(t) for t in order),
            ),
            cols,
        )
        return reqid

    def delay_request(self, request_id, minutes=10):
        for r in self.get_requests(request_id):
            # Note: the semantics of time objects is DB driver
            # dependent, and not standardised in PEP 249.
            # PgSQL will convert to ticks when forced into int().
            run_at = date_compat.get_datetime_tz(r['run_at'])
            if not run_at or run_at < self.now:
                run_at = self.now
            new_run_at = run_at + datetime.timedelta(minutes=minutes)
            self._db.execute(
                """
                  UPDATE [:table schema=cerebrum name=bofhd_request]
                  SET run_at=:when
                  WHERE request_id=:id
                """,
                {
                    'when': new_run_at,
                    'id': request_id,
                },
            )
            return
        raise Errors.NotFoundError("No such request: " + repr(request_id))

    def delete_request(self, entity_id=None, request_id=None,
                       operator_id=None, operation=None):
        cols = {}
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if request_id is not None:
            cols['request_id'] = request_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        self._db.execute(
            """
              DELETE FROM [:table schema=cerebrum name=bofhd_request]
              WHERE {}
            """.format(
                " AND ".join("{0}=:{0}".format(x) for x in cols.keys())
            ),
            cols,
        )

    def get_requests(self, request_id=None, operator_id=None, entity_id=None,
                     operation=None, destination_id=None, given=False,
                     only_runnable=False):
        cols = {}
        if request_id is not None:
            cols['request_id'] = request_id
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        if destination_id is not None:
            cols['destination_id'] = int(destination_id)
        where = ["%s = :%s" % (x, x) for x in cols.keys()]
        if only_runnable:
            cols['now'] = date_utils.now()
            where.append("run_at <= :now")

        qry = """
          SELECT request_id, requestee_id, run_at, operation, entity_id,
                 destination_id, state_data
          FROM [:table schema=cerebrum name=bofhd_request]
          WHERE {}
        """
        ret = self._db.query(qry.format(" AND ".join(where)), cols)
        if given:
            group = Factory.get('Group')(self._db)
            tmp = [str(x["group_id"])
                   for x in group.search(member_id=operator_id,
                                         indirect_members=True)]
            if len(tmp) > 0:
                extra_where = "AND destination_id IN (%s)" % ", ".join(tmp)
            else:
                extra_where = ""
            ret.extend(
                self._db.query(
                    qry.format("operation=:op " + extra_where),
                    {'op': int(self.co.bofh_move_give)}))
        return ret

    def get_operations(self):
        """
        Retrieves the various types/operations that it is possible
        to generate bofhd-requests for.
        """
        qry = """
          SELECT code, code_str, description
          FROM [:table schema=cerebrum name=bofhd_request_code]
          ORDER BY code_str
        """
        return self._db.query(qry)
