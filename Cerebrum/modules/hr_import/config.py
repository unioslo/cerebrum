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
Settings for the hr import routine.

Configuration options of datasource and importer depends on implementation, so
the configuration of these modules are split into separate configuration files.

See :mod:`Cerebrum.modules.amqp.config` for more info on how to configure the
consumer.

Example config
==============

Sample config for use with :mod:`Cerebrum.modules.no.uio.sap`

.. code:: yaml

    client:
      module: "Cerebrum.modules.no.uio.sap.client:SapClientConfig"
      config_file: /path/to/sap-client.yml

    mapper:
      module: "Cerebrum.modules.no.uio.sap.mapper:MapperConfig"
      config_file: /path/to/sap-mapper.yml

    import_class: "Cerebrum.modules.no.uio.sap.importer:EmployeeImport"
    task_class: "Cerebrum.modules.no.uio.sap.tasks:EmployeeTasks"

"""
from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import String
from Cerebrum.utils.module import resolve
from Cerebrum.config.loader import read_config as read_config_file


def get_configurable_module(config):
    """Load a ``ConfigurableModule``"""
    config_init = resolve(config.module)
    config_instance = config_init()
    config_dict = read_config_file(config.config_file)
    config_instance.load_dict(config_dict)
    return config_instance


class ConfigurableModule(Configuration):
    """ Python object and config file pair.

    Example use:

    ::

        class MyConfig(Configuration):
            ...

        config = ConfigurableModule({
            'module': 'module:MyConfig',
            'config_file': 'my_config.yml',
        })
        other_config = get_configurable_module(config)
    """
    module = ConfigDescriptor(
        String,
        doc='Reference to a configurable item (module:item)',
    )

    config_file = ConfigDescriptor(
        String,
        default=None,
        doc='A config file to use for this module',
    )


class TaskImportConfig(Configuration):

    client = ConfigDescriptor(
        Namespace,
        config=ConfigurableModule,
        doc='Client module and config for the import',
    )

    import_class = ConfigDescriptor(
        String,
        doc='Class to perform import (Cerebrum.modules.hr_import.importer)',
    )

    task_class = ConfigDescriptor(
        String,
        doc='Class for handling tasks (Cerebrum.modules.tasks.process)',
    )

    @classmethod
    def from_file(cls, filename):
        config = cls()
        config.load_dict(read_config_file(filename))
        return config


if __name__ == '__main__':
    print(TaskImportConfig.documentation())
