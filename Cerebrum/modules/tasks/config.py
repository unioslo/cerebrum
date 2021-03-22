#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" Configuration for generating tasks.  """

from Cerebrum.config.configuration import (
    ConfigDescriptor,
    Configuration,
    Namespace,
)
from Cerebrum.config.settings import (
    Setting,
    String,
    Iterable,
)
from Cerebrum.utils.module import resolve


class Callable(Setting):
    """
    A callable setting.

    See :py:func:`Cerebrum.utils.module.resolve` for format.
    """

    # TODO: Do we want this in Cerebrum.config.settings?

    def serialize(self, value):
        if value is None:
            return None
        return value.__module__ + ':' + value.__name__

    def unserialize(self, value):
        if value is None:
            return None
        return resolve(value)

    def validate(self, value):
        if super(Callable, self).validate(value):
            return True

        if not callable(value):
            raise ValueError('not a callable')
        return False


class TaskGeneratorConfig(Configuration):
    """
    Configuration for a single task.

    Example:

    .. code:: json

        {
            "source": "foo",
            "get_tasks": "Cerebrum.foo.bar:get_foo_tasks",
        }
    """
    source = ConfigDescriptor(
        String,
        doc='Name of a task source'
    )
    get_tasks = ConfigDescriptor(
        Callable,
        doc='a function that generates tasks (e.g. foo.bar:baz)',
    )


class TaskListMixin(Configuration):
    """ Mixin with a task list setting. """

    tasks = ConfigDescriptor(
        Iterable,
        template=Namespace(config=TaskGeneratorConfig),
        doc="a list of tasks to handle",
    )
