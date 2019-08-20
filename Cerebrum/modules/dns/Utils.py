# -*- coding: utf-8 -*-
import re
import cereconf
import socket

from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import AAAARecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import IPv6Number
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import Subnet
from Cerebrum.modules.dns import IPv6Subnet
from Cerebrum.modules.dns.Errors import DNSError, SubnetError
from Cerebrum.modules.dns.IPUtils import IPCalc, IPUtils
from Cerebrum.modules.dns.IPv6Utils import IPv6Calc, IPv6Utils
from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules import dns


class DnsParser(object):
    """Map user-entered data to dns datatypes/database-ids"""

    def __init__(self, db, default_zone):
        self._db = db
        self._arecord = ARecord.ARecord(self._db)
        self._ip_number = IPNumber.IPNumber(self._db)
        self._dns_owner = DnsOwner.DnsOwner(self._db)
        self._mx_set = DnsOwner.MXSet(self._db)
        self._host = HostInfo.HostInfo(self._db)
        self._cname = CNameRecord.CNameRecord(self._db)
        self._default_zone = default_zone

    def parse_subnet_or_ip(self, ip_id):
        """Parse ip_id either as a subnet, or as an IP-number.

        Return: (subnet, ip)
          - subnet is None if unknown
          - ip is only set if the user requested a specific IP

        A request for a subnet is identified by a trailing /, or for IPv4 an
        IP with < 4 octets. IPv6-subnets must always be specified with a
        trailing /, followed by a mask number. Examples::

          129.240.200    -> adress on 129.240.200.0/23
          129.240.200.0/ -> adress on 129.240.200.0/23
          129.240.200.0  -> explicit IP
          2001:700:100:2::/64 -> address on 2001:700:100:2::/64
          2001:700:100:2::3   -> explicit IP
        """
        tmp = ip_id.split("/")
        ip = tmp[0]
        subnet_slash = len(tmp) > 1
        full_ip = False

        if IPUtils.is_valid_ipv4(ip):  # ipv4
            IPUtils.parse_ipv4(ip)

            if ip.count('.') == 3 and not subnet_slash:
                full_ip = True

            elif ip.count('.') == 3 and subnet_slash or \
                    ip.count('.') == 2 and not subnet_slash:
                pass

            else:
                raise CerebrumError(("'%s' does not look like a valid subnet "
                                     "or ip-address.") % ip_id)

        elif IPv6Utils.is_valid_ipv6(ip_id):  # full ipv6
            full_ip = True
            ip = ip_id

        elif IPv6Subnet.IPv6Subnet.is_valid_subnet(ip_id):
            ip = ip_id

        else:
            try:  # Assume hostname
                self._arecord.clear()
                self._arecord.find_by_name(self.qualify_hostname(ip))
                self._ip_number.clear()
                self._ip_number.find(self._arecord.ip_number_id)
            except Errors.NotFoundError:
                raise CerebrumError("Could not find host %s" % ip)
            ip = self._ip_number.a_ip
        try:
            ipc = Find(self._db, None)
            subnet_ip = ipc._find_subnet(ip)
        except:
            subnet_ip = None
        return subnet_ip, full_ip and ip or None

    def parse_force(self, string):
        if string and not string[0] in ('Y', 'y', 'N', 'n'):
            raise CerebrumError("Force should be Y or N")
        if string and string[0] in ('Y', 'y'):
            return True
        return False

    def parse_hostname_repeat(self, name):
        """Handles multiple hostnames with the same prefix and a
        numeric suffix.  We have these variants:

        - pcubit#20 = start at the highest existing pcubit+1 and
          return the next 20 names.
        - pcubit#20-30 = return the names pcubit20 .. pcubit30

        Use multiple # to provide leading zeros.  We do not assert that the
        specified name does not exist (relevant for the #\d-\d syntax).
        """
        def find_last_startnum(prefix):
            ret = 0
            like_str = '%s%%%s' % (prefix, self._default_zone.postfix)
            re_num = re.compile(like_str.replace('%', '(\d+)'))
            for row in self._dns_owner.search(name_like=like_str):
                m = re_num.search(row['name'])
                if m:
                    if ret < int(m.group(1)):
                        ret = int(m.group(1))
            return ret

        name = name.lower()
        m = re.search(r'(.*?)(#+)(.*)', name)
        if not m:
            return [name]
        ret = []
        fill = str(len(m.group(2)))
        if not m.group(3):
            num = [1]
        else:
            try:
                num = [int(x) for x in m.group(3).split('-')]
            except ValueError, msg:
                raise CerebrumError("error parsing number: %s" % msg)
        if len(num) == 2:
            for n in range(num[0], num[1]+1):
                ret.append(("%s%0"+fill+"i") % (m.group(1), n))
        else:
            start = find_last_startnum(m.group(1)) + 1
            for n in range(start, start+num[0]):
                ret.append(("%s%0"+fill+"i") % (m.group(1), n))
        if not ret:
            raise CerebrumError("'%s' gives no IPs" % name)
        return ret

    def qualify_hostname(self, name):
        """Convert dns names to fully qualified by appending default domain"""
        if not name:
            raise CerebrumError('Subnet or IP can not be empty.')
        if not name[-1] == '.':
            postfix = self._default_zone.postfix
            if name.endswith(postfix[:-1]):
                return name+"."
            else:
                chk = postfix[postfix.find('.', 1):-1]
                if name.endswith(chk):
                    raise CerebrumError(
                        "The name ends with '%s' which may be ambigous.  "
                        "Use trailing dot" % chk)
                return name+postfix
        return name


class Find(object):
    def __init__(self, db, default_zone):
        self._db = db
        self._ip_number = IPNumber.IPNumber(db)
        self._ipv6_number = IPv6Number.IPv6Number(db)
        self._arecord = ARecord.ARecord(db)
        self._aaaarecord = AAAARecord.AAAARecord(db)
        self._dns_owner = DnsOwner.DnsOwner(db)
        self._mx_set = DnsOwner.MXSet(db)
        self._host = HostInfo.HostInfo(db)
        self._cname = CNameRecord.CNameRecord(db)
        self._dns_parser = DnsParser(db, default_zone)

    def find_dns_owners(self, dns_owner_id, only_type=True):
        """Return information about entries using this dns_owner.  If
        only_type=True, returns a list of owner_type.  Otherwise
        returns a list of (owner_type, owner_id) tuples"""

        ret = []
        arecord = ARecord.ARecord(self._db)
        for row in arecord.list_ext(dns_owner_id=dns_owner_id):
            ret.append((dns.A_RECORD, row['a_record_id']))
        aaaarecord = AAAARecord.AAAARecord(self._db)
        for row in aaaarecord.list_ext(dns_owner_id=dns_owner_id):
            ret.append((dns.AAAA_RECORD, row['aaaa_record_id']))
        hi = HostInfo.HostInfo(self._db)
        try:
            hi.find_by_dns_owner_id(dns_owner_id)
            ret.append((dns.HOST_INFO, hi.entity_id))
        except Errors.NotFoundError:
            pass
        dns_owner = DnsOwner.DnsOwner(self._db)
        for row in dns_owner.list_srv_records(owner_id=dns_owner_id):
            ret.append((dns.SRV_OWNER, row['service_owner_id']))
        for row in dns_owner.list_general_dns_records(
                dns_owner_id=dns_owner_id):
            ret.append((dns.GENERAL_DNS_RECORD, row['dns_owner_id']))
        cn = CNameRecord.CNameRecord(self._db)
        for row in cn.list_ext(cname_owner=dns_owner_id):
            ret.append((dns.CNAME_OWNER, row['cname_id']))
        if only_type:
            return [x[0] for x in ret]
        return ret

    def find_overrides(self, dns_owner_id, only_type=False):
        """
        """
        ret = []
        ip = IPNumber.IPNumber(self._db)
        for row in ip.list_override(dns_owner_id=dns_owner_id):
            ret.append((dns.IP_NUMBER, row['ip_number_id'],))
        ip = IPv6Number.IPv6Number(self._db)
        for row in ip.list_override(dns_owner_id=dns_owner_id):
            ret.append((dns.IPv6_NUMBER, row['ipv6_number_id'],))

        if only_type:
            return [x[0] for x in ret]
        return ret

    def find_referers(self, ip_number_id=None, dns_owner_id=None,
                      only_type=True, ip_type=dns.IP_NUMBER):
        """Return information about registrations that point to this
        ip-number/dns-owner. If only_type=True, returns a list of
        owner_type.  Otherwise returns a list of (owner_type,
        owner_id) tuples"""

        # We choose classes and record type depending on the ip_type
        # parameter. This is a bit dirty, but reduces the amount of
        # functions required.
        ip_class = IPNumber.IPNumber if (
            ip_type == dns.IP_NUMBER
        ) else IPv6Number.IPv6Number
        record_class = ARecord.ARecord if (
            ip_type == dns.IP_NUMBER
        ) else AAAARecord.AAAARecord
        record_type = dns.A_RECORD if (
            ip_type == dns.IP_NUMBER
        ) else dns.AAAA_RECORD

        ip_key = 'ip_number_id' if (
            ip_type == dns.IP_NUMBER
        ) else 'ipv6_number_id'
        record_key = 'a_record_id' if (
            ip_type == dns.IP_NUMBER
        ) else 'aaaa_record_id'

        # Not including entity-note
        assert not (ip_number_id and dns_owner_id)
        ret = []

        if ip_number_id and ip_type == dns.REV_IP_NUMBER:
            for ipn, key in [
                    (IPNumber.IPNumber(self._db), 'ip_number_id'),
                    (IPv6Number.IPv6Number(self._db), 'ipv6_number_id')]:
                for row in ipn.list_override(ip_number_id=ip_number_id):
                    ret.append((dns.REV_IP_NUMBER, row[key]))

            if only_type:
                return [x[0] for x in ret]
            return ret

        if ip_number_id:
            ipnumber = ip_class(self._db)
            for row in ipnumber.list_override(ip_number_id=ip_number_id):
                ret.append((dns.REV_IP_NUMBER, row[ip_key]))
            arecord = record_class(self._db)
            for row in arecord.list_ext(ip_number_id=ip_number_id):
                ret.append((record_type, row[record_key]))
            if only_type:
                return [x[0] for x in ret]
            return ret
        mx = DnsOwner.MXSet(self._db)
        for row in mx.list_mx_sets(target_id=dns_owner_id):
            ret.append((dns.MX_SET, row['mx_set_id']))
        dns_owner = DnsOwner.DnsOwner(self._db)
        for row in dns_owner.list_srv_records(target_owner_id=dns_owner_id):
            ret.append((dns.SRV_TARGET, row['service_owner_id']))
        cn = CNameRecord.CNameRecord(self._db)
        for row in cn.list_ext(target_owner=dns_owner_id):
            ret.append((dns.CNAME_TARGET, row['cname_id']))
        arecord = record_class(self._db)
        for row in arecord.list_ext(dns_owner_id=dns_owner_id):
            ret.append((record_type, row[record_key]))
        hi = HostInfo.HostInfo(self._db)
        for row in hi.list_ext(dns_owner_id=dns_owner_id):
            ret.append((dns.HOST_INFO, row['host_id'],))
        if only_type:
            return [x[0] for x in ret]
        return ret

    def find_target_by_parsing(self, host_id, target_type):
        """Find a target with given host_id of the specified
        target_type.  Legal target_types are IP_NUMBER and DNS_OWNER.
        Host_id may be given in a number of ways, one can lookup IP_NUMBER
        by both hostname (A record) and ip or id:ip_number_id etc.

        Returns dns_owner_id or ip_number_id depending on target_type.
        """
        # TODO: handle idtype:id syntax

        if not host_id:
            raise CerebrumError("Expected hostname/ip, found empty string")
        tmp = host_id.split(".")

        if host_id.count(':') > 2:
            # It is an IPv6-number
            self._ipv6_number.clear()
            try:
                self._ipv6_number.find_by_ip(host_id)
            except Errors.NotFoundError:
                raise CerebrumError("Could not find ip-number: %s" % host_id)
            if target_type == dns.IPv6_NUMBER:
                return self._ipv6_number.entity_id

            self._aaaarecord.clear()
            try:
                self._aaaarecord.find_by_ip(self._ipv6_number.entity_id)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "Could not find name for ip-number: %s" % host_id
                )
            except Errors.TooManyRowsError:
                raise CerebrumError(
                    "Not unique name for ip-number: %s" % host_id
                )
            return self._aaaarecord.dns_owner_id

        if tmp[-1].isdigit():
            # It is an IP-number
            self._ip_number.clear()
            try:
                self._ip_number.find_by_ip(host_id)
            except Errors.NotFoundError:
                raise CerebrumError("Could not find ip-number: %s" % host_id)
            if target_type == dns.IP_NUMBER:
                return self._ip_number.entity_id

            self._arecord.clear()
            try:
                self._arecord.find_by_ip(self._ip_number.entity_id)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "Could not find name for ip-number: %s" % host_id
                )
            except Errors.TooManyRowsError:
                raise CerebrumError(
                    "Not unique name for ip-number: %s" % host_id
                )
            return self._arecord.dns_owner_id

        failed = []
        if host_id[-1] != '.':
            self._dns_owner.clear()
            try:
                self._dns_owner.find_by_name(host_id+'.')
                host_id = host_id+'.'
            except Errors.NotFoundError:
                failed.append(host_id+'.')
        host_id = self._dns_parser.qualify_hostname(host_id)
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(host_id)
        except Errors.NotFoundError:
            failed.append(host_id)
            raise CerebrumError("'%s' does not exist" % "/".join(failed))

        if target_type == dns.DNS_OWNER:
            return self._dns_owner.entity_id
        self._arecord.clear()
        try:
            self._arecord.find_by_dns_owner_id(self._dns_owner.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError(
                "Could not find ip-number for name: %s" % host_id
            )
        except Errors.TooManyRowsError:
            raise CerebrumError("Not ip-number for name: %s" % host_id)
        return self._arecord.ip_number_id

    def find_mx_set(self, name):
        self._mx_set.clear()
        try:
            self._mx_set.find_by_name(name)
        except Errors.NotFoundError:
            raise CerebrumError("No mx-set with name %s" % name)
        return self._mx_set

    def find_target_type(self, owner_id, target_ip=None):
        """Find a target and its type by prefering hosts above
        a-records"""

        self._host.clear()
        try:
            self._host.find_by_dns_owner_id(owner_id)
            return self._host, self._host.entity_id
        except Errors.NotFoundError:
            pass

        self._cname.clear()
        try:
            self._cname.find_by_cname_owner_id(owner_id)
            return self._cname, self._cname.entity_id
        except Errors.NotFoundError:
            pass

        self._arecord.clear()
        try:
            if target_ip:
                raise NotImplementedError
            else:
                self._arecord.find_by_dns_owner_id(owner_id)
            return self._arecord, self._arecord.entity_id
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError:
            raise CerebrumError("Not unique a-record: %s" % owner_id)

    def find_free_ip(self, subnet, first=None, no_of_addrs=None, start=0):
        """Returns the first free IP on the subnet"""
        a_ip = self._find_available_ip(subnet, no_of_addrs, first or start)

        if not a_ip:
            raise CerebrumError("No available ip on that subnet")

        if first is not None:
            a_ip = [i for i in a_ip if i >= first]

        ipc = IPCalc if '.' in self._find_subnet(subnet) else IPv6Calc
        return [ipc.long_to_ip(t) for t in a_ip]

    def _find_subnet(self, subnet):
        """Translate the user-entered subnet to the key in
        self.subnets"""
        if not subnet:
            return None
        try:
            sub = Subnet.Subnet(self._db)
            sub.find(subnet)
        except SubnetError:
            sub = IPv6Subnet.IPv6Subnet(self._db)
            sub.find(subnet)
        return sub.subnet_ip

    def _find_available_ip(self, subnet, no_of_addrs=None, search_start=0):
        """Returns all ips that are not reserved or taken on the given
        subnet in ascending order."""
        try:
            sub = Subnet.Subnet(self._db)
            sub.find(subnet)
            ip_number = IPNumber.IPNumber(self._db)
            ip_key = 'ip_number_id'
            ipnr = lambda x: x['ipnr']
            start = sub.ip_min
        except SubnetError:
            sub = IPv6Subnet.IPv6Subnet(self._db)
            sub.find(subnet)
            ip_number = IPv6Number.IPv6Number(self._db)
            ip_key = 'ipv6_number_id'
            ipnr = lambda x: IPv6Calc.ip_to_long(x['aaaa_ip'])
            # We'll do this, since we don't want bofh to be stuck forever
            # trying to fetch all IPv6-addresses.
            # This is ugly, but it's not only-only.
            if no_of_addrs is None:
                no_of_addrs = 100
            # A special case for IPv6 subnets, is that we'll want to be able
            # to start allocating addresses a given place in the subnet,
            # without using the reserved-addresses-functionality.
            if search_start >= sub.ip_min:
                start = search_start
            else:
                start = (sub.ip_min +
                         cereconf.DEFAULT_IPv6_SUBNET_ALLOCATION_START +
                         search_start)
        try:
            taken = {}
            for row in ip_number.find_in_range(start, sub.ip_max):
                taken[long(ipnr(row))] = int(row[ip_key])

            stop = sub.ip_max - start + 1
            n = 0
            ret = []
            while n < stop:
                if no_of_addrs is not None and len(ret) == no_of_addrs:
                    break
                if (
                        long(start+n) not in taken and
                        n+start not in sub.reserved_adr
                ):
                    ret.append(n+start)
                n += 1
            return ret
        except SubnetError:
            # Unable to find subnet; therefore, no available ips to report
            return []

    def count_used_ips(self, subnet):
        """Returns the number of used ips on the given subnet.

        Returns a long.

        """

        if '.' in subnet:
            ip_number = IPNumber.IPNumber(self._db)
            sub = Subnet.Subnet(self._db)
        else:
            ip_number = IPv6Number.IPv6Number(self._db)
            sub = IPv6Subnet.IPv6Subnet(self._db)
        sub.find(subnet)
        return ip_number.count_in_range(sub.ip_min, sub.ip_max)

    def find_used_ips(self, subnet):
        """Returns all ips that are taken on the given subnet in
        ascending order.

        Addresses returned are as xxx.xxx.xxx.xxx, not longs.

        """
        if '.' in subnet:
            ip_number = IPNumber.IPNumber(self._db)
            sub = Subnet.Subnet(self._db)
            ip_key = 'a_ip'
        else:
            ip_number = IPv6Number.IPv6Number(self._db)
            sub = IPv6Subnet.IPv6Subnet(self._db)
            ip_key = 'aaaa_ip'
        ip_number.clear()
        sub.clear()
        sub.find(subnet)
        ret = []
        for row in ip_number.find_in_range(sub.ip_min, sub.ip_max):
            ret.append(row[ip_key])
        return ret

    def find_entity_id_of_dns_target(self, target):
        """Return entity_id for given 'DNS-thing'.

        Currently only able to handle subnets and IPs, but can be
        extended further if teh need arises.

        """
        if '/' in target:
            # Subnet.find can search both by subnet ID (x/y) and IP; opt for
            # IP in all cases for simplicity's sake.
            sub = Subnet.Subnet(self._db)
            sub.find(target.split('/')[0])
            return sub.entity_id
        else:
            # If not, must be an IP; other stuff will cause failures (for now)
            return self.find_ip(target)

    def find_ip(self, a_ip):
        self._ip_number.clear()
        try:
            self._ip_number.find_by_ip(a_ip)
            return self._ip_number.entity_id
        except Errors.NotFoundError:
            return None

    def find_a_record(self, host_name, ip=None):
        owner_id = self.find_target_by_parsing(host_name, dns.DNS_OWNER)

        # Check for IPv6 / IPv4
        if ip and ip.count(':') > 1:
            ar = AAAARecord.AAAARecord(self._db)
            ip_type = dns.IPv6_NUMBER
            rt = 'AAAA-record'
        elif host_name.count(':') > 1:
            # No IP specified.
            # See if host_name is an IPv6 addr and select an IPv6-type if it is
            ar = AAAARecord.AAAARecord(self._db)
            ip_type = dns.IPv6_NUMBER
            rt = 'AAAA-record'
        else:
            ar = ARecord.ARecord(self._db)
            ip_type = dns.IP_NUMBER
            rt = 'A-record'
        if ip:
            a_ip = ip
            ip = self.find_target_by_parsing(
                ip, ip_type)
            try:
                ar.find_by_owner_and_ip(ip, owner_id)
            except Errors.NotFoundError:
                raise CerebrumError(
                    "No %s with name=%s and ip=%s" % (rt, host_name, a_ip))
        else:
            try:
                ar.find_by_dns_owner_id(owner_id)
            except Errors.NotFoundError:
                raise CerebrumError("No %s with name=%s" % (rt, host_name))
            except Errors.TooManyRowsError:
                raise CerebrumError("Multiple %s with name=%s" %
                                    (rt, host_name))
        return ar.entity_id
