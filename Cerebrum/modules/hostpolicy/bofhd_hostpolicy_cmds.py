# -*- coding: iso-8859-1 -*-
# Copyright 2011 University of Oslo, Norway
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
from Cerebrum import Cache
#from Cerebrum.Errors import NotFoundError
#from Cerebrum.Entity import Entity
from Cerebrum.Utils import Factory, argument_to_sql

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth


class HostPolicyBofhdAuth(BofhdAuth):
    """Specialized bofhd-auth for the Hostpolicy bofhd-extension.

    Though a module of its own, Hostpolicy-commands use the same
    access groups as the DNS-module (on which it depends anyway), so
    the same mechanisms used there are also used here.
    
    """
    # TODO: This should be put somepace better, more generic and less
    # repetetive
    def assert_dns_superuser(self, operator, query_run_any=False):
        if (not (self.is_dns_superuser(operator)) and
            not (self.is_superuser(operator))):
            raise PermissionDenied("Currently limited to dns_superusers")

    def is_dns_superuser(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        return self._has_operation_perm_somewhere(
            operator, self.const.auth_dns_superuser)



class HostPolicyBofhdExtension(BofhdCommandBase):
    """Class to expand bofhd with commands for manipulating host
    policies.

    """

    all_commands = {}

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        self.ba = HostPolicyBofhdAuth(self.db)


    def get_help_strings(self):
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
            
            'subnet_name_prefix':
            ['name_prefix', 'Name prefix',
             """Name-prefix to be used for the given subnet """],
            
            'subnet_reserved':
            ['#_reserved_adr', 'Number of reserved addresses',
             """Number of adresses to set as reserved at the beginning of the given subnet."""],
            
            'subnet_vlan':
            ['vlan_id', 'VLAN ID number',
             """ID of the VLAN the subnet uses/represents."""],
            }

        return (group_help, command_help,
                arg_help)




if __name__ == '__main__':
    pass
