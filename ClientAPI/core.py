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
"""Core functionality an utilities for the ClientAPI."""

from Cerebrum.Utils import Factory
import twisted.python.log


class SimpleLogger(object):
    """ Simple log wrapper. This logger use the same API as the Cerebrum
    logger. Set up to log to L{twisted.python.log}.
    """

    def __init__(self):
        pass

    def _log(self, *args):
        """ Log to the twisted logger."""
        # TODO: note that this has to be changed if we won't use twisted in
        # the future
        twisted.python.log.msg(' '.join(args))

    def error(self, msg):
        """ Log an error. Will show up as 'ERROR: <msg>' """
        self._log('ERROR:', msg)

    def warning(self, msg):
        """ Log a warning. Will show up as 'WARNING: <msg>' """
        self._log('WARNING:', msg)

    def info(self, msg):
        """ Log a notice. Will show up as 'INFO: <msg>' """
        self._log('INFO:', msg)

    def debug(self, msg):
        """ Log a debug notice. Will show up as 'DEBUG: <msg>' """
        self._log('DEBUG:', msg)


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
            self.log.warning("Problems with db.close: %s" % e)


# TODO: Should this be here?
class Utils(object):
    @staticmethod
    def get_entity(db, entity_id):
        """Fetch an entity.

        :type db: <Cerebrum.Database.Database>
        :param db: A Cerebrum database object.

        :type entity_id: int
        :param entity_id: The entitys id.
        """
        en = Factory.get('Entity')(db)
        # TODO: How do we handle NotFoundErrors?
        en.find(entity_id)
        return en

    @staticmethod
    def get_group(db, id_type, group_id):
        """Fetch a group by id.

        :type db: <Cerebrum.Database.Database>
        :param db: A Cerebrum database object.

        :type id_type: str
        :param id_type: The identificators type, i.e. 'name'

        :param group_id: The groups idebtificator.
        """
        from Cerebrum import Errors
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
            lookup(group_id)
        except Errors.NotFoundError:
            return None
        return gr
