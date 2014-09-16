# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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
"""Account client stuff."""

# TODO: Describe the above better.

import cerebrum_path
getattr(cerebrum_path, '', None)  # Silence the linter.
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from ClientAPI.core import ClientAPI
from ClientAPI.core import Utils

from Cerebrum.modules.bofhd.auth import BofhdAuth

# TODO: move this?
from Cerebrum.modules.cis.Utils import commit_handler


class Entity(ClientAPI):
    """Exposing API for Account functions."""

    def __init__(self, operator_id, service_name, config):
        """Init the API.

        :type operator_id: int
        :param operator_id: The operators id, used for auth.

        :type service_name: str
        :param service_name: The calling serices name.
        """
        super(Entity, self).__init__(service_name)
        self.operator_id = operator_id
        self.config = config

        self.ba = BofhdAuth(self.db)

    def quarantine_list(self, id_type, entity_id):
        """Retrieve a list of entity's quarantines.

        :type id_type: basestring
        :param id_type: one of "id", "name", "uname", "gname"

        :type entity_id: basestring
        :param entity_id: textual representatiod of id in given type

        :rtype: list of dicts {
            quarantine_type: str (code)
            description: unicode
            start_date: datetime
            end_date: datetime
            disable_until: datetime
            is_active: boolean (if quarantine is active now)
            lock_out: boolean (if the quarantine means entity is locked out)
            auto: boolean (if the quarantine is set by automatic scripts)
        """
        # q[i] = {quarantine_type: int, creator_id: int, description: string,
        #         create_date: DateTime, start_date: DateTime, disable_until: DateTime, 
        #         DateTime: end_date}
        e = Utils.get(self.db, 'entity', id_type, entity_id)
        q = e.get_entity_quarantine()

        types = dict()
        qhandlers = dict()
        now = mx.DateTime.now()
        def fixer(row):
            # Use code string for quarantine type
            new = dict()
            qt = row['quarantine_type']
            if qt in types:
                new['quarantine_type'] = str(types[qt])
                new['lock_out'] = qhandlers[qt].is_locked()
            else:
                qtype = self.constants.map_const(qt)
                types[qt] = qtype
                qhandlers[qt] = QuarantineHandler(self.db, qtype)
                new['quarantine_type'] = str(qtype)
                new['lock_out'] = qtype.is_locked()
            new['is_active'] = (row['start_date'] <= now and 
                    (row['end_date'] is None or row['end_date'] > now) and
                    (row['disable_until'] is Null or row['disable_until'] <= now))
            new['auto'] = (str(types[qt]) in cereconf.QUARANTINE_AUTOMATIC
                    or str(types[qt]) in cereconf.QUARANTINE_STRICTLY_AUTOMATIC)
            for i in ('description', 'start_date', 'end_date', 'disable_until'):
                new[i] = row[i]
            return new
        return map(fixer, q)

    def spread_list(self, id_type, entity_id):
        """List account's spreads"""
        e = Utils.get(self.db, 'entity', id_type, entity_id)
        spreads = dict()
        def fixer(id):
            if id in spreads:
                return str(spreads[id])
            s = spreads[id] = self.constants.map_const(id)
            return s
        try:
            return map(fixer, e.get_spread())
        except NameError:
            raise Errors.CerebrumRPCException("No spreads in entity")

