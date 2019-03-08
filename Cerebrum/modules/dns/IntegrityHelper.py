# -*- coding: iso-8859-1 -*-
# Copyright 2005-2006 University of Oslo, Norway
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

import re

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import AAAARecord
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import IPv6Number
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns.Errors import DNSError
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.dns import Utils


class Validator(object):
    def __init__(self, db, default_zone):
        self._db = db
        self._default_zone = default_zone
        self._find = Utils.Find(self._db, default_zone)

    def dns_reg_owner_ok(self, name, record_type, allow_underscores=False):
        """Checks if it is legal to register a record of type
        record_type with given name.  Raises an exception if record_type
        is illegal, or name is illegal.  Returns:
          - dns_owner_ref: reference to dns_owner or None if non-existing
          - same_type: boolean set to true if a record of the same type exists."""

        dns_owner = DnsOwner.DnsOwner(self._db)
        self.legal_dns_owner_name(name, record_type, allow_underscores)
        try:
            dns_owner.find_by_name(name)
        except Errors.NotFoundError:
            return None, None

        owner_types = self._find.find_dns_owners(dns_owner.entity_id)

        if dns.CNAME_OWNER in owner_types:
            raise DNSError, "%s is already a CNAME" % name

        if record_type == dns.CNAME_OWNER:
            if owner_types:
                raise DNSError, "%s already exists" % name
        if record_type == dns.HOST_INFO:
            if dns.HOST_INFO in owner_types:
                raise DNSError, "%s already exists" % name
        # TODO: This should probarbly be rewritten, since it is a bit ugly.
        # The difference between A- and AAAA-records is minimal, so this is
        # enough for now.
        if record_type in (dns.A_RECORD, dns.AAAA_RECORD,):
            if dns.A_RECORD in owner_types or dns.AAAA_RECORD in owner_types:
                return dns_owner.entity_id, True

        return dns_owner.entity_id, False

    def legal_dns_owner_name(self, name, record_type, allow_underscores=False):
        uber_hyphen = re.compile(r'---+')
        uber_underscore = re.compile(r'__+')
        if record_type == dns.SRV_OWNER or allow_underscores:
            valid_chars = re.compile(r'^[a-zA-Z\-_0-9]*$')
        else:
            valid_chars = re.compile(r'^[a-zA-Z\-0-9]+$')

        if not name.endswith('.'):
            raise DNSError, "Name not fully qualified"

        for n in name[:-1].split("."):
            if n.startswith("-") or n.endswith("-"):
                raise DNSError, "Illegal name: '%s'; Cannot start or end with '-'" % name
            if uber_hyphen.search(n):
                raise DNSError, "Illegal name: '%s'; More than two '-' in a row" % name
            if not valid_chars.search(n):
                raise DNSError, "Illegal name: '%s'; Invalid character(s)" % name
            if record_type == dns.SRV_OWNER:
                if uber_underscore.search(n):
                    raise DNSError, "Illegal name: '%s'; More than one '_' in a row" % name

    def legal_mx_target(self, target_id):
        owner_types = self._find.find_dns_owners(target_id)
        if not dns.A_RECORD in owner_types:
            raise errors.CerebrumError("MX target must be an A-record")


class Updater(object):
    def __init__(self, db):
        self._validator = Validator(db, None)
        self._db = db
        self._find = Utils.Find(self._db, None)

    def remove_arecord(self, a_record_id, try_dns_remove=False):
        """Remove an a-record identified by a_record_id.

        Will also update override_revmap and remove the entry in ip_number if
        it is no longer referred to by other tables.

        :param int a_record_id: The ARecords id.
        :param bool try_dns_remove: Remove the DNSOwner too.
        """
        ip_type = dns.IP_NUMBER
        record_type = dns.A_RECORD
        arecord = ARecord.ARecord(self._db)

        try:
            arecord.find(a_record_id)
            ip_number_id = arecord.ip_number_id
            ipnumber = IPNumber.IPNumber(self._db)
        except Errors.NotFoundError:
            arecord = AAAARecord.AAAARecord(self._db)
            arecord.find(a_record_id)
            ip_type = dns.IPv6_NUMBER
            record_type = dns.AAAA_RECORD
            ip_number_id = arecord.ipv6_number_id
            ipnumber = IPv6Number.IPv6Number(self._db)

        ipnumber.find(ip_number_id)

        dns_owner_id = arecord.dns_owner_id
        arecord._delete()

        refs = self._find.find_referers(ip_number_id=ipnumber.entity_id,
                                        ip_type=ip_type)
        if dns.REV_IP_NUMBER in refs:
            self._update_override(ipnumber.entity_id, dns_owner_id)
            refs = self._find.find_referers(ip_number_id=ipnumber.entity_id,
                                            ip_type=ip_type)

        if not (dns.REV_IP_NUMBER in refs or record_type in refs):
            # IP no longer used
            ipnumber.delete()

        # Assert that any cname/srv targets still point to atleast one
        # a-record.  Assert that host_info has atleast one associated
        # a_record.
        # TODO: This check should be somewhere that makes it is easier
        # to always enforce this constraint.
        refs = self._find.find_referers(dns_owner_id=dns_owner_id,
                                        ip_type=ip_type)
        if record_type not in refs:
            if dns.SRV_TARGET in refs or dns.CNAME_TARGET in refs:
                raise DNSError("Host is used as target for CNAME or SRV")

        if try_dns_remove:
            self.remove_dns_owner(dns_owner_id)

    def remove_host_info(self, dns_owner_id, try_dns_remove=False):
        hi = HostInfo.HostInfo(self._db)
        try:
            hi.find_by_dns_owner_id(dns_owner_id)
        except Errors.NotFoundError:
            return              # No deletion needed
        hi._delete()
        if try_dns_remove:
            self.remove_dns_owner(dns_owner_id)

    def remove_cname(self, dns_owner_id, try_dns_remove=False):
        c = CNameRecord.CNameRecord(self._db)
        try:
            c.find_by_cname_owner_id(dns_owner_id)
        except Errors.NotFoundError:
            return              # No deletion needed
        c._delete()
        if try_dns_remove:
            self.remove_dns_owner(dns_owner_id)

    def remove_dns_owner(self, dns_owner_id):
        refs = self._find.find_referers(dns_owner_id=dns_owner_id)
        if refs:
            raise DNSError("dns_owner still refered in %s" % str(refs))

        dns_owner = DnsOwner.DnsOwner(self._db)
        dns_owner.find(dns_owner_id)

        if not self._find.find_overrides(dns_owner_id=dns_owner_id):
            dns_owner.delete()
        else:
            for t in dns_owner.get_traits().keys():
                try:
                    dns_owner.delete_trait(t)
                except Errors.NotFoundError:
                    pass
            dns_owner.mx_set_id = None
            dns_owner.write_db()


    def full_remove_dns_owner(self, dns_owner_id):
        # fjerner alle entries der dns_owner vil være til venstre i
        # sonefila.

        self.remove_host_info(dns_owner_id)
        arecord = ARecord.ARecord(self._db)
        for row in arecord.list_ext(dns_owner_id=dns_owner_id):
            self.remove_arecord(row['a_record_id'])
        aaaarecord = AAAARecord.AAAARecord(self._db)
        for row in aaaarecord.list_ext(dns_owner_id=dns_owner_id):
            self.remove_arecord(row['aaaa_record_id'])
        self.remove_cname(dns_owner_id)
        dns_owner = DnsOwner.DnsOwner(self._db)
        for row in dns_owner.list_general_dns_records(
            dns_owner_id=dns_owner_id):
            dns_owner.delete_general_dns_record(dns_owner_id,
                                                row['field_type'])
        self.remove_dns_owner(dns_owner_id)

        # rev-map override må brukeren rydde i selv, da vi ikke vet
        #   hva som er rett.

    def _update_override(self, ip_number_id, dns_owner_id):
        """Handles the updating of the override_reversemap when an
        ARecord is removed."""

        # Select correct IP-variant
        try:
            ipnumber = IPNumber.IPNumber(self._db)
            ipnumber.clear()
            ipnumber.find(ip_number_id)
            ar = ARecord.ARecord(self._db)
        except Errors.NotFoundError:
            ipnumber = IPv6Number.IPv6Number(self._db)
            ar = AAAARecord.AAAARecord(self._db)


        owners = []
        for row in ipnumber.list_override(ip_number_id=ip_number_id):
            if dns_owner_id == row['dns_owner_id']:
                # Always remove the reverse which corresponds to the
                # ARecord which is being removed.
                ipnumber.delete_reverse_override(ip_number_id, dns_owner_id)
            elif row['dns_owner_id'] == None:
                # We know that this IP has been associated with an
                # ARecord.  If PTR generation has been surpressed by
                # setting owner to NULL, we want to remove the reverse
                # to avoid surprises when the IP is reused.
                ipnumber.delete_reverse_override(ip_number_id, None)
            else:
                owners.append(row['dns_owner_id'])

        if len(owners) != 1:
            return

        # The single entry left is redundant if there is only one
        # ARecord referring to the IP.
        rows = ar.list_ext(ip_number_id=ip_number_id)
        if len(rows) == 1 and rows[0]['dns_owner_id'] == owners[0]:
            ipnumber.delete_reverse_override(ip_number_id, owners[0])

    def add_reverse_override(self, ip_number_id, dest_host):
        # TODO: Only allow one None/ip
        try: 
            ipnumber = IPv6Number.IPv6Number(self._db)
            ipnumber.find(ip_number_id)
        except Errors.NotFoundError:
            ipnumber = IPNumber.IPNumber(self._db)

        ipnumber.add_reverse_override(ip_number_id, dest_host)

    def remove_reverse_override(self, ip_number_id, dest_host):
        """Remove reverse-map override for ip_number_id.  Will remove
        dns_owner and ip_number entries if they are no longer in
        use."""

        try:
            ipnumber = IPv6Number.IPv6Number(self._db)
            ipnumber.find(ip_number_id)
            a_type = dns.AAAA_RECORD
            ip_type = dns.IPv6_NUMBER
            o_ip_type = dns.IP_NUMBER
            o_ipnumber = IPNumber.IPNumber(self._db)
        except Errors.NotFoundError:
            ipnumber = IPNumber.IPNumber(self._db)
            ipnumber.find(ip_number_id)
            a_type = dns.A_RECORD
            ip_type = dns.IP_NUMBER
            o_ip_type = dns.IPv6_NUMBER
            o_ipnumber = IPv6Number.IPv6Number(self._db)

        ipnumber.delete_reverse_override(ip_number_id, dest_host)

        refs = self._find.find_referers(ip_number_id=ip_number_id, ip_type=ip_type)
        if not (dns.REV_IP_NUMBER in refs or a_type in refs):
            # IP no longer used
            ipnumber.delete()

        if dest_host is not None:
            refs = self._find.find_referers(dns_owner_id=dest_host, 
                                            ip_type=ip_type)
            refs += self._find.find_referers(dns_owner_id=dest_host,
                                            ip_type=o_ip_type)
            if not refs:
                tmp = []
                for row in ipnumber.list_override(dns_owner_id=dest_host):
                    # One might argue that find_referers also should find 
                    # this type of refs.
                    tmp.append((dns.DNS_OWNER, row['dns_owner_id']))
                for row in o_ipnumber.list_override(dns_owner_id=dest_host):
                    tmp.append((dns.DNS_OWNER, row['dns_owner_id']))

                if not tmp:
                    dns_owner = DnsOwner.DnsOwner(self._db)
                    dns_owner.find(dest_host)
                    dns_owner.delete()

