# -*- coding: iso-8859-1 -*-
import re

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd import errors

class DNSError(errors.CerebrumError):
    """The operation is illegal for DNS"""
    # TODO: It is a bit unfortunate to use a bofhd exception class
    # here.  The purpose is to make bofh recognize this as a
    # user-error
    pass

class Helper(DatabaseAccessor):
    """Defines a number of methods that tries to assert that data in
    the zone-file will be legal.

    The API should use these methods to assert that new data does not
    break consistency like additional records for something that is a
    CNAME.

    TODO: that is easier said than done, as we don't really know from
    the DnsOwner class what type of data is being registered."""

##     IP_NUMBER = 'IPNumber'
##     A_RECORD = 'ARecord'
##     HOST_INFO = 'HostInfo'
##     MX_SET = 'MXSet'
##     SRV_TARGET = "SRV_target"
##     SRV_OWNER = "SRV_owner"
##     GENERAL_TTL_RECORD = "GeneralTTLRecord"
##     CNAME_OWNER = "Cname_owner"
##     CNAME_TARGET = "Cname_target"

    def __init__(self, database):
        super(Helper, self).__init__(database)

    def dns_reg_owner_ok(self, name, record_type):
        """Checks if it is legal to register a record of type
        record_type with given name.  Raises an exception if record_type
        is illegal, or name is illegal.  Returns:
          - dns_owner_ref: reference to dns_owner or None if non-existing
          - same_type: boolean set to true if a record of the same type exists."""

        dns_owner = DnsOwner.DnsOwner(self._db)
        self.legal_dns_owner_name(name)
        try:
            dns_owner.find_by_name(name)
        except Errors.NotFoundError:
            return None, None

        referers = self.get_referers(dns_owner_id=dns_owner.entity_id)
        if dns.CNAME_OWNER in referers:
            raise DNSError, "name already in use by CNAME"

        if record_type == dns.CNAME_OWNER:
            if referers:
                raise DNSError, "Bad CNAME: other records exist with the same name"
        if record_type == dns.HOST_INFO:
            if dns.HOST_INFO in referers:
                raise DNSError, "name already in use by a HOST entry"
        if record_type == dns.A_RECORD:
            if dns.A_RECORD in referers:
                return dns.entity_id, True
        return dns_owner.entity_id, False

    def legal_dns_owner_name(self, name):
        if not re.search(r'^[0-9]*[a-zA-Z]+[a-zA-Z\-0-9]*', name):
            raise DNSError, "Illegal name: '%s'" % name

    def get_referers(self, ip_number_id=None, dns_owner_id=None):
        """Return information about registrations that point to this
        ip-number/dns-owner"""

        # Not including entity-note
        assert not (ip_number_id and dns_owner_id)
        ret = []

        if ip_number_id:
            ipnumber = IPNumber.IPNumber(self._db)
            for row in ipnumber.list_override(ip_number_id=ip_number_id):
                ret.append(dns.REV_IP_NUMBER)
            arecord = ARecord.ARecord(self._db)
            for row in arecord.list_ext(ip_number_id=ip_number_id):
                ret.append(dns.A_RECORD)
            return ret
        arecord = ARecord.ARecord(self._db)
        for row in arecord.list_ext(dns_owner_id=dns_owner_id):
            ret.append(dns.A_RECORD)
        hi = HostInfo.HostInfo(self._db)
        try:
            hi.find_by_dns_owner_id(dns_owner_id)
            ret.append(dns.HOST_INFO)
        except Errors.NotFoundError:
            pass
        mx = DnsOwner.MXSet(self._db)
        for row in mx.list_mx_sets(target_id=dns_owner_id):
            ret.append(dns.MX_SET)
        dns_owner = DnsOwner.DnsOwner(self._db)
        for row in dns_owner.list_srv_records(owner_id=dns_owner_id):
            ret.append(dns.SRV_OWNER)
        for row in dns_owner.list_srv_records(target_owner_id=dns_owner_id):
            ret.append(dns.SRV_TARGET)
        for row in dns_owner.list_ttl_records(dns_owner_id=dns_owner_id):
            ret.append(dns.GENERAL_TTL_RECORD)
        cn = CNameRecord.CNameRecord(self._db)
        for row in cn.list_ext(cname_owner=dns_owner_id):
            ret.append(dns.CNAME_OWNER)
        for row in cn.list_ext(target_owner=dns_owner_id):
            ret.append(dns.CNAME_TARGET)
        return ret

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

        refs = self.get_referers(ip_number_id=ipnumber.ip_number_id)
        if not (dns.REV_IP_NUMBER in refs or dns.A_RECORD in refs):
            # IP no longer used
            ipnumber.delete()


        # Assert that any cname/srv targets still point to atleast one
        # a-record.  Assert that host_info has atleast one associated
        # a_record.
        # TODO: This check should be somewhere that makes it is easier
        # to always enforce this constraint.
        refs = self.get_referers(dns_owner_id=dns_owner_id)
        if ((dns.HOST_INFO in refs or dns.CNAME_TARGET in refs or
             dns.SRV_TARGET in refs)
            and not dns.A_RECORD in refs):
            raise DNSError(
                "A-record is used as target, or has a host_info entry")

        if try_dns_remove:
            self.remove_dns_owner(self, dns_owner_id)

    def remove_host_info(self, dns_owner_id, try_dns_remove=False):
        hi = HostInfo.HostInfo(self._db)
        try:
            hi.find_by_dns_owner_id(dns_owner_id)
        except Errors.NotFoundError:
            return              # No deletion needed
        hi._delete()
        if try_dns_remove:
            self.remove_dns_owner(self, dns.entity_id)

    def remove_cname(self, dns_owner_id, try_dns_remove=False):
        c = CNameRecord.CNameRecord(self._db)
        try:
            c.find_by_cname_owner_id(dns_owner_id)
        except Errors.NotFoundError:
            return              # No deletion needed
        c._delete()
        if try_dns_remove:
            self.remove_dns_owner(self, dns.entity_id)

    def remove_dns_owner(self, dns_owner_id):
        refs = self.get_referers(dns_owner_id=dns_owner_id)
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
        self.remove_dns_owner(dns_owner_id)

        # rev-map override må brukeren rydde i selv, da vi ikke vet
        #   hva som er rett.


    def update_reverse_override(self, ip_number_id, dest_host=None):
        """Remove (if dest_host=None)/update reverse-map override for
        ip_number_id.  Will remove dns_owner and ip_number entries if
        they are no longer in use."""

        ipnumber = IPNumber.IPNumber(self._db)
        ipnumber.find(ip_number_id)
        rows = ipnumber.list_override(ip_number_id=ip_number_id)

        if not dest_host:
            ipnumber.delete_reverse_override()
        else:
            ipnumber.update_reverse_override(ip_number_id, dest_host)

        refs = self.get_referers(ip_number_id=ipnumber.ip_number_id)
        if not (dns.REV_IP_NUMBER in refs or dns.A_RECORD in refs):
            # IP no longer used
            ipnumber.delete()

        if rows:
            refs = self.get_referers(dns_owner_id=rows[0]['dns_owner_id'])
            if not refs:
                dns_owner = DnsOwner.DnsOwner(self._db)
                dns_owner.find(rows[0]['dns_owner_id'])
                dns_owner.delete()

# arch-tag: f3000618-d5a9-49ff-a553-8cab7895939d
