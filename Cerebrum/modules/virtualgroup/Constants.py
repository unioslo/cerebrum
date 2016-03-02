# coding: utf-8
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


"""Constants for virtual group support"""

from Cerebrum.Constants import _EntityTypeCode, CoreConstants, _CerebrumCode
from Cerebrum.Utils import Factory


class _VirtualGroupType(_CerebrumCode):
    """Mapping for virtual group types"""
    _lookup_table = '[:table schema=cerebrum name=virtual_group_type_code]'


class Constants(CoreConstants):
    entity_virtual_group = _EntityTypeCode(
        'virtualgroup',
        'Virtual group - see table "cerebrum.virtual_group_info" and friends.')
    VirtualGroupType = _VirtualGroupType

Factory.type_component_map['virtualgroup'] = 'Group'
