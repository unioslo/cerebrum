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
"""Generalized Entity operations presented in a functional API."""

import cerebrum_path
getattr(cerebrum_path, '', None)  # Silence the linter.
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from ClientAPI.core import ClientAPI
from ClientAPI.core import Utils

from Cerebrum.modules.bofhd.auth import BofhdAuth


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
        import mx
        from Cerebrum.QuarantineHandler import QuarantineHandler

        co = Factory.get('Constants')(self.db)
        # q[i] = {quarantine_type: int, creator_id: int, description: string,
        #         create_date: DateTime, start_date: DateTime,
        #         disable_until: DateTime, DateTime: end_date}
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
                qtype = co.map_const(qt)
                types[qt] = qtype
                qhandlers[qt] = QuarantineHandler(self.db, [qtype])
                new['quarantine_type'] = str(qtype)
                new['lock_out'] = qhandlers[qt].is_locked()
            new['is_active'] = (row['start_date'] <= now and
                                (row['end_date'] is None or
                                    row['end_date'] > now) and
                                (row['disable_until'] is None or
                                    row['disable_until'] <= now))
            new['auto'] = (str(types[qt]) in cereconf.QUARANTINE_AUTOMATIC or
                           str(types[qt]) in
                           cereconf.QUARANTINE_STRICTLY_AUTOMATIC)
            for i in ('description', 'start_date',
                      'end_date', 'disable_until'):
                new[i] = row[i]
            return new
        return map(fixer, q)

    def spread_list(self, id_type, entity_id):
        """List account's spreads.

        :type id_type: basestring
        :param id_type: The id-type to look-up by.

        :type entity_id: basestring
        :param entity_id: The entitys id."""
        co = Factory.get('Constants')(self.db)
        e = Utils.get(self.db, 'entity', id_type, entity_id)
        spreads = dict()

        def fixer(id):
            if id[0] in spreads:
                return str(spreads[id[0]])
            s = spreads[id[0]] = co.map_const(id[0])
            return str(s)
        try:
            return map(fixer, e.get_subclassed_object().get_spread())
        except NameError:
            raise Errors.CerebrumRPCException("No spreads in entity")

    def in_system(self, id_type, entity_id, system):
        """Check if a user is represented in a system.

        :type id_type: basestring
        :param id_type: The id-type to look-up by.

        :type entity_id: basestring
        :param entity_id: The entitys id.

        :type system: basestring
        :param system: The system to check."""
        co = Factory.get('Constants')(self.db)

        # Fetch entity
        e = Utils.get(self.db, 'entity', id_type, entity_id)
        if not e:
            # TODO: Should this be raised in the Utils-module/class/whatever?
            raise Errors.CerebrumRPCException('Entity does not exist')

        try:
            sys = co.Spread(system)
            int(sys)
        except Errors.NotFoundError:
            raise Errors.CerebrumRPCException('System does not exist')

        try:
            return bool(e.get_subclassed_object().has_spread(sys))
        except AttributeError:
            # If we wind up here, the entity does not have the EntitySpread
            # class mixed into itself. When the EntitySpread-class is not mixed
            # in, we get an AttributeError since has_spread() is not defined.
            # TBD: Return false, or raise something?
            return False

    def active_in_system(self, id_type, entity_id, system):
        """Check if a user is represented and active in a system.

        :type id_type: basestring
        :param id_type: The id-type to look-up by.

        :type entity_id: basestring
        :param entity_id: The entitys id.

        :type system: basestring
        :param system: The system to check."""
        # Check for existing quarantines on the entity that are locking the
        # entity out, and also check if the entity is in the system.
        if (filter(lambda x: bool(x['lock_out']) is True,
            self.quarantine_list(id_type, entity_id)) or not
                self.in_system(id_type, entity_id, system)):
            return False
        else:
            return True
