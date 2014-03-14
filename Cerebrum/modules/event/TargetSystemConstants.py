# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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

"""This is kind of the definition of target system codes. This is
used by the event-handler framework.
"""

from Cerebrum import Constants

class _TargetSystemCode(Constants._CerebrumCode):
    "Mappings stored in the target_system_code table"
    _lookup_table = '[:table schema=cerebrum name=target_system_code]'


class TargetSystemConstants(Constants.Constants):
    TargetSystem = _TargetSystemCode
