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
import Cerebrum.Constants
from Cerebrum import Constants as cereconst  # noqa: N813
from Cerebrum.modules.EntityTrait import _EntityTraitCode
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode


class _LegacyDnsConstants(cereconst.Constants):
    """ Common DNS module constants. """

    # TODO: move these to Cerebrum/modules/bofhd/utils.py?
    auth_dns_superuser = _AuthRoleOpCode(
        'dns_superuser',
        'Perform any DNS command',
    )

    auth_dns_lita = _AuthRoleOpCode(
        'dns_lita',
        'Perform LITA-level DNS commands',
    )

    #
    # DNS Entities
    #
    entity_dns_cname = cereconst._EntityTypeCode(
        'cname',
        'cname - see table "cerebrum.cname_info" and friends.',
    )
    entity_dns_host = cereconst._EntityTypeCode(
        # name-clash with existing entity_type
        'dns_host',
        'dns_host - see table "cerebrum.dns_host_info" and friends.',
    )
    entity_dns_a_record = cereconst._EntityTypeCode(
        'a_record',
        'a_record - see table "cerebrum.a_record_info" and friends.',
    )
    entity_dns_aaaa_record = cereconst._EntityTypeCode(
        'aaaa_record',
        'aaaa_record - see table "cerebrum.aaaa_record_info" and friends.',
    )
    entity_dns_owner = cereconst._EntityTypeCode(
        'dns_owner',
        'dns_owner - see table "cerebrum.dns_owner" and friends.',
    )
    entity_dns_ip_number = cereconst._EntityTypeCode(
        'dns_ip_number',
        'dns_ip_number - see table "cerebrum.dns_ip_number" and friends.',
    )
    entity_dns_ipv6_number = cereconst._EntityTypeCode(
        'dns_ipv6_number',
        'dns_ipv6_number - see table "cerebrum.dns_ipv6_number" and friends.',
    )
    entity_dns_subnet = cereconst._EntityTypeCode(
        'dns_subnet',
        'dns_subnet - see table "cerebrum.dns_subnet" and friends.',
    )
    entity_dns_ipv6_subnet = cereconst._EntityTypeCode(
        'dns_ipv6_subnet',
        'dns_ipv6_subnet - see table "cerebrum.dns_ipv6_subnet" and friends.',
    )

    #
    # Namespace for DNS names
    #
    dns_owner_namespace = cereconst._ValueDomainCode(
        'dns_owner_ns',
        'Domain for dns_owners',
    )

    #
    # NIS host group?
    #
    spread_uio_machine_netgroup = cereconst._SpreadCode(
        'NIS_mng@uio',
        cereconst.Constants.entity_group,
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


class _LegacyDnsChangelogLConstants(cereconst.CLConstants):
    a_record_add = cereconst._ChangeTypeCode(
        'host_a_rec',
        'add',
        'add a-record %(subject)s -> %(dest)s',
    )
    a_record_del = cereconst._ChangeTypeCode(
        'host_a_rec',
        'remove',
        'del a-record %(subject)s -> %(dest)s',
    )
    a_record_update = cereconst._ChangeTypeCode(
        'host_a_rec',
        'modify',
        'update a-record %(subject)s -> %(dest)s',
    )
    aaaa_record_add = cereconst._ChangeTypeCode(
        'host_aaaa_rec',
        'add',
        'add aaaa-record %(subject)s -> %(dest)s',
    )
    aaaa_record_del = cereconst._ChangeTypeCode(
        'host_aaaa_rec',
        'remove',
        'del aaaa-record %(subject)s -> %(dest)s',
    )
    aaaa_record_update = cereconst._ChangeTypeCode(
        'host_aaaa_rec',
        'modify',
        'update aaaa-record %(subject)s -> %(dest)s',
    )
    cname_add = cereconst._ChangeTypeCode(
        'host_cname',
        'add',
        'add cname %(subject)s -> %(dest)s',
    )
    cname_del = cereconst._ChangeTypeCode(
        'host_cname',
        'remove',
        'del cname %(subject)s -> %(dest)s',
    )
    cname_update = cereconst._ChangeTypeCode(
        'host_cname',
        'modify',
        'update cname %(subject)s -> %(dest)s',
    )
    dns_owner_add = cereconst._ChangeTypeCode(
        'host_dns_owner',
        'add',
        'add dns-owner %(subject)s',
    )
    dns_owner_update = cereconst._ChangeTypeCode(
        'host_dns_owner',
        'modify',
        'update dns-owner %(subject)s',
    )
    dns_owner_del = cereconst._ChangeTypeCode(
        'host_dns_owner',
        'remove',
        'del dns-owner %(subject)s',
    )
    general_dns_record_add = cereconst._ChangeTypeCode(
        'host_gen_dns_rec',
        'add',
        'add record for %(subject)s',
        ('%(int:field_type)s=%(string:data)s',),
    )
    general_dns_record_del = cereconst._ChangeTypeCode(
        'host_gen_dns_rec',
        'remove',
        'del record for %(subject)s',
        ('type=%(int:field_type)s',),
    )
    general_dns_record_update = cereconst._ChangeTypeCode(
        'host_gen_dns_rec',
        'modify',
        'update record for %(subject)s',
        ('%(int:field_type)s=%(string:data)s',),
    )
    host_info_add = cereconst._ChangeTypeCode(
        'host_info',
        'add',
        'add %(subject)s',
        ('hinfo=%(string:hinfo)s',),
    )
    host_info_update = cereconst._ChangeTypeCode(
        'host_info',
        'modify',
        'update %(subject)s',
        ('hinfo=%(string:hinfo)s',),
    )
    host_info_del = cereconst._ChangeTypeCode(
        'host_info',
        'remove',
        'del %(subject)s',
    )
    ip_number_add = cereconst._ChangeTypeCode(
        'host_ip_number',
        'add',
        'add %(subject)s',
        ('a_ip=%(string:a_ip)s',),
    )
    ip_number_update = cereconst._ChangeTypeCode(
        'host_ip_number',
        'modify',
        'update %(subject)s',
        ('a_ip=%(string:a_ip)s',),
    )
    ip_number_del = cereconst._ChangeTypeCode(
        'host_ip_number',
        'remove',
        'del %(subject)s',
    )
    ipv6_number_add = cereconst._ChangeTypeCode(
        'host_ipv6_number',
        'add',
        'add %(subject)s',
        ('aaaaaaa_ip=%(string:aaaa_ip)s',),
    )
    ipv6_number_update = cereconst._ChangeTypeCode(
        'host_ipv6_number',
        'modify',
        'update %(subject)s',
        ('aaaaaaa_ip=%(string:aaaa_ip)s',),
    )
    ipv6_number_del = cereconst._ChangeTypeCode(
        'host_ipv6_number',
        'remove',
        'del %(subject)s',
    )
    mac_adr_set = cereconst._ChangeTypeCode(
        'host_mac_adr',
        'set',
        'set %(subject)s',
        ('mac_adr=%(string:mac_adr)s',),
    )
    rev_override_add = cereconst._ChangeTypeCode(
        'host_rev_ovr',
        'add',
        'add rev-override %(subject)s -> %(dest)s',
    )
    rev_override_del = cereconst._ChangeTypeCode(
        'host_rev_ovr',
        'remove',
        'del rev-override for %(subject)s',
    )
    rev_override_update = cereconst._ChangeTypeCode(
        'host_rev_ovr',
        'modify',
        'update rev-override %(subject)s -> %(dest)s',
    )
    subnet_create = cereconst._ChangeTypeCode(
        'subnet',
        'create',
        'create subnet %(subject)s',
    )
    subnet_mod = cereconst._ChangeTypeCode(
        'subnet',
        'modify',
        'modify subnet %(subject)s',
    )
    subnet_delete = cereconst._ChangeTypeCode(
        'subnet',
        'delete',
        'delete subnet %(subject)s',
    )
    subnet6_create = cereconst._ChangeTypeCode(
        'subnet6',
        'create',
        'create IPv6 subnet %(subject)s',
    )
    subnet6_mod = cereconst._ChangeTypeCode(
        'subnet6',
        'modify',
        'modify IPv6 subnet %(subject)s',
    )
    subnet6_delete = cereconst._ChangeTypeCode(
        'subnet6',
        'delete',
        'delete IPv6 subnet %(subject)s',
    )
    srv_record_add = cereconst._ChangeTypeCode(
        'host_srv_rec',
        'add',
        'add srv-record %(subject)s -> %(dest)s',
    )
    srv_record_del = cereconst._ChangeTypeCode(
        'host_srv_rec',
        'remove',
        'del srv-record %(subject)s -> %(dest)s',
    )


class _LegacyHostpolicyConstants(cereconst.Constants):
    """
    Legacy entity-related constants for Cerebrum.modules.hostpolicy.

    They should not be used, or referred to from anywhere.  These constants
    need to be kept around, as the base entities and entity-related audit log
    records are still present in the database.
    """
    legacy_entity_hostpolicy_atom = cereconst._EntityTypeCode(
        'hostpolicy_atom',
        'hostpolicy_atom - '
        'see table "cerebrum.hostpolicy_component" and friends.',
    )
    legacy_entity_hostpolicy_role = cereconst._EntityTypeCode(
        'hostpolicy_role',
        'hostpolicy_role - '
        'see table "cerebrum.hostpolicy_component" and friends.',
    )
    legacy_hostpolicy_component_namespace = cereconst._ValueDomainCode(
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
    _LegacyDnsChangelogLConstants,
    Cerebrum.Constants.CLConstants,
):
    """ Legacy constants to keep around for now. """
    pass
