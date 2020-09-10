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
Generic HR import.
"""
import logging

from Cerebrum.Utils import Factory

from .importer import AbstractImport
# TODO: Move import_to_cerebrum.* into this module
from .import_to_cerebrum import HRDataImport

logger = logging.getLogger(__name__)


class EmployeeImportBase(AbstractImport):

    def create(self, employee_data):
        """ Create a new Person object using employee_data. """
        # TODO: Warn about name matches
        assert employee_data is not None
        person_obj = Factory.get('Person')(self.db)
        self.update_person(employee_data, person_obj)

    def update(self, employee_data, person_obj):
        """ Update the Person object using employee_data. """
        assert employee_data is not None
        assert person_obj is not None
        assert person_obj.entity_id
        updater = HRDataImport(self.db, employee_data, person_obj, logger)
        updater.update_person()

    def remove(self, person_obj):
        """ Clear HR data from a Person object. """
        assert person_obj is not None
        assert person_obj.entity_id
        # TODO: clear all sap-data (except ext-ids?)
