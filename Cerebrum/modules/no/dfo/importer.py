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
DFØ import.
"""
from Cerebrum.modules.hr_import.config import get_configurable_module
from Cerebrum.modules.no.dfo.client import get_client
from Cerebrum.modules.no.dfo.datasource import EmployeeDatasource
from Cerebrum.modules.no.dfo.mapper import EmployeeMapper
from Cerebrum.Utils import Factory


class EmployeeImport(object):
    """
    A DFØ employee import
    """

    def __init__(self, db, config):
        client_config = get_configurable_module(config.client)
        client = get_client(client_config)
        datasource = EmployeeDatasource(client)
        mapper_config = get_configurable_module(config.mapper)
        mapper = EmployeeMapper(mapper_config)
        co = Factory.get('Constants')(db)
        super(EmployeeImport, self).__init__(db, datasource, mapper,
                                             co.system_dfo_sap)
        # TODO: denne brekker vel? Er ingen superklasse
