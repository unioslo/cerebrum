# -*- coding: iso-8859-1 -*-
import re
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import IntegrityHelper
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError
import cereconf_dns
from Cerebrum.modules import dns

class DnsParser(object):
    """Map user-entered data to dns datatypes/database-ids"""

    def __init__(self, db, default_zone):
        self._db = db
        self._validator = IntegrityHelper.Validator(db, default_zone)
        self._arecord = ARecord.ARecord(self._db)
        self._ip_number = IPNumber.IPNumber(self._db)
        self._dns_owner = DnsOwner.DnsOwner(self._db)
        self._mx_set = DnsOwner.MXSet(self._db)
        self._host = HostInfo.HostInfo(self._db)
        self._cname = CNameRecord.CNameRecord(self._db)

    def parse_subnet_or_ip(self, ip_id):
        """Parse ip_id either as a subnet, or as an IP-number.

        Return: (subnet, a_ip)
          - subnet is None if unknown
          - a_ip is only set if the user requested a spesific IP
        
        A request for a subnet is identified by a trailing /, or an IP
        with < 4 octets.  Example::

          129.240.200    -> adress on 129.240.200.0/23 
          129.240.200.0/ -> adress on 129.240.200.0/23 
          129.240.200.0  -> explicit IP
        """

        tmp = ip_id.split("/")
        ip_id = tmp[0]
        if (not ip_id[0].isdigit()) and len(tmp) > 1:  # Support ulrik.uio.no./
            try:
                self._arecord.clear()
                self._arecord.find_by_name(self._validator.qualify_hostname(ip_id))
                self._ip_number.clear()
                self._ip_number.find(self._arecord.ip_number_id)
            except Errors.NotFoundError:
                raise CerebrumError, "Could not find %s" % ip_id
            ip_id = self._ip_number.a_ip

        full_ip = len(ip_id.split(".")) == 4
        if len(tmp) > 1 or not full_ip:  # Trailing "/" or few octets
            full_ip = False
        try:
            ipc = Find(self._db, None)
            subnet = ipc._find_subnet(ip_id).net
        except IntegrityHelper.DNSError:
            subnet = None
        return subnet, full_ip and ip_id or None

    def parse_force(self, string):
        if string and string[0] in ('Y', 'y'):
            return True
        return False

    def parse_hostname_repeat(self, name):
        """Handles names like pcusit[01..30]"""
        
        m = re.search(r'(.*)\[(\d+)\.\.(\d+)]', name)
        if not m:
            return [name]
        ret = []
        fill = str(len(m.group(2)))      # Leading zeroes
        for n in range(int(m.group(2)), int(m.group(3))+1):
            ret.append(("%s%0"+fill+"i") % (m.group(1), n))
        return ret

class Find(object):
    def __init__(self, db, default_zone):
        self._db = db
        self._ip_number = IPNumber.IPNumber(db)
        self._arecord = ARecord.ARecord(db)
        self._dns_owner = DnsOwner.DnsOwner(db)
        self._mx_set = DnsOwner.MXSet(db)
        self._host = HostInfo.HostInfo(db)
        self._cname = CNameRecord.CNameRecord(db)
        self._validator = IntegrityHelper.Validator(db, default_zone)
        self.subnets = {}
        ic = IPCalc()
        for sub_def in cereconf_dns.all_nets:
            start, stop = ic.ip_range_by_netmask(sub_def.net, sub_def.mask)
            self.subnets[sub_def.net] = sub_def

    def find_target_by_parsing(self, host_id, target_type):
        """Find a target with given host_id of the specified
        target_type.  Legal target_types ad IP_NUMBER and DNS_OWNER.
        Host_id may be given in a number of ways, one can lookup IP_NUMBER
        by both hostname (A record) and ip or id:ip_number_id etc.

        Returns dns_owner_id or ip_number_id depending on target_type.
        """

        # TODO: handle idtype:id syntax
        
        tmp = host_id.split(".")
        if tmp[-1].isdigit():
            # It is an IP-number
            self._ip_number.clear()
            try:
                self._ip_number.find_by_ip(host_id)
            except Errors.NotFoundError:
                raise CerebrumError, "Could not find ip-number: %s" % host_id
            if target_type == dns.IP_NUMBER:
                return self._ip_number.ip_number_id

            self._arecord.clear()
            try:
                self._arecord.find_by_ip(self._ip_number.ip_number_id)
            except Errors.NotFoundError:
                raise CerebrumError, "Could not find name for ip-number: %s" % host_id
            except Errors.TooManyRowsError:
                raise CerebrumError, "Not unique name for ip-number: %s" % host_id
            return self._arecord.dns_owner_id

        host_id = self._validator.qualify_hostname(host_id)
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(host_id)
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find dns-owner: %s" % host_id
        if target_type == dns.DNS_OWNER:
            return self._dns_owner.entity_id

        self._arecord.clear()
        try:
            self._arecord.find_by_dns_owner_id(self._dns_owner.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find ip-number for name: %s" % host_id
        except Errors.TooManyRowsError:
            raise CerebrumError, "Not ip-number for name: %s" % host_id
        return self._arecord.ip_number_id

    def find_mx_set(self, name):
        self._mx_set.clear()
        try:
            self._mx_set.find_by_name(name)
        except Errors.NotFoundError:
            raise CerebrumError, "No mx-set with name %s" % name
        return self._mx_set

    def find_target_type(self, owner_id, target_ip=None):
        """Find a target and its type by prefering hosts above
        a-records"""

        self._host.clear()
        try:
            self._host.find_by_dns_owner_id(self._dns_owner.entity_id)
            return self._host, self._host.entity_id
        except Errors.NotFoundError:
            pass

        self._cname.clear()
        try:
            self._cname.find_by_cname_owner_id(self._dns_owner.entity_id)
            return self._cname, self._cname.entity_id
        except Errors.NotFoundError:
            pass

        self._arecord.clear()
        try:
            if target_ip:
                raise NotImplemented
            else:
                self._arecord.find_by_dns_owner_id(owner_id)
            return self._arecord, self._arecord.entity_id
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError:
            raise CerebrumError, "Not unique a-record: %s" % owner_id

    def find_free_ip(self, subnet):
        """Returns the first free IP on the subnet"""
        subnet_def = self._find_subnet(subnet)
        a_ip = self._find_available_ip(subnet_def)
        if not a_ip:
            raise ValueError, "No available ip on that subnet"
        return [IPCalc.long_to_ip(t) for t in a_ip]

    def _find_subnet(self, subnet):
        """Translate the user-entered subnet to the key in
        self.subnets"""
        if len(subnet.split(".")) == 3:
            subnet += ".0"
        numeric_ip = IPCalc.ip_to_long(subnet)
        for net, subnet_def in self.subnets.items():
            if numeric_ip >= subnet_def.start and numeric_ip <= subnet_def.stop:
                print "REROT: ", repr(net)
                return subnet_def
        raise IntegrityHelper.DNSError, "%s is not in any known subnet" % subnet

    def _find_available_ip(self, subnet_def):
        """Returns all ips that are not reserved or taken on the given
        subnet in ascending order."""

        ip_number = IPNumber.IPNumber(self._db)
        ip_number.clear()
        taken = {}
        for row in ip_number.find_in_range(subnet_def.start, subnet_def.stop):
            taken[long(row['ipnr'])] = int(row['ip_number_id'])
        ret = []
        for n in range(0, (subnet_def.stop-subnet_def.start)+1):
            if (not taken.has_key(long(subnet_def.start+n)) and
                n not in subnet_def.reserved):
                ret.append(n+subnet_def.start)
        return ret

    def find_ip(self, a_ip):
        self._ip_number.clear()
        try:
            self._ip_number.find_by_ip(a_ip)
            return self._ip_number.ip_number_id
        except Errors.NotFoundError:
            return None

    def find_a_record(self, host_name, ip=None):
        owner_id = self.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        ar = ARecord.ARecord(self._db)
        if ip:
            a_ip = ip
            ip = self.find_target_by_parsing(
                ip, dns.IP_NUMBER)
            try:
                ar.find_by_owner_and_ip(ip, owner_id)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "No A-record with name=%s and ip=%s" % (host_name, a_ip))
        else:
            try:
                ar.find_by_dns_owner_id(owner_id)
            except Errors.ErrorsNotFoundError:
                raise CerebrumError("No A-record with name=%s" % host_name)
            except Errors.TooManyRowsError:
                raise CerebrumError("Multiple A-records with name=%s" % host_name)
        return ar.entity_id

# arch-tag: 48677ab8-12e8-11da-9116-393d26bedebb
