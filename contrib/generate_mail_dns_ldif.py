#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

"""Generate LDAP host/domain info to be used by the mail system.
See Cerebrum/default_config.py:LDAP_MAIL_DNS_* for configuration."""

import os
import re

import cerebrum_path
import cereconf
from Cerebrum import Entity
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory,SimilarSizeWriter
from Cerebrum.modules.LDIFutils import container_entry_string

filename = os.path.join(cereconf.LDAP_DUMP_DIR, "mail-dns.ldif")

# Expect /local/bin/dig output like this:
#   ; <<>> DiG 9.2.1 <<>> uio.no. @nissen.uio.no. axfr
#   bb.uio.no.              86400   IN      CNAME   beeblebrox.uio.no.
#   beeblebrox.uio.no.      86400   IN      MX      10 smtp.uio.no.
#   beeblebrox.uio.no.      86400   IN      A       129.240.10.17
dig_line_re = re.compile(r'(\S+)\.\s+\d+\s+IN\s+(A|MX|CNAME)\s+(.*[^.\n])\.?$')
dig_version_re = re.compile(r';[ <>]+DiG 9\.', re.IGNORECASE)


def get_hosts_and_cnames():
    """Return dicts host->[cnames, if any], cname->host, lowercase host->host.

    All keys are lowercase, as well as all values except in the 3rd dict."""
    host_has_A_record = {}              # host  -> True if host has A record
    host2cnames       = {}              # host  -> {cname: True, ...}
    cname2host        = {}              # cname -> host
    host2mx           = {}              # host  -> {MX priority: MX name, ...}
    lower2host        = {}              # lowercase hostname -> hostname

    # Read in the above variables from Dig
    for args in cereconf.LDAP_MAIL_DNS_DIG_ARGS:
        dig_version_found = False
        f = os.popen(cereconf.LDAP_MAIL_DNS_DIG_CMD % args, 'r')
        for line in f:
            match = dig_line_re.match(line)
            if match:
                name, type, info = match.groups()
                lname = name.lower()
                info = info.lower()
                lower2host[lname] = name
                if type == 'A':
                    host_has_A_record[lname] = True
                elif type == 'CNAME':
                    if not host2cnames.has_key(info):
                        host2cnames[info] = {}
                    host2cnames[info][lname] = True
                    cname2host[lname] = info
                elif type == 'MX':
                    prio, mx = info.split()
                    if not host2mx.has_key(lname):
                        host2mx[lname] = {}
                    host2mx[lname][prio] = mx
            elif dig_version_re.match(line):
                dig_version_found = True
        if f.close() is not None:
            raise SystemExit("Dig failed.")
        if not dig_version_found:
            raise SystemExit("Dig version changed.  Check output format.")

    # Add fake Dig records
    for host in cereconf.LDAP_MAIL_DNS_EXTRA_A_HOSTS:
        host_has_A_record[host] = True

    # Find hosts that both have an A record
    # and has its 'best' MX record in cereconf.LDAP_MAIL_DNS_MX_HOSTS.
    hosts = {}
    accept_mx = dict(zip(*((cereconf.LDAP_MAIL_DNS_MX_HOSTS,) * 2))).has_key
    for host, mx_dict in host2mx.items():
        if host in host_has_A_record:
            prio = 99.0e9
            mx = "-"
            for p, m in mx_dict.items():
                p = int(p)
                if p < prio:
                    prio = p
                    mx = m
            if accept_mx(mx):
                if host2cnames.has_key(host):
                    hosts[host] = host2cnames[host].keys()
                    hosts[host].sort()
                else:
                    hosts[host] = ()

    # Remove cnames that do not appear in host2cnames ??? should be hosts[]?
    for cname in cname2host.keys():
        if not host2cnames.has_key(cname2host[cname]):
            del cname2host[cname]

    return hosts, cname2host, lower2host


def write_mail_dns():
    f = SimilarSizeWriter(filename,'w')
    f.set_size_change_limit(cereconf.LDAP_MAIL_DNS_MAX_CHANGE)

    hosts, cnames, lower2host = get_hosts_and_cnames()

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    email = Email.EmailDomain(db)
    email_domain = {}
    for dom_entry in email.list_email_domains():
        email_domain[int(dom_entry['domain_id'])] = dom_entry['domain']
    for no_exp_dom in email.list_email_domains_with_category(co.email_domain_category_noexport):
        del email_domain[int(no_exp_dom['domain_id'])]
    domains = email_domain.values()
    domains.sort()
    domain_dict = {}
    for domain in domains:
        domain_dict[domain.lower()] = True

    def handle_domain_host(host):
        f.write("host: %s\n" % lower2host[host])
        for cname in hosts[host]:
            if not domain_dict.has_key(cname):
                f.write("cn: %s\n" % lower2host[cname])
                del cnames[cname]
        del hosts[host]

    dn_suffix = cereconf.LDAP_MAIL_DNS_DN

    f.write(container_entry_string('MAIL_DNS'))

    for domain in domains:
        f.write("""dn: cn=%s,%s
objectClass: uioHost
cn: %s
""" % (domain, dn_suffix, domain))
        domain = domain.lower()
        if cnames.has_key(domain):
            f.write("cn: %s\n" % lower2host[cnames[domain]])
            handle_domain_host(cnames[domain])
        elif hosts.has_key(domain):
            handle_domain_host(domain)
        f.write('\n')

    sorted_hosts = hosts.keys()
    sorted_hosts.sort()
    for host in sorted_hosts:
        f.write("""dn: host=%s,%s
objectClass: uioHost
host: %s
cn: %s
""" % (lower2host[host], dn_suffix, lower2host[host], lower2host[host]))
        for cname in hosts[host]:
            f.write("cn: %s\n" % lower2host[cname])
        f.write('\n')
    f.close()


write_mail_dns()

# arch-tag: 2c36018d-930a-4894-8a51-39af6847a10c
