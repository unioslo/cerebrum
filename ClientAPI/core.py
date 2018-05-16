# -*- coding: utf-8 -*-
# Copyright 2014-2018 University of Oslo, Norway
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
"""Core functionality and utilities for the ClientAPI."""

from __future__ import unicode_literals

from Cerebrum.Utils import Factory
from Cerebrum import Errors
import twisted.python.log


class SimpleLogger(object):
    """ Simple log wrapper. This logger use the same API as the Cerebrum
    logger. Set up to log to L{twisted.python.log}.
    """

    def __init__(self):
        pass

    def _log(self, level, msg, *args):
        """ Log to the twisted logger."""
        # TODO: note that this has to be changed if we won't use twisted in
        # the future
        twisted.python.log.msg(level + (msg % args if args else msg))

    def error(self, msg, *args):
        """ Log an error. Will show up as 'ERROR: <msg>' """
        self._log('ERROR:', msg, *args)

    def warning(self, msg, *args):
        """ Log a warning. Will show up as 'WARNING: <msg>' """
        self._log('WARNING:', msg, *args)

    def info(self, msg, *args):
        """ Log a notice. Will show up as 'INFO: <msg>' """
        self._log('INFO:', msg, *args)

    def debug(self, msg, *args):
        """ Log a debug notice. Will show up as 'DEBUG: <msg>' """
        self._log('DEBUG:', msg, *args)


class ClientAPI(object):
    """ The base class for a CIS module. Sets up the db-connection, changelog
    and log. Contains common helper functions.
    """

    def __init__(self, name):
        """Init logger and database object.

        :type name: str
        :param name: A name identifying this instance, for the changelog.
        """
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program=name)

        # TODO: pythons logger?
        self.log = SimpleLogger()
        self.operator_id = None

    def close(self):
        """Explicitly close this instance of the class. This is to make sure
        that all is closed down correctly, even if the garbage collector can't
        destroy the instance. """
        try:
            self.db.close()
        except Exception, e:
            self.log.warning("Problems with db.close: %s", e)


# TODO: Should this be here?
class Utils(object):
    @staticmethod
    def get_entity_by_id(db, entity_id):
        """Fetch an entity by ID.

        :type db: <Cerebrum.database.Database>
        :param db: A Cerebrum database object.

        :type entity_id: int
        :param entity_id: The entity ID.
        """
        en = Factory.get('Entity')(db)
        try:
            en.find(entity_id)
        except Errors.NotFoundError:
            return None
        return en

    @staticmethod
    def get(db, entity_type, id_type, entity):
        """Fetch an entity by entity and identifier type.

        :type db: <Cerebrum.database.Database>
        :param db: A Cerebrum database object

        :type etype: text
        :param etype: Type of entity to find
                      Valid entity types: 'entity', 'account', 'group'


        :type id_type: text
        :param id_type: The type of the identifier
                        Valid identifiers: 'id', 'account_name', 'group_name'

        :type entity: text
        :param entity: The identifier for the entity we want
        """
        obj = None

        if id_type == 'id':
            if entity_type == 'account':
                obj = Utils.get_account(db=db, id_type='id', account=entity)

            elif entity_type == 'group':
                obj = Utils.get_group(db=db, id_type='id', group=entity)

            else:
                obj = Utils.get_entity_by_id(db=db, entity_id=entity)

        elif id_type == 'group_name':
            obj = Utils.get_group(db=db, id_type='name', group=entity)

        elif id_type == 'account_name':
            obj = Utils.get_account(db=db, id_type='name', account=entity)

        return obj

    @staticmethod
    def get_entity_designator(entity):
        """Lookup entity's type, return entity designator compatible with get()

        :type entity: <Cerebrum.Entity.Entity> subtype
        :param entity: An entity holding the correct type

        :rtype: tuple(str, str)
        :returns: Values suitable for
            Utils.get(None, *Utils.get_entity_designator(entity))
        """
        if entity.__class__ is Factory.get("Account"):
            return "account_name", entity.account_name
        elif entity.__class__ is Factory.get("Group"):
            return "group_name", entity.group_name
        else:
            return "id", str(entity.entity_id)

    @staticmethod
    def get_account(db, id_type, account):
        """Fetch a group by id.

        :type db: <Cerebrum.database.Database>
        :param db: A Cerebrum database object.

        :type id_type: str
        :param id_type: The identifier type, 'name' or 'id'

        :type id_type: str or int
        :param group: The account identifier

        :rtype: Account or None
        """
        ac = Factory.get('Account')(db)

        if id_type == 'name':
            lookup = ac.find_by_name
        elif id_type == 'id':
            lookup = ac.find
        else:
            raise Errors.CerebrumRPCException('Invalid id_type.')

        try:
            lookup(account)
        except Errors.NotFoundError:
            return None
        return ac

    @staticmethod
    def get_group(db, id_type, group):
        """Fetch a group by id.

        :type db: <Cerebrum.database.Database>
        :param db: A Cerebrum database object.

        :type id_type: str
        :param id_type: The identifier type, 'name' or 'id'

        :type group: str or int
        :param group: The group identifier

        :rtype: Group or None
        """
        gr = Factory.get('Group')(db)

        # Determine lookup type
        if id_type == 'name':
            lookup = gr.find_by_name
        elif id_type == 'id':
            lookup = gr.find
        else:
            raise Errors.CerebrumRPCException('Invalid id_type.')

        # Perform actual lookup
        # TODO: How do we handle NotFoundErrors? Is this correct?
        try:
            lookup(group)
        except Errors.NotFoundError:
            return None
        return gr
