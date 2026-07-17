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
UiO-specific Greg import logic.
"""
from Cerebrum.group.template import GroupTemplate
from Cerebrum.modules.greg import mapper
from Cerebrum.modules.greg import importer


GREG_CONSENT_GROUP = GroupTemplate(
    group_name='greg-aktivt-samtykke',
    group_description='Guests who consents to electronic publication',
    group_type='internal-group',
    group_visibility='A',
)


class _UioGregOrgunitIds(mapper.GregOrgunitIds):

    type_map = {
        ('orgreg', 'orgreg_id'): 'ORGREG_OU_ID',
        ('sapuio', 'legacy_stedkode'): 'NO_SKO',
    }


class _UioGregRoles(mapper.GregRoles):

    type_map = {
        'emeritus': 'TILKNYTTET/emeritus',
        'external-consultant': 'TILKNYTTET/ekst_partner',
        'external-partner': 'TILKNYTTET/ekst_partner',
        'guest-researcher': 'TILKNYTTET/gjesteforsker',
        'grader': 'TILKNYTTET/sensor',
    }

    get_orgunit_ids = _UioGregOrgunitIds()


class _UioGregMapper(mapper.GregMapper):

    get_affiliations = _UioGregRoles()


class UioGregImporter(importer.GregImporter):

    CONSENT_GROUPS = {
        'greg-publish': GREG_CONSENT_GROUP,
    }

    mapper = _UioGregMapper()
