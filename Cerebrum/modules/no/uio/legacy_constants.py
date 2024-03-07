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

This module contains collections of CerebrumCode types that *should* be
removed, but can't because of various constraints.  Note that the module is
specific for UiO - other deployments should have their own legacy constant
collections, if needed.

DNS and hostpolicy
-------------------
These constants should not occur in their referenced tables (e.g.
entity_info, entity_trait, etc...), but they may still be referenced as
change params in change_log and audit_log records.  We *mainly* keep these
around because:

- Change/audit records may refer to the constants by their numeric/code value,
  which makes no sense if we don't have a code to human readable mapping.

- Certain change types may require these values to exist in CLASS_CONSTANTS for
  formatting.  Showing history for entities with these changes may break if the
  constant disappears.

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
    """
    Deprecated constants from the deleted Cerebrum.modules.dns module.
    """

    #
    # DNS Entities
    #
    _legacy_entity_dns_cname = _cereconst._EntityTypeCode(
        "cname",
        "Deprecated entity type - Cerebrum.modules.dns CNAME record",
    )
    _legacy_entity_dns_host = _cereconst._EntityTypeCode(
        # name-clash with existing entity_type
        "dns_host",
        "Deprecated entity type - Cerebrum.modules.dns HINFO record",
    )
    _legacy_entity_dns_a_record = _cereconst._EntityTypeCode(
        "a_record",
        "Deprecated entity type - Cerebrum.modules.dns A record",
    )
    _legacy_entity_dns_aaaa_record = _cereconst._EntityTypeCode(
        "aaaa_record",
        "Deprecated entity type - Cerebrum.modules.dns AAAA record",
    )
    _legacy_entity_dns_owner = _cereconst._EntityTypeCode(
        "dns_owner",
        "Deprecated entity type - Cerebrum.modules.dns DNS label",
    )
    _legacy_entity_dns_ip_number = _cereconst._EntityTypeCode(
        "dns_ip_number",
        "Deprecated entity type - Cerebrum.modules.dns reserved IPv4 address"
    )
    _legacy_entity_dns_ipv6_number = _cereconst._EntityTypeCode(
        "dns_ipv6_number",
        "Deprecated entity type - Cerebrum.modules.dns reserved IPv6 address"
    )
    _legacy_entity_dns_subnet = _cereconst._EntityTypeCode(
        "dns_subnet",
        "Deprecated entity type - Cerebrum.modules.dns IPv4 subnet"
    )
    _legacy_entity_dns_ipv6_subnet = _cereconst._EntityTypeCode(
        "dns_ipv6_subnet",
        "Deprecated entity type - Cerebrum.modules.dns IPv6 subnet"
    )

    #
    # Namespace for DNS names
    #
    _legacy_dns_owner_namespace = _cereconst._ValueDomainCode(
        "dns_owner_ns",
        "Deprecated namespace - Cerebrum.modules.dns label names",
    )

    #
    # NIS host group
    #
    _legacy_spread_uio_machine_netgroup = _cereconst._SpreadCode(
        "NIS_mng@uio",
        _cereconst.Constants.entity_group,
        "Deprecated spread - Cerebrum.modules.dns spread for host groups",
    )

    #
    # Traits
    #
    _legacy_trait_dns_contact = _EntityTraitCode(
        "dns_contact",
        _legacy_entity_dns_owner,
        "Deprecated trait - Cerebrum.modules.dns owner contact info",
    )
    _legacy_trait_dns_comment = _EntityTraitCode(
        "dns_comment",
        _legacy_entity_dns_owner,
        "Deprecated trait - Cerebrum.modules.dns owner description",
    )


class _LegacyHostpolicyConstants(_cereconst.Constants):
    """
    Deprecated constants from the deleted Cerebrum.modules.hostpolicy module.
    """
    _legacy_entity_hostpolicy_atom = _cereconst._EntityTypeCode(
        "hostpolicy_atom",
        "Deprecated entity type - was part of Cerebrum.modules.hostpolicy",
    )
    _legacy_entity_hostpolicy_role = _cereconst._EntityTypeCode(
        "hostpolicy_role",
        "Deprecated entity type - was part of Cerebrum.modules.hostpolicy",
    )
    _legacy_hostpolicy_component_namespace = _cereconst._ValueDomainCode(
        "hostpol_comp_ns",
        "Deprecated namespace - was part of Cerebrum.modules.hostpolicy",
    )


class LegacyConstants(
    _LegacyDnsConstants,
    _LegacyHostpolicyConstants,
    Cerebrum.Constants.Constants,
):
    """
    Legacy constants to keep.
    """
    pass


class LegacyChangelogConstants(
    Cerebrum.Constants.CLConstants,
):
    """
    Legacy changelog constants to keep.
    """
    pass
