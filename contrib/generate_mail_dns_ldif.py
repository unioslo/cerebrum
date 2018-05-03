#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
""" Generate LDAP host/domain info to be used by the mail system.

This script dumps email domains in Cerebrum as objects to an LDIF file, merged
with hostname data from DNS.  The information from this LDIF is used by Exim,
our MTA.


output
------
The script generates an LDIF file with email domain entries that looks like:

    dn: cn=<email-domain>,<cereconf.LDAP_MAIL_DNS['dn']>
    objectClass: uioHost
    cn: <email-domain>
    host: <hostname>
    cn: <addional-cname>
    cn: <addional-cname>
    ...

In addition, if the <email-domain> matches a zone in
``cereconf.LDAP_MAIL_DNS['dig_args']``, we will use a zone transfer (AXFR) to
dump that zone, and include some of the DNS records as LDAP object attributes:

- host: the hostname/name with an actual A/AAAA record
- cn: additional CNAME records for the hostname.

Finally, all hostnames (A/AAAA) in the DNS zones that have a valid MX, but is
not set up as an email domain in Cerebrum is dumped as:

    dn: host=<hostname>,ou=mail-dns,dc=uio,dc=no
    objectClass: uioHost
    host: <hostname>
    cn: <additional-cname>
    cn: <additional-cname>
    ...


cereconf
--------

This script is configured with LDAP_MAIL_DNS, which is a dictionary with the
following values:

dig_args (e.g. [("example.org", "ns.example.org"), ])
    Sequence of tuples (dns zone, dns name server) with arguments to 'dig_cmd'.
    DNS data will be gathered at the given name server for the given zone in
    each tuple, and included in the output LDIF.

dig_cmd (e.g. "/usr/bin/dig %s. @%s. axfr")
    The 'dig' command used to fetch information from DNS. Zone and name server
    will be replaced from 'dig_args'.

dn (e.g. "cn=mail-dns,dc=example,dc=org")
    dn-suffix for all objects that this script produces. With the example
    provided, an email domain 'foo.example.org' in Cerebrum would be exported
    as 'dn: cn=foo.example.org,cn=mail-dns,dc=example,dc=org'

extra_a_hosts (e.g. ["foo.example.org", "bar.example.org"])
    Accept these hostnames as real A/AAAA records, even if they don't exist in
    DNS.

file (e.g. "mail-dns.ldif")
    filename (within the `cereconf.LDAP['dump_dir']`) for the LDIF file.

mx_hosts (e.g. ["smtp1.example.org", "smtp2.example.org"])
    List of valid MX values. Only consider hosts which have these hosts as
    lowest priority MX record and also are A records.

save_dig_output (e.g. 3)
    If set to a positive value, the output from DiG is saved to
    cereconf.LDAP['dump_dir'] as 'dig.out'. For every number higher than one,
    an additional old output file is kept as (dig.out.N).

"""
from __future__ import absolute_import, unicode_literals
import operator
import os
import re
import shlex
import subprocess
from collections import defaultdict, OrderedDict
from warnings import warn

import cereconf

from Cerebrum.Errors import CerebrumError
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.LDIFutils import (container_entry_string,
                                        end_ldif_outfile,
                                        ldapconf,
                                        ldif_outfile)


# TODO: Replace DNS lookups and dig output parsing with the dnspython module

# Expect /local/bin/dig output like this:
#
#   ; <<>> DiG 9.3.5-P1 <<>> uio.no. @nissen.uio.no. axfr
#   ;; global options:  printcmd
#   cerebrum.uio.no.	43200	IN	CNAME	cerebellum.uio.no.
#   cerebellum.uio.no.	43200	IN	A	129.240.2.117
#   cerebellum.uio.no.	43200	IN	MX	10 smtp.uio.no.
#   ;; Query time: 2021 msec
#   ;; SERVER: ...
#   ;; WHEN: ...
#   ;; XFR size: 141769 records (messages 92)
#
# Dig (as of version 9.2.1) may not return a non-zero exit status on
# failure, so check if the output matches the above and fail otherwise
#
# The output format from dig has changed between versions, so
# this program may have to be changed when dig is upgraded again.

# record -> (name, type, rdata)
match_dig_line = re.compile(
    r"(\S+)\.\s+\d+\s+IN\s+(\w+)\s+(.*[^.\n])\.?$").match

# comment or blank line
check_dig_line = re.compile(r"(?:;;? |$)").match

# expected output -> version
match_checked_lines = re.compile(r"""
*; <<>> DiG (\d+)\..+
(?:;; (?:\w+ )?options: .+
)*;; Query time: \d+ msec
;; SERVER: .+
;; WHEN: .+
;; XFR size: \d+ records.*
+$""").match

expect_dig_version = "9"


def get_savefile(filename, copies=9):
    """ Get a file descriptor for a named file and rotate any older copies. """
    # copies and rotate dig output, so unexpected output can be inspected.
    # TODO: Could we use atomicfile for this?
    try:
        if copies < 1:
            raise ValueError("not using savefile")
        if not filename:
            raise ValueError("no filename")
        if copies > 1:
            backups = [(filename, filename + ".1")]
            for i in range(2, copies):
                backups.insert(0, (backups[0][1], "%s.%d" % (filename, i)))
            for oldname, newname in backups:
                if os.path.isfile(oldname):
                    os.rename(oldname, newname)
        return open(filename, "w")
    except Exception as e:
        warn("Unable to open {0}, using {1} ({2})".format(repr(filename),
                                                          os.devnull,
                                                          repr(e)),
             RuntimeWarning)
        return open(os.devnull, "w")


def get_zone_records(ns, zone, rtypes, savefile):
    """ Do a zone tranfer with `dig`.

    :param str ns: The name server to use
    :param str zone: The dns zone to transfer
    :param list rtypes: A sequence of record types to include in the result.
    :param file fd: A file object to write the output from `dig` to.

    :return generator:
        A generator that yields tuples of (name, type, rdata) for matching DNS
        records.
    """
    # TODO: There's really very little reason to have anything other than the
    # executable as config. The arguments might as well be hard-coded, as long
    # as the version number is hard-coded in regexp here.
    cmd = shlex.split(cereconf.LDAP_MAIL_DNS['dig_cmd'] % (zone, ns))
    savefile.write("## {0} ##\n".format(subprocess.list2cmdline(cmd)))

    check_lines = []
    pipe = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE)
    out, err = pipe.communicate()

    if pipe.returncode != 0:
        raise RuntimeError(
            "dig failed with exitcode {}: {}".format(pipe.returncode,
                                                     out))

    for line in out.splitlines(True):
        savefile.write(line)
        match = match_dig_line(line)
        if match:
            name, rtype, rdata = match.groups()
            if rtype not in rtypes:
                continue
            yield name, rtype, rdata
        elif check_dig_line(line):
            check_lines.append(line)
        else:
            raise ValueError("Unexpected output from dig:\n" + line)

    match = match_checked_lines("".join(check_lines))
    if not match:
        if len(check_lines) > 12:
            check_lines[12:] = ["...\n"]
        raise ValueError("Unexpected comments from dig:\n"
                         "".join(check_lines).strip("\n"))

    if match.group(1) != expect_dig_version:
        raise ValueError(
            "dig version changed.  Check if its output format changed.")


def get_hosts_and_cnames():
    """ Get DNS records with an affiliated MX record.

    1. For every MX record, find the highest priority record and filter with
       LDAP_MAIL_DNS['mx_names']
    2. Find all hostnames (A/AAAA record names) that also have one of the MX
       records from (1)
    3. Find all CNAMEs that has a hostname record from (2)

    :return tuple:
        Returns a tuple with four values:

        dict: str -> list
            A dict that maps every hostname (a, aaaa record names) to a list of
            (potentially zero) cnames.  All hostnames and cnames are lowercase.
            Every hostname in this dict will have an MX record.

        dict: str -> str
            A reverse lookup of 'host2cnames'.

        dict: str -> str
            All names in the other dicts are lowercased, for lookup purposes.
            This dict maps dns records names back to the proper casing.

        set: str
            A set of names that only has MX records (and no A/AAAA) in DNS.
    """
    a_records = set()               # names of a/aaaa records
    host2cnames = defaultdict(set)  # hostname -> set(cname, ...)
    cname2host = {}                 # cname -> hostname
    host2mx = defaultdict(dict)     # name -> {priority: mx-name, ...}
    lower2name = {}                 # lowercase name -> name

    with get_savefile(
            os.path.join(cereconf.LDAP['dump_dir'], "dig.out"),
            cereconf.LDAP_MAIL_DNS.get('save_dig_output', 0)) as savefile:

        for zone, ns in cereconf.LDAP_MAIL_DNS['dig_args']:
            for name, rr_type, rdata in get_zone_records(
                    ns, zone, ["A", "AAAA", "CNAME", "MX"], savefile):
                lname = name.lower()
                rdata = rdata.lower()
                lower2name[lname] = name
                if rr_type in ('A', 'AAAA',):
                    a_records.add(lname)
                elif rr_type == 'CNAME':
                    host2cnames[rdata].add(lname)
                    cname2host[lname] = rdata
                elif rr_type == 'MX':
                    prio, mx = rdata.split()
                    host2mx[lname][int(prio)] = mx

    # Add fake Dig records
    for host in cereconf.LDAP_MAIL_DNS.get('extra_a_hosts') or ():
        a_records.add(host)

    # Find hosts that both have an A record
    # and has its 'best' MX record in cereconf.LDAP_MAIL_DNS['mx_hosts'].
    hosts = {}
    hosts_only_mx = set()
    accept_mx = set(cereconf.LDAP_MAIL_DNS['mx_hosts'] or ())
    for host, mx_dict in host2mx.items():
        # get the MX record value with the highest priority
        mx = max(mx_dict.items(), key=operator.itemgetter(0))[1]

        if mx in accept_mx:
            if host in a_records:
                hosts[host] = list(sorted(host2cnames.get(host, ())))
            else:
                # no A/AAAA record, but MX
                hosts_only_mx.add(host)

    # Remove cnames that do not appear in host2cnames ??? should be hosts[]?
    for cname in list(cname2host.keys()):
        if cname2host[cname] not in host2cnames:
            del cname2host[cname]

    return hosts, cname2host, lower2name, hosts_only_mx


def get_email_domains():
    """ Get email domains from Cerebrum.

    :return generator:
        A generator that yield email domains that are not excluded from export.
    """
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    email = Email.EmailDomain(db)

    exclude = set(
        (int(row['domain_id'])
         for row in email.list_email_domains_with_category(
             co.email_domain_category_noexport)))

    for row in email.list_email_domains():
        if int(row['domain_id']) in exclude:
            continue
        yield row['domain']


def write_mail_dns():
    """ Gather data and dump to ldif. """
    logger = Factory.get_logger('cronjob')

    hosts, cnames, lower2host, hosts_only_mx = get_hosts_and_cnames()

    # email domains (lowercase -> domain), in alphabetical order
    domains = OrderedDict(
        (d.lower(), d) for d in sorted(get_email_domains()))

    domain_wo_mx = set()
    for domain in domains:
        # Verify that domains have an MX-record.
        for arg in cereconf.LDAP_MAIL_DNS['dig_args']:
            zone = arg[0]
            if domain.endswith(zone) and not (domain in hosts_only_mx or
                                              domain in hosts):
                logger.error("email domain without MX defined: %s" % domain)
                domain_wo_mx.add(domain.lower())
        # Valid email domains only requires MX
        if domain in hosts_only_mx:
            hosts_only_mx.remove(domain)

    for host in hosts_only_mx:
        logger.warn(
            "MX defined but no A/AAAA record or valid email domain: %s" % host)

    if domain_wo_mx:
        cause = "{0:d} email domains without mx".format(len(domain_wo_mx))
        logger.error("{0}, this must be rectified manually!".format(cause))
        raise CerebrumError(cause)

    f = ldif_outfile('MAIL_DNS')

    def handle_domain_host(host):
        f.write("host: %s\n" % lower2host[host])
        for cname in hosts[host]:
            if cname not in domains:
                f.write("cn: %s\n" % lower2host[cname])
                del cnames[cname]
        del hosts[host]

    dn_suffix = ldapconf('MAIL_DNS', 'dn')

    f.write(container_entry_string('MAIL_DNS'))

    for domain, output in domains.items():
        f.write("""dn: cn=%s,%s
objectClass: uioHost
cn: %s
""" % (output, dn_suffix, output))
        try:
            if domain in cnames:
                # This fails `if domain not in hosts`
                f.write("cn: %s\n" % lower2host[cnames[domain]])
                handle_domain_host(cnames[domain])
            elif domain in hosts:
                handle_domain_host(domain)
        except Exception:
            logger.error("domain=%r, cnames[domain]=%r, "
                         "in hosts=%r, in cnames=%r",
                         domain, cnames.get(domain),
                         domain in hosts, domain in cnames)
            raise
        f.write('\n')

    for host in sorted(hosts.keys()):
        f.write("""dn: host=%s,%s
objectClass: uioHost
host: %s
cn: %s
""" % (lower2host[host], dn_suffix, lower2host[host], lower2host[host]))
        for cname in hosts[host]:
            f.write("cn: %s\n" % lower2host[cname])
        f.write('\n')
    end_ldif_outfile('MAIL_DNS', f)


if __name__ == '__main__':
    write_mail_dns()
