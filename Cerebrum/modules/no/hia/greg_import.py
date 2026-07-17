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
UiA-specific Greg import logic.

TODO
----
This is a placeholder, until we get actual info on roles, ou-mapping, etc...
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

# from Cerebrum.group import template as _group_template
from Cerebrum.modules.greg import importer as _base_import
from Cerebrum.modules.greg import mapper as _base_mapper


# GREG_CONSENT_GROUP = _group_template.GroupTemplate(
#     group_name='greg-aktivt-samtykke',
#     group_description='Guests who consents to electronic publication',
#     group_type='internal-group',
#     group_visibility='A',
# )


class _UiaGregOrgunitIds(_base_mapper.GregOrgunitIds):
    """ Orgunit-mapper for Greg roles at UiA. """

    # TODO: Figure out how to identify org units
    type_map = {
        # ('orgreg', 'orgreg_id'): 'ORGREG_OU_ID',
        # ('sap', 'legacy_stedkode'): 'NO_SKO',
    }


class _UiaGregRoles(_base_mapper.GregRoles):
    """ Roles-mapper for Greg at UiA. """

    # TODO: UiA needs to specify greg-role to aff mappings
    type_map = {
        # 'external-consultant': 'TILKNYTTET/ekstern',
        # 'external-partner': 'TILKNYTTET/ekstern',
    }

    # mapper for finding a matching org unit
    get_orgunit_ids = _UiaGregOrgunitIds()


class _UiaGregConsents(_base_mapper.GregConsents):
    """ Consent-mapper for Greg at UiA. """

    # TODO: Does UiA need any consents from Greg to be represented in Cerebrum?
    #
    # Note: Nothing happens to roles by default, unless there is a
    # CONSENT_GROUPS mapping with the target/translated role in the importer.
    type_map = {
        # 'publish': 'greg-publish',
    }


class _UiaGregContactInfo(_base_mapper.GregContactInfo):

    # TODO: Does UiA need any custom contact info mappings?
    #       This module can be omitted if they only need the defaults.
    type_map = {
        # 'private_email': 'EMAIL',
        # 'private_mobile': 'PRIVATEMOBILE',
    }


class _UiaGregPersonIds(_base_mapper.GregPersonIds):

    # TODO: Does UiA need any custom extenal id mappings?
    #       This module can be omitted if they only need the defaults.
    #
    #       We probably want some sort of migration id - e.g. employee id of
    #       guests that are moved from the HR system.
    type_map = {
        # We include the primary identifier from System-X.  This will help
        # match old Cerebrum/System-X guests with new Cerebrum/Greg guests.
        # ('system-x', 'migration_id'): 'SYS_X_ID',

        # Default mappings:
        # 'norwegian_national_id_number': 'NO_BIRTHNO',
        # 'passport_number': 'PASSNR',
    }


class _UiaGregMapper(_base_mapper.GregMapper):

    # Override default mappers with custom mappers from this module:
    get_affiliations = _UiaGregRoles()
    get_consents = _UiaGregConsents()
    get_contact_info = _UiaGregContactInfo()
    get_person_ids = _UiaGregPersonIds()


class UiaGregImporter(_base_import.GregImporter):

    # TODO: This can probably be removed - don't expect UiA to have any
    #       different needs here.
    # REQUIRED_PERSON_ID = (
    #     'NO_BIRTHNO',
    #     'PASSNR',
    # )

    # TODO: This can probably be removed - don't expect UiA to have any
    #       different needs here.
    # MATCH_ID_TYPES = (
    #     'GREG_PID',
    # )

    # TODO: Does UiA need any consent groups?  Ref. _UiaGregConsents
    # CONSENT_GROUPS = {
    #     # 'greg-publish': GREG_CONSENT_GROUP,
    # }

    # Override default mapper with main mapper from this module
    mapper = _UiaGregMapper()
