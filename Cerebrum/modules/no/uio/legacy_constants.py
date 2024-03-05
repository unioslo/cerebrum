# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
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
Deprecated constants.

This module contains collections of CerebrumCode types that are either:

1. Scheduled from removal
2. *Should* be removed, but can't be because of various constraints
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import Cerebrum.Constants
from Cerebrum.modules.EntityTrait import _EntityTraitCode


_cereconst = Cerebrum.Constants


class _LegacyDnsConstants(Cerebrum.Constants.Constants):
    """ Common DNS module constants. """

    #
    # DNS Entities
    #
    entity_dns_cname = _cereconst._EntityTypeCode(
        'cname',
        'cname - see table "cerebrum.cname_info" and friends.',
    )
    entity_dns_host = _cereconst._EntityTypeCode(
        # name-clash with existing entity_type
        'dns_host',
        'dns_host - see table "cerebrum.dns_host_info" and friends.',
    )
    entity_dns_a_record = _cereconst._EntityTypeCode(
        'a_record',
        'a_record - see table "cerebrum.a_record_info" and friends.',
    )
    entity_dns_aaaa_record = _cereconst._EntityTypeCode(
        'aaaa_record',
        'aaaa_record - see table "cerebrum.aaaa_record_info" and friends.',
    )
    entity_dns_owner = _cereconst._EntityTypeCode(
        'dns_owner',
        'dns_owner - see table "cerebrum.dns_owner" and friends.',
    )
    entity_dns_ip_number = _cereconst._EntityTypeCode(
        'dns_ip_number',
        'dns_ip_number - see table "cerebrum.dns_ip_number" and friends.',
    )
    entity_dns_ipv6_number = _cereconst._EntityTypeCode(
        'dns_ipv6_number',
        'dns_ipv6_number - see table "cerebrum.dns_ipv6_number" and friends.',
    )
    entity_dns_subnet = _cereconst._EntityTypeCode(
        'dns_subnet',
        'dns_subnet - see table "cerebrum.dns_subnet" and friends.',
    )
    entity_dns_ipv6_subnet = _cereconst._EntityTypeCode(
        'dns_ipv6_subnet',
        'dns_ipv6_subnet - see table "cerebrum.dns_ipv6_subnet" and friends.',
    )

    #
    # Namespace for DNS names
    #
    dns_owner_namespace = _cereconst._ValueDomainCode(
        'dns_owner_ns',
        'Domain for dns_owners',
    )

    #
    # NIS host group?
    #
    spread_uio_machine_netgroup = _cereconst._SpreadCode(
        'NIS_mng@uio',
        _cereconst.Constants.entity_group,
        'Machine netgroup in NIS domain "uio"',
    )

    #
    # Traits
    #
    trait_dns_contact = _EntityTraitCode(
        'dns_contact',
        entity_dns_owner,
        """Contact information (e-mail address) for the host.""",
    )
    trait_dns_comment = _EntityTraitCode(
        'dns_comment',
        entity_dns_owner,
        """A freeform comment about the host.""",
    )


class _LegacyHostpolicyConstants(_cereconst.Constants):
    """
    Legacy entity-related constants for Cerebrum.modules.hostpolicy.

    They should not be used, or referred to from anywhere.  These constants
    need to be kept around, as the base entities and entity-related audit log
    records are still present in the database.
    """
    legacy_entity_hostpolicy_atom = _cereconst._EntityTypeCode(
        'hostpolicy_atom',
        'hostpolicy_atom - '
        'see table "cerebrum.hostpolicy_component" and friends.',
    )
    legacy_entity_hostpolicy_role = _cereconst._EntityTypeCode(
        'hostpolicy_role',
        'hostpolicy_role - '
        'see table "cerebrum.hostpolicy_component" and friends.',
    )
    legacy_hostpolicy_component_namespace = _cereconst._ValueDomainCode(
        'hostpol_comp_ns',
        'Domain for hostpolicy-components',
    )


class LegacyConstants(
    _LegacyDnsConstants,
    _LegacyHostpolicyConstants,
    Cerebrum.Constants.Constants,
):
    """ Legacy constants to keep around for now. """
    pass


class LegacyChangelogConstants(
    Cerebrum.Constants.CLConstants,
):
    """ Legacy constants to keep around for now. """
    pass
