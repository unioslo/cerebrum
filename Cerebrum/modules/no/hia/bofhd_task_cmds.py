# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
This module contains task-related commands for UiA.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.greg import bofhd_greg_cmds
from Cerebrum.modules.no.hia.bofhd_uia_auth import UiaAuth
from Cerebrum.modules.tasks import bofhd_task_cmds

logger = logging.getLogger(__name__)


class _UiaTaskAuth(UiaAuth,
                   bofhd_greg_cmds.BofhdGregAuth,
                   bofhd_task_cmds.BofhdTaskAuth):
    """ UiA-specific task auth. """


class BofhdTaskCommands(bofhd_greg_cmds.BofhdGregCommands,
                        bofhd_task_cmds.BofhdTaskCommands):
    all_commands = {}
    authz = _UiaTaskAuth
    parent_commands = True
    omit_parent_commands = (
        # disallow task_add, as adding tasks without payload may beak
        # some imports.  task_add is implemented through queue-specific
        # commands, such as `greg import`
        'task_add',
    )

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            super(BofhdTaskCommands, cls).get_help_strings(),
            ({}, {}, {}))
