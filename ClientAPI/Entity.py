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

from __future__ import unicode_literals

from six import text_type

from Cerebrum import Errors
from Cerebrum.Utils import Factory

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

        :type service_name: string
        :param service_name: The calling serices name.
        """
        super(Entity, self).__init__(service_name)
        self.operator_id = operator_id
        self.config = config

        self.ba = BofhdAuth(self.db)

    def spread_list(self, id_type, entity_id):
        """List account's spreads.

        :type id_type: string
        :param id_type: The id-type to look-up by.

        :type entity_id: string
        :param entity_id: The entitys id."""
        co = Factory.get('Constants')(self.db)
        e = Utils.get(self.db, 'entity', id_type, entity_id)
        spreads = dict()

        def fixer(id):
            if id[0] in spreads:
                return text_type(spreads[id[0]])
            s = spreads[id[0]] = co.map_const(id[0])
            return text_type(s)
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
        # entity out (if the quarantine is active), and also check if the
        # entity is in the system.
        # TODO: Should this evaluate the shell set by quarantine rules? Some
        #       quarantines does not result in a locked-status, but has
        #       nologin-shells associated with them..
        import mx
        from Cerebrum.QuarantineHandler import QuarantineHandler

        co = Factory.get('Constants')(self.db)
        # q[i] = {quarantine_type: int, creator_id: int, description: string,
        #         create_date: DateTime, start_date: DateTime,
        #         disable_until: DateTime, DateTime: end_date}
        e = Utils.get(self.db, 'entity', id_type, entity_id)

        # Fetch quarantines if applicable
        try:
            quars = e.get_entity_quarantine()
        except AttributeError:
            quars = []

        now = mx.DateTime.now()

        locked = False
        for q in quars:
            # Use code string for quarantine type
            qt = q['quarantine_type']
            qtype = co.map_const(qt)
            qhandler = QuarantineHandler(self.db, [qtype])
            if (qhandler.is_locked() and
                    (q['start_date'] <= now and
                     (q['end_date'] is None or
                      q['end_date'] > now) and
                     (q['disable_until'] is None or
                      q['disable_until'] <= now))):
                locked = True
        if (locked or not self.in_system(id_type, entity_id, system)):
            return False
        else:
            return True

    @commit_handler()
    def add_to_system(self, id_type, entity_id, system):
        """Add an entity to a system.

        :type id_type: string
        :param id_type: The id-type to look-up by.

        :type entity_id: string
        :param entity_id: The entitys id.

        :type system: string
        :param system: The system the entity should be added to."""
        # Fetch entity
        en = Utils.get(self.db, 'entity', id_type, entity_id)
        if not en:
            # TODO: Should this be raised in the Utils-module/class/whatever?
            raise Errors.CerebrumRPCException('Entity does not exist')

        co = Factory.get('Constants')(self.db)

        try:
            sys = co.Spread(system)
            int(sys)
        except Errors.NotFoundError:
            raise Errors.CerebrumRPCException('System does not exist')

        self.ba.can_add_spread(self.operator_id, en, sys)

        try:
            if en.get_subclassed_object().has_spread(sys):
                return

            en.get_subclassed_object().add_spread(sys)
        except AttributeError:
            raise Errors.CerebrumRPCException('Can\'t add entity to system.')
        except self.db.IntegrityError:
            # TODO: This seems correct?
            raise Errors.CerebrumRPCException(
                'Entity not applicable for system.')
