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
"""
from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import String
from Cerebrum.modules.amqp.config import ConsumerConfig


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


class HrImportConfig(Configuration):

    consumer = ConfigDescriptor(
        Namespace,
        config=ConsumerConfig,
        doc='Message broker configuration',
    )

    importer = ConfigDescriptor(
        Namespace,
        config=ConfigurableModule,
        doc='Import module to use',
    )
