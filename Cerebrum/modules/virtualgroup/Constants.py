# -*- coding: utf-8 -*-
# Copyright 2016-2018 University of Oslo, Norway
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

from Cerebrum.Constants import CoreConstants, _CerebrumCode, _GroupTypeCode


class _VirtualGroupType(_CerebrumCode):
    """Mapping for virtual group types"""
    _lookup_table = '[:table schema=cerebrum name=virtual_group_type_code]'


class _VirtualGroupOURecursionCode(_CerebrumCode):
    """Recursion code from virtual_group_ou_recursion_code"""
    _lookup_table = \
        '[:table schema=cerebrum name=virtual_group_ou_recursion_code]'


class _VirtualGroupOUMembershipType(_CerebrumCode):
    """Membership type for virtual ou group (virtual_group_ou_membership_type"""
    _lookup_table = \
        '[:table schema=cerebrum name=virtual_group_ou_membership_type_code]'


class Constants(CoreConstants):
    VirtualGroup = _VirtualGroupType

    vg_normal_group = _VirtualGroupType(
        'normal_group',
        'Normal group - uses group_member table')

    group_type_virtual = _GroupTypeCode(
        'virtual-group',
        'Automatic group - group memberships are generated on-demand')


class OUGroupConstants(Constants):
    """OU group constants"""
    vg_ougroup = _VirtualGroupType(
        'ougroup',
        'Virtual group based on OU structure, see '
        '"cerebrum.virtual_group_ou_info" and friends')

    # Recursion
    VirtualGroupOURecursion = _VirtualGroupOURecursionCode

    virtual_group_ou_recursive = _VirtualGroupOURecursionCode(
        'recursive',
        'Recursive OU group')

    virtual_group_ou_flattened = _VirtualGroupOURecursionCode(
        'flattened',
        'Flattened OU group')

    virtual_group_ou_nonrecursive = _VirtualGroupOURecursionCode(
        'nonrecursive',
        'Nonrecursive OU group')

    # Memberships
    VirtualGroupOUMembership = _VirtualGroupOUMembershipType

    virtual_group_ou_person = _VirtualGroupOUMembershipType(
        'person',
        'Group of persons in OU')

    virtual_group_ou_primary = _VirtualGroupOUMembershipType(
        'primary_account',
        'Group of primary accounts in OU')

    virtual_group_ou_accounts = _VirtualGroupOUMembershipType(
        'accounts',
        'Group of accounts in OU')
