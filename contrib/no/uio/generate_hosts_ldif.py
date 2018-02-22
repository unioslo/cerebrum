#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2012-2018 University of Oslo, Norway
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

"""Generate an LDIF file with host information which supplements DNS."""

from collections import defaultdict
from itertools import imap
from operator import itemgetter

from Cerebrum.Utils import Factory
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.LDIFutils import LDIFWriter

logger = Factory.get_logger("cronjob")


def main():
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    arecord = ARecord.ARecord(db)
    dns_owner = DnsOwner.DnsOwner(db)

    get_id_mac = itemgetter('dns_owner_id', 'mac_adr')
    get_id_name = itemgetter('dns_owner_id', 'name')
    get_trait = itemgetter('entity_id', 'code', 'strval')
    trait2attr = {
        int(co.trait_dns_comment): 'uioHostComment',
        int(co.trait_dns_contact): 'uioHostContact',
    }

    ldif = LDIFWriter('HOSTS', None)
    logger.info('Start of hosts export to %s', ldif.f.name)
    ldif.write_container()
    base_dn = ldif.getconf('dn')

    id2attrs = defaultdict(dict)
    for entity_id, code, strval in imap(get_trait, dns_owner.list_traits(
            code=trait2attr.keys())):
        if strval:
            id2attrs[int(entity_id)][trait2attr[code]] = (strval,)

    arecords = defaultdict(set)
    for owner_id, mac in imap(get_id_mac, arecord.list_ext()):
        if mac:
            arecords[int(owner_id)].add(mac)

    done = set()
    for owner_id, name in sorted(imap(get_id_name, dns_owner.list())):
        owner_id, name = int(owner_id), name.rstrip('.')
        # We have both lowercase and uppercase versions of some host
        # names.  Ignore one, hostnames are case-insensitive in LDAP.
        key = name.lower()
        if key not in done:
            done.add(key)
            entry = {
                'host': (name,),
                'objectClass': ['uioHostinfo'],
                'uioHostMacAddr': arecords.get(owner_id, ()),
            }
            entry.update(id2attrs.get(owner_id, ()))
            ldif.write_entry("host={},{}".format(name, base_dn), entry)

    ldif.close()
    logger.info('Done')


if __name__ == '__main__':
    main()
