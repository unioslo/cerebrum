#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Generate an LDIF-file for the VOIP extension.
"""

import getopt
import sys

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import ldapconf
from Cerebrum.modules.LDIFutils import entry_string
from Cerebrum.modules.LDIFutils import ldif_outfile
from Cerebrum.modules.LDIFutils import container_entry_string
from Cerebrum.modules.no.uio.voip.voipClient import VoipClient
from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress



def object2encoding(obj, encoding="utf-8"):
    """Convert all text-like fields of obj to specified encoding.

    LDIF files ought to be in utf-8. This function accomplishes just that. Given
    an object, the method traverses it recursively and forces all text-like
    fields into the specified encoding.

    This method cannot be used on recursive structures.

    This method cannot be used on compound structures with nesting level deeper
    than approximately the recursion limit (default: about 1000).
    
    For str type the assumption is that the underlying encoding matches the
    encoding of this file, iso8859-1. Should this change, the method must be
    adjusted accordingly. 
    """

    if isinstance(obj, str):
        return unicode(obj, "iso8859-1").encode(encoding)

    if isinstance(obj, unicode):
        return obj.encode(encoding)

    if isinstance(obj, (tuple, set, list)):
        return type(obj)(object2encoding(x, encoding)
                         for x in obj)

    if isinstance(obj, dict):
        return dict((x, object2encoding(obj[x], encoding))
                    for x in obj)
    return obj
# end object2encoding



def generate_voip_clients(sink, addr_id2dn, encoding, *args):
    db = Factory.get("Database")()
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

        if entry["sipClientType"] == str(const.voip_client_type_softphone):
            attr = "uid"
            assert attr in entry
        elif entry["sipClientType"] == str(const.voip_client_type_hardphone):
            attr = "sipMacAddress"
            assert "uid" not in entry
        else:
            logger.warn("Aiee! Unknown voip_client type: %s (entry: %s)",
                        entry["sipClientType"], repr(entry))
            continue

        dn = "%s=%s,%s" % (attr, entry[attr],
                           ldapconf('VOIP_CLIENT', 'dn', None))
        sink.write(entry_string(object2encoding(dn, encoding),
                                object2encoding(entry, encoding)))
# end generate_voip_clients

def generate_voip_addresses(sink, encoding, *args):
    db = Factory.get("Database")()
    va = VoipAddress(db)
    sink.write(container_entry_string('VOIP_ADDRESS'))
    addr_id2dn = dict()
    for entry in va.list_voip_attributes(*args):
        entry['objectClass'] = ['top','voipAddress']
        dn = "voipOwnerId=%s,%s" % (entry['voipOwnerId'], 
                            ldapconf('VOIP_ADDRESS', 'dn', None))
        entity_id = entry.pop("entity_id")
        addr_id2dn[entity_id] = dn
        entry = object2encoding(entry, encoding)
        if not entry.get("cn"):
            entry["cn"] = ()
        sink.write(entry_string(object2encoding(dn, encoding), entry))

    return addr_id2dn
# end generate_voip_addresses

def get_voip_persons_and_primary_accounts():
    db = Factory.get("Database")()
    va = VoipAddress(db)
    ac = Factory.get("Account")(db)
    const = Factory.get("Constants")()

    voippersons = list()
    for row in va.search(owner_entity_type=const.entity_person):
        voippersons.append(row["owner_entity_id"])

    sysadm_aid = ac.list_sysadm_accounts()

    primary2pid = dict((r["account_id"], r["person_id"])
       for r in ac.list_accounts_by_type(primary_only=True,
                                         person_id=voippersons,
                                         exclude_account_id=sysadm_aid))
    return voippersons, primary2pid, sysadm_aid

def main():
    global logger
    logger = Factory.get_logger("cronjob")
    ofile = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ho:",("help","outfile="))
    except getopt.GetoptError, e:
        usage(str(e))

    if args:
        usage("Invalid arguments: " + " ".join(args))
    for opt, val in opts:
        if opt in ("-o", "--outfile"):
            ofile = val
        else:
            usage()

    output_encoding = "utf-8"
    f = ldif_outfile('VOIP', ofile)
    f.write(container_entry_string('VOIP'))
    voippersons, primary2pid, sysadm_aid = get_voip_persons_and_primary_accounts()
    addr_id2dn = generate_voip_addresses(f, output_encoding, voippersons, primary2pid, sysadm_aid)
    generate_voip_clients(f, addr_id2dn, output_encoding, voippersons, primary2pid, sysadm_aid)
    f.close()
# end main


def usage(err=0):
    if err:
        print >>sys.stderr, err
    print >>sys.stderr, __doc__
    sys.exit(bool(err))
# end usage

if __name__ == '__main__':
    main()
