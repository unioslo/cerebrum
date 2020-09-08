# -*- coding: utf-8 -*-
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
from __future__ import unicode_literals

"""
Example of config:
{
  "tasks": [
    {
      "name": "test_task",
      "call": "mod.sub/func",
      "triggers": [
          {"routing_key": "no.uio.sap.scim.employees.",
           "exchange": "ex_messages"}
      ],
    }
  ]
}

"""

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Namespace,
                                           Configuration)
from Cerebrum.config.settings import String, Iterable
from Cerebrum.config.loader import read, read_config


class Trigger(Configuration):
    routing_key = ConfigDescriptor(
        String,
        doc='Routing key which should trigger a task to run (matched by regex)'
    )
    exchange = ConfigDescriptor(
        String,
        default='',
        doc='Exchange name which should trigger a task to run (exact match). '
            'Skipped if empty.'
    )


class ListedTask(Configuration):
    name = ConfigDescriptor(
        String,
        doc='Name of the task'
    )
    call = ConfigDescriptor(
        String,
        doc='The callable to call when triggered '
            '(see Cerebrum.utils.module.resolve). '
            'Example: "mod.sub:Cls.func"'
    )
    triggers = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Trigger)
    )


class MapperConfig(Configuration):
    tasks = ConfigDescriptor(
        Iterable,
        template=Namespace(config=ListedTask),
        default=[],
        doc='Tasks which can be triggered by incoming messages'
    )


def load_config(cls, name, filepath=None):
    """Load config from default location (see `loader.lookup_dirs`) or file"""
    config_cls = cls()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, name)
    config_cls.validate()
    return config_cls
