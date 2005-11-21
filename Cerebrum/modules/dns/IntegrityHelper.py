# -*- coding: iso-8859-1 -*-
import re

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import IPNumber
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

    def dns_reg_owner_ok(self, name, record_type):
        """Checks if it is legal to register a record of type
        record_type with given name.  Raises an exception if record_type
        is illegal, or name is illegal.  Returns:
          - dns_owner_ref: reference to dns_owner or None if non-existing
          - same_type: boolean set to true if a record of the same type exists."""

        dns_owner = DnsOwner.DnsOwner(self._db)
        self.legal_dns_owner_name(name, record_type)
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
        if record_type == dns.A_RECORD:
            if dns.A_RECORD in owner_types:
                return dns_owner.entity_id, True
        return dns_owner.entity_id, False

    def legal_dns_owner_name(self, name, record_type):
        if record_type == dns.SRV_OWNER:
            rexp = re.compile(r'^[0-9_]*[a-zA-Z]+[a-zA-Z\-0-9]*$')
        else:
            rexp = re.compile(r'^[0-9]*[a-zA-Z]+[a-zA-Z\-0-9]*$')
        if not name.endswith('.'):
            raise DNSError, "Name not fully qualified"
        for n in name[:-1].split("."):
            if not rexp.search(n):
                raise DNSError, "Illegal name: '%s'" % name

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
        """Remove an a-record identified by a_record_id.  Will also
        remove the entry in ip_number if it is no longer refered by
        other tables"""
        
        arecord = ARecord.ARecord(self._db)
        arecord.find(a_record_id)
        ipnumber = IPNumber.IPNumber(self._db)
        ipnumber.find(arecord.ip_number_id)
        dns_owner_id = arecord.dns_owner_id
        arecord._delete()

        refs = self._find.find_referers(ip_number_id=ipnumber.entity_id)
        if not (dns.REV_IP_NUMBER in refs or dns.A_RECORD in refs):
            # IP no longer used
            ipnumber.delete()

        # Assert that any cname/srv targets still point to atleast one
        # a-record.  Assert that host_info has atleast one associated
        # a_record.
        # TODO: This check should be somewhere that makes it is easier
        # to always enforce this constraint.
        refs = self._find.find_referers(dns_owner_id=dns_owner_id)
        if ((dns.HOST_INFO in refs or dns.CNAME_TARGET in refs or
             dns.SRV_TARGET in refs)
            and not dns.A_RECORD in refs):
            raise DNSError(
                "A-record is used as target, or has a host_info entry")

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
            self.remove_dns_owner(dns.entity_id)

    def remove_cname(self, dns_owner_id, try_dns_remove=False):
        c = CNameRecord.CNameRecord(self._db)
        try:
            c.find_by_cname_owner_id(dns_owner_id)
        except Errors.NotFoundError:
            return              # No deletion needed
        c._delete()
        if try_dns_remove:
            self.remove_dns_owner(dns.entity_id)

    def remove_dns_owner(self, dns_owner_id):
        refs = self._find.find_referers(dns_owner_id=dns_owner_id)
        if refs:
            raise DNSError("dns_owner still refered in %s" % str(refs))
        dns_owner = DnsOwner.DnsOwner(self._db)
        dns_owner.find(dns_owner_id)
        dns_owner.delete()

    def full_remove_dns_owner(self, dns_owner_id):
        # fjerner alle entries der dns_owner vil være til venstre i
        # sonefila.

        self.remove_host_info(dns_owner_id)
        arecord = ARecord.ARecord(self._db)
        for row in arecord.list_ext(dns_owner_id=dns_owner_id):
            self.remove_arecord(row['a_record_id'])
        self.remove_cname(dns_owner_id)
        dns_owner = DnsOwner.DnsOwner(self._db)
        for row in dns_owner.list_general_dns_records(
            dns_owner_id=dns_owner_id):
            dns_owner.delete_general_dns_record(dns_owner_id,
                                                row['field_type'])
        self.remove_dns_owner(dns_owner_id)

        # rev-map override må brukeren rydde i selv, da vi ikke vet
        #   hva som er rett.

    def add_reverse_override(self, ip_number_id, dest_host):
        # TODO: Only allow one None/ip
        ipnumber = IPNumber.IPNumber(self._db)
        ipnumber.add_reverse_override(ip_number_id, dest_host)

    def remove_reverse_override(self, ip_number_id, dest_host):
        """Remove reverse-map override for ip_number_id.  Will remove
        dns_owner and ip_number entries if they are no longer in
        use."""
        ipnumber = IPNumber.IPNumber(self._db)
        ipnumber.find(ip_number_id)
        ipnumber.delete_reverse_override(ip_number_id, dest_host)

        refs = self._find.find_referers(ip_number_id=ip_number_id)
        if not (dns.REV_IP_NUMBER in refs or dns.A_RECORD in refs):
            # IP no longer used
            ipnumber.delete()

        if dest_host is not None:
            refs = self._find.find_referers(dns_owner_id=dest_host)
            if not refs:
                dns_owner = DnsOwner.DnsOwner(self._db)
                dns_owner.find(dest_host)
                dns_owner.delete()

# arch-tag: 4805ae64-12e8-11da-84aa-8318af99ae66
