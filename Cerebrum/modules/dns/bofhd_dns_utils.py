# -*- coding: iso-8859-1 -*-

import re
import struct
import socket
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.dns.HostInfo import HostInfo
#from Cerebrum.modules.dns. import 
#from Cerebrum.modules.dns import EntityNote
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import Helper
from Cerebrum.modules import dns
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.modules.bofhd.errors import CerebrumError

class IPUtils(object):
    """Methods for playing with IP-numbers"""
    
    def __init__(self, server):
        super(IPUtils, self).__init__(server)
        # http://dager.uio.no/nett-doc/vlanibruk.txt
        self._parse_netdef("/cerebrum/etc/cerebrum/vlanibruk.txt")
        self.db = server.db

    def netmask_to_intrep(netmask):
        return pow(2L, 32) - pow(2L, 32-netmask)
    netmask_to_intrep = staticmethod(netmask_to_intrep)

    def _parse_netdef(self, fname):
        f = file(fname)
        ip_re = re.compile(r'\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+')
        self.subnets = {}
        for line in f.readlines():
            match = ip_re.search(line)
            if match:
                net, mask = match.group(1), int(match.group(2))
                self.subnets[net] = (mask, ) + \
                                    self._ip_range_by_netmask(net, mask)

    def _ip_range_by_netmask(self, subnet, netmask):
        tmp = struct.unpack('!L', socket.inet_aton(subnet))[0]
        start = tmp & IPUtils.netmask_to_intrep(netmask)
        stop  =  tmp | (pow(2L, 32) - 1 - IPUtils.netmask_to_intrep(netmask))
        return start, stop

    def _find_subnet(self, subnet):
        """Translate the user-entered subnet to the key in
        self.subnets"""
        if len(subnet.split(".")) == 3:
            subnet += ".0"
        numeric_ip = struct.unpack('!L', socket.inet_aton(subnet))[0]
        for net, (mask, start, stop) in self.subnets.items():
            if numeric_ip >= start and numeric_ip <= stop:
                return net
        raise Helper.DNSError, "%s is not in any known subnet" % subnet

    def _find_available_ip(self, subnet):
        """Returns all ips that are not reserved or taken on the given
        subnet in ascending order."""

        subnet = self._find_subnet(subnet)
        mask, start, stop = self.subnets[subnet]
        #start, stop = self._ip_range_by_netmask(subnet, mask)
        
        #print "start: ", socket.inet_ntoa(struct.pack('!L', start))
        #print "stop: ", socket.inet_ntoa(struct.pack('!L', stop))

        if mask == 23:
            reserved = ([0] +            # (Possible) broadcast address
                        range(1,9+1) +     # Reserved for routers (and servers)
                        range(101,120+1) + # Reserved for nett-drift
                        range(255,257+1)+  # $subnet.255, $subnet+1.0 and $subnet+1.1
                        [511])             # $subnet+1.255
        else:
            # TODO: Hvilke nummer i øvrige nettmasker skal man ligge unna?
            reserved = []
        self._ip_number.clear()
        taken = {}
        for row in self._ip_number.find_in_range(start, stop):
            taken[long(row['ipnr'])] = int(row['ip_number_id'])
        ret = []
        for n in range(0, (stop-start)+1):
            if not taken.has_key(long(start+n)) and n not in reserved:
                ret.append(n+start)
        return ret

class DnsParser(object):
    """Map user-entered data to dnss datatypes/database-ids"""
    # Must be used as a mix-in for DnsBofhdUtils, should not be
    # instantiated directly

    def parse_subnet_or_ip(self, subnet_or_ip):
        """Parse subnet_or_ip as a subnet or an IP-number.

        Returns the subnet, a_ip and ip_ref.  If IP is not in
        database, ip_ref is None.  If the explicit IP is on an unknown
        subnet, subnet is None"""

        if len(subnet_or_ip.split(".")) < 3:
            subnet_or_ip = '129.240.%s' % subnet_or_ip
        if len(subnet_or_ip.split(".")) == 5:  # Explicit IP
            a_ip = subnet_or_ip
            self._ip_number.clear()
            try:
                self._ip_number.find_by_ip(a_ip)
                ip_ref = self._ip_number.ip_number_id
            except Errors.NotFoundError:
                ip_ref = None
            try:
                return self._find_subnet(subnet_or_ip[:-1]), a_ip[:-1], ip_ref
            except Helper.DNSError:
                return None, a_ip[:-1], ip_ref
        else:
            return self._find_subnet(subnet_or_ip), None, None

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

    def filter_zone_suffix(self, name):
        if name.endswith(dns.ZONE):
            name=name[:-(len(dns.ZONE)+1)]
        elif name.endswith(dns.ZONE+"."):
            name=name[:-(len(dns.ZONE)+2)]
        return name

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

        self._dns_owner.clear()
        try:
            host_id = self.filter_zone_suffix(host_id)
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
        self._mx_set.find_by_name(name)
        return self._mx_set.mx_set_id

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
        a_ip = self._find_available_ip(subnet)
        if not a_ip:
            raise ValueError, "No available ip on that subnet"
        return [socket.inet_ntoa(struct.pack('!L', t)) for t in a_ip]

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
        ar = ARecord.ARecord(self.db)
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

class DnsBofhdUtils(IPUtils, DnsParser):

    # A number of utility methods used by
    # bofhd_dns_cmds.BofhdExtension.

    # TODO: We should try to put most of the business-logic in this
    # class and not BofhdExtension.  That would make it easier for
    # non-jbofh clients to communicate with dns.  This is a long-term
    # goal, however, and it has not been determined how to approach
    # the problem.
    

    def __init__(self, server):
        super(DnsBofhdUtils, self).__init__(server)
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        # TBD: This pre-allocating may interfere with multi-threaded bofhd
        self._arecord = ARecord.ARecord(self.db)
        self._host = HostInfo.HostInfo(self.db)
        self._dns_owner = DnsOwner.DnsOwner(self.db)
        self._ip_number = IPNumber.IPNumber(self.db)
        self._cname = CNameRecord.CNameRecord(self.db)
        self.mr_helper = Helper.Helper(self.db)
        self._mx_set = DnsOwner.MXSet(self.db)



    def ip_rename(self, name_type, old_id, new_id):
        """Performs an ip-rename by directly updating dns_owner or
        ip_number.  new_id cannot already exist."""

        if name_type == dns.IP_NUMBER:
            old_ref = self.find_target_by_parsing(old_id, dns.IP_NUMBER)
            self._ip_number.clear()
            try:
                self._ip_number.find_by_ip(new_id)
                raise CerebrumError("New IP in use")
            except Errors.NotFoundError:
                pass
            self._ip_number.clear()
            self._ip_number.find(old_ref)
            self._ip_number.a_ip = new_id
            self._ip_number.write_db()
        else:
            old_ref = self.find_target_by_parsing(old_id, dns.DNS_OWNER)
            # Check if the name is in use, or is illegal
            self.mr_helper.dns_reg_owner_ok(new_id, dns.CNAME_OWNER)
            self._dns_owner.clear()
            self._dns_owner.find(old_ref)
            self._dns_owner.name = new_id
            self._dns_owner.write_db()

    def ip_free(self, name_type, id, force):
        if name_type == dns.IP_NUMBER:
            ip_id = self.find_target_by_parsing(id, dns.IP_NUMBER)
            self._ip_number.clear()
            self._ip_number.find(ip_id)
            try:
                self._ip_number.delete()
            except Database.DatabaseError, m:
                raise CerebrumError, "Database violation: %s" % m
        else:
            owner_id = self.find_target_by_parsing(
                id, dns.DNS_OWNER)

            refs = self.mr_helper.get_referers(dns_owner_id=owner_id)
            if not force and (
                refs.count(dns.A_RECORD) > 1 or
                dns.GENERAL_TTL_RECORD in refs):
                raise CerebrumError(
                    "Multiple records would be deleted, must force")
            try:
                self.mr_helper.full_remove_dns_owner(owner_id)
            except Database.DatabaseError, m:
                raise CerebrumError, "Database violation: %s" % m

            #raise NotImplementedError

    #
    # host, cname, entity-note
    #

    def alloc_host(self, name, hinfo, mx_set, comment, contact):
        dns_owner_ref, same_type = self.mr_helper.dns_reg_owner_ok(
            name, dns.HOST_INFO)

        self._dns_owner.clear()
        self._dns_owner.find(dns_owner_ref)
        self._dns_owner.mx_set_id = mx_set
        self._dns_owner.write_db()
        
        self._host.clear()
        self._host.populate(dns_owner_ref, int(hinfo))
        self._host.write_db()
        if comment:
            self._host.add_entity_note(self.const.note_type_comment, comment)
        if contact:
            self._host.add_entity_note(self.const.note_type_contact, contact)

    def alloc_cname(self, cname_name, target_name, force):
        dns_owner_ref, same_type = self.mr_helper.dns_reg_owner_ok(
            cname_name, dns.CNAME_OWNER)
        dns_owner_ref = self.alloc_dns_owner(cname_name)
        try:
            target_ref = self.find_target_by_parsing(
                target_name, dns.DNS_OWNER)
        except CerebrumError:
            if not force:
                raise CerebrumError, "Target does not exist, must force"
            target_ref = self.alloc_dns_owner(target_name)
        
        self._cname.clear()
        self._cname.populate(dns_owner_ref, target_ref)
        self._cname.write_db()
        return self._cname.entity_id

    def alter_entity_note(self, owner_id, note_type, dta):
        obj_ref, obj_id = self.find_target_type(owner_id)
        if not dta:
            obj_ref.delete_entity_note(note_type)
            return "removed"

        try:
            obj_ref.get_entity_note(note_type)
        except Errors.NotFoundError:
            obj_ref.add_entity_note(note_type, dta)
            return "added"
        obj_ref.update_entity_note(note_type, dta)
        return "updated"

    #
    # IP-numbers
    #

    def alloc_ip(self, a_ip, force=False):
        """Allocates an IP-number.  force must be true to use IPs in a
        reserved range"""

        self._ip_number.clear()
        if not force:
            # TODO: Check if IP is in reserved range
            pass
        self._ip_number.populate(a_ip)
        self._ip_number.write_db()
        return self._ip_number.ip_number_id

    #
    # dns-owners, general_ttl_records and mx-sets, srv_records
    #
    
    def alloc_dns_owner(self, name, mx_set=None):
        self._dns_owner.clear()
        self._dns_owner.populate(name, mx_set_id=mx_set)
        self._dns_owner.write_db()
        return self._dns_owner.entity_id

    def alter_ttl_record(self, owner_id, ttl_type, dta, ttl=None):
        self._dns_owner.clear()
        self._dns_owner.find(owner_id)
        if not dta:
            self._dns_owner.delete_ttl_record(self._dns_owner.entity_id, ttl_type)
            return "removed"
        try:
            self._dns_owner.get_ttl_record(self._dns_owner.entity_id, ttl_type)
        except Errors.NotFoundError:
            self._dns_owner.add_ttl_record(
                self._dns_owner.entity_id, ttl_type, ttl, dta)
            return "added"
        self._dns_owner.update_ttl_record(
            self._dns_owner.entity_id, ttl_type, ttl, dta)
        return "updated"

    def alter_srv_record(self, operation, service_name, pri,
                         weight, port, target, ttl=None):
        # TBD: should we assert that target is of a given type?
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(service_name)
            #TBD: raise error if operation==add depending on type of existing data?
            if operation == 'del':
                self._dns_owner.delete_srv_record(
                    self._dns_owner.entity_id, pri, weight, port,
                    target)
        except Errors.NotFoundError:
            if operation == 'add':
                self.alloc_dns_owner(self, service_name)

        if operation == 'add':
            self._dns_owner.add_srv_record(
                self._dns_owner.entity_id, pri, weight, port, ttl,
                target)

    def mx_set_add(self, mx_set, priority, target_id, ttl=None):
        if ttl:
            ttl = int(ttl)
        else:
            ttl = None
        priority = int(priority)
        self._mx_set.clear()
        try:
            self._mx_set.find_by_name(mx_set)
        except Errors.NotFoundError:
            self._mx_set.populate(mx_set)
            self._mx_set.write_db()
        self._mx_set.add_mx_set_member(ttl, priority, target_id)

    def mx_set_del(self, mx_set, target_id):
        self._mx_set.clear()
        try:
            self._mx_set.find_by_name(mx_set)
        except Errors.NotFoundError:
            raise CerebrumError, "Cannot find mx-set %s" % mx_set
        self._mx_set.del_mx_set_member(target_id)

        # If set is empty, remove it
        if not self._mx_set.list_mx_sets(mx_set_id=self._mx_set.mx_set_id):
            self._mx_set.delete()


    def set_ttl(self, owner_id, ttl):
        """Set TTL entries for this dns_owner"""

        # TODO: Currently we do this by updating the TTL in all
        # tables.  It has been decided to move ttl-information into
        # dns_owner.  However, we will not do this until after we have
        # gone into production to avoid a huge diff when comparing
        # autogenerated zone files to the original ones.
        
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        arecord = ARecord.ARecord(self.db)
        for row in arecord.list_ext(dns_owner_id=owner_id):
            arecord.clear()
            arecord.find(row['a_record_id'])
            arecord.ttl=ttl
            arecord.write_db()

        host = HostInfo.HostInfo(self.db)
        try:
            host.find_by_dns_owner_id(owner_id)
        except Errors.NotFoundError:
            pass
        else:
            host.ttl = ttl
            host.write_db()

        for row in dns_owner.list_ttl_records(dns_owner_id=owner_id):
            dns_owner.update_ttl_record(owner_id, row['field_type'],
                                        ttl, row['data'])

        mx_set = DnsOwner.MXSet(self.db)
        for row in mx_set.list_mx_sets(target_id=owner_id):
            mx_set.clear()
            mx_set.find(row['mx_set_id'])
            mx_set.update_mx_set_member(ttl, row['pri'], row['target_id'])
        cname = CNameRecord.CNameRecord(self.db)
        for row in cname.list_ext(cname_owner=owner_id):
            cname.clear()
            cname.find(row['cname_id'])
            cname.ttl = ttl
            cname.write_db()

        for row in dns_owner.list_srv_records(owner_id=owner_id):
            dns_owner.update_srv_record(owner_id, row['pri'], row['weight'],
                                        row['port'], ttl,
                                        row['target_owner_id'])


    #
    # A-Records, reverse-map
    #

    def _alloc_arecord(self, owner_id, ip_id):
        self._arecord.clear()
        self._arecord.populate(owner_id, ip_id)
        self._arecord.write_db()
        return self._arecord.entity_id

    def alloc_arecord(self, host_name, subnet, ip, force):
        # Check for existing record with same name
        dns_owner_ref, same_type = self.mr_helper.dns_reg_owner_ok(
            host_name, dns.A_RECORD)
        if dns_owner_ref and same_type and not force:
            raise CerebrumError, "name already in use, must force"

        # Check or get free IP
        if not ip:
            ip = self.find_free_ip(subnet)[0]
            ip_ref = None
        else:
            ip_ref = self.find_ip(ip)
            if ip_ref and not force:
                raise CerebrumError, "IP already in use, must force"

        # Register dns_owner and/or ip_number
        if not ip_ref:
            ip_ref = self.alloc_ip(ip, force=force)
        if not dns_owner_ref:
            dns_owner_ref = self.alloc_dns_owner(host_name)
        self._alloc_arecord(dns_owner_ref, ip_ref)
        return ip

    def remove_arecord(self, a_record_id):
        self.mr_helper.remove_arecord(a_record_id)

    def register_revmap_override(self, ip_host_id, dest_host, force):
        # TODO: clear up empty dest_host
        self._ip_number.clear()
        self._ip_number.find(ip_host_id)
        if not dest_host:
            self.mr_helper.update_reverse_override(ip_host_id)
            return "deleted"
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(dest_host)
        except Errors.NotFoundError:
            if not force:
                raise CerebrumError, "Target does not exist, must force"
            self._dns_owner.populate(dest_host)
            self._dns_owner.write_db()
        if self._ip_number.list_override(
            ip_number_id=self._ip_number.ip_number_id):
            self.mr_helper.update_reverse_override(
                self._ip_number.ip_number_id, self._dns_owner.entity_id)
            return "updated"
        else:
            self._ip_number.add_reverse_override(
                self._ip_number.ip_number_id, self._dns_owner.entity_id)
            return "added"



if __name__ == '__main__':
    class foo(object):
        pass

    tmp = foo()
    tmp.db = Factory.get('Database')()
    tmp.logger =Factory.get_logger('console')
    mu = DnsBofhdUtils(tmp)
    #print mu.get_free_ip("129.240.186")
    for n in ('129.240.186', '129.240.2.3',
              '129.240.254.148', '129.240.254.163'):
        print "%s->%s" % (n, mu._find_subnet(n))
    tmp.db.commit()

# arch-tag: f085073a-5cde-4aea-8c92-295fd81dc8b2
