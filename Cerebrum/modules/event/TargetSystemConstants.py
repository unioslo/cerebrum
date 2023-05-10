# -*- coding: utf-8 -*-
#
# Copyright 2014-2023 University of Oslo, Norway
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
Target system codes for events.

This module contains the constant type that defines a target system for the
``Cerebrum.modules.EventLog``.

TODO: Should probably be moved to a ``Cerebrum.modules.eventlog`` submodule.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import Cerebrum.Constants


class _TargetSystemCode(Cerebrum.Constants._CerebrumCode):
    """Mappings stored in the target_system_code table"""

    _lookup_table = "[:table schema=cerebrum name=target_system_code]"


class TargetSystemConstants(Cerebrum.Constants.Constants):
    TargetSystem = _TargetSystemCode
