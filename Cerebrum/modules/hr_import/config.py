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

A basic sample config for use with :mod:`Cerebrum.modules.no.uio.sap`

::

    consumer:
      connection:
        host: example.org
        host: 5671
        ssl_enable: true
      consumer_tag: crb-hr-import
      exchanges:
        - name: ex_messages
          durable: true
          exchange_type: topic
      queues:
        - name: q_hr_import
          durable: true
      bindings:
        - exchange: ex_messages
          queue: q_hr_import
          routing_keys:
            - "no.uio.sap.scim.employees.#"

    importer:
      module: Cerebrum.modules.no.uio.sap.importer:autoload_employee_import
      config_file: hr-import-logic.yml
"""
from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import String
from Cerebrum.modules.amqp.config import ConsumerConfig, PublisherConfig
from Cerebrum.modules.amqp.mapper_config import MapperConfig
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
    """
    Load a module and an accompanying configuration file.

    Example use:

    ::

        class MyConfig(Configuration):
            ...

        class MyLogic(object):
            ...

        def autoload(path_or_name):
            config_obj = MyConfig()
            if os.path.isfile(path_or_name):
                config_obj.load_dict(loader.read_config(name_or_filename))
            else:
                loader.read(config_obj, name_or_filename)
            config_obj.validate()

            return functools.partial(MyLogic, config=config_obj)

        Configuration({'module': 'module:autoload',
                       'config_file': 'my_config.yml'})
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


class EmployeeImportConfig(Configuration):
    client = ConfigDescriptor(
        Namespace,
        config=ConfigurableModule,
        doc='Which client config to use',
    )

    mapper = ConfigDescriptor(
        Namespace,
        config=ConfigurableModule,
        doc='Which mapper config to use'
    )


class HrImportBaseConfig(Configuration):

    importer = ConfigDescriptor(
        Namespace,
        config=EmployeeImportConfig,
        doc='Importer config to use',
    )


class SingleEmployeeImportConfig(HrImportBaseConfig):

    importer_class = ConfigDescriptor(
        String,
        doc='Importer class to use'
    )


class HrImportConfig(HrImportBaseConfig):

    consumer = ConfigDescriptor(
        Namespace,
        config=ConsumerConfig,
        doc='Message broker configuration',
    )

    publisher = ConfigDescriptor(
        Namespace,
        config=PublisherConfig,
        doc='Message republish configuration',
    )

    task_mapper = ConfigDescriptor(
        Namespace,
        config=MapperConfig,
        doc='Configuration for the task mapper',
    )


if __name__ == '__main__':
    print(HrImportConfig.documentation())
