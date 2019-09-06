#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2019 University of Oslo, Norway
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
from __future__ import unicode_literals

import logging

import mx.DateTime

import posixconf

from Cerebrum.Entity import EntityName
from Cerebrum.Utils import Factory
from Cerebrum.utils import transliterate
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.LDIFutils import ldapconf, LDIFWriter, entry_string

logger = logging.getLogger(__name__)


class HostGroupExport(object):
    """
    Export host netgroups
    """

    # Include expired groups
    EMULATE_POSIX_LDIF = False

    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(db)
        self.clconst = Factory.get('CLConstants')(db)
        self.group = Factory.get('Group')(db)
        self.posix_user = Factory.get('PosixUser')(db)
        self.posix_group = PosixGroup.PosixGroup(db)

    def main(self, filename, spread, zone):
        self._namecachedtime = mx.DateTime.now()

        self._num = 0
        self.e_id2name = {}
        self.host_netgroups = {}
        self._names = set()

        logger.info('Setting up...')
        self.setup(spread, zone)

        ldif_file = LDIFWriter('POSIX', filename, module=posixconf)
        logger.debug('writing output to %r', ldif_file)
        logger.info('Generating...')
        try:
            self.generate_netgroup_output(ldif_file)
        finally:
            ldif_file.close()

    def setup(self, spread, zone):
        self.spread = spread
        self.zone = zone
        self.ngrp_dn = ldapconf('NETGROUP', 'dn', default=None,
                                module=posixconf)
        self._build_entity2name_mapping(self.co.group_namespace)
        self._build_entity2name_mapping(self.co.dns_owner_namespace)
        logger.info('Caching groups with spread=%r', self.spread)
        for row in self.posix_group.search(
                spread=self.spread,
                filter_expired=not self.EMULATE_POSIX_LDIF):
            self.host_netgroups[int(row['group_id'])] = row['name']

    def find_groups(self):
        """Must be called before expand_*group()."""
        groups, descs = {}, {}
        for row in self.group.search(
                spread=self.spread,
                filter_expired=not self.EMULATE_POSIX_LDIF):
            group_id = int(row['group_id'])
            groups[group_id] = row['name']
            descs[group_id] = (row['description'] or "").rstrip()
        self.exported_groups = groups
        self.group2desc = descs.get

    def clear_groups(self):
        """Cleanup after find_groups()"""
        del self.exported_groups, self.group2desc

    def generate_netgroup_output(self, f_ldif):
        f_ldif.write_container('NETGROUP')

        zone = self.zone.postfix
        zone_offset = -len(zone or "")
        self.find_groups()
        for g_id in self.host_netgroups:
            group_members, host_members = map(sorted, self.expand_netgroup(
                    g_id, self.co.entity_dns_owner, None))
            members = set("(%s,-,)" % m[:-1] for m in host_members)
            if zone is not None:
                members.update("(%s,-,)" % m[:zone_offset]
                               for m in host_members if m.endswith(zone))
            dn, entry = self.ldif_netgroup(g_id, group_members, members)
            f_ldif.write(entry_string(dn, entry, False))
        self.clear_groups()

    def _build_entity2name_mapping(self, namespace):
        logger.info('Caching names in namespace=%r', namespace)
        for row in EntityName(self.db).list_names(namespace):
            self.e_id2name[int(row['entity_id'])] = row['entity_name']
        self._names.add(namespace)

    def expand_netgroup(self, gid, member_type, member_spread):
        """
        Expand a group and all of its members.

        Subgroups are included regardles of spread, but if they are of a
        different spread, the groups members are expanded.
        """
        groups, non_groups = set(), set()  # members may be added several times
        self.group.clear()
        self.group.find(gid)

        # direct members
        for row in self.group.search_members(
                group_id=self.group.entity_id,
                member_spread=member_spread,
                member_type=member_type):
            member_id = int(row["member_id"])
            name = self.e_id2name.get(member_id)
            if name:
                if "_" not in name:
                    non_groups.add(name)
            else:
                logger.warning('No name for member_id=%r', member_id)

        # subgroups
        for row in self.group.search_members(group_id=gid,
                                             member_type=self.co.entity_group):
            t_gid = int(row["member_id"])
            if t_gid in self.exported_groups:
                groups.add(self.exported_groups[t_gid])
            else:
                t_g, t_ng = self.expand_netgroup(
                    t_gid, member_type, member_spread)
                groups.update(t_g)
                non_groups.update(t_ng)

        return groups, non_groups

    def ldif_netgroup(self, group_id, group_members, direct_members):
        """Create the group-entry attributes"""
        name = self.host_netgroups[group_id]
        dn = ','.join(('cn=' + name, self.ngrp_dn))
        entry = {
            'objectClass': ('top', 'nisNetGroup'),
            'cn': (name,),
            'nisNetgroupTriple': direct_members,
            'memberNisNetgroup': group_members,
        }
        desc = self.group2desc(group_id)
        if desc:
            entry['description'] = (transliterate.to_iso646_60(desc),)
        return dn, entry
