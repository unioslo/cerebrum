# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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

import time

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Errors
from mx import DateTime


class BofhdRequests(object):
    def __init__(self, db, const):
        self._db = db
        self.co = const

        midnight = DateTime.today()
        now = DateTime.now()
        # if we are past 22:00 this day, schedule for tomorrow evening
        if (now - midnight) > DateTime.TimeDeltaFrom(hours=22):
            self.batch_time = midnight + DateTime.TimeDeltaFrom(days=1,
                                                                hours=22)
        # ... otherwise, schedule for this day
        else:
            self.batch_time = midnight + DateTime.TimeDeltaFrom(hours=22)

        self.now = now

        # "None" means _no_ conflicts, there can even be several of
        # that op pending.  All other ops implicitly conflict with
        # themselves, so there can only be one of each op.
        self.conflicts = {
            int(const.bofh_move_user): [const.bofh_move_student,
                                        const.bofh_move_user_now,
                                        const.bofh_move_request,
                                        const.bofh_delete_user],
            int(const.bofh_move_student): [const.bofh_move_user,
                                           const.bofh_move_user_now,
                                           const.bofh_move_request,
                                           const.bofh_delete_user],
            int(const.bofh_move_user_now): [const.bofh_move_student,
                                            const.bofh_move_user,
                                            const.bofh_move_request,
                                            const.bofh_delete_user],
            int(const.bofh_move_request): [const.bofh_move_user,
                                           const.bofh_move_user_now,
                                           const.bofh_move_student,
                                           const.bofh_delete_user],
            int(const.bofh_move_give): None,
            int(const.bofh_archive_user): [const.bofh_move_user,
                                           const.bofh_move_user_now,
                                           const.bofh_move_student,
                                           const.bofh_delete_user],
            int(const.bofh_delete_user): [const.bofh_move_user,
                                          const.bofh_move_user_now,
                                          const.bofh_move_student,
                                          const.bofh_email_create],
            int(const.bofh_email_create): [const.bofh_email_delete,
                                           const.bofh_delete_user],
            int(const.bofh_email_delete): [const.bofh_email_create],
            int(const.bofh_email_convert): [const.bofh_email_delete],
            int(const.bofh_sympa_create): [const.bofh_sympa_remove],
            int(const.bofh_sympa_remove): [const.bofh_sympa_create],
            int(const.bofh_quarantine_refresh): None,
            int(const.bofh_email_restore): [const.bofh_email_create],
            int(const.bofh_homedir_restore): [const.bofh_move_user,
                                              const.bofh_move_user_now,
                                              const.bofh_move_student,
                                              const.bofh_delete_user]
            }

    def get_conflicts(self, op):
        """Returns a list of conflicting operation types.  op can be
        an integer or a constant."""

        conflicts = self.conflicts[int(op)]

        if conflicts is None:
            conflicts = []
        else:
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
                    raise CerebrumError("Conflicting request exists (%s)" %
                                        self.co.BofhdRequestOp(r['operation']).
                                        description)

        reqid = int(self._db.nextval('request_id_seq'))
        cols = {
            'requestee_id': operator,
            'run_at': when,
            'operation': int(op_code),
            'entity_id': entity_id,
            'destination_id': destination_id,
            'state_data': state_data,
            'request_id': reqid
            }

        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_request] (%(tcols)s)
        VALUES (%(binds)s)""" % {
            'tcols': ", ".join(cols.keys()),
            'binds': ", ".join([":%s" % t for t in cols.keys()])},
                         cols)
        return reqid

    def delay_request(self, request_id, minutes=10):
        for r in self.get_requests(request_id):
            # Note: the semantics of time objects is DB driver
            # dependent, and not standardised in PEP 249.
            # PgSQL will convert to ticks when forced into int().
            t = int(r['run_at'])
            # don't use self.now, it's a DateTime object.
            now = time.time()
            if t < now:
                t = now
            when = self._db.TimestampFromTicks(int(t + minutes*60))
            self._db.execute("""
                UPDATE [:table schema=cerebrum name=bofhd_request]
                SET run_at=:when WHERE request_id=:id""",
                             {'when': when, 'id': request_id})
            return
        raise Errors.NotFoundError("No such request %d" % request_id)

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
            """DELETE FROM [:table schema=cerebrum name=bofhd_request]
            WHERE %s""" % " AND "
            .join(["%s=:%s" % (x, x) for x in cols.keys()]), cols)

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
            cols['now'] = DateTime.now()
            where.append("run_at <= :now")
        qry = """
        SELECT request_id, requestee_id, run_at, operation, entity_id,
               destination_id, state_data
        FROM [:table schema=cerebrum name=bofhd_request]
        WHERE """
        ret = self._db.query(qry + " AND ".join(where), cols)
        if given:
            group = Factory.get('Group')(self._db)
            tmp = [str(x["group_id"])
                   for x in group.search(member_id=operator_id,
                                         indirect_members=True)]
            extra_where = ""
            if len(tmp) > 0:
                extra_where = "AND destination_id IN (%s)" % ", ".join(tmp)
            ret.extend(self._db.query(qry + "operation=:op %s" % extra_where,
                                      {'op': int(self.co.bofh_move_give)}))
        return ret

    def get_operations(self):
        """Retrieves the various types/operations that it is possible
        to generate bofhd-requests for.

        """
        qry = """
        SELECT code, code_str, description
        FROM [:table schema=cerebrum name=bofhd_request_code]
        ORDER BY code_str
        """
        return self._db.query(qry)
