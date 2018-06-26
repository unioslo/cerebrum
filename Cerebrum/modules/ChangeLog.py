#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2016 University of Oslo, Norway
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
""" A changelog API that stores changes in the Database. """

import Cerebrum.ChangeLog
from Cerebrum.Utils import argument_to_sql
import Cerebrum.utils.json as json


__version__ = "1.5"


def _params_to_db(params, separators=(',', ':')):
    """ Return None or json of params.

    :param params: Params to json, mostly dicts or None
    :param separators: See json.dumps. Default is the most compact style.
    """
    if params is None:
        return None
    return json.dumps(params, separators=separators)


class ChangeLog(Cerebrum.ChangeLog.ChangeLog):
    # Don't want to override the Database constructor
    def cl_init(self, change_by=None, change_program=None, **kw):
        super(ChangeLog, self).cl_init(**kw)
        self.change_by = change_by
        self.change_program = change_program
        self.messages = []

    def update_log_event(self, change_id, change_params):
        """ Update a logged change.

        This method is typically used to update/replace the json parameters
        that are stored in the changelog entry.

        :param int change_id:
            The change id

        :param change_params:
            The parameters to store in the change entry. This can be
            None (remove parameters), or any json-able object.

        """
        self.execute("""
        UPDATE [:table schema=cerebrum name=change_log]
        SET change_params=:change_params
        WHERE change_id=:change_id""", {
            'change_id': int(change_id),
            'change_params': _params_to_db(change_params)})

    def remove_log_event(self, change_id):
        """ Remove a logged change.

        :param int change_id: The change id

        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=change_log]
        WHERE change_id=:change_id""", {
            'change_id': int(change_id)})

    def log_change(self,
                   subject_entity,
                   change_type_id,
                   destination_entity,
                   change_params=None,
                   change_by=None,
                   change_program=None,
                   skip_change=False,
                   **kw):
        """ Log a change.

        :param int subject_entity:
            Subject entity?

        :param int,ChangeType change_type_id:
            The type of change

        :param int destination_entity:
            Destination entity?

        :param None,dict change_params:
            None, or json-able object to store with the change entry.

        :param int change_by:
            The entity that performed the change, if any. Default: Value
            initialized by cl_init.

        :param str change_program:
            The script, system  or daemon that performed the change. Default:
            Value initialized by cl_init, if any.

        :param bool skip_change:
            If no entry should be stored in the database for this change.
            Default: False

        NOTE: change_by or change_program must be set when logging a change.

        """
        super(ChangeLog, self).log_change(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params=change_params,
            change_by=change_by,
            change_program=change_program,
            **kw)
        if skip_change:
            return
        self.messages.append(
            dict(
                subject_entity=subject_entity,
                change_type_id=int(change_type_id),
                destination_entity=destination_entity,
                change_by=self.change_by if change_by is None else change_by,
                change_program=(self.change_program if change_program is None
                                else change_program),
                change_params=_params_to_db(change_params)))

    def clear_log(self):
        """See write_log"""
        super(ChangeLog, self).clear_log()
        self.messages = []

    def write_log(self):
        """ Write change entries to the database.

        This method should be called right before a database commit to
        synchronize the changes and change entries.

        """
        super(ChangeLog, self).write_log()

        for m in self.messages:
            m['id'] = int(self.nextval('change_log_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=change_log]
               (change_id, subject_entity, change_type_id, dest_entity,
                change_params, change_by, change_program)
            VALUES (:id, :subject_entity, :change_type_id,
                    :destination_entity, :change_params, :change_by,
                    :change_program)""", m)
        self.messages = []

    def get_log_events(self, start_id=0, max_id=None, types=None,
                       subject_entity=None, dest_entity=None,
                       any_entity=None, change_by=None, change_program=None,
                       sdate=None, return_last_only=False, limit=None):
        """ Fetch change entries from the database.

        :param int start_id:
            The first change id that should be returned.

        :param int max_id:
            The last change id that should be returned.

        :param int|Constants.ChangeType types:
            Filter changes by a given change type.

        :param int subject_entity:
            Filter changes by a given subject entity.

        :param int dest_entity:
            Filter changes by a given destination entity.

        :param int any_entity:
            Filter changes where the given entity is either subject entity or
            destination entity.
            NOTE: Cannot be used with `subject_entity' or `dest_entity'.

        :param int change_by:
            Filter change by the entity that performed the change.

        :param str change_program:
            Filter change by the script that caused the change.

        :param string sdate:
            Filter changes by date (YYYY-MM-DD). All changes before this date
            are filtered.

        :param boolean return_last_only:
            Only return the last change. Default: False.
            NOTE: Requires `types' to be used as well.
        :param int limit:
            Perform LIMIT in SQL query.

        :return list|dbrow:
            Returns a list of dbrow results. If `return_last_only' is set, only
            one row is returned.

        """
        if any_entity and (dest_entity or subject_entity):
            raise self.ProgrammingError("any_entity is mutually exclusive "
                                        "with dest_entity or subject_entity")
        if return_last_only and not types:
            raise self.ProgrammingError(
                "you need to choose at least one change type "
                "to deliver last cl entry for")
        where = ["change_id >= :start_id"]
        bind = {'start_id': int(start_id)}
        if subject_entity is not None:
            where.append(argument_to_sql(subject_entity, "subject_entity",
                                         bind, int))
        if dest_entity is not None:
            where.append("dest_entity=:dest_entity")
            bind['dest_entity'] = int(dest_entity)
        if any_entity is not None:
            where.append("subject_entity=:any_entity OR "
                         "dest_entity=:any_entity")
            bind['any_entity'] = int(any_entity)
        if change_by is not None:
            where.append("change_by=:change_by")
            bind['change_by'] = int(change_by)
        if change_program is not None:
            where.append("change_program=:change_program")
            bind['change_program'] = change_program
        if max_id is not None:
            where.append("change_id <= :max_id")
            bind['max_id'] = int(max_id)
        if types is not None:
            where.append(argument_to_sql(types, "change_type_id", bind, int))
        if sdate is not None:
            where.append("tstamp > :sdate")
            bind['sdate'] = sdate
        where = "WHERE (" + ") AND (".join(where) + ")"
        if return_last_only:
            where = where + 'ORDER BY tstamp DESC LIMIT 1'
        elif limit:
            where = where + 'ORDER BY change_id LIMIT {}'.format(limit)
        else:
            where = where + 'ORDER BY change_id'
        return self.query("""
        SELECT tstamp, change_id, subject_entity, change_type_id, dest_entity,
               change_params, change_by, change_program
        FROM [:table schema=cerebrum name=change_log] %s
        """ % where, bind, fetchall=False)

    def get_log_events_date(self, type=None, sdate=None, edate=None):
        """ Fetch change entries from the database by date.

        :param int|Constants.ChangeType type:
            Filter changes by a given change type.

        :param string sdate:
            Filter changes by date (YYYY-MM-DD). All changes before this date
            are filtered.

        :param string edate:
            Filter changes by date (YYYY-MM-DD). All changes after this date
            are filtered.

        :return list:
            Returns a list of dbrow results.

        """
        where = []
        if type is not None:
            where.append("change_type_id = %s" % type)
        if sdate is not None:
            if edate is not None:
                where.append("""tstamp BETWEEN TO_DATE('%s', 'YYYY-MM-DD')
                                AND TO_DATE('%s', 'YYYY-MM-DD')""" % (sdate,
                                                                      edate))
            else:
                where.append("tstamp >= TO_DATE('%s', 'YYYY-MM-DD')" % sdate)
        else:
            if edate is not None:
                where.append("tstamp <= TO_DATE('%s', 'YYYY-MM-DD')" % edate)
        if (type, sdate, edate) is not None:
            where = "WHERE "+" AND ".join(where)
        return self.query("""
        SELECT tstamp, change_id, subject_entity, change_type_id,
               dest_entity, change_params, change_by, change_program
        FROM [:table schema=cerebrum name=change_log] %s
        ORDER BY change_id""" % where)

    def get_changetypes(self):
        """ List the change types registered in the database. """
        return self.query("""
        SELECT change_type_id, category, type, msg_string
        FROM [:table schema=cerebrum name=change_type]""")

    def get_last_changelog_id(self):
        """ Get the id of the last change entry in the database. """
        return self.query_1("""
        SELECT change_id
        FROM [:table schema=cerebrum name=change_log]
        ORDER BY change_id DESC LIMIT 1""")
