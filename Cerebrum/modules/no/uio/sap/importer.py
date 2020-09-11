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
SAPUiO import.
"""
import functools
import os

from Cerebrum.config import loader as config_loader
from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.modules.hr_import.employee_import import EmployeeImportBase

from .datasource import EmployeeDatasource
from .client import SapClientConfig, get_client
from .mapper import EmployeeMapper


class EmployeeImportConfig(Configuration):

    client = ConfigDescriptor(
        Namespace,
        config=SapClientConfig,
        doc='SAPUiO client configuration',
    )


class EmployeeImport(EmployeeImportBase):
    """
    An employee import for SAPUiO @ UiO.
    """

    mapper_cls = EmployeeMapper

    def __init__(self, db, datasource):
        self.db = db
        self._ds = datasource

    @property
    def datasource(self):
        return self._ds

    @property
    def mapper(self):
        if not hasattr(self, '_mapper'):
            self._mapper = self.mapper_cls(self.db)
        return self._mapper


def get_employee_importer(config):
    client = get_client(config.client)
    ds = EmployeeDatasource(client)
    return functools.partial(EmployeeImport, datasource=ds)


def autoload_employee_import(filename_or_namespace):
    """
    Fetch employee import implementation from a config file.

    :param filename_or_namespace:
        A configuration file.  Either a path to a config file, or a namespace
        to look up in the config lookup dirs (see Cerebrum.config.loader.read).
    """
    config_obj = EmployeeImportConfig()
    if os.path.isfile(filename_or_namespace):
        config_obj.load_dict(config_loader.read_config(filename_or_namespace))
    else:
        config_loader.read(config_obj, filename_or_namespace)
    config_obj.validate()
    return get_employee_importer(config_obj)
