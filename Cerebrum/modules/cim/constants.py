#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
""" Constants specific for CIM. """

from Cerebrum import Constants
from Cerebrum.modules.event import TargetSystemConstants


class ConstantsMixin(Constants.Constants):

    u""" Additional CIM constants. """

    target_system_cim = TargetSystemConstants._TargetSystemCode(
        'CIM',
        'CIM as a destination system')

    spread_cim_person = Constants._SpreadCode(
        'CIM_person', Constants.Constants.entity_person,
        'Person exported to CIM')
