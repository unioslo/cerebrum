#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2024 University of Oslo, Norway
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
Generate an LDIF file for the VOIP extension.

Configuration
-------------
This module uses the following LDAP configs:

``cereconf.LDAP``
    Base config for all LDAP exports.  Typically reads `dump_dir` and
    `max_change` from this.

``cereconf.LDAP_VOIP``
    Base config for this voip export.

    This config can set the default filename for exports, as well as the base
    dn, and top-level container attributes.

``cereconf.LDAP_VOIP_ADDRESS``
    Config for the voip address subtree

``cereconf.LDAP_VOIP_CLIENT``
    Config for the voip client subtree
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (
    attr_unique,
    container_entry_string,
    entry_string,
    ldapconf,
    ldif_outfile,
    normalize_string,
)
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress


logger = logging.getLogger(__name__)


def generate_voip_clients(sink, db, addr_id2dn, *args):
    vc = VoipClient(db)
    const = Factory.get("Constants")()
    sink.write(container_entry_string('VOIP_CLIENT'))
    base_dn = ldapconf('VOIP_CLIENT', 'dn', None)

    for entry in vc.list_voip_attributes(*args):
        voip_address_id = entry.pop("voip_address_id")

        if voip_address_id not in addr_id2dn:
            logger.debug("skipping address id=%s - address not in cache",
                         repr(voip_address_id))
            continue

        entry['objectClass'] = ['top', 'sipClient']
        entry['sipVoipAddressDN'] = addr_id2dn[voip_address_id]

        if entry["sipClientType"] == six.text_type(
                const.voip_client_type_softphone):
            attr = "uid"
            assert attr in entry
        elif entry["sipClientType"] == six.text_type(
                const.voip_client_type_hardphone):
            attr = "sipMacAddress"
            assert "uid" not in entry
        else:
            logger.warn("skipping address id=%s - unknown voip_client type=%s",
                        repr(voip_address_id), repr(entry["sipClientType"]))
            continue

        dn = "{}={},{}".format(attr, entry[attr], base_dn)
        sink.write(entry_string(dn, entry, add_rdn=False))


def generate_voip_addresses(sink, db, *args):
    va = VoipAddress(db)
    sink.write(container_entry_string('VOIP_ADDRESS'))
    addr_id2dn = dict()
    base_dn = ldapconf('VOIP_ADDRESS', 'dn', None)
    for entry in va.list_voip_attributes(*args):
        entry['objectClass'] = ['top', 'voipAddress']
        dn = "voipOwnerId={},{}".format(entry['voipOwnerId'], base_dn)
        entity_id = entry.pop("entity_id")
        addr_id2dn[entity_id] = dn
        if not entry.get("cn"):
            entry["cn"] = ()
        if entry.get('mobile'):
            entry['mobile'] = attr_unique(entry['mobile'],
                                          normalize=normalize_string)
        sink.write(entry_string(dn, entry, add_rdn=False))
    return addr_id2dn


def _get_voip_persons(db):
    """ Get all person ids with voip addreses. """
    va = VoipAddress(db)
    entity_type = va.const.entity_person
    person_ids = set()
    for row in va.search(owner_entity_type=entity_type):
        person_ids.add(row['owner_entity_id'])
    return person_ids


def _get_sysadm_accounts(db):
    """ Get sysadm account ids. """
    # TODO: Should use sysadm_utils here
    ac = Factory.get("Account")(db)
    return set(ac.list_sysadm_accounts())


def get_voip_persons_and_accounts(db):
    ac = Factory.get("Account")(db)

    voip_persons = sorted(set(_get_voip_persons(db)))
    sysadm_accounts = _get_sysadm_accounts(db)

    primary2pid = dict(
        (r["account_id"], r["person_id"])
        for r in ac.list_accounts_by_type(primary_only=True,
                                          person_id=voip_persons,
                                          exclude_account_id=sysadm_accounts))
    return voip_persons, primary2pid, sysadm_accounts


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        type=six.text_type,
        dest='output',
        help='output file',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()

    with ldif_outfile("VOIP", filename=args.output) as f:
        logger.info("writing voip export to %s", f.name)
        f.write(container_entry_string("VOIP"))

        logger.info("fetching persons and primary accounts")
        (persons, primary2pid, sysadm_aid) = get_voip_persons_and_accounts(db)

        logger.info("writing voip addresses")
        addr_id2dn = generate_voip_addresses(f, db, persons, primary2pid,
                                             sysadm_aid)

        logger.info("writing voip clients")
        generate_voip_clients(f, db, addr_id2dn, persons, primary2pid,
                              sysadm_aid)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
