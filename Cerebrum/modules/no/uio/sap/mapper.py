# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Mapper for SAPUiO.
"""
import logging

from Cerebrum.modules.hr_import import mapper as _base
from Cerebrum import Errors
from Cerebrum.Utils import Factory

# TODO: Move populate.* into this module
from .populate import populate_hr_person

logger = logging.getLogger(__name__)


class EmployeeMapper(_base.AbstractMapper):
    """
    """
    def __init__(self, db):
        self.db = db
        self.const = Factory.get('Constants')(db)

    def find_entity(self, hr_object):
        """ Extract reference from event. """
        db_object = Factory.get('Person')(self.db)

        match_ids = (
            self.const.externalid_sap_ansattnr,
            hr_object.hr_id,
            self.const.system_sap,
        ) + tuple(
            (i.id_type, i.external_id)
            for i in hr_object.external_ids
        )

        try:
            db_object.find_by_external_ids(*match_ids)
            logger.info('Found existing person with id=%r',
                        db_object.entity_id)
        except Errors.NotFoundError:
            logger.debug('could not find person by id_type=%r',
                         tuple(i[0] for i in match_ids))
            raise _base.NoMappedObjects('no matching persons')
        except Errors.TooManyRowsError as e:
            # TODO: Include which entity in error?
            raise _base.ManyMappedObjects(
                'Person mismatch: found multiple matches: {}'.format(e))
        return db_object

    def translate(self, reference, obj):
        person, assignments, roles = obj
        return populate_hr_person(person, assignments, roles, self.db)
