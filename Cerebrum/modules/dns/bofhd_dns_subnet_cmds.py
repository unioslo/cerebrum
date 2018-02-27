# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
""" dns subnet commands for bofhd. """
import cereconf

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (Command,
                                              FormatSuggestion,
                                              Integer,
                                              Parameter,
                                              SimpleString)
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.dns import Utils
from Cerebrum.modules.dns.Errors import DNSError, SubnetError
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum.modules.dns.IPv6Subnet import IPv6Subnet
from Cerebrum.modules.dns.IPv6Utils import IPv6Calc
from Cerebrum.modules.dns.Subnet import Subnet
from Cerebrum.modules.dns.bofhd_dns_cmds import DnsBofhdAuth


class SubnetBofhdAuth(DnsBofhdAuth):
    """ DNS auth. """
    pass


class Force(Parameter):
    _type = 'force'
    _help_ref = 'force'


class SubnetIdentifier(Parameter):
    """Represents subnet-parameters given to bofh"""
    _type = 'subnet_identifier'
    _help_ref = 'subnet_identifier'


def _is_ipv6(subnet):
    return isinstance(subnet, IPv6Subnet)


def _subnet_to_identifier(subnet):
    return "{0.subnet_ip}/{0.subnet_mask}".format(subnet)


class BofhdExtension(BofhdCommandBase):
    """Class to expand bofhd with commands for manipulating subnets."""

    all_commands = {}
    parent_commands = False
    authz = SubnetBofhdAuth

    def __init__(self, *args, **kwargs):
        default_zone = getattr(cereconf, 'DNS_DEFAULT_ZONE',
                               kwargs.pop('default_zone', 'uio'))
        super(BofhdExtension, self).__init__(*args, **kwargs)
        self.default_zone = self.const.DnsZone(default_zone)

    @property
    def _find(self):
        try:
            return self.__find_util
        except AttributeError:
            self.__find_util = Utils.Find(self.db, self.default_zone)
            return self.__find_util

    def _get_subnet_ipv4(self, subnet_identifier):
        try:
            s = Subnet(self.db)
            s.find(subnet_identifier)
            return s
        except (ValueError, SubnetError, DNSError):
            raise CerebrumError("Unable to find subnet %r" % subnet_identifier)

    def _get_subnet_ipv6(self, subnet_identifier):
        try:
            s = IPv6Subnet(self.db)
            s.find(subnet_identifier)
            return s
        except (ValueError, SubnetError, DNSError):
            raise CerebrumError("Unable to find subnet %r" % subnet_identifier)

    def _get_subnet(self, subnet_identifier):
        try:
            return self._get_subnet_ipv4(subnet_identifier)
        except CerebrumError:
            return self._get_subnet_ipv6(subnet_identifier)

    @classmethod
    def get_help_strings(cls):
        _, _, args = get_help_strings()
        return merge_help_strings(
            ({}, {}, args),
            (HELP_SUBNET_GROUP, HELP_SUBNET_CMDS, HELP_SUBNET_ARGS))

    #
    # subnet info <subnet>
    #
    all_commands['subnet_info'] = Command(
        ("subnet", "info"),
        SubnetIdentifier(),
        fs=FormatSuggestion([
            ("Subnet:                 %s", ('subnet', )),
            ("Entity ID:              %s", ('entity_id', )),
            ("Netmask:                %s", ('netmask', )),
            ("Prefix:                 %s", ("prefix", )),
            ("Description:            '%s'\n"
             "Name-prefix:            '%s'\n"
             "VLAN:                   %s\n"
             "DNS delegated:          %s\n"
             "IP-range:               %s", ("desc", "name_prefix", "vlan",
                                            "delegated", "ip_range")),
            ("Reserved host adresses: %s", ("no_of_res_adr", )),
            ("Reserved addresses:     %s", ("res_adr1", )),
            ("                        %s", ('res_adr', )),
            ("Used addresses:         %i\n"
             "Unused addresses:       %i (excluding reserved adr.)",
             ('used', 'unused')),
        ]))

    def subnet_info(self, operator, identifier):
        """Lists the following information about the given subnet:

        * Subnett
        * Netmask
        * Entity ID
        * Description
        * Name-prefix
        * VLAN number
        * DNS-delegation status
        * Range of IPs on subnet
        * Number of reserved addresses
        * A list of the reserved adresses
        """
        s = self._get_subnet(identifier)
        is_ipv6 = isinstance(s, IPv6Subnet)
        ipc = IPv6Calc if is_ipv6 else IPCalc

        data = {
            'subnet': _subnet_to_identifier(s),
            'entity_id': str(s.entity_id),
            'desc': s.description,
            'delegated': "Yes" if s.dns_delegated else "No",
            'name_prefix': s.name_prefix,
            'no_of_res_adr': str(s.no_of_reserved_adr)
        }

        # ipv4 netmask or ipv6 prefix
        if isinstance(s, Subnet):
            data['netmask'] = ipc.netmask_to_ip(s.subnet_mask)
        else:
            data['prefix'] = '/' + str(s.subnet_mask)

        if s.vlan_number is not None:
            data['vlan'] = str(s.vlan_number)
        else:
            data['vlan'] = "(None)"

        data['ip_range'] = "%s - %s" % (ipc.long_to_ip(s.ip_min),
                                        ipc.long_to_ip(s.ip_max))

        # Calculate number of used and unused IP-addresses on this subnet
        #                              ^^^^^^ excluding reserved addresses
        uip = self._find.count_used_ips(s.subnet_ip)
        data['used'] = int(uip)
        data['unused'] = int(s.ip_max - s.ip_min - uip - 1)

        reserved_adresses = list(sorted(s.reserved_adr))

        if reserved_adresses:
            data["res_adr1"] = "%s (net)" % ipc.long_to_ip(
                reserved_adresses.pop(0))
        else:
            data["res_adr1"] = "(None)"

        ret = [data, ]

        if reserved_adresses:
            last_ip = reserved_adresses.pop()
            for address in reserved_adresses:
                ret.append({
                    'res_adr': ipc.long_to_ip(address),
                })
            ret.append({
                'res_adr': "%s (broadcast)" % ipc.long_to_ip(last_ip),
            })

        return ret

    #
    # subnet set_vlan <subnet> <vlan>
    #
    all_commands['subnet_set_vlan'] = Command(
        ("subnet", "set_vlan"),
        SubnetIdentifier(),
        Integer(help_ref="subnet_vlan"),
        fs=FormatSuggestion([
            ("OK; VLAN for subnet %s updated from %i to %i",
             ('subnet_id', 'old_vlan', 'new_vlan')),
        ]),
        perm_filter='is_dns_superuser')

    def subnet_set_vlan(self, operator, identifier, new_vlan):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        try:
            new_vlan = int(new_vlan)
        except:
            raise CerebrumError("VLAN must be an integer; %r isn't" %
                                new_vlan)

        s = self._get_subnet(identifier)
        old_vlan = s.vlan_number
        s.vlan_number = new_vlan
        s.write_db(perform_checks=False)
        return {
            'subnet_id': _subnet_to_identifier(s),
            'old_vlan': old_vlan,
            'new_vlan': new_vlan,
        }

    #
    # subnet set_description <subnet> <description>
    #
    all_commands['subnet_set_description'] = Command(
        ("subnet", "set_description"),
        SubnetIdentifier(),
        SimpleString(help_ref="subnet_description"),
        fs=FormatSuggestion([
            ("OK; description for subnet %s updated to '%s'",
             ('subnet_id', 'new_description')),
        ])
    )

    def subnet_set_description(self, operator, identifier, new_description):
        self.ba.assert_dns_superuser(operator.get_entity_id())

        s = self._get_subnet(identifier)
        old_description = s.description or ''
        s.description = new_description
        s.write_db(perform_checks=False)
        subnet_id = _subnet_to_identifier(s)
        return {
            'subnet_id': subnet_id,
            'old_description': old_description,
            'new_description': new_description,
        }

    #
    # subnet set_name_prefix
    #
    all_commands['subnet_set_name_prefix'] = Command(
        ("subnet", "set_name_prefix"),
        SubnetIdentifier(),
        SimpleString(help_ref="subnet_name_prefix"),
        fs=FormatSuggestion([
            ("OK; name_prefix for subnet %s updated from '%s' to '%s'",
             ('subnet_id', 'old_prefix', 'new_prefix'))
        ]),
        perm_filter='is_dns_superuser')

    def subnet_set_name_prefix(self, operator, identifier, new_prefix):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = self._get_subnet(identifier)
        old_prefix = s.name_prefix
        s.name_prefix = new_prefix
        s.write_db(perform_checks=False)
        subnet_id = self._subnet_to_identifier(s)
        return {
            'subnet_id': subnet_id,
            'old_prefix': old_prefix,
            'new_prefix': new_prefix,
        }

    #
    # subnet set_dns_delegated
    #
    all_commands['subnet_set_dns_delegated'] = Command(
        ("subnet", "set_dns_delegated"),
        SubnetIdentifier(),
        Force(optional=True),
        fs=FormatSuggestion([
            ("Subnet %s set as delegated to external"
             " DNS server", ('subnet_id',)),
            ("Note: %s", ('warning', )),
        ]),
        perm_filter='is_dns_superuser')

    def subnet_set_dns_delegated(self, operator, identifier, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())

        s = self._get_subnet(identifier)
        subnet_id = _subnet_to_identifier(s)

        if s.dns_delegated:
            raise CerebrumError("Subnet %s is already set as being delegated"
                                " to external DNS server" % subnet_id)

        ret = [{'subnet_id': subnet_id, }]

        if s.has_adresses_in_use():
            if not force:
                raise CerebrumError("Subnet '%s' has addresses in use;"
                                    " must force to delegate" % subnet_id)
            ret.append({'warning': "Subnet has address in use!"})

        s.dns_delegated = True
        s.write_db(perform_checks=False)
        return ret

    #
    # subnet unset_dns_delegated
    #
    all_commands['subnet_unset_dns_delegated'] = Command(
        ("subnet", "unset_dns_delegated"),
        SubnetIdentifier(),
        fs=FormatSuggestion([
            ("Subnet %s no longer set as delegated to external"
             " DNS server", ('subnet_id',)),
        ]),
        perm_filter='is_dns_superuser')

    def subnet_unset_dns_delegated(self, operator, identifier):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        s = self._get_subnet(identifier)
        subnet_id = _subnet_to_identifier(s)

        if not s.dns_delegated:
            raise CerebrumError("Subnet %s is already set as not being"
                                " delegated to external DNS server" %
                                subnet_id)

        s.dns_delegated = False
        s.write_db(perform_checks=False)
        return {'subnet_id': subnet_id, }

    #
    # subnet set_reserved
    #
    all_commands['subnet_set_reserved'] = Command(
        ("subnet", "set_reserved"),
        SubnetIdentifier(),
        Integer(help_ref="subnet_reserved"),
        fs=FormatSuggestion([
            ("OK; Number of reserved addresses for subnet %s "
             "updated from %i to %i", ('subnet_id', 'old_reserved',
                                       'new_reserved')),
            ("FIY: %s", ('warning', )),
        ]),
        perm_filter='is_dns_superuser')

    def subnet_set_reserved(self, operator, identifier, new_res):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        try:
            new_res = int(new_res)
        except:
            raise CerebrumError("The number of reserved addresses must be "
                                "an integer; %r isn't" % new_res)

        if new_res < 0:
            raise CerebrumError("Cannot set number of reserved addresses to " +
                                "a negative number such as '%s'" % new_res)

        s = self._get_subnet(identifier)

        old_res = s.no_of_reserved_adr

        s.no_of_reserved_adr = new_res
        s.calculate_reserved_addresses()

        res = [{
            'subnet_id': _subnet_to_identifier(s),
            'old_reserved': old_res,
            'new_reserved': new_res,
        }]

        if new_res > old_res:
            try:
                s.check_reserved_addresses_in_use()
            except SubnetError as se:
                res.append({'warning': str(se), })

        s.write_db(perform_checks=False)
        return res


HELP_SUBNET_GROUP = {
    'subnet': "Commands for handling subnets",
}

HELP_SUBNET_CMDS = {
    'subnet': {
        'subnet_info':
            'Provide information about a subnet',
        'subnet_set_vlan':
            'Set VLAN-ID for a subnet',
        'subnet_set_description':
            'Set description for a subnet',
        'subnet_set_dns_delegated':
            'Set subnet zone as delegated to external DNS-server',
        'subnet_set_name_prefix':
            'Set name-prefix for a subnet',
        'subnet_set_reserved':
            'Set number of reserved addresses for a subnet',
        'subnet_unset_dns_delegated':
            'Set subnet zone as not delegated to external DNS-server',
    }
}

HELP_SUBNET_ARGS = {
    'subnet_description':
        ['desc', 'Enter subnet description',
         "Description of what the subnet is intended for."],
    'subnet_identifier':
        ['subnet', 'Enter subnet',
         "Subnet identifier, either on format"
         "  - ddd.ddd.ddd.ddd/dd                                    OR"
         "  - ddd.ddd.ddd.ddd    (for any IP in the subnet's range) OR"
         "  - id:<entity-id>"],
    'subnet_name_prefix':
        ['name_prefix', 'Enter subnet name prefix',
         "Name-prefix to be used for the given subnet "],
    'subnet_reserved':
        ['#_reserved_adr', 'Enter number of reserved addresses',
         "Number of adresses to set as reserved at the beginning of the"
         " given subnet."],
    'subnet_vlan':
        ['vlan_id', 'Enter VLAN ID number',
         "ID of the VLAN the subnet uses/represents."],
}
