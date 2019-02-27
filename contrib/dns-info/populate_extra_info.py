#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import sys
import re
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import DnsOwner


logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program="pop_extra_dinfo")
co = Factory.get('Constants')(db)


def import_hinfo(fname):
    """Import the hinfo file.  It has the format::
      hostname, hinfo, TODO = line.split()

    Update HINFO for all hosts in the file unless they are already
    registered as DHCP.
    """
    host = HostInfo.HostInfo(db)
    dns_id2name = {}
    for row in DnsOwner.DnsOwner(db).list():
        dns_id2name[int(row['dns_owner_id'])] = row['name']
    name2info = {}
    for row in host.list():
        name = dns_id2name[int(row['dns_owner_id'])]
        name = name[:-1]                 # FQDN without trailing dot
        name2info[name] = (row['hinfo'], int(row['dns_owner_id']))

    ok_line = re.compile(r'^\S*?\.uio\.no')  # Temporary work-around for
                                             # data & info messages in same file
    n_lines, n_changed, n_unknown, n_dhcp, n_nf = 0, 0, 0, 0, 0
    for line in open(fname, "r"):
        n_lines += 1
        line = line.strip()
        if not ok_line.match(line):
            logger.info("Ignoring '%s'" % line)
            continue
        hostname, new_hinfo1, new_hinfo2 = line.split(None, 2)
        new_hinfo = "%s\t%s" % (new_hinfo1, new_hinfo2)
        if not name2info.has_key(hostname):
            logger.info("unknown host '%s'" % hostname)
            n_unknown += 1
            continue
        old_hinfo, dns_owner_id = name2info.get(hostname)
        if old_hinfo.startswith('DHCP') or new_hinfo == old_hinfo:
            n_dhcp += 1
            continue
        try:
            host.clear()
            host.find_by_dns_owner_id(dns_owner_id)
        except Errors.NotFoundError:
            n_nf += 1
            continue
        logger.debug("Setting new hinfo '%s' for %s/%s (old=%s)" % (
            new_hinfo, dns_owner_id, hostname, host.hinfo))
        host.hinfo = new_hinfo
        host.write_db()
        db.commit()
        n_changed += 1
    logger.info("Read %i lines, changed %i, %i unknown, %i dhcp, %i nf" % (
        n_lines, n_changed, n_unknown, n_dhcp, n_nf))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['help', 'hinfo='])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--hinfo',):
            import_hinfo(val)
            
    if not opts:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    Maintain various extra info, typically ran regulatly by a cronjob.
    Currently supported jobs are:
    
    --hinfo fname: Fix HINFO entries.
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

