# -*- coding: utf-8 -*-
#
# Copyright 2005-2018 University of Oslo, Norway
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
from collections import OrderedDict

from six import text_type

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    GroupName,
    Parameter,
    YesNo
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.dns import AAAARecord
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import IPv6Number
from Cerebrum.modules.dns import Subnet, IPv6Subnet
from Cerebrum.modules.dns import Utils
from Cerebrum.modules.dns.Errors import SubnetError
from Cerebrum.modules.dns.IPUtils import IPCalc, IPUtils
from Cerebrum.modules.dns.IPv6Utils import IPv6Calc, IPv6Utils
from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as cl_base


class DnsBofhdAuth(BofhdAuth):

    def assert_dns_superuser(self, operator, query_run_any=False):
        if (not (self.is_dns_superuser(operator)) and
                not (self.is_superuser(operator))):
            raise PermissionDenied("Currently limited to dns_superusers")

    def is_dns_superuser(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        return self._has_operation_perm_somewhere(
            operator, self.const.auth_dns_superuser)

    def can_do_lita_dns_by_ip(self, operator, target):
        """Check if operator is allowed to perform DNS operations at
        'LITA level' on the target in question.

        It checks whether the operator has permissions on the subnet
        where the IP (host) resides, or, lacking that, if the operator
        has permissions for the specific IP.

        @type operator: int
        @param operator: Entity ID of the user performing the operation

        @type target: string
        @param target: The IP address in question.

        @rtype: boolean
        @return: Whether or not the operatior has permission to do
                 DNS operations on the ip in question
        """
        db = Factory.get('Database')()
        const = Factory.get('Constants')(db)

        # These guys always get to do stuff
        if self.is_dns_superuser(operator):
            return True

        # First, check if operator has permissions on the subnet the IP is on
        s = Subnet.Subnet(db)
        s.find(target)
        target_id = s.entity_id
        if self._list_target_permissions(operator,
                                         self.const.auth_dns_lita,
                                         self.const.auth_target_type_dns,
                                         target_id):
            return True

        # OK, didn't have that; check for permissions on the specific host
        dns_finder = Utils.Find(db, const.DnsZone('uio'))
        target_id = dns_finder.find_target_by_parsing(target, dns.IP_NUMBER)
        if self._list_target_permissions(operator,
                                         self.const.auth_dns_lita,
                                         self.const.auth_target_type_dns,
                                         target_id):
            return True

        # Apparently, neither was the case. Bummer.
        return False


def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))


# Parameter types
class HostId(Parameter):
    _type = 'host_id'
    _help_ref = 'host_id'


class HostName(Parameter):
    _type = 'host_name'
    _help_ref = 'host_name'


class HostNameRepeat(Parameter):
    _type = 'host_name_repeat'
    _help_ref = 'host_name_repeat'


class HostSearchPattern(Parameter):
    _type = 'host_search_pattern'
    _help_ref = 'host_search_pattern'


class HostSearchType(Parameter):
    _type = 'host_search_type'
    _help_ref = 'host_search_type'


class ServiceName(Parameter):
    _type = 'service_name'
    _help_ref = 'service_name'


class Ip(Parameter):
    _type = 'ip'
    _help_ref = 'ip_number'


class Hinfo(Parameter):
    _type = 'hinfo'
    _help_ref = 'hinfo'


class MACAdr(Parameter):
    _type = 'mac_adr'
    _help_ref = 'mac_adr'


class MXSet(Parameter):
    _type = 'mx_set'
    _help_ref = 'mx_set'


class TXT(Parameter):
    _type = 'txt'
    _help_ref = 'txt'


class TTL(Parameter):
    _type = 'ttl'
    _help_ref = 'ttl'


class Contact(Parameter):
    _type = 'contact'
    _help_ref = 'contact'


class Comment(Parameter):
    _type = 'comment'
    _help_ref = 'comment'


class Priority(Parameter):
    _type = 'pri'
    _help_ref = 'pri'


class Weight(Parameter):
    _type = 'weight'
    _help_ref = 'weight'


class Port(Parameter):
    _type = 'port'
    _help_ref = 'port'


class SubNetOrIP(Parameter):
    _type = 'subnet_or_ip'
    _help_ref = 'subnet_or_ip'


class NumberOrRange(Parameter):
    _type = 'number_or_range'
    _help_ref = 'number_or_range'


class Force(Parameter):
    _type = 'force'
    _help_ref = 'force'


class AllowDnsUnderscores(Parameter):
    _type = 'allow_dns_underscores'
    _help_ref = 'allow_dns_underscores'


def int_or_none_as_str(val):
    # Unfortunately the client don't understand how to
    # format: "%i" % None
    if val is not None:
        return str(int(val))
    return None


LEGAL_HINFO = OrderedDict((
    ("win", "IBM-PC\tWINDOWS"),
    ("linux", "IBM-PC\tLINUX"),
    ("printer", "PRINTER\tPRINTER"),
    ("unix", "UNIX\tUNIX"),
    ("nett", "NET\tNET"),
    ("mac", "MAC\tDARWIN"),
    ("other", "OTHER\tOTHER"),
    ("dhcp", "DHCP\tDHCP"),
    ("netapp", "NETAPP\tONTAP")
))


def get_hinfo_code(code_str):
    try:
        return LEGAL_HINFO[code_str]
    except KeyError:
        raise CerebrumError("Illegal HINFO (%r)" % code_str)


def _compress_ipv4(ip):
    return ip


def _compress_ipv6(ip):
    return IPv6Utils.compress(ip)


# TODO: Ugh, let's make a generic changelog formatter class
@copy_func(
    cl_base,
    methods=[
        '_format_changelog_entry',
        '_format_from_cl',
    ]
)
class BofhdExtension(BofhdCommandBase):
    all_commands = {}
    parent_commands = False
    authz = DnsBofhdAuth

    def __init__(self, *args, **kwargs):
        default_zone = kwargs.pop('default_zone', 'uio')
        super(BofhdExtension, self).__init__(*args, **kwargs)
        self.default_zone = self.const.DnsZone(
            getattr(cereconf, 'DNS_DEFAULT_ZONE', default_zone))

    @property
    def _find(self):
        try:
            return self.__find_util
        except AttributeError:
            self.__find_util = Utils.Find(self.db, self.default_zone)
            return self.__find_util

    @property
    def dns_parser(self):
        try:
            return self.__dns_parser
        except AttributeError:
            self.__dns_parser = Utils.DnsParser(self.db, self.default_zone)
            return self.__dns_parser

    @property
    def mb_utils(self):
        try:
            return self.__mb_utils
        except AttributeError:
            self.__mb_utils = DnsBofhdUtils(
                self.db, self.logger, self.default_zone)
            return self.__mb_utils

    @classmethod
    def get_help_strings(cls):
        group, _, args = get_help_strings()
        return merge_help_strings(
            (group, {}, args),
            (HELP_DNS_GROUPS, HELP_DNS_CMDS, HELP_DNS_ARGS))

    def _alloc_a_record(self, *args):
        return _compress_ipv4(self.mb_utils.alloc_arecord(*args))

    def _alloc_aaaa_record(self, *args):
        return _compress_ipv6(self.mb_utils.alloc_aaaa_record(*args))

    #
    # group hadd
    #
    all_commands['group_hadd'] = Command(
        ("group", "hadd"),
        HostName(),
        GroupName(help_ref="group_name_dest"),
        perm_filter='can_alter_group')

    def group_hadd(self, operator, src_name, dest_group):
        dest_group = self._get_group(dest_group)
        self._raise_PermissionDenied_if_not_manual_group(dest_group)
        owner_id = self._find.find_target_by_parsing(src_name, dns.DNS_OWNER)
        self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        # Check if member is in the group or not.
        if not dest_group.has_member(owner_id):
            dest_group.add_member(owner_id)
            if self._is_perishable_manual_group(dest_group):
                dest_group.set_default_expire_date()
            dest_group.write_db()
        else:
            raise CerebrumError("Member '%s' already in group '%s'" %
                                (src_name, dest_group))
        return "OK, added %s to %s" % (src_name, dest_group.group_name)

    #
    # group host
    #
    all_commands['group_host'] = Command(
        ('group', 'host'),
        HostName(),
        fs=FormatSuggestion(
            "%-9s %-25s %s", ("memberop", "group", "spreads"),
            hdr="%-9s %-25s %s" % ("Operation", "Group", "Spreads")
        ))

    def group_host(self, operator, hostname):
        # TODO: Should make use of "group memberships" command instead
        owner_id = self._find.find_target_by_parsing(hostname, dns.DNS_OWNER)
        group = self.Group_class(self.db)
        co = self.const
        ret = []
        for row in group.search(member_id=owner_id, indirect_members=False):
            grp = self._get_group(row['group_id'], idtype="id")
            # IVR 2008-06-13 TBD: Does it make sense to report union, when it
            # is the ONLY possibility?
            ret.append({
                'memberop': text_type(co.group_memberop_union),
                'entity_id': grp.entity_id,
                'group': grp.group_name,
                'spreads': ",".join([text_type(co.Spread(a['spread']))
                                     for a in grp.get_spread()]),
            })
        ret.sort(lambda a, b: cmp(a['group'], b['group']))
        return ret

    #
    # group hrem
    #
    all_commands['group_hrem'] = Command(
        ("group", "hrem"),
        HostName(),
        GroupName(help_ref="group_name_dest"),
        perm_filter='can_alter_group')

    def group_hrem(self, operator, src_name, dest_group):
        dest_group = self._get_group(dest_group)
        self._raise_PermissionDenied_if_not_manual_group(dest_group)
        owner_id = self._find.find_target_by_parsing(src_name, dns.DNS_OWNER)
        self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        dest_group.remove_member(owner_id)
        if self._is_perishable_manual_group(dest_group):
            dest_group.set_default_expire_date()
        dest_group.write_db()
        return "OK, removed %s from %s" % (src_name, dest_group.group_name)

    #
    # host a_add
    #
    all_commands['host_a_add'] = Command(
        ("host", "a_add"),
        HostName(),
        SubNetOrIP(),
        Force(optional=True),
        perm_filter='is_dns_superuser')
    # TBD: Comment/contact?

    def host_a_add(self, operator, host_name, subnet_or_ip, force=False):
        """BOFH command for adding a new A/AAAA record to a host.

        :param operator: The logged-in account calling the method.
        :type  operator: An account object.
        :param host_name: The hostname of the host being added.
        :type  host_name: str
        :param subnet_or_ip: An IPv4/IPv6-address or subnet.
        :type  subnet_or_ip: str
        :param force: Indicates if the method should force the operation, even
                      if the entered IP is not part of any registered subnet,
                      or is part of a subnet handled by an external DNS-server.
        :type  force: boolean

        :returns: A string indicating the added IP for the host.
        :rtype: str
        """
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        host_name = host_name.lower()
        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet_or_ip)

        if subnet is None:
            if not force:
                # Allow IPv6-addresses if DNS_HOST_A_ADD... is set as True
                if not cereconf.DNS_HOST_A_ADD_ACCEPT_MISSING_IPV6_SUBNET and \
                        IPv6Utils.is_valid_ipv6(ip):
                    raise CerebrumError("Unknown subnet. Must force.")

        if IPUtils.is_valid_ipv4(subnet) or IPUtils.is_valid_ipv4(ip):
            s = Subnet.Subnet(self.db)
            a_alloc = self._alloc_a_record

        elif IPv6Utils.is_valid_ipv6(subnet) or IPv6Utils.is_valid_ipv6(ip):
            s = IPv6Subnet.IPv6Subnet(self.db)
            a_alloc = self._alloc_aaaa_record
        else:
            raise CerebrumError("Please specify a valid subnet or IP-address.")

        if subnet is not None:
            if s.dns_delegated and not force:
                raise CerebrumError("Must force 'host a_add' for subnets "
                                    "delegated to external DNS-server")

            if ip is None:
                new_ip_addr = self.mb_utils.get_relevant_ips(subnet_or_ip,
                                                             force,
                                                             no_of_addrs=1)[0]
        if ip is not None:
            if ip.endswith('.0'):
                raise CerebrumError("Cannot allocate address "
                                    "that ends with .0")
            new_ip_addr = ip

        ip_addr = a_alloc(host_name, subnet, new_ip_addr, force)
        return "OK, ip=%s" % ip_addr

    #
    # host a_remove
    #
    all_commands['host_a_remove'] = Command(
        ("host", "a_remove"),
        HostName(),
        Ip(optional=True),
        perm_filter='is_dns_superuser')

    def host_a_remove(self, operator, host_name, ip=None):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        a_record_id = self._find.find_a_record(host_name, ip)
        self.mb_utils.remove_arecord(a_record_id)
        return "OK"

    #
    # host add
    #
    all_commands['host_add'] = Command(
        ('host', 'add'),
        HostNameRepeat(),
        SubNetOrIP(),
        Hinfo(),
        Contact(),
        Comment(),
        Force(optional=True),
        AllowDnsUnderscores(optional=True),
        fs=FormatSuggestion(
            '%-30s %s', ('name', 'ip'),
            hdr='%-30s %s' % ('name', 'ip')
        ),
        perm_filter='is_dns_superuser')

    def host_add(self, operator, hostname, subnet_or_ip, hinfo,
                 contact, comment, force=False, allow_underscores=False):
        """
        Adds a record for a new host.

        :param operator: The current active Bofhd-session.
        :type  operator: A Bofhd-session object.
        :param hostname: The hostname of the host being added.
        :type  hostname: str
        :param subnet_or_ip: An IPv4/IPv6-address or subnet.
        :type  subnet_or_ip: str
        :param hinfo: Host-info code, for example 'win', 'linux', 'printer'
        :type  hinfo: str
        :param contact: Email-address for the host's contact-person/department.
        :type  contact: str
        :param comment: General info about the host.
        :type  comment: str
        :param force: Indicates if the method should force the operation, even
                      if the entered IP is not part of any registered subnet,
                      or is part of a subnet handled by an external DNS-server.
        :param allow_underscores: Allow underscores in the resulting DNS-record
                                  when adding the host.
        :returns: A list of dictionaries, containing the added hostnames and
                  their related IPs.
        :rtype: list

        """
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        allow_underscores = self.dns_parser.parse_force(allow_underscores)
        hostnames = self.dns_parser.parse_hostname_repeat(hostname)
        hinfo = get_hinfo_code(hinfo)

        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet_or_ip)

        if subnet is None and not force:
            raise CerebrumError("Unknown subnet. Must force.")

        if IPUtils.is_valid_ipv4(subnet) or IPUtils.is_valid_ipv4(ip):
            s = Subnet.Subnet(self.db)
            a_alloc = self._alloc_a_record

        elif IPv6Utils.is_valid_ipv6(subnet) or IPv6Utils.is_valid_ipv6(ip):
            s = IPv6Subnet.IPv6Subnet(self.db)
            a_alloc = self._alloc_aaaa_record
        else:
            raise CerebrumError("Please specify a valid subnet or IP-address.")

        if subnet is not None:
            if s.dns_delegated and not force:
                raise CerebrumError("Cannot add host to subnet zone "
                                    "delegated to external DNS-server")

            if ip is None:
                free_ip_numbers = self.mb_utils.get_relevant_ips(
                                                    subnet_or_ip,
                                                    force,
                                                    no_of_addrs=len(hostnames))
        if ip is not None:
            if ip.endswith('.0'):
                raise CerebrumError("Cannot allocate address "
                                    "that ends with .0")
            free_ip_numbers = [ip]

        if len(free_ip_numbers) < len(hostnames):
            raise CerebrumError("Not enough free ips")

        # If user don't want mx_set, it must be removed with "host mx_set"
        if hasattr(cereconf, 'DNS_DEFAULT_MX_SET'):
            mx_set = self._find.find_mx_set(cereconf.DNS_DEFAULT_MX_SET)
            mx_set_id = mx_set.mx_set_id
        else:
            mx_set_id = None

        ret = []
        for name in hostnames:
            # TODO: bruk hinfo ++ for å se etter passende sekvens uten
            # hull (i en passende klasse)
            ip = a_alloc(
                name, subnet, free_ip_numbers.pop(0), force, allow_underscores
            )
            self.mb_utils.alloc_host(
                name, hinfo, mx_set_id, comment, contact, allow_underscores)
            ret.append({'name': name, 'ip': ip})
        return ret

    #
    # host cname_add
    #
    all_commands['host_cname_add'] = Command(
        ("host", "cname_add"),
        HostName(help_ref="host_name_alias"),
        HostName(help_ref="host_name_exist"),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_cname_add(self, operator, cname_name, target_name, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        cname_name = cname_name.lower()
        try:
            self.mb_utils.alloc_cname(cname_name, target_name, force)
        except ValueError as ve:
            raise CerebrumError("%s" % ve)
        return "OK, cname registered for %s" % target_name

    #
    # host cname_remove
    #
    all_commands['host_cname_remove'] = Command(
        ("host", "cname_remove"),
        HostName(help_ref="host_name"),
        perm_filter='is_dns_superuser')

    def host_cname_remove(self, operator, cname_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(cname_name, dns.DNS_OWNER)
        obj_ref, obj_id = self._find.find_target_type(owner_id)
        if not isinstance(obj_ref, CNameRecord.CNameRecord):
            raise CerebrumError("No such cname")
        self.mb_utils.ip_free(dns.DNS_OWNER, cname_name, False)
        return "OK, cname %s completely removed" % cname_name

    #
    # host comment
    #
    all_commands['host_comment'] = Command(
        ("host", "comment"),
        HostName(),
        Comment(),
        perm_filter='is_dns_superuser')

    def host_comment(self, operator, host_name, comment):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.trait_dns_comment, comment)
        return "OK, %s comment for %s" % (operation, host_name)

    #
    # host contact
    #
    all_commands['host_contact'] = Command(
        ("host", "contact"),
        HostName(),
        Contact(),
        perm_filter='is_dns_superuser')

    def host_contact(self, operator, name, contact):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.trait_dns_contact, contact)
        return "OK, %s contact for %s" % (operation, name)

    #
    # host find
    #
    all_commands['host_find'] = Command(
        ("host", "find"),
        HostSearchType(),
        HostSearchPattern(),
        fs=FormatSuggestion(
            "%-30s %s", ('name', 'info'),
            hdr="%-30s %s" % ("Host", "Info")
        ))

    def host_find(self, operator, search_type, pattern):
        if '*' not in pattern and '?' not in pattern:
            pattern = '*' + pattern + '*'
        if search_type == 'contact':
            matches = self._hosts_matching_trait(self.const.trait_dns_contact,
                                                 pattern)
        elif search_type == 'comment':
            matches = self._hosts_matching_trait(self.const.trait_dns_comment,
                                                 pattern)
        elif search_type == 'name':
            if pattern[-1].isalpha():
                # All names should be fully qualified, but it's easy to
                # forget the trailing dot.
                pattern += "."
            matches = self._hosts_matching_name(pattern)
        else:
            raise CerebrumError("Unknown search type %s" % search_type)
        self._assert_limit(matches, 500)
        matches.sort(lambda a, b: cmp(a['name'], b['name']))
        return matches

    def _assert_limit(self, rows, limit):
        if len(rows) > limit:
            raise CerebrumError("More than %d matches (%d)."
                                " Refine your search." % (limit, len(rows)))

    def _hosts_matching_trait(self, trait, pattern):
        dns_owner = DnsOwner.DnsOwner(self.db)
        matches = []
        for row in dns_owner.list_traits(trait, strval_like=pattern):
            e_id = row['entity_id']
            try:
                dns_owner.clear()
                dns_owner.find(row['entity_id'])
                name = dns_owner.name
            except Errors.NotFoundError:
                self.logger.error("No DNS Owner with entity_id=%r", e_id)
                continue
            matches.append({'name': name, 'info': row['strval']})
        return matches

    def _hosts_matching_name(self, pattern):
        dns_owner = DnsOwner.DnsOwner(self.db)
        matches = []
        for row in dns_owner.search(name_like=pattern):
            matches.append({'name': row['name'], 'info': ""})
        return matches

    #
    # host free
    #
    all_commands['host_remove'] = Command(
        ("host", "remove"),
        HostId(),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_remove(self, operator, host_id, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)

        ip_type = None

        if IPUtils.is_valid_ipv4(host_id):
            IPUtils.parse_ipv4(host_id)
            arecord = ARecord.ARecord(self.db)
            ip_type = dns.IP_NUMBER

        elif IPv6Utils.is_valid_ipv6(host_id):
            arecord = AAAARecord.AAAARecord(self.db)
            ip_type = dns.IPv6_NUMBER

        if ip_type == dns.IPv6_NUMBER or ip_type == dns.IP_NUMBER:
            # Freeing an ip-number
            owner_id = self._find.find_target_by_parsing(host_id, ip_type)
            names = dict([(a['name'], True)
                          for a in arecord.list_ext(ip_number_id=owner_id)])
            if len(names) > 1:
                raise CerebrumError("IP matches multiple names")
            if len(names) == 0:
                raise CerebrumError("IP does not point at a host in Cerebrum. "
                                    "Use host ptr_remove to remove the PTR")
            owner_id = names.keys()[0]
        try:
            owner_id = self._find.find_target_by_parsing(host_id,
                                                         dns.DNS_OWNER)
            owners = self._find.find_dns_owners(owner_id)
            if dns.CNAME_OWNER in owners:
                raise CerebrumError("Use 'host cname_remove' to remove cnames")
        except Errors.NotFoundError:
            pass
        # Remove links to policies if hostpolicy is used:
        try:
            policy = PolicyComponent(self.db)
            for row in policy.search_hostpolicies(dns_owner_id=owner_id):
                policy.clear()
                policy.find(row['policy_id'])
                policy.remove_from_host(owner_id)
        except CerebrumError:
            raise
        except Exception:
            # This could be due to that hostpolicy isn't implemented at the
            # instance, will therefore log all errors in the start:
            self.logger.warn('host_remove policy error', exc_info=True)
        self.mb_utils.ip_free(dns.DNS_OWNER, host_id, force)
        return "OK, DNS-owner %s completely removed" % host_id

    #
    # host hinfo_list
    #
    all_commands['host_hinfo_list'] = Command(
        ("host", "hinfo_list")
    )

    def host_hinfo_list(self, operator):
        return "\n".join(["%-10s -> %s" % (k, v)
                          for k, v in LEGAL_HINFO.items()])

    #
    # host hinfo_set
    #
    all_commands['host_hinfo_set'] = Command(
        ("host", "hinfo_set"),
        HostName(),
        Hinfo(),
        perm_filter='is_dns_superuser')

    def host_hinfo_set(self, operator, host_name, hinfo):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        hinfo = get_hinfo_code(hinfo)
        owner_id = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        host = HostInfo.HostInfo(self.db)
        try:
            host.find_by_dns_owner_id(owner_id)
        except Errors.NotFoundError:
            raise CerebrumError('Cannot set host info on A-record %s.' %
                                host_name)
        host.hinfo = hinfo
        host.write_db()
        return "OK, hinfo set for %s" % host_name

    #
    # host info
    #
    all_commands['host_info'] = Command(
        ("host", "info"), HostId(),
        YesNo(optional=True, help_ref='show_policy'),
        fs=FormatSuggestion([
            # Name line
            ("%-22s %%s\n%-22s contact=%%s\n%-22s comment=%%s" % ("Name:", ' ',
                                                                  ' '),
             ('dns_owner', 'contact', 'comment')),
            # A-records
            ("  %-20s %-20s %s", ('name', 'ip', 'mac'),
             "%-22s %-20s MAC" % ('A-records', 'IP')),
            # AAAA-records
            ("  %-20s %-40s %s", ('name6', 'ipv6', 'mac6'),
             "%-22s %-40s MAC" % ('AAAA-records', 'IPv6')),
            # Hinfo line
            ("%-22s %s" % ('Hinfo:', 'os=%s cpu=%s'), ('hinfo.os',
                                                       'hinfo.cpu')),
            # MX
            ("%-22s %s" % ("MX-set:", "%s"), ('mx_set',)),
            # TTL
            ("%-22s %s" % ("TTL:", "%s"), ('ttl',)),
            # TXT
            ("%-22s %s" % ("TXT:", "%s"), ('txt',)),
            # entity_id
            ("%-22s %%d" % ("Owner ID:",), ('owner_id',)),
            # Cnames
            ("%-22s %s" % ('Cname:', '%s -> %s'), ('cname', 'cname_target')),
            # SRV
            ("SRV: %s %i %i %i %s %s",
             ('srv_owner', 'srv_pri', 'srv_weight', 'srv_port', 'srv_ttl',
              'srv_target')),
            # Rev-map
            ("  %-20s %s", ('rev_ip', 'rev_name'), "Rev-map override:"),
            # Hostpolicy
            ("  %-20s", ('policy_name',), 'Hostpolicies:'),
        ])
    )

    def host_info(self, operator, host_id, policy=False):
        arecord = ARecord.ARecord(self.db)
        aaaarecord = AAAARecord.AAAARecord(self.db)
        tmp = host_id.split(".")
        if policy and policy == 'policy':
            policy = True
        else:
            policy = False

        # Ugly way to check if this is IPv4 or IPv6, and selecting
        # appropriate target type.
        if host_id.find(':') != -1:
            target_type = dns.IPv6_NUMBER
        elif tmp[-1].isdigit():
            target_type = dns.IP_NUMBER
        else:
            target_type = None

        if target_type:
            # When host_id is an IP, we only return A- and AAAA-records
            owner_id = self._find.find_target_by_parsing(
                host_id, target_type)

            ret = []
            for a in arecord.list_ext(ip_number_id=owner_id):
                ret.append({
                    'ip': a['a_ip'],
                    'name': a['name'],
                    'mac': a['mac_adr'],
                })

            for a in aaaarecord.list_ext(ip_number_id=owner_id):
                ret.append({
                    'ipv6': IPv6Utils.compress(a['aaaa_ip']),
                    'name6': a['name'],
                    'mac6': a['mac_adr'],
                })

            ip = IPNumber.IPNumber(self.db)
            ipv6 = IPv6Number.IPv6Number(self.db)
            added_rev = False
            for row in ip.list_override(ip_number_id=owner_id):
                ret.append({
                    'rev_ip': row['a_ip'],
                    'rev_name': row['name'],
                })
                added_rev = True
            for row in ipv6.list_override(ip_number_id=owner_id):
                ret.append({
                    'rev_ip': IPv6Utils.compress(row['aaaa_ip']),
                    'rev_name': row['name'],
                })
                added_rev = True
            if not ret:
                self.logger.warn("Nothing known about host_id=%r ?", host_id)
            if not added_rev:
                rev_type = ('A-record' if target_type == dns.IP_NUMBER
                            else 'AAAA-record')
                ret.append({
                    'rev_ip': host_id,
                    'rev_name': "using default PTR from " + rev_type,
                })

            return ret

        owner_id = self._find.find_target_by_parsing(host_id, dns.DNS_OWNER)

        # Wait a moment; we need to check if this is a Cname
        try:
            cname_record = CNameRecord.CNameRecord(self.db)
            cname_record.find_by_cname_owner_id(owner_id)
            # It is! Then we need the main entry to proceed
            owner_id = cname_record.target_owner_id
        except Errors.NotFoundError:
            # It wasn't; then it must be the main host we're dealing with
            # Sorry for the inconvenience; carry on
            pass

        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        tmp = {'dns_owner': dns_owner.name}
        for key, trait in (('comment', self.const.trait_dns_comment),
                           ('contact', self.const.trait_dns_contact)):
            tmp[key] = dns_owner.get_trait(trait)
            if tmp[key] is not None:
                tmp[key] = tmp[key]['strval']
        ret = [tmp]
        ret.append({'owner_id': dns_owner.entity_id})

        # HINFO records
        ret.append({'zone': text_type(self.const.DnsZone(dns_owner.zone))})
        try:
            host = HostInfo.HostInfo(self.db)
            host.find_by_dns_owner_id(owner_id)
            hinfo_cpu, hinfo_os = host.hinfo.split("\t", 1)
            ret.append({
                'hinfo.os': hinfo_os,
                'hinfo.cpu': hinfo_cpu,
            })
        except Errors.NotFoundError:  # not found
            pass

        txt = dns_owner.list_general_dns_records(
            field_type=self.const.field_type_txt,
            dns_owner_id=dns_owner.entity_id)
        if txt:
            ret.append({'txt': txt[0]['data']})

        forward_ips = []
        # A records
        tmp = []
        for a in arecord.list_ext(dns_owner_id=owner_id):
            forward_ips.append((a['a_ip'], a['ip_number_id']))
            tmp.append({
                'ip': a['a_ip'],
                'name': a['name'],
                'mac': a['mac_adr'],
            })
        tmp.sort(lambda x, y: cmp(IPCalc.ip_to_long(x['ip']),
                                  IPCalc.ip_to_long(y['ip'])))
        ret.extend(tmp)

        ip_ref = IPNumber.IPNumber(self.db)
        for row in ip_ref.list_override(dns_owner_id=owner_id):
            ret.append({
                'rev_ip': row['a_ip'],
                'rev_name': row['name'],
            })

        # AAAA records
        tmp = []
        for a in aaaarecord.list_ext(dns_owner_id=owner_id):
            tmp.append({
                'ipv6': IPv6Utils.compress(a['aaaa_ip']),
                'name6': a['name'],
                'mac6': a['mac_adr'],
            })
        tmp.sort(lambda x, y: cmp(IPv6Calc.ip_to_long(x['ipv6']),
                                  IPv6Calc.ip_to_long(y['ipv6'])))
        ret.extend(tmp)

        ipv6_ref = IPv6Number.IPv6Number(self.db)
        for row in ipv6_ref.list_override(dns_owner_id=owner_id):
            ret.append({
                'rev_ip': IPv6Utils.compress(row['aaaa_ip']),
                'rev_name': row['name'],
            })

        # MX records
        if dns_owner.mx_set_id:
            mx_set = DnsOwner.MXSet(self.db)
            mx_set.find(dns_owner.mx_set_id)
            ret.append({'mx_set': mx_set.name})

        # TTL settings
        ttl = self.mb_utils.get_ttl(owner_id)
        if ttl is None:
            ret.append({'ttl': '(Default)'})
        else:
            ret.append({'ttl': str(ttl)})

        # CNAME records with this as target, or this name
        cname = CNameRecord.CNameRecord(self.db)
        tmp = cname.list_ext(target_owner=owner_id)
        tmp.extend(cname.list_ext(cname_owner=owner_id))
        for c in tmp:
            row = ({
                'cname': c['name'],
                'cname_target': c['target_name'],
            })
            ret.append(row)

        # SRV records dersom dette er target/owner for en srv record
        r = dns_owner.list_srv_records(owner_id=owner_id)
        r.extend(dns_owner.list_srv_records(target_owner_id=owner_id))
        for srv in r:
            ret.append({
                'srv_owner': srv['service_name'],
                'srv_pri': srv['pri'],
                'srv_weight': srv['weight'],
                'srv_port': srv['port'],
                'srv_ttl': int_or_none_as_str(srv['ttl']),
                'srv_target': srv['target_name'],
            })
        if policy:
            # Hostpolicies
            policy = PolicyComponent(self.db)
            for row in policy.search_hostpolicies(dns_owner_id=owner_id):
                ret.append({'policy_name': row['policy_name']})
        return ret

    #
    # host unused_list
    #
    all_commands['host_unused_list'] = Command(
        ("host", "unused_list"),
        SubNetOrIP(),
        NumberOrRange(optional=True),
        fs=FormatSuggestion(
            [("%s", ('ip',)),
             ("In total: %s (from range: %s-%s)",
              ('unused', 'start', 'stop'))],
            hdr="Ip")
    )

    def host_unused_list(self, operator, subnet, num_or_range=None):
        # TODO: Skal det være mulig å få listet ut ledige reserved IP?

        display = range = {}
        if num_or_range:
            nor = num_or_range.split('-')
            if len(nor) == 2:
                range = {'no_of_addrs': abs(int(nor[1]) - int(nor[0])),
                         'start': int(nor[0])}
                display = {'no_of_addrs': nor[1], 'start': nor[0]}
            else:
                range = {'no_of_addrs': int(nor[0])}
                display = {'no_of_addrs': nor[0]}

        subnet = self.dns_parser.parse_subnet_or_ip(subnet)[0]
        if subnet is None:
            raise CerebrumError("Unknown subnet")
        ret = []
        for ip in self._find.find_free_ip(subnet, **range):
            ret.append({'ip': ip})
        ret.append({
            "unused": str(len(self._find.find_free_ip(subnet, **range))),
            "start": display.get('start', '0'),
            "stop": display.get('no_of_addrs', ''),
        })
        return ret

    #
    # host used_list
    #
    all_commands['host_used_list'] = Command(
        ("host", "used_list"),
        SubNetOrIP(),
        fs=FormatSuggestion(
            [("%-22s  %s", ('ip', 'hostname'),),
             ("In total: %s", ('used',))],
            hdr="%-22s  %s" % ('Ip', 'Hostname')
        ))

    def host_used_list(self, operator, subnet_or_ip):
        if '.' in subnet_or_ip:
            arecord = ARecord.ARecord(self.db)
            s = Subnet.Subnet(self.db)
            t_type = dns.IP_NUMBER
            compress = _compress_ipv4
            ipc = IPCalc
            s.find(subnet_or_ip)
        elif ':' in subnet_or_ip:
            arecord = AAAARecord.AAAARecord(self.db)
            s = IPv6Subnet.IPv6Subnet(self.db)
            t_type = dns.IPv6_NUMBER
            compress = _compress_ipv6
            ipc = IPv6Calc
            s.find(subnet_or_ip)
        else:
            raise SubnetError('Invalid IP')

        ret = []
        for ip in self._find.find_used_ips(s.subnet_ip):
            owner_id = self._find.find_target_by_parsing(
                ip, t_type)
            try:
                name = arecord.list_ext(ip_number_id=owner_id)[0]['name']
            except:
                # Need to expand how names are looked for, but this needs
                # testing
                name = "(Unknown)"
            ret.append({'ip': compress(ip), 'hostname': name})
        ret.sort(key=lambda x: ipc.ip_to_long(x['ip']))
        ret.append({"used": str(len(self._find.find_used_ips(s.subnet_ip)))})
        return ret

    #
    # host mxdef_add
    #
    all_commands['host_mxdef_add'] = Command(
        ("host", "mxdef_add"),
        MXSet(),
        Priority(),
        HostName(),
        perm_filter='is_dns_superuser')

    def host_mxdef_add(self, operator, mx_set, priority, host_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host_ref = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_add(mx_set, priority, host_ref)
        return "OK, added %s to mx_set %s" % (host_name, mx_set)

    #
    # host mxdef_remove
    #
    all_commands['host_mxdef_remove'] = Command(
        ("host", "mxdef_remove"),
        MXSet(),
        HostName(),
        perm_filter='is_dns_superuser')

    def host_mxdef_remove(self, operator, mx_set, target_host_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host_ref = self._find.find_target_by_parsing(
            target_host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_del(mx_set, host_ref)
        return "OK, deleted %s from mx_set %s" % (target_host_name, mx_set)

    #
    # host history
    #
    all_commands['host_history'] = Command(
        ("host", "history"),
        HostName(),
        fs=FormatSuggestion(
            "%s [%s]: %s", ("timestamp", "change_by", "message")
        ),
        perm_filter='can_show_history')

    def host_history(self, operator, host_name):
        host_ref = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        # TODO: shouldn't access to host_history be limited somewhat?
        # self.ba.can_show_history(operator.get_entity_id(), host_ref)
        ret = []
        for r in self.db.get_log_events(0, subject_entity=host_ref):
            ret.append(self._format_changelog_entry(r))
        return ret

    #
    # host mx_set
    #
    all_commands['host_mx_set'] = Command(
        ("host", "mx_set"),
        HostName(),
        MXSet(),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_mx_set(self, operator, name, mx_set, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        mx_set_id = self._find.find_mx_set(mx_set).mx_set_id
        force = self.dns_parser.parse_force(force)
        try:
            owner_id = self._find.find_target_by_parsing(
                name, dns.DNS_OWNER)
        except CerebrumError:
            # FIXME: a bit ugly, since all kinds of errors in
            # find_target_by_parsing will raise CerebrumError
            if not force:
                raise
            name = self.dns_parser.qualify_hostname(name)
            owner_id = self.mb_utils.alloc_dns_owner(name, mx_set=mx_set_id)
        self.mb_utils.mx_set_set(owner_id, mx_set)
        return "OK, mx set for %s" % name

    #
    # host mx_unset
    #
    all_commands['host_mx_unset'] = Command(
        ("host", "mx_unset"),
        HostName(),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_mx_unset(self, operator, name, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        try:
            owner_id = self._find.find_target_by_parsing(
                name, dns.DNS_OWNER)
        except CerebrumError:
            # FIXME: a bit ugly, since all kinds of errors in
            # find_target_by_parsing will raise CerebrumError
            if not force:
                raise
            name = self.dns_parser.qualify_hostname(name)
            owner_id = self.mb_utils.alloc_dns_owner(name, mx_set=None)
        self.mb_utils.mx_set_set(owner_id, '')
        return "OK, mx cleared for %s" % name

    #
    # host mxdef_show
    #
    all_commands['host_mxdef_show'] = Command(
        ("host", "mxdef_show"),
        MXSet(optional=True),
        fs=FormatSuggestion(
            "%-20s %-12s %-10i %s", ('mx_set', 'ttl', 'pri', 'target'),
            hdr="%-20s %-12s %-10s %s" % ('MX-set', 'TTL', 'Priority',
                                          'Target')
        ))

    def host_mxdef_show(self, operator, mx_set=None):
        m = DnsOwner.MXSet(self.db)
        if mx_set is None:
            mx_set = [row['name'] for row in m.list()]
        else:
            self._find.find_mx_set(mx_set)
            mx_set = [mx_set]
        ret = []
        for name in mx_set:
            m.clear()
            m.find_by_name(name)
            for row in m.list_mx_sets(mx_set_id=m.mx_set_id):
                ret.append({
                    'mx_set': m.name,
                    'ttl': int_or_none_as_str(row['ttl']),
                    'pri': row['pri'],
                    'target': row['target_name'],
                })
        return ret

    #
    # host rename
    #
    all_commands['host_rename'] = Command(
        ("host", "rename"),
        HostId(help_ref='host_name_exist'),
        HostId(help_ref='host_name_rename_new'),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_rename(self, operator, old_id, new_id, force=False):
        """
        Renames a host. Valid inputs for old_id & new_id are hostnames, IPv4 or
        IPv6. new_id can be both a specific IP, or a subnet. If the method is
        given a subnet as new_id, the host will be assigned a free IP found in
        it.

        :param operator: The current Bofhd-Session.
        :type  operator: An account object
        :param old_id: An existing host's hostname, or IPv4/IPv6-address.
        :type  old_id: str
        :param new_id: The new hostname, IPv4/IPv6-address or subnet.
        :type  new_id: str
        :param force: Indicates if the method should force the operation, even
                      if the entered IP is not part of any registered subnet,
                      or is part of a subnet handled by an external DNS-server.
        :type  force: boolean

        :returns: A string, indicating the changes made after the operation.
        :rtype: str
        """
        self.ba.assert_dns_superuser(operator.get_entity_id())

        force = self.dns_parser.parse_force(force)

        if old_id == "" or new_id == "":
            raise CerebrumError("Cannot rename without both an "
                                "old and a new name.")

        # Verify that old_id and new_id is valid and of same type
        if IPUtils.is_valid_ipv4(old_id):
            IPUtils.parse_ipv4(old_id)
            new_ip_error = None
            try:
                IPUtils.parse_ipv4(new_id)
            except CerebrumError, error:
                new_ip_error = error
            if new_ip_error is not None:
                raise CerebrumError("New host-id must be of same type as old "
                                    "host-id (IPv4 address or subnet).\n"
                                    "Error: %s" % new_ip_error)

        elif IPv6Utils.is_valid_ipv6(old_id):
            if not IPv6Utils.is_valid_ipv6(new_id):
                raise CerebrumError("New host-id must be of same type as old "
                                    "host-id (IPv6).")

        else:  # hostname
            if IPUtils.is_valid_ipv4(new_id) or \
               IPv6Utils.is_valid_ipv6(new_id):
                raise CerebrumError("New host-id must be of same type as old "
                                    "host-id (hostname).\n"
                                    "This is due to the fact that a host may"
                                    "have multiple A/AAAA-records.")

        # Verify IP in new_id is valid or that subnet in new_id has free IPs.
        if IPUtils.is_valid_ipv4(new_id) or \
           IPv6Utils.is_valid_ipv6(new_id):

            new_ip_addr = self.mb_utils.get_relevant_ips(subnet_or_ip=new_id,
                                                         no_of_addrs=1,
                                                         force=force)[0]
            if IPUtils.is_valid_ipv4(old_id):
                ip_type = dns.IP_NUMBER
            else:
                ip_type = dns.IPv6_NUMBER

            self.mb_utils.ip_rename(ip_type, old_id, new_ip_addr)
            return "OK, ip-number %s renamed to %s" % (old_id, new_ip_addr)

        else:  # hostname
            new_id = self.dns_parser.qualify_hostname(new_id)
            self.mb_utils.ip_rename(dns.DNS_OWNER, old_id, new_id)
            owner_id = self._find.find_target_by_parsing(new_id, dns.DNS_OWNER)
            arecord = ARecord.ARecord(self.db)
            aaaarecord = AAAARecord.AAAARecord(self.db)
            ips = [row['a_ip'] for row in
                   arecord.list_ext(dns_owner_id=owner_id)]
            ips += [IPv6Utils.compress(row['aaaa_ip']) for row in
                    aaaarecord.list_ext(dns_owner_id=owner_id)]

            return "OK, DNS-owner %s renamed to %s (IP: %s)" % (old_id, new_id,
                                                                ", ".join(ips))

    #
    # host ptr_add
    #
    all_commands['host_ptr_add'] = Command(
        ("host", "ptr_add"),
        Ip(),
        HostName(),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_ptr_add(self, operator, ip_host_id, dest_host, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        skip_ipv6 = False

        if IPUtils.is_valid_ipv4(ip_host_id):
            IPUtils.parse_ipv4(ip_host_id)
            s = Subnet.Subnet(self.db)
        # Fast check for IPv6
        elif IPv6Utils.is_valid_ipv6(ip_host_id):
            skip_ipv6 = cereconf.DNS_HOST_A_ADD_ACCEPT_MISSING_IPV6_SUBNET
            s = IPv6Subnet.IPv6Subnet(self.db)
        else:
            raise CerebrumError('IP is invalid')

        if not skip_ipv6:
            s.find(ip_host_id)
            if s.dns_delegated:
                raise CerebrumError("Cannot add reversemap in subnet zone "
                                    "delegated to external DNS-server")

        self.mb_utils.add_revmap_override(ip_host_id, dest_host, force)

        return "OK, added reversemap override for %s -> %s" % (
            ip_host_id, dest_host)

    #
    # host ptr_remove
    #
    all_commands['host_ptr_remove'] = Command(
        ("host", "ptr_remove"),
        Ip(),
        HostName(),
        perm_filter='is_dns_superuser')

    def host_ptr_remove(self, operator, ip_host_id, dest_host, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)

        if IPUtils.is_valid_ipv4(ip_host_id):
            IPUtils.parse_ipv4(ip_host_id)
            ip_type = dns.IP_NUMBER
        elif IPv6Utils.is_valid_ipv6(ip_host_id):
            ip_type = dns.IPv6_NUMBER
        else:
            raise CerebrumError('IP is invalid.')

        ip_owner_id = self._find.find_target_by_parsing(
            ip_host_id, ip_type)

        if not self._find.find_referers(ip_number_id=ip_owner_id,
                                        ip_type=dns.REV_IP_NUMBER):
            raise CerebrumError("Can't delete the default reverse ptr. "
                                "Use 'host remove' instead")

        if dest_host:
            dest_owner_id = self._find.find_target_by_parsing(
                dest_host, dns.DNS_OWNER)
        else:
            dest_owner_id = None

        self.mb_utils.remove_revmap_override(ip_owner_id, dest_owner_id)

        return "OK, removed reversemap override for %s -> %s" % (
            ip_host_id, dest_host)

    #
    # host srv_add
    #
    all_commands['host_srv_add'] = Command(
        ("host", "srv_add"),
        ServiceName(),
        Priority(),
        Weight(),
        Port(),
        HostName(),
        Force(optional=True),
        perm_filter='is_dns_superuser')

    def host_srv_add(self, operator, service_name, priority,
                     weight, port, target_name, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        target_id = self._find.find_target_by_parsing(target_name,
                                                      dns.DNS_OWNER)
        self.mb_utils.alter_srv_record(
            'add', service_name, int(priority), int(weight),
            int(port), target_id, force=force)
        return "OK, added SRV record %s -> %s" % (service_name, target_name)

    #
    # host srv_remove
    #
    all_commands['host_srv_remove'] = Command(
        ("host", "srv_remove"),
        ServiceName(),
        Priority(),
        Weight(),
        Port(),
        HostName(),
        perm_filter='is_dns_superuser')

    def host_srv_remove(self, operator, service_name, priority,
                        weight, port, target_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        target_id = self._find.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        self.mb_utils.alter_srv_record(
            'del', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, deleted SRV record %s -> %s" % (service_name, target_name)

    #
    # host ttl_set
    #
    all_commands['host_ttl_set'] = Command(
        ("host", "ttl_set"),
        HostName(),
        TTL(),
        perm_filter='is_dns_superuser')

    def host_ttl_set(self, operator, host_name, ttl):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        ttl = int(ttl) if ttl else None
        self.mb_utils.set_ttl(owner_id, ttl)
        return "OK, set TTL record for %s to %s" % (host_name, ttl)

    #
    # host ttl_unset
    #
    all_commands['host_ttl_unset'] = Command(
        ("host", "ttl_unset"),
        HostName(),
        perm_filter='is_dns_superuser')

    def host_ttl_unset(self, operator, host_name):
        """Utility command for unsetting TTL, i.e. resetting to default.

        Acts as a proxy to 'host_ttl_set' since its way of resetting
        to default can be somewhat obscure. Provides error-message if
        no TTL is set for given host.

        """
        owner_id = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        if self.mb_utils.get_ttl(owner_id) is None:
            raise CerebrumError("Host '%s' has no explicit TTL set" %
                                host_name)
        self.host_ttl_set(operator, host_name, "")
        return "OK, TTL record for %s reverted to default value" % host_name

    #
    # host ttl_show
    #
    all_commands['host_ttl_show'] = Command(
        ("host", "ttl_show"),
        HostName())

    def host_ttl_show(self, operator, host_name):
        """Display TTL for given host.

        If no specific TTL has been set, TTL is given as 'default',
        rather than listing what the default is.

        """
        owner_id = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        ttl = self.mb_utils.get_ttl(owner_id)
        if ttl is None:
            return "TTL:    Default"
        else:
            return "TTL:    %s" % str(ttl)

    #
    # host txt
    #
    all_commands['host_txt_set'] = Command(
        ("host", "txt_set"),
        HostName(),
        TXT(),
        perm_filter='is_dns_superuser')

    def host_txt_set(self, operator, host_name, txt):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_general_dns_record(
            owner_id, int(self.const.field_type_txt), txt)
        return "OK, %s TXT record for %s" % (operation, host_name)

    #
    # dhcp assoc <ip_or_hostname> <mac> [y|n]
    #
    all_commands['dhcp_assoc'] = Command(
        ("dhcp", "assoc"),
        HostId(),
        MACAdr(),
        Force(optional=True))

    def dhcp_assoc(self, operator, host_id, mac_adr, force=False):
        """Assign/reassign which MAC-address the given host/IP should
        be associated with.

        If there already is a MAC-address associated with the host/IP,
        the change must be forced.

        """
        force = self.dns_parser.parse_force(force)
        if host_id.count(':') > 1:
            ipnumber = IPv6Number.IPv6Number(self.db)
            arecord = AAAARecord.AAAARecord(self.db)
            ip_type = dns.IPv6_NUMBER
            ip_key = 'ipv6_number_id'
            ipu = IPv6Utils
            record_key = 'aaaa_ip'
        else:
            arecord = ARecord.ARecord(self.db)
            ipnumber = IPNumber.IPNumber(self.db)
            ip_type = dns.IP_NUMBER
            ip_key = 'ip_number_id'
            ipu = IPUtils
            record_key = 'a_ip'

        # Identify the host we are dealing with, and retrieve the A-records
        tmp = host_id.split(".")
        if ((host_id.find(":") == -1 and tmp[-1].isdigit()) or
                host_id.count(':') > 2):
            owner_id = self._find.find_target_by_parsing(host_id, ip_type)
            arecords = arecord.list_ext(ip_number_id=owner_id)
        else:
            owner_id = self._find.find_target_by_parsing(host_id,
                                                         dns.DNS_OWNER)
            arecords = arecord.list_ext(dns_owner_id=owner_id)

        if not arecords:
            raise CerebrumError("You can't assoc. a MAC-address with a CNAME")

        # Retrive IPNumber-interface
        ipnumber.clear()
        ipnumber.find(arecords[0][ip_key])

        # Now that we have the IP, ensure operator has proper permissions
        # to do this
        if not self.ba.can_do_lita_dns_by_ip(operator.get_entity_id(),
                                             arecords[0][record_key]):
            raise PermissionDenied("No access to host '{!s}'".format(host_id))

        res = ipnumber.find_by_mac(mac_adr.lower())
        ips = [x[record_key] for x in res]
        in_sub = filter(lambda x: ipu.in_subnet(x), ips)
        not_in_sub = list(set(ips) - set(in_sub))
        in_same_sub = filter(
            lambda x: ipu.same_subnet(x, arecords[0][record_key]),
            ips)

        if not_in_sub or in_same_sub:
            raise CerebrumError("MAC-adr '%s' already in use by '%s'" %
                                (mac_adr, res[0][record_key]))

        # Cannot associate a MAC-address unless we have a single
        # specific address to associate with.
        if len(arecords) != 1:
            raise CerebrumError(
                    "Must have 1 and only 1 IP-address to associate "
                    "MAC-adr (%s has %i)." % (host_id, len(arecords)))

        if ipnumber.mac_adr is not None and not force:
            # Already has MAC = reassign => force required
            raise CerebrumError("%s already associated with %s, use force to "
                                "re-assign" % (host_id, ipnumber.mac_adr))
        ipnumber.mac_adr = mac_adr
        ipnumber.write_db()  # Will raise DNSError if malformed MAC

        return "MAC-adr '{!s}' associated with host '{!s}'".format(
            ipnumber.mac_adr, host_id)

    #
    # dhcp assoc <ip_or_hostname> [y|n]
    #
    all_commands['dhcp_disassoc'] = Command(
        ("dhcp", "disassoc"),
        HostId(),
        Force(optional=True))

    def dhcp_disassoc(self, operator, host_id, force=False):
        """Remove any MAC-addresses registred for the given host/IP.

        If the host has multiple IPs, the removal must be forced.
        """
        force = self.dns_parser.parse_force(force)
        if host_id.count(':') > 1:
            ipnumber = IPv6Number.IPv6Number(self.db)
            arecord = AAAARecord.AAAARecord(self.db)
            ip_type = dns.IPv6_NUMBER
            ip_key = 'ipv6_number_id'
            record_key = 'aaaa_ip'
            compress = _compress_ipv6
        else:
            arecord = ARecord.ARecord(self.db)
            ipnumber = IPNumber.IPNumber(self.db)
            ip_type = dns.IP_NUMBER
            ip_key = 'ip_number_id'
            record_key = 'a_ip'
            compress = _compress_ipv4

        # Identify the host we are dealing with, and retrieve the A-records
        tmp = host_id.split(".")
        if ((host_id.find(":") == -1 and tmp[-1].isdigit()) or
                host_id.count(':') > 2):
            owner_id = self._find.find_target_by_parsing(host_id, ip_type)
            arecords = arecord.list_ext(ip_number_id=owner_id)

            host_id = compress(host_id)
        else:
            owner_id = self._find.find_target_by_parsing(host_id,
                                                         dns.DNS_OWNER)
            arecords = arecord.list_ext(dns_owner_id=owner_id)

        # Now that we have the IP, ensure operator has proper
        # permissions to do this
        if not self.ba.can_do_lita_dns_by_ip(operator.get_entity_id(),
                                             arecords[0][record_key]):
            raise PermissionDenied("No access to host '{!s}'".format(host_id))

        if len(arecords) != 1 and not force:
            raise CerebrumError("Host has multiple A-records, must force (y)")

        old_macs = set()
        for arecord_row in arecords:
            ipnumber.clear()
            ipnumber.find(arecord_row[ip_key])
            if ipnumber.mac_adr is None:
                continue

            old_macs.add(ipnumber.mac_adr)  # For informational purposes only
            ipnumber.mac_adr = None
            ipnumber.write_db()

        if not old_macs:
            # Nothing to do
            raise CerebrumError(
                "No MAC-adr found for host '{!s}'".format(host_id))

        return "MAC-adr '{!s}' no longer associated with '{!s}'".format(
            "','".join(old_macs), host_id)


HELP_DNS_GROUPS = {
    'host': "Commands for administrating IP numbers",
    'group': "Group commands",
    'dhcp': 'Commands for handling MAC-IP associations'
}

# The texts in command_help are automatically line-wrapped, and should
# not contain \n
HELP_DNS_CMDS = {
    'host': {
        'host_a_add':
            'Add an A record',
        'host_a_remove':
            'Remove an A record',
        'host_add':
            'Add a new host with IP address',
        'host_cname_add':
            'Add a CNAME',
        'host_cname_remove':
            'Remove a CNAME',
        'host_comment':
            'Set comment for a host',
        'host_contact':
            'Set contact for a host',
        'host_find':
            'List hosts matching search criteria',
        'host_remove':
            'Remove data for specified host or IP',
        'host_hinfo_list':
            'List acceptable HINFO values',
        'host_hinfo_set':
            'Set HINFO',
        'host_history':
            'Show history for a host',
        'host_info':
            'List data for given host, IP-address or CNAME',
        'host_unused_list':
            'List unused IP addresses',
        'host_used_list':
            'List used IP addresses',
        'host_mx_set':
            'Set MX for host to specified MX definition',
        'host_mx_unset':
            'Remove MX from host',
        'host_mxdef_add':
            'Add host to MX definition',
        'host_mxdef_remove':
            'Remove host from MX definition',
        'host_mxdef_show':
            'List all MX definitions, or show hosts in one MX definition',
        'host_rename':
            'Rename an IP address or hostname',
        'host_ptr_add':
            'Add override for IP reverse map',
        'host_ptr_remove':
            'Remove override for IP reverse map',
        'host_srv_add':
            'Add a SRV record',
        'host_srv_remove':
            'Remove a SRV record',
        'host_ttl_set':
            'Set TTL for a host',
        'host_ttl_unset':
            'Revert TTL for a host back to default',
        'host_ttl_show':
            'Display TTL for a host',
        'host_txt_set':
            'Set TXT for a host',
    },
    'group': {
        'group_hadd':
            'Add machine to a netgroup',
        'group_host':
            'List groups where host is a member',
        'group_hrem':
            'Remove machine from a netgroup'
    },
    'dhcp': {
        'dhcp_assoc':
            'Associate a MAC-address with an IP-address',
        'dhcp_disassoc':
            'Remove associattion between a MAC-address and an IP-address',
    }
}

HELP_DNS_ARGS = {
    'group_name_dest':
        ['gname', 'Enter the destination group'],
    'group_operation':
        ['op', 'Enter group operation',
         'Three values are legal: union, intersection and difference.'
         ' Normally only union is used.'],
    'ip_number':
        ['ip', 'Enter IP number',
         'Enter the IP number for this operation'],
    'host_id':
        ['host_id', 'Enter host_id',
         'Enter a unique host_id for this machine,'
         ' typicaly the DNS name or IP'],
    'new_host_id_or_clear':
        ['new_host_id', 'Enter new host_id/leave blank',
         'Enter a new host_id, or leave blank to clear'],
    'host_name':
        ['host_name', 'Enter host name',
         'Enter the host name for this operation'],
    'host_name_exist':
        ['existing_host', 'Enter existing host name',
         'Enter the host name for this operation'],
    'host_name_alias':
        ['alias_name', 'Enter new alias',
         'Enter the alias name for this operation'],
    'host_name_repeat':
        ['host_name_repeat', 'Enter host name(s)',
         'To specify 20 names starting at pcusitN+1, where N is '
         'the highest currently existing number, use pcusit#20.  To '
         'get the names pcusit20 to pcusit30 use pcusit#20-30.'],
    'host_name_rename_new':
        ['host_name', 'Enter new host name',
         'Enter the new host name to give this host'],
    'host_search_pattern':
        ['pattern', 'Enter pattern',
         'Use ? and * as wildcard characters. If there are no'
         ' wildcards, it will be a substring search. If there are no'
         ' capital letters, the search will be case-insensitive.'],
    'host_search_type':
        ['search_type', 'Enter search type',
         'You can search by "name", "comment" or "contact".'],
    'service_name':
        ['service_name', 'Enter service name',
         'Enter the service name for this operation'],
    'subnet_or_ip':
        ['subnet_or_ip', 'Enter subnet or ip',
         'Enter subnet or ip for this operation.  129.240.x.y = IP. '
         '129.240.x or 129.240.x.y/ indicates a subnet.'],
    'number_or_range':
        ['number_or_range', 'Enter a number or range',
         'Enter a number (ex. 5) or a range (ex. 5-10).'],
    'hinfo':
        ['hinfo', 'Enter HINFO code',
         'Legal values are: \n%s' % "\n".join(
             (" - %-8s -> %s" % (k, v)
              for k, v in LEGAL_HINFO.items()))],
    'mx_set':
        ['mxdef', 'Enter name of mxdef',
         'Use "host mxdef_show" to get a list of legal values'],
    'contact':
        ['contact', 'Enter contact',
         'Typically an e-mail address'],
    'comment':
        ['comment', 'Enter comment',
         'Typically location'],
    'txt':
        ['txt', 'Enter TXT value'],
    'pri':
        ['pri', 'Enter priority value'],
    'weight':
        ['weight', 'Enter weight value'],
    'port':
        ['port', 'Enter port value'],
    'ttl':
        ['ttl', 'Enter TTL value'],
    'mac_adr':
        ['mac_adr', 'Enter MAC-address'],
    'force':
        ['force', 'Force the operation',
         'Enter y to force the operation'],
    'show_policy':
        ['policy', 'Show policies? (policy)',
         'If argument is "policy", all hostpolicies related to the'
         ' given host will be listed'],
    'allow_dns_underscores':
        ['allow_dns_underscores', 'Allow underscores in DNS entries?',
         'Enter y to allow underscores. If in doubt, do not enter y.'],
}
