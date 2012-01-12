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

import cerebrum_path, cereconf
from Cerebrum import Cache, Errors
#from Cerebrum.Entity import Entity
from Cerebrum.Utils import Factory, argument_to_sql

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uio.bofhd_auth import BofhdAuth
from Cerebrum.modules.dns.bofhd_dns_cmds import HostId

from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent, Role, Atom


class HostPolicyBofhdAuth(BofhdAuth):
    """Specialized bofhd-auth for the Hostpolicy bofhd-extension.

    Though a module of its own, Hostpolicy-commands use the same access groups
    as the DNS-module (on which it depends anyway), so the same mechanisms used
    there are also used here.
    
    """
    # TODO: This should be put somepace better, more generic and less
    # repetetive
    # TODO: it should have the dns module's BofhdAuth as its superclass
    def assert_dns_superuser(self, operator, query_run_any=False):
        if (not (self.is_dns_superuser(operator)) and
            not (self.is_superuser(operator))):
            raise PermissionDenied("Currently limited to dns_superusers")

    def is_dns_superuser(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        return self._has_operation_perm_somewhere(
            operator, self.const.auth_dns_superuser)

# TODO: should this be moved to Cerebrum/modules/bofhd/cmd_param.py?
# Define cmd_params for HostPolicy:
class AtomId(Parameter):
    _type = 'atom'
    _help_ref = 'atom_id'
class AtomName(Parameter):
    _type = 'name' # TODO: check what these means
    _help_ref = 'atom_name'

class RoleId(Parameter):
    _type = 'role'
    _help_ref = 'role_id'
class RoleName(Parameter):
    _type = 'name'
    _help_ref = 'role_name'

class PolicyId(Parameter):
    _type = 'policy'
    _help_ref = 'policy_id'

class CreateDate(Parameter):
    _type = 'date'
    _help_ref = 'create_date'

class HostPolicyBofhdExtension(BofhdCommandBase):
    """Class to expand bofhd with commands for manipulating host
    policies.

    """

    all_commands = {}

    def __init__(self, server):
        super(HostPolicyBofhdExtension, self).__init__(server)
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
            'subnet_set_vlan': 'Set VLAN-Id for a subnet',
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
            ['vlan_id', 'VLAN Id number',
             """Id of the VLAN the subnet uses/represents."""],
            }

        return (group_help, command_help,
                arg_help)

    def _get_component(self, comp_id, comp_class=PolicyComponent):
        """Helper method for getting a component, or a given subtype."""
        comp = comp_class(self.db)
        try:
            if type(comp_id) == int or comp_id.isdigit():
                comp.find(comp_id)
            else:
                comp.find_by_name(comp_id)
        except Errors.NotFoundError:
            raise CerebrumError("Couldn't find component with id=%s" % comp_id)
        return comp

    def _get_atom(self, atom_id):
        """Helper method for getting an atom."""
        return self._get_component(atom_id, Atom)

    def _get_role(self, role_id):
        """Helper method for getting a role."""
        return self._get_component(atom_id, Role)

    all_commands['policy_atom_add'] = Command(
            ('policy', 'atom_add'),
            AtomId(), AtomName(), SimpleString(help_ref='description'),
            SimpleString(help_ref='foundation'), CreateDate(optional=True),
            # TODO: make create_date optional
            perm_filter='is_dns_superuser')
    def policy_atom_add(self, operator, name, description, foundation,
                        create_date):
        """Adds a new atom and its data. Its can only consist of lowercased,
        alpha numrice characters and -."""
        assert_dns_superuser(operator.get_entity_id())
        atom = Atom(self.db)
        # TODO: data should be validated - e.g. isn't ';' allowed
        atom.new(name, description, foundation, create_date)
        return "New atom %s created" % atom.component_name

    all_commands['policy_atom_remove'] = Command(
            ('policy', 'atom_remove'),
            AtomId(),
            perm_filter='is_dns_superuser')
    def policy_atom_remove(self, operator, atom_id):
        """Try to remove an atom if it hasn't been used in any policy or
        relationship."""
        assert_dns_superuser(operator.get_entity_id())
        atom = self._get_atom(atom_id)
        # TODO: check if the atom has any relationship and/or is in any active
        # policy - if so: fail
        name = atom.component_name
        atom.delete()
        atom.write_db()
        return "Atom %s deleted" % name

    all_commands['policy_role_add'] = Command(
            ('policy', 'role_add'),
            RoleName(), SimpleString(help_ref='description'),
            SimpleString(help_ref='foundation'), CreateDate(),
            # TODO: make create_date optional
            perm_filter='is_dns_superuser')
    def policy_role_add(self, operator, name, description, foundation,
                        create_date=None):
        """Adds a new role and its data. Its can only consist of lowercased,
        alpha numrice characters and -."""
        assert_dns_superuser(operator.get_entity_id())
        role = role(self.db)
        # TODO: validate data - ';' isn't allowed, for instance
        role.new(name, description, foundation, create_date)
        return "New role %s created" % role.component_name
    
    all_commands['policy_role_remove'] = Command(
            ('policy', 'role_remove'), RoleId(),
            perm_filter='is_dns_superuser')
    def policy_role_remove(self, operator, role_id):
        """Try to remove a given role if it's not in any relationship, or is in
        any policy."""
        assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        # TODO: check if any relation and/or policy, and then list these.
        name = role.component_name
        role.delete()
        role.write_db()
        return "Role %s deleted" % name

    all_commands['policy_add_member'] = Command(
            ('policy', 'add_member'),
            RoleId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def policy_add_member(self, operator, role_id, member_id):
        """Try to add a given component as a member of a role."""
        assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        member = self._get_component(member_id)
        
        # TODO: add checking to comply with the constraints
        # Give feedback about _what_ is wrong, if so
        role.add_relationship(self.const.hostpolicy_contains, member.entity_id)
        role.write_db()
        return "Component %s is now member of role %s" % (member.component_name,
                                                          role.component_name)

    all_commands['policy_remove_member'] = Command(
            ('policy', 'remove_member'),
            RoleId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def policy_remove_member(self, operator, role_id, member_id):
        """Try to remove a given member from a given role."""
        assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        member = self._get_component(member_id)
        # TODO: check if it actually has the relationship
        
        # TODO: add checking to comply with the constraints
        # Give feedback about _what_ is wrong
        role.remove_relationship(self.const.hostpolicy_contains, member.entity_id)
        role.write_db()
        return "Component %s no longer member of %s" % (member.component_name, 
                                                        role.component_name)

    all_commands['policy_list_members'] = Command(
            ('policy', 'list_members'),
            RoleId(),
            perm_filter='is_dns_superuser',
            # TODO
            fs=FormatSuggestion(None, None))
    def policy_list_members(self, operator, role_id):
        """List out all members of a given role."""
        assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        # TODO: needs to be sorted "hierarkisk"
        ret = []
        for row in role.search_relations(source_id=role.entity_id,
                            relationship_code=self.const.hostpolicy_contains):
            ret.append(row['target_name'])
        return ret

    all_commands['host_policy_add'] = Command(
            ('host', 'policy_add'),
            HostId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def host_policy_add(self, operator, dns_owner_id, comp_id):
        """Give a host - dns owner - a policy, i.e. a role/atom."""
        assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        comp = self._get_component(comp_id)
        # TODO: do check the constraints here! Tell what's wrong if so.
        comp.add_policy(host.entity_id)
        return "Policy %s added to host %s" % (comp.component_name,
                                               host.host_name)

    all_commands['host_policy_remove'] = Command(
            ('host', 'policy_remove'),
            HostId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def host_policy_remove(self, operator, dns_owner_id, comp_id):
        """Remove a given policy from a given host."""
        assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        comp = self._get_comp(comp_id)
        # TODO: check that the comp is actually given to the host
        comp.remove_policy(host.entity_id)
        return "Policy %s removed from host %s" % (comp.component_name,
                                                   host.host_name)

    all_commands['host_policy_list'] = Command(
            ('host', 'policy_list'),
            HostId(),
            perm_filter='is_dns_superuser')
    def host_policy_list(self, operator, dns_owner_id):
        """List all roles/atoms associated to a given host."""
        assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        comp = PolicyComponent(db)
        ret = []
        for row in comp.search_hostpolicies(dns_owner_id=host.entity_id):
            ret.append(row['policy_name'])
        return ret

    all_commands['policy_list_hosts'] = Command(
            ('policy', 'list_hosts'),
            PolicyId(),
            perm_filter='is_dns_superuser')
    def policy_list_hosts(self, operator, component_id):
        """List all hosts that has a given policy (role/atom)."""
        assert_dns_superuser(operator.get_entity_id())
        comp = self._get_component(component_id)
        ret = []
        for row in comp.search_hostpolicies(policy_id=comp.entity_id):
            ret.append(row['dns_owner_name'])
        return ret

    # TBD: Trengs det en kommando som lister hvilke roller en gitt polciy inngår i?

    all_commands['policy_list_atoms'] = Command(
            ('policy', 'list_atoms'),
            SimpleString(), # TODO
            )
    def policy_list_atoms(self, operator, filter):
        """Return a list of atoms that match the given filters."""
        # This method is available for everyone
        atom = Atom(db)
        # TODO: add the filters, see how UiO's bofhd have done this
        # the filter might contain dates as well
        #
        # Dumper en liste med alle atomer, representert ved deres navn og beskrivelse.
        # 
        # FILTER kan brukes for å filtrere resultatene, enten på atomnavn, eller på create_date:
        # 
        #     * Navnefiltering: Wildcards:
        #           o * - et vilkårlig antall vilkårlige tegn
        #           o ? - ett vilkårlig tegn
        #     * Datofiltrering:
        #           o YYYY-MM-DD - Policy laget denne datoen
        #           o :YYYY-MM-DD - Policy laget denne datoen eller tidligere
        #           o YYYY-MM-DD: - Policy laget denne datoen eller senere
        #           o YYYY-MM-DD:YYYY-MM-DD - Policy laget mellom disse datoene (inklusive datoene selv)
        #
        # Should be possible to use more methods in same go (group search
        # handles it, for instance)
        ret = []
        for row in atom.search(entity_type=co.entity_hostpolicy_atom,
                               name=filter):
            ret.append(row['name'])
        return ret

    all_commands['policy_list_roles'] = Command(
            ('policy', 'list_roles'),
            SimpleString())
    def policy_list_roles(self, operator, filter):
        """Return a list of roles that match the given filters."""
        # This method is available for everyone
        role = Role(db)
        # TODO: add the filters, see how UiO's bofhd have done this
        # the filter might contain dates as well
        #
        # Dumper en liste med alle atomer, representert ved deres navn og beskrivelse.
        # 
        # FILTER kan brukes for å filtrere resultatene, enten på atomnavn, eller på create_date:
        # 
        #     * Navnefiltering: Wildcards:
        #           o * - et vilkårlig antall vilkårlige tegn
        #           o ? - ett vilkårlig tegn
        #     * Datofiltrering:
        #           o YYYY-MM-DD - Policy laget denne datoen
        #           o :YYYY-MM-DD - Policy laget denne datoen eller tidligere
        #           o YYYY-MM-DD: - Policy laget denne datoen eller senere
        #           o YYYY-MM-DD:YYYY-MM-DD - Policy laget mellom disse datoene (inklusive datoene selv)
        #
        # Should be possible to use more methods in same go (group search
        # handles it, for instance)
        ret = []
        for row in role.search(entity_type=co.entity_hostpolicy_role,
                               name=filter):
            ret.append(row['name'])
        return ret

    all_commands['policy_info'] = Command(
            ('policy', 'info'),
            RoleId(),
            fs=FormatSuggestion(None, None)) # TODO
    def policy_info(self, operator, policy_id):
        """Return a list of roles that match the given filters."""
        # This method is available for everyone
        comp = self._get_component(policy_id)
        # * Navn
        # * Hvorvidt det er et atom eller en rolle
        # * Beskrivelse
        # * Forankring/begrunnelse
        # * Hvis rolle, hvilke roller/atomer den inneholder (ikke rekursivt)
        # * Hvilke roller den inngår i
        return "name: %s, desc: %s (TODO)" % (comp.component_name, comp.description)

    # TODO: host remove: Utvides til ukritisk å slette alle roller/atomer assosiert med maskinen.

    # TODO: host info: Utvides til å liste alle roller/atomer som er direkte
    # knyttet til host'en dersom det optional-parameteret policy er lagt til på
    # kommandoen.
