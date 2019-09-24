#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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

# $Id$
"""
The Constants defined for the HostPolicy module, depending on the DNS module.
"""

from Cerebrum import Constants as CereConst

__version__ = "$Revision$"
# $URL$
# $Source$


class _PolicyRelationshipCode(CereConst._CerebrumCode):
    """Mappings stored in the hostpolicy_relationship_code table"""
    _lookup_table = '[:table schema=cerebrum name=hostpolicy_relationship_code]'


class Constants(CereConst.Constants):
    entity_hostpolicy_atom = CereConst._EntityTypeCode(
        'hostpolicy_atom',
        'hostpolicy_atom - see table "cerebrum.hostpolicy_component" and friends.')
    entity_hostpolicy_role = CereConst._EntityTypeCode(
        'hostpolicy_role',
        'hostpolicy_role - see table "cerebrum.hostpolicy_component" and friends.')

    hostpolicy_component_namespace = CereConst._ValueDomainCode(
        'hostpol_comp_ns',
        'Domain for hostpolicy-components')

    hostpolicy_mutually_exclusive = _PolicyRelationshipCode(
        "hostpol_mutex",
        "Source policy and target policy are mutually exclusive")
    hostpolicy_contains = _PolicyRelationshipCode(
        "hostpol_contains",
        "Source policy contains target policy")


class CLConstants(CereConst.CLConstants):
    # ChangeLog constants
    hostpolicy_atom_create = CereConst._ChangeTypeCode(
        'hostpolicy_atom', 'create', 'create atom %(subject)s')
    hostpolicy_atom_mod = CereConst._ChangeTypeCode(
        'hostpolicy_atom', 'modify', 'modify atom %(subject)s')
    hostpolicy_atom_delete = CereConst._ChangeTypeCode(
        'hostpolicy_atom', 'delete', 'delete atom %(subject)s')
    hostpolicy_role_create = CereConst._ChangeTypeCode(
        'hostpolicy_role', 'create', 'create role %(subject)s')
    hostpolicy_role_mod = CereConst._ChangeTypeCode(
        'hostpolicy_role', 'modify', 'modify role %(subject)s')
    hostpolicy_role_delete = CereConst._ChangeTypeCode(
        'hostpolicy_role', 'delete', 'delete role %(subject)s')

    hostpolicy_relationship_add = CereConst._ChangeTypeCode(
        'hostpolicy_relationship',
        'add',
        'add relationship %(subject)s -> %(dest)s')
    # TODO: type is not given here
    hostpolicy_relationship_remove = CereConst._ChangeTypeCode(
        'hostpolicy_relationship',
        'remove',
        'remove relationship %(subject)s -> %(dest)s')
    # TODO: type is not given here

    hostpolicy_policy_add = CereConst._ChangeTypeCode(
        'hostpolicy',
        'add',
        'add policy %(dest)s to host %(subject)s')
    hostpolicy_policy_remove = CereConst._ChangeTypeCode(
        'hostpolicy',
        'remove',
        'remove policy %(dest)s from host %(subject)s')


PolicyRelationshipCode = _PolicyRelationshipCode
