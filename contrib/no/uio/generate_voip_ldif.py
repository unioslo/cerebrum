#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2004-2018 University of Oslo, Norway
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

"""Generate an LDIF file for the VOIP extension."""

from __future__ import unicode_literals

import argparse
from six import text_type

from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldapconf,
                                        entry_string,
                                        ldif_outfile,
                                        container_entry_string)
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress


logger = Factory.get_logger("cronjob")
db = Factory.get("Database")()


def generate_voip_clients(sink, addr_id2dn, *args):
    vc = VoipClient(db)
    const = Factory.get("Constants")()
    sink.write(container_entry_string('VOIP_CLIENT'))
    for entry in vc.list_voip_attributes(*args):
        voip_address_id = entry.pop("voip_address_id")

        if voip_address_id not in addr_id2dn:
            logger.debug("voip client %s refers to voip_address %s, but the "
                         "latter is not in the cache. Has %s been recently "
                         "created?",
                         repr(entry), voip_address_id, voip_address_id)
            continue

        entry['objectClass'] = ['top', 'sipClient']
        entry['sipVoipAddressDN'] = addr_id2dn[voip_address_id]

        if entry["sipClientType"] == text_type(const.voip_client_type_softphone):
            attr = "uid"
            assert attr in entry
        elif entry["sipClientType"] == text_type(const.voip_client_type_hardphone):
            attr = "sipMacAddress"
            assert "uid" not in entry
        else:
            logger.warn("Aiee! Unknown voip_client type: %s (entry: %s)",
                        entry["sipClientType"], repr(entry))
            continue

        dn = "{}={},{}".format(attr, entry[attr],
                               ldapconf('VOIP_CLIENT', 'dn', None))
        sink.write(entry_string(dn, entry))


def generate_voip_addresses(sink, *args):
    va = VoipAddress(db)
    sink.write(container_entry_string('VOIP_ADDRESS'))
    addr_id2dn = dict()
    for entry in va.list_voip_attributes(*args):
        entry['objectClass'] = ['top', 'voipAddress']
        dn = "voipOwnerId={},{}".format(entry['voipOwnerId'],
                                        ldapconf('VOIP_ADDRESS', 'dn', None))
        entity_id = entry.pop("entity_id")
        addr_id2dn[entity_id] = dn
        if not entry.get("cn"):
            entry["cn"] = ()
        sink.write(entry_string(dn, entry))
    return addr_id2dn


def get_voip_persons_and_primary_accounts():
    va = VoipAddress(db)
    ac = Factory.get("Account")(db)
    const = Factory.get("Constants")()

    voippersons = list()
    for row in va.search(owner_entity_type=const.entity_person):
        voippersons.append(row["owner_entity_id"])

    sysadm_aid = ac.list_sysadm_accounts()

    primary2pid = dict(
        (r["account_id"], r["person_id"])
        for r in ac.list_accounts_by_type(primary_only=True,
                                          person_id=voippersons,
                                          exclude_account_id=sysadm_aid))
    return voippersons, primary2pid, sysadm_aid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        type=text_type,
        dest='output',
        help='output file')
    args = parser.parse_args()

    f = ldif_outfile('VOIP', args.output)
    logger.info('Starting VoIP LDIF export to %s', f.name)
    f.write(container_entry_string('VOIP'))
    logger.info('Fetching persons and primary accounts')
    persons, primary2pid, sysadm_aid = get_voip_persons_and_primary_accounts()
    logger.info('Fetching VoIP addresses')
    addr_id2dn = generate_voip_addresses(f, persons, primary2pid, sysadm_aid)
    logger.info('Fetching VoIP clients')
    generate_voip_clients(f, addr_id2dn, persons, primary2pid, sysadm_aid)
    f.close()
    logger.info('Done')


if __name__ == '__main__':
    main()
