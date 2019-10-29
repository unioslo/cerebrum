#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
""" Generate LDAP domain info to be used by the mail system.

This script dumps email domains in Cerebrum as objects to an LDIF file
The information from this LDIF is used by Exim, our MTA.

output
------
The script generates an LDIF file with email domain entries that looks like:

    dn: cn=<email-domain>,<cereconf.LDAP_ORG['dn']>
    objectClass: uioHost
    cn: <email-domain>
    host: <email-domain>
    ...

cereconf
--------

This script is configured with LDAP_MAIL_DOMAINS, which is a dictionary with
the following values:

dn (e.g. "cn=mail-domains,dc=example,dc=org")
    dn-suffix for all objects that this script produces. With the example
    provided, an email domain 'foo.example.org' in Cerebrum would be exported
    as 'dn: cn=foo.example.org,cn=mail-domains,dc=example,dc=org'

file (e.g. "mail-domains.ldif")
    filename (within the `cereconf.LDAP['dump_dir']`) for the LDIF file.

"""
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email, LDIFutils


def get_email_domains():
    """ Get email domains from Cerebrum.

    :return generator:
        A generator that yield email domains that are not excluded from export.
    """
    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)
    email = Email.EmailDomain(db)

    exclude = set(
        (
            int(row["domain_id"])
            for row in email.list_email_domains_with_category(
                co.email_domain_category_noexport
            )
        )
    )

    for row in email.list_email_domains():
        if int(row["domain_id"]) in exclude:
            continue
        yield row["domain"].lower()


def write_mail_domains():
    """ Gather data and dump to ldif. """
    logger = Factory.get_logger("cronjob")
    logger.debug("Reading domains...")
    domains = sorted(get_email_domains())

    lw = LDIFutils.LDIFWriter("MAIL_DOMAINS", filename=None)
    dn_suffix = lw.getconf("dn")
    lw.write_container()

    logger.debug("Writing domains...")
    for domain in domains:
        dn = "cn=%s,%s" % (domain, dn_suffix)
        entry = {"cn": domain, "host": domain, "objectClass": ("uioHost",)}
        lw.write_entry(dn, entry)
    logger.debug("Done.")
    lw.close()


if __name__ == "__main__":
    write_mail_domains()
