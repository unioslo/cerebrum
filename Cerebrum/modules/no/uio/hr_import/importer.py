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
UIO import.
"""
import functools
import os

from Cerebrum.config.settings import String
from Cerebrum.config import loader as config_loader
from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.utils.module import resolve
from Cerebrum.modules.hr_import.employee_import import EmployeeImportBase
from Cerebrum.modules.hr_import.config import (ConfigurableModule,
                                               get_configurable_module)

from leader_groups import LeaderGroupUpdater
from reservation_group import ReservationGroupUpdater
from account_type import AccountTypeUpdater


class EmployeeImportConfig(Configuration):
    client_config = ConfigDescriptor(
        Namespace,
        config=ConfigurableModule,
        doc='Which client config to use',
    )

    client_class = ConfigDescriptor(
        String,
        doc='Which client class to use'
    )

    mapper_config = ConfigDescriptor(
        Namespace,
        config=ConfigurableModule,
        doc='Which mapper config to use'
    )

    mapper_class = ConfigDescriptor(
        String,
        doc='Which mapper class to use'
    )

    datasource_class = ConfigDescriptor(
        String,
        doc='Which datasource class to use'
    )


class EmployeeImport(EmployeeImportBase):
    """
    An employee import for SAPUiO @ UiO.
    """

    def __init__(self, db, mapper_cls, datasource):
        self.db = db
        self.mapper_cls = mapper_cls
        self._ds = datasource

    @property
    def datasource(self):
        return self._ds

    @property
    def mapper(self):
        if not hasattr(self, '_mapper'):
            self._mapper = self.mapper_cls(self.db)
        return self._mapper

    def update(self, hr_object, db_object):
        print('Update')
        account_types = AccountTypeUpdater(
            self.db,
            restrict_affiliation=self.const.affiliation_ansatt,
            restrict_source=self.mapper.source_system)

        def _get_affiliations():
            return set(
                (r['affiliation'], r['status'], r['ou_id'])
                for r in db_object.list_affiliations(
                    person_id=db_object.entity_id,
                    affiliation=account_types.restrict_affiliation,
                    source_system=account_types.restrict_source))

        affs_before = _get_affiliations()
        super(EmployeeImport, self).update(hr_object, db_object)
        affs_after = _get_affiliations()

        if affs_before != affs_after:
            account_types.sync(db_object,
                               added=affs_after - affs_before,
                               removed=affs_before - affs_after)

        reservation_group = ReservationGroupUpdater(self.db)
        reservation_group.set(db_object.entity_id, hr_object.reserved)

        leader_groups = LeaderGroupUpdater(self.db)
        leader_groups.sync(db_object.entity_id, hr_object.leader_groups)


@memoize
def get_employee_importer(config):
    """Get employee importer from config

    :type config: EmployeeImportConfig
    """

    client_config = get_configurable_module(config.client_config)
    client_cls = resolve(config.client_class)
    client = client_cls(client_config)

    mapper_config = get_configurable_module(config.mapper_config)
    mapper_cls = resolve(config.mapper_class)
    mapper_cls = functools.partial(mapper_cls, config=mapper_config)

    datasource_cls = resolve(config.datasource_class)
    datasource = datasource_cls(client)

    return functools.partial(EmployeeImport,
                             mapper_cls=mapper_cls,
                             datasource=datasource)


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
