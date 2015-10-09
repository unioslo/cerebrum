#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003-2009 University of Oslo, Norway
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
See Cerebrum/default_config.py:LDAP_MAIL_DNS for configuration."""

import os
import re
import sys

import cerebrum_path
import cereconf
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import \
     ldapconf, ldif_outfile, end_ldif_outfile, container_entry_string

dif_outfile('MAIL_DNS')

    hosts, cnames, lower2host, hosts_only_mx = get_hosts_and_cnames()

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    logger = Factory.get_logger('cronjob')
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
        # Verify that domains have a MX-record.
        for arg in cereconf.LDAP_MAIL_DNS['dig_args']:
            zone = arg[0]
            if domain.endswith(zone) and not (domain in hosts_only_mx or
                                              domain in hosts):
                logger.error("email domain without MX defined: %s" % domain)
        # Valid email domains only requires MX
        if domain in hosts_only_mx:
            del hosts_only_mx[domain]

    for host in hosts_only_mx:
        logger.warn("MX defined but no A/AAAA record or valid email domain: %s" % host)
            
    def handle_domain_host(host):
        f.write("host: %s\n" % lower2host[host])
        for cname in hosts[host]:
            if not domain_dict.has_key(cname):
                f.write("cn: %s\n" % lower2host[cname])
                del cnames[cname]
        del hosts[host]

    dn_suffix = ldapconf('MAIL_DNS', 'dn')

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
    end_ldif_outfile('MAIL_DNS', f)


write_mail_dns()

