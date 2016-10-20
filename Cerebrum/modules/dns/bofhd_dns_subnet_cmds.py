# -*- coding: utf-8 -*-
#
# Copyright 2013-2016 University of Oslo, Norway
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

import cereconf

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import *

from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth

from Cerebrum.modules.dns.Subnet import Subnet
from Cerebrum.modules.dns.IPv6Subnet import IPv6Subnet
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum.modules.dns.IPv6Utils import IPv6Calc

from Cerebrum.modules.dns.Errors import SubnetError


class Force(Parameter):
    _type = 'force'
    _help_ref = 'force'


class SubnetIdentifier(Parameter):
    """Represents subnet-parameters given to bofh"""
    _type = 'subnet_identifier'
    _help_ref = 'subnet_identifier'


class DnsBofhdAuth(BofhdAuth):
    # TODO: Shouldn't need to repeat it here, but bofhd_dns_cmds is
    # cranky when you try to import it
    def assert_dns_superuser(self, operator, query_run_any=False):
        if (not (self.is_dns_superuser(operator))
                and not (self.is_superuser(operator))):
            raise PermissionDenied("Currently limited to dns_superusers")

    def is_dns_superuser(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        return self._has_operation_perm_somewhere(
            operator, self.const.auth_dns_superuser)


class BofhdExtension(BofhdCommandBase):
    """Class to expand bofhd with commands for manipulating subnets."""

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
            from Cerebrum.modules.dns import Utils
            self.__find_util = Utils.Find(self.db, self.default_zone)
            return self.__find_util

    @classmethod
    def get_help_strings(cls):
        group_help = {
            'subnet': "Commands for handling subnets",
        }

        command_help = {
            'subnet': {
            #'subnet_add': 'Add a new subnet with given description and optional given VLAN',
            #'subnet_remove': 'Remove an existing subnet',
            'subnet_info': 'Provide information about a subnet',
            'subnet_set_vlan': 'Set VLAN-ID for a subnet',
            'subnet_set_description': 'Set description for a subnet',
            'subnet_set_dns_delegated': 'Set subnet zone as delegated to external DNS-server',
            'subnet_set_name_prefix': 'Set name-prefix for a subnet',
            'subnet_set_reserved': 'Set number of reserved addresses for a subnet',
            'subnet_unset_dns_delegated': 'Set subnet zone as not delegated to external DNS-server',
            }
        }

        arg_help = {
            'subnet_description':
            ['desc', 'Subnet description',
             """Description of what the subnet is intended for."""],

            'subnet_identifier':
            ['subnet', 'Subnet',
             """Subnet identifier, either on format
- ddd.ddd.ddd.ddd/dd                                    OR
- ddd.ddd.ddd.ddd    (for any IP in the subnet's range) OR
- id:<entity-id>"""],
            'subnet_name_prefix':
            ['name_prefix', 'Name prefix',
             """Name-prefix to be used for the given subnet """],
            'subnet_reserved':
            ['#_reserved_adr', 'Number of reserved addresses',
             """Number of adresses to set as reserved at the beginning of the given subnet."""],
            'subnet_vlan': [
                'vlan_id',
                'VLAN ID number',
                """ID of the VLAN the subnet uses/represents."""
            ],
        }

        return (group_help,
                command_help,
                arg_help)

    all_commands['subnet_info'] = Command(
        ("subnet", "info"), SubnetIdentifier(),
        fs=FormatSuggestion([("Subnet:                 %s\n" +
                              "Entity ID:              %s",
                             ("subnet", "entity_id")),
                             ("Netmask:                %s", ("netmask",)),
                             ("Prefix:                 %s", ("prefix",)),
                             ("Description:            '%s'\n" +
                              "Name-prefix:            '%s'\n" +
                              "VLAN:                   %s\n" +
                              "DNS delegated:          %s\n" + 
                              "IP-range:               %s\n" +
                              "Reserved host adresses: %s\n" +
                              "Reserved addresses:     %s",
                              ("desc",
                               "name_prefix", "vlan", "delegated",
                               "ip_range", "no_of_res_adr", "res_adr1")),
                             ("                        %s", ('res_adr',)),
                             ("Used addresses:         %s\n"+
                              "Unused addresses:       %s (excluding reserved adr.)",
                              ('used', 'unused'))]))
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
        s = Subnet(self.db)
        ipc = IPCalc
        try:
            s.find(identifier)
        except (ValueError, SubnetError):
            s = IPv6Subnet(self.db)
            s.find(identifier)
            ipc = IPv6Calc
        
        if s.dns_delegated:
            delegated = "Yes"
        else:
            delegated = "No"
            
        data = {'subnet': "%s/%s" % (s.subnet_ip, s.subnet_mask),
               'entity_id': str(s.entity_id),
               'desc': s.description,
               'delegated': delegated,
               'name_prefix': s.name_prefix,
               'no_of_res_adr': str(s.no_of_reserved_adr)}
        
        if isinstance(s, Subnet):
            data['netmask'] = ipc.netmask_to_ip(s.subnet_mask)
        else:
            data['prefix'] = '/' + str(s.subnet_mask)
    

        if s.vlan_number is not None:
            data['vlan'] = str(s.vlan_number)
        else:
            data['vlan'] =  "(None)"

        data['ip_range'] = "%s - %s" % (ipc.long_to_ip(s.ip_min),
                                        ipc.long_to_ip(s.ip_max))

        # Calculate number of used and unused IP-addresses on this subnet
        #                              ^^^^^^ excluding reserved addresses
        uip = self._find.count_used_ips(s.subnet_ip)
        data['used'] = str(uip)
        data['unused'] = str(s.ip_max - s.ip_min - uip - 1)
        
        reserved_adresses = list(s.reserved_adr)

        if reserved_adresses:
            reserved_adresses.sort()
            data["res_adr1"] = "%s (net)" % ipc.long_to_ip(reserved_adresses.pop(0))
        else:
            data["res_adr1"] = "(None)"

        ret = [data,]

        if reserved_adresses:
            last_ip = reserved_adresses.pop()
            for address in reserved_adresses:
                ret.append({'res_adr': ipc.long_to_ip(address)})
            ret.append({'res_adr': "%s (broadcast)" % ipc.long_to_ip(last_ip)})
            
        return ret


    all_commands['subnet_set_vlan'] = Command(
        ("subnet", "set_vlan"),
        SubnetIdentifier(),
        Integer(help_ref="subnet_vlan"))
    def subnet_set_vlan(self, operator, identifier, new_vlan):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        try:
            int(new_vlan)
        except:
            raise CerebrumError("VLAN must be an integer; '%s' isn't" % new_vlan)

        s = Subnet(self.db)
        try:
            s.find(identifier)
        except SubnetError:
            s = IPv6Subnet(self.db)
            s.find(identifier)
        old_vlan = s.vlan_number
        s.vlan_number = new_vlan
        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return "OK; VLAN for subnet %s updated from '%s' to '%s'" % (subnet_id, old_vlan, new_vlan)


    all_commands['subnet_set_description'] = Command(
        ("subnet", "set_description"),
        SubnetIdentifier(),
        SimpleString(help_ref="subnet_description"))
    def subnet_set_description(self, operator, identifier, new_description):
        raise CerebrumError('Description updates are not allowed for the time beeing.')
        self.ba.assert_dns_superuser(operator.get_entity_id())
        
        s = Subnet(self.db)
        try:
            s.find(identifier)
        except SubnetError:
            s = IPv6Subnet(self.db)
            s.find(identifier)

        s.description = new_description
        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return "OK; description for subnet %s updated to '%s'" % (subnet_id, new_description)
        

    all_commands['subnet_set_name_prefix'] = Command(
        ("subnet", "set_name_prefix"),
        SubnetIdentifier(),
        SimpleString(help_ref="subnet_name_prefix"))
    def subnet_set_name_prefix(self, operator, identifier, new_prefix):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        
        s = Subnet(self.db)
        try:
            s.find(identifier)
        except SubnetError:
            s = IPv6Subnet(self.db)
            s.find(identifier)

        old_prefix = s.name_prefix
        s.name_prefix = new_prefix
        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return ("OK; name_prefix for subnet %s updated " % subnet_id +
                "from '%s' to '%s'" % (old_prefix, new_prefix))


    all_commands['subnet_set_dns_delegated'] = Command(
        ("subnet", "set_dns_delegated"),
        SubnetIdentifier(), Force(optional=True))
    def subnet_set_dns_delegated(self, operator, identifier, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        
        s = Subnet(self.db)
        try:
            s.find(identifier)
        except SubnetError:
            s = IPv6Subnet(self.db)
            s.find(identifier)

        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)

        if s.dns_delegated:
            return ("Subnet %s is already set as " % subnet_id +
                    "being delegated to external DNS server")

        in_use = ""
        if s.has_adresses_in_use():
            if force:
                in_use = "\nNote! Subnet has addresses in use!"
            else:
                raise CerebrumError, ("Subnet '%s' has addresses " % subnet_id +
                                      "in use; must force to delegate")

        s.dns_delegated = True
        s.write_db(perform_checks=False)
        return "Subnet %s set as delegated to external DNS server%s" % (subnet_id, in_use)
        
        
    all_commands['subnet_unset_dns_delegated'] = Command(
        ("subnet", "unset_dns_delegated"),
        SubnetIdentifier())
    def subnet_unset_dns_delegated(self, operator, identifier):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        
        s = Subnet(self.db)
        try:
            s.find(identifier)
        except SubnetError:
            s = IPv6Subnet(self.db)
            s.find(identifier)

        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)

        if not s.dns_delegated:
            return ("Subnet %s is already set as not " % subnet_id +
                    "being delegated to external DNS server" )

        s.dns_delegated = False
        s.write_db(perform_checks=False)
        return "Subnet %s no longer set as delegated to external DNS server" % subnet_id
    

    all_commands['subnet_set_reserved'] = Command(
        ("subnet", "set_reserved"),
        SubnetIdentifier(),
        Integer(help_ref="subnet_reserved"))
    def subnet_set_reserved(self, operator, identifier, new_res):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        
        try:
            int(new_res)
        except:
            raise CerebrumError("The number of reserved addresses must be " +
                                "an integer; '%s' isn't" % new_res)

        if new_res < 0:
            raise CerebrumError("Cannot set number of reserved addresses to " +
                                "a negative number such as '%s'" % new_res)
       
        s = Subnet(self.db)
        try:
            s.find(identifier)
        except SubnetError:
            s = IPv6Subnet(self.db)
            s.find(identifier)

        old_res = s.no_of_reserved_adr

        s.no_of_reserved_adr = int(new_res)
        s.calculate_reserved_addresses()

        in_use = ""
        if new_res > old_res:
            try:
                s.check_reserved_addresses_in_use()
            except SubnetError, se:
                in_use = "\nFYI: %s" % str(se)

        s.write_db(perform_checks=False)
        subnet_id = "%s/%s" % (s.subnet_ip, s.subnet_mask)
        return ("OK; Number of reserved addresses for subnet %s " % subnet_id +
                "updated from '%s' to '%s'%s" % (old_res, new_res, in_use))


if __name__ == '__main__':
    pass

