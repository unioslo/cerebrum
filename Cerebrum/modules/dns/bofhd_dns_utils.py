# -*- coding: utf-8 -*-

import cereconf

import re
from Cerebrum.Utils import Factory
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import AAAARecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import IPv6Number
from Cerebrum.modules.dns.IPUtils import IPCalc, IPUtils
from Cerebrum.modules.dns.IPv6Utils import IPv6Calc, IPv6Utils
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import IntegrityHelper
from Cerebrum.modules.dns import Utils
from Cerebrum.modules.dns.Errors import DNSError
from Cerebrum.modules import dns
from Cerebrum import Errors
from Cerebrum import database
from Cerebrum.modules.bofhd.errors import CerebrumError

class DnsBofhdUtils(object):
    # A number of utility methods used by
    # bofhd_dns_cmds.BofhdExtension.

    # TODO: We should try to put most of the business-logic in this
    # class and not BofhdExtension.  That would make it easier for
    # non-jbofh clients to communicate with dns.  This is a long-term
    # goal, however, and it has not been determined how to approach
    # the problem.

    def __init__(self, db, logger, default_zone):
        self.logger = logger
        self.db = db
        self.const = Factory.get('Constants')(self.db)
        # TBD: This pre-allocating may interfere with multi-threaded bofhd
        self._arecord = ARecord.ARecord(self.db)
        self._aaaarecord = AAAARecord.AAAARecord(self.db)
        self._host = HostInfo.HostInfo(self.db)
        self._dns_owner = DnsOwner.DnsOwner(self.db)
        self._ip_number = IPNumber.IPNumber(self.db)
        self._ipv6_number = IPv6Number.IPv6Number(self.db)
        self._cname = CNameRecord.CNameRecord(self.db)
        self._validator = IntegrityHelper.Validator(self.db, default_zone)
        self._update_helper = IntegrityHelper.Updater(self.db)
        self._mx_set = DnsOwner.MXSet(self.db)
        self.default_zone = default_zone
        self._find = Utils.Find(self.db, default_zone)
        self._parser = Utils.DnsParser(self.db, default_zone)

    def ip_rename(self, name_type, old_id, new_id):
        """Performs an ip-rename by directly updating dns_owner or
        ip_number.  new_id cannot already exist."""

        if name_type == dns.IP_NUMBER:
            old_ref = self._find.find_target_by_parsing(old_id, dns.IP_NUMBER)
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
        elif name_type == dns.IPv6_NUMBER:
            old_ref = self._find.find_target_by_parsing(old_id, dns.IPv6_NUMBER)
            self._ipv6_number.clear()
            try:
                self._ipv6_number.find_by_ip(new_id)
                raise CerebrumError("New IP in use")
            except Errors.NotFoundError:
                pass
            self._ipv6_number.clear()
            self._ipv6_number.find(old_ref)
            self._ipv6_number.aaaa_ip = new_id
            self._ipv6_number.write_db()
        else:  # Assume hostname
            old_ref = self._find.find_target_by_parsing(old_id, dns.DNS_OWNER)
            new_id = self._parser.qualify_hostname(new_id)
            # Check if the name is in use, or is illegal
            self._validator.dns_reg_owner_ok(new_id, dns.CNAME_OWNER)
            self._dns_owner.clear()
            self._dns_owner.find(old_ref)
            self._dns_owner.name = new_id
            self._dns_owner.zone = self.get_zone_from_name(new_id)
            self._dns_owner.write_db()

    def ip_free(self, name_type, id, force):
        if name_type == dns.DNS_OWNER:
            owner_id = self._find.find_target_by_parsing(
                id, dns.DNS_OWNER)

            # krev force hvis maskinen har cname.  Returner info om slettet cname.
            refs = self._find.find_dns_owners(dns_owner_id=owner_id)
            if not force and (
                refs.count(dns.AAAA_RECORD) > 1 or
                refs.count(dns.A_RECORD) > 1 or
                dns.GENERAL_DNS_RECORD in refs):
                raise CerebrumError(
                    "Multiple records would be deleted, must force (y)")
            try:
                self._update_helper.full_remove_dns_owner(owner_id)
            except database.DatabaseError, m:
                raise CerebrumError, "Database violation: %s" % m

    #
    # host, cname, entity-note
    #

    def alloc_host(self, name, hinfo, mx_set, comment, contact,
                   allow_underscores=False):
        name = self._parser.qualify_hostname(name)
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            name, dns.HOST_INFO, allow_underscores)

        self._dns_owner.clear()
        self._dns_owner.find(dns_owner_ref)
        self._dns_owner.mx_set_id = mx_set

        self._host.clear()
        self._host.populate(dns_owner_ref, hinfo)
        self._host.write_db()
        if comment:
            self._dns_owner.populate_trait(self.const.trait_dns_comment,
                                           strval=comment)
        if contact:
            self._dns_owner.populate_trait(self.const.trait_dns_contact,
                                           strval=contact)
        self._dns_owner.write_db()

    def alloc_cname(self, cname_name, target_name, force):
        cname_name = self._parser.qualify_hostname(cname_name)
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            cname_name, dns.CNAME_OWNER)
        dns_owner_ref = self.alloc_dns_owner(cname_name, warn_other=True, force=force)
        try:
            target_ref = self._find.find_target_by_parsing(
                target_name, dns.DNS_OWNER)
        except CerebrumError:
            if not force:
                raise CerebrumError, "Target does not exist, must force (y)"
            target_ref = self.alloc_dns_owner(target_name)
        self._cname.clear()
        self._cname.populate(dns_owner_ref, target_ref)
        self._cname.write_db()
        return self._cname.entity_id

    def alter_entity_note(self, owner_id, trait, dta):
        dta = dta.strip()
        if trait == self.const.trait_dns_contact:
            mail_ok_re = re.compile(
                cereconf.DNS_EMAIL_REGEXP)
            if dta and not mail_ok_re.match(dta):
                raise DNSError("'%s' does not look like an e-mail address" % dta)
        self._dns_owner.clear()
        self._dns_owner.find(owner_id)
        if not dta:
            try:
                self._dns_owner.delete_trait(trait)
            except Errors.NotFoundError: # Already deleted, noop
                pass
            return "removed"
        if self._dns_owner.populate_trait(trait, strval=dta) == 'INSERT':
            action = "added"
        else:
            action = 'updated'
        self._dns_owner.write_db()
        return action

    #
    # IP-numbers
    #
    def get_relevant_ips(self, subnet_or_ip, force=False, no_of_addrs=None):
        """
        Returns a list of available IPs. If a subnet is given as input,
        the list consists of avaiable IPs on the subnet. If a specific IP is
        given as input, the list will only contain that IP.

        :param subnet_or_ip: An IPv4/IPv6 subnet or IP-address
        :type  subnet_or_ip: str
        :param force: Indicates if the method should attempt to force the
                      operation, even if there is no record that the IP given
                      as input belongs to any subnet records.
        :type  force: boolean
        :param no_of_addrs: The max number of ips to be returned.
        :type  no_of_addrs: int

        :returns: A list of available IPs found, or a list containing only
                  the specified IP given to the method in subnet_or_ip, if
                  it is evaluated to a full IP.
        :rtype:   list
        """
        subnet, ip = self._parser.parse_subnet_or_ip(subnet_or_ip)
        if subnet is None and not force:
            raise CerebrumError("Unknown subnet. Must force")

        elif subnet is None and ip is None:
            raise CerebrumError("Please specify a valid subnet or IP-address.")

        elif subnet is not None and ip is None:

            first = subnet_or_ip.split('/')[0]

            if IPUtils.is_valid_ipv4(first):
                first = IPCalc.ip_to_long(first)

            elif IPv6Utils.is_valid_ipv6(first):
                first = None

            free_ip_numbers = self._find.find_free_ip(subnet, first=first,
                                                      no_of_addrs=no_of_addrs)
        else:
            free_ip_numbers = [ip]

        return free_ip_numbers

    def alloc_ip(self, ip, force=False):
        if ip.count(':') > 2:
            ipn = self._ipv6_number
        else:
            ipn = self._ip_number

        new = False
        ipn.clear()
        try:
            ipn.find_by_ip(ip)
        except Errors.NotFoundError:
            new = True
            ipn.clear()
            ipn.populate(ip)
            ipn.write_db()

        if not force and not new:
            raise CerebrumError, 'IP already in use, must force (y)'
        return ipn.entity_id


    #
    # dns-owners, general_dns_records and mx-sets, srv_records
    #
    def get_zone_from_name(self, name):
        """Try to guess a zone from a name. Returns a DnsZone Constant
        object."""
        def _get_reverse_order(lst):
            """Return index of sorted zones"""
            # We must sort the zones to assert that trofast.uio.no
            # does not end up in the uio.no zone.  This is acheived by
            # spelling the zone postfix backwards and sorting the
            # resulting list backwards
            lst = [str(x.postfix)[::-1] for x in lst]
            t = range(len(lst))
            t.sort(lambda a, b: cmp(lst[b], lst[a]))
            return t
        zone = None
        zones = self.const.fetch_constants(self.const.DnsZone)
        for n in _get_reverse_order(zones):
            z = zones[n]
            if z.postfix and name.endswith(z.postfix):
                zone = z
                break
        if not zone:
            zone = self.const.other_zone
        return zone

    def alloc_dns_owner(self, name, mx_set=None, warn_other=False, force=False):
        """If warn_other=True, force must be True to place the new
        name in the other zone.  This is meant to catch attempts to
        for instance register CNAMEs in zones that we don't populate.
        """
        zone = self.get_zone_from_name(name)
        if zone == self.const.other_zone and warn_other and not force:
            raise CerebrumError, "'%s' would end up in the 'other' zone, must force (y)" % name
        self._dns_owner.clear()
        self._dns_owner.populate(zone, name, mx_set_id=mx_set)
        self._dns_owner.write_db()
        return self._dns_owner.entity_id

    def alter_general_dns_record(self, owner_id, ttl_type, dta, ttl=None):
        self._dns_owner.clear()
        self._dns_owner.find(owner_id)
        if not dta:
            self._dns_owner.delete_general_dns_record(self._dns_owner.entity_id, ttl_type)
            return "removed"
        try:
            self._dns_owner.get_general_dns_record(self._dns_owner.entity_id, ttl_type)
        except Errors.NotFoundError:
            self._dns_owner.add_general_dns_record(
                self._dns_owner.entity_id, ttl_type, ttl, dta)
            return "added"
        self._dns_owner.update_general_dns_record(
            self._dns_owner.entity_id, ttl_type, ttl, dta)
        return "updated"


    def alter_srv_record(self, operation, service_name, pri,
                         weight, port, target, ttl=None, force=False):
        service_name = self._parser.qualify_hostname(service_name)
        if operation != 'del':
            dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
                service_name, dns.SRV_OWNER)
        # TBD: should we assert that target is of a given type?
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(service_name)
            #TBD: raise error if operation==add depending on type of existing data?
            if operation == 'del':
                # Make sure it exists first, otherwise we say we
                # delete things that aren't there
                if self._dns_owner.list_srv_records(owner_id=self._dns_owner.entity_id,
                                                    target_owner_id=target, pri=pri,
                                                    weight=weight, port=port):
                    self._dns_owner.delete_srv_record(
                        self._dns_owner.entity_id, pri, weight, port, target)
                else:
                    raise CerebrumError("No service with given parameters found")
        except Errors.NotFoundError:
            if operation == 'add':
                self.alloc_dns_owner(service_name, warn_other=True, force=force)
            if operation == 'del':
                raise CerebrumError("No service '%s' found" % service_name)

        if operation == 'add':
            self._dns_owner.add_srv_record(
                self._dns_owner.entity_id, pri, weight, port, ttl,
                target)


    def mx_set_add(self, mx_set, priority, target_id, ttl=None):
        self._validator.legal_mx_target(target_id)
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

    def mx_set_set(self, owner_id, mx_set):
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)
        self._validator.dns_reg_owner_ok(dns_owner.name, dns.MX_SET)
        if mx_set == '':
            dns_owner.mx_set_id = None
        else:
            dns_owner.mx_set_id = self._find.find_mx_set(mx_set).mx_set_id
        dns_owner.write_db()


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

        aaaarecord = AAAARecord.AAAARecord(self.db)
        for row in aaaarecord.list_ext(dns_owner_id=owner_id):
            aaaarecord.clear()
            aaaarecord.find(row['aaaa_record_id'])
            aaaarecord.ttl=ttl
            aaaarecord.write_db()

        host = HostInfo.HostInfo(self.db)
        try:
            host.find_by_dns_owner_id(owner_id)
        except Errors.NotFoundError:
            pass
        else:
            host.ttl = ttl
            host.write_db()

        for row in dns_owner.list_general_dns_records(dns_owner_id=owner_id):
            dns_owner.update_general_dns_record(owner_id, row['field_type'],
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
            dns_owner.update_srv_record_ttl(owner_id, ttl)


    def get_ttl(self, owner_id):
        """Retrieve TTL ('Time to Live') setting for the records
        associated with gievn DNS-owner.

        """
        # Caveat: if TTL is set for one of the host's A*-records, it is
        # set for the host in general. If no A*-record exists, we don't
        # acknowledge any other TTL than "default"
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        # This adaption to A- and AAAA-records is very ugly, but it honours
        # "The Old Way" of getting the TTL for a host.
        ar = ARecord.ARecord(self.db)
        ar.clear()
        for r in ar.list_ext(dns_owner_id=owner_id):
            ar.find(r['a_record_id'])
            return ar.ttl
        ar = AAAARecord.AAAARecord(self.db)
        ar.clear()
        for r in ar.list_ext(dns_owner_id=owner_id):
            ar.find(r['aaaa_record_id'])
            return ar.ttl
        return None


    #
    # A-Records, reverse-map
    #

    def _alloc_arecord(self, owner_id, ip_id):
        old_a_records = self._arecord.list_ext(ip_number_id=ip_id)
        self._arecord.clear()
        self._arecord.populate(owner_id, ip_id)
        self._arecord.write_db()

        # If we now have two A-records for the same IP, register an
        # override for the previous ip.
        if len(old_a_records) == 1:
            if len(self._ip_number.list_override(ip_number_id=ip_id,
                                                 dns_owner_id=old_a_records[0]['dns_owner_id'])) < 1:
                self._ip_number.add_reverse_override(
                    ip_id, old_a_records[0]['dns_owner_id'])
        return self._arecord.entity_id

    def alloc_arecord(self, host_name, subnet, ip, force,
                      allow_underscores=False):
        host_name = self._parser.qualify_hostname(host_name)
        # Check for existing record with same name
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            host_name, dns.A_RECORD, allow_underscores)

        # Check to see if this has been added before
        try:
            self._ip_number.clear()
            self._ip_number.find_by_ip(ip)
            ip_i = self._ip_number.entity_id
        except Errors.NotFoundError:
            ip_i = -1
        try:
            self._arecord.clear()
            self._arecord.find_by_owner_and_ip(ip_i, dns_owner_ref)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "host already has this A-record!"

        if dns_owner_ref and same_type and not force:
            owner_types = self._find.find_dns_owners(dns_owner_ref)
            if dns.A_RECORD in owner_types:
                raise CerebrumError, "name already in use, must force (y)"

        # Check or get free IP
        if not ip:
            ip = self._find.find_free_ip(subnet)[0]
            ip_ref = None
        else:
            ip_ref = self._find.find_ip(ip)
            if ip_ref and not force:
                raise CerebrumError, "IP already in use or reserved, must force (y)"
            # Catch Utils.Find.find_free_ip()s CerebrumError in case there
            # are no free IPs. You must still force to register the a_record.
            new_ips = []
            try:
                new_ips = self._find.find_free_ip(subnet)
            except CerebrumError:
                # No IPs available
                pass
            if (subnet and ip not in new_ips) and not force:
                raise CerebrumError, "IP appears to be reserved, must force (y)"

        # Register dns_owner and/or ip_number
        if not ip_ref:
            ip_ref = self.alloc_ip(ip, force=force)
        if not dns_owner_ref:
            dns_owner_ref = self.alloc_dns_owner(host_name, warn_other=True, force=force)
        self._alloc_arecord(dns_owner_ref, ip_ref)
        return ip

    def _alloc_aaaarecord(self, owner_id, ip_id):
        old_aaaa_records = self._aaaarecord.list_ext(ip_number_id=ip_id)
        self._aaaarecord.clear()
        self._aaaarecord.populate(owner_id, ip_id)
        self._aaaarecord.write_db()

        # If we now have two AAAA-records for the same IP, register an
        # override for the previous ip.
        if len(old_aaaa_records) == 1:
            if len(self._ipv6_number.list_override(ip_number_id=ip_id,
                    dns_owner_id=old_aaaa_records[0]['dns_owner_id'])) < 1:
                self._ipv6_number.add_reverse_override(
                    ip_id, old_aaaa_records[0]['dns_owner_id'])
        return self._aaaarecord.entity_id

    def alloc_aaaa_record(self, host_name, subnet_ip, ip, force,
                          allow_underscores=False):
        host_name = self._parser.qualify_hostname(host_name)
        # Check for existing record with same name
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            host_name, dns.AAAA_RECORD, allow_underscores)

        # Check to see if this has been added before
        try:
            self._ipv6_number.clear()
            self._ipv6_number.find_by_ip(ip)
            ip_i = self._ipv6_number.entity_id
        except Errors.NotFoundError:
            ip_i = -1
        try:
            self._aaaarecord.clear()
            self._aaaarecord.find_by_owner_and_ip(ip_i, dns_owner_ref)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "host already has this AAAA-record!"

        # We'll check if the IP is reserved
        ip_ref = self._find.find_ip(ip)
        if ip_ref and not force:
            raise CerebrumError, "IP already in use or reserved, must force (y)"
        # Catch Utils.Find.find_free_ip()s CerebrumError in case there
        # are no free IPs. You must still force to register the a_record.
        new_ips = []
        try:
            new_ips = self._find.find_free_ip(subnet_ip)
        except CerebrumError:
            # No IPs available
            pass
        if (subnet_ip and ip not in new_ips) and not force:
            raise CerebrumError, "IP appears to be reserved, must force (y)"

        # Checking if the AAAA-record allready exists
        if dns_owner_ref and same_type and not force:
            owner_types = self._find.find_dns_owners(dns_owner_ref)
            if dns.AAAA_RECORD in owner_types:
                raise CerebrumError, "name already in use, must force (y)"

        ip_eid = self.alloc_ip(ip, force=force)
        if not dns_owner_ref:
            dns_owner_ref = self.alloc_dns_owner(host_name,
                                                 warn_other=True,
                                                 force=force)

        self._alloc_aaaarecord(dns_owner_ref, ip_eid)
        return ip

    def remove_arecord(self, a_record_id):
        # If this IP is in override_reversemap, the helper will
        # update that too as needed.
        self._update_helper.remove_arecord(a_record_id)

    def add_revmap_override(self, ip_host_id, dest_host, force):
        if ip_host_id.count(':') > 2:
            ip_type= dns.IPv6_NUMBER
            a_type = dns.A_RECORD
        else:
            ip_type = dns.IP_NUMBER
            a_type = dns.A_RECORD

        if dest_host:
            dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
                                                        dest_host, a_type)
            self._dns_owner.clear()
            try:
                self._dns_owner.find_by_name(dest_host)
                dest_host = self._dns_owner.entity_id
            except Errors.NotFoundError:
                if not force:
                    raise CerebrumError(
                        "'%s' does not exist, must force (y)" % dest_host)
                dest_host  = self.alloc_dns_owner(dest_host)
        else:
            dest_host = None

        try:
            ip_owner_id = self._find.find_target_by_parsing(
                ip_host_id, ip_type)
        except (Errors.NotFoundError, CerebrumError):
            if not force:
                raise CerebrumError(
                    "IP '%s' does not exist, must force (y)" % ip_host_id)
            ip_owner_id = self.alloc_ip(ip_host_id)

        self._update_helper.add_reverse_override(ip_owner_id, dest_host)

    def remove_revmap_override(self, ip_host_id, dest_host_id):
        self._update_helper.remove_reverse_override(
            ip_host_id, dest_host_id)

