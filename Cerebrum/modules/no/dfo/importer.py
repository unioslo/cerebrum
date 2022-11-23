# -*- coding: utf-8 -*-
#
# Copyright 2020-2022 University of Oslo, Norway
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
DFØ import class.

TODO
----
We already have a ``Cerebrum.modules.no.uio.dfo`` - do we really need to make
the client/datasource/mapper classes configurable?

Is this DFØ-shim even needed?  Maybe we should just do all this in
``Cerebrum.modules.no.uio.dfo`` (or equivalent) directly?
"""
import logging

from Cerebrum.modules.hr_import.employee_import import EmployeeImportBase
from Cerebrum.modules.hr_import.config import get_configurable_module
from Cerebrum.modules.no.dfo.client import get_client
from Cerebrum.modules.no.dfo.datasource import AssignmentDatasource
from Cerebrum.modules.no.dfo.datasource import EmployeeDatasource
from Cerebrum.modules.no.dfo.mapper import EmployeeMapper
from Cerebrum.Utils import Factory
from Cerebrum.utils.date import now

logger = logging.getLogger(__name__)


class DfoEmployeeImport(EmployeeImportBase):
    """
    A DFØ employee import
    """

    MATCH_ID_TYPES = ('DFO_PID',)
    KEEP_ID_TYPES = EmployeeImportBase.KEEP_ID_TYPES + ('DFO_PID',)

    datasource_cls = EmployeeDatasource
    mapper_cls = EmployeeMapper

    def __init__(self, db, config):
        client_config = get_configurable_module(config.client)
        client = get_client(client_config)
        datasource = self.datasource_cls(client)
        mapper_config = get_configurable_module(config.mapper)
        mapper = self.mapper_cls(mapper_config)
        co = Factory.get('Constants')(db)
        super(DfoEmployeeImport, self).__init__(db, datasource, mapper,
                                                co.system_dfo_sap)


class DfoAssignmentImport(object):
    """
    A *mock import* for dfø assignments.

    This import deviates slightly from the employee_import, in that it doesn't
    _actually_ import anything.  It only generates data for creating new
    employee tasks.

    See :py:class:`Cerebrum.modules.no.dfo.tasks.AssignmentTasks` for usage.
    """

    def __init__(self, db, config):
        client_config = get_configurable_module(config.client)
        client = get_client(client_config)
        self.datasource = AssignmentDatasource(client)
        client = get_client(client_config)

    def handle_reference(self, reference):
        """
        Initiate hr import from reference.

        This is the entrypoint for use with e.g. scripts.
        Fetches object data from the datasource and calls handle_object.
        """
        assignment = self.datasource.get_object(reference)
        if not assignment:
            logger.info('Empty assignment-id=%r', reference)
            return []

        cutoff = now()

        needs_update = []
        for employee_id in assignment['employees']:
            # We queue an immediate update - the regular import should handle
            # any future start or end date in the employments.
            needs_update.append((employee_id, cutoff))
            logger.debug('assignment-id=%r, update needed for employee-id=%r',
                         reference, employee_id)

        return needs_update
