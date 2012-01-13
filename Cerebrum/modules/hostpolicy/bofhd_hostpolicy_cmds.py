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

# Imports from the DNS module:
from Cerebrum.modules.dns import DnsOwner, IP_NUMBER, DNS_OWNER
from Cerebrum.modules.dns.CNameRecord import CNameRecord
from Cerebrum.modules.dns.Utils import Find

from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent, Role, Atom

# Import for bofhd
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.dns.bofhd_dns_cmds import HostId, DnsBofhdAuth, format_day



class HostPolicyBofhdAuth(DnsBofhdAuth):
    """Specialized bofhd-auth for the Hostpolicy bofhd-extension.

    Though a module of its own, Hostpolicy-commands use the same access groups
    as the DNS-module (on which it depends anyway), so the same mechanisms used
    there are also used here.
    """
    # TODO: do we need more auth methods here?
    pass

# Define cmd_params for the HostPolicy module
# The Parameters are used to make an explanation for each parameter at input in
# jbofh.
class AtomId(Parameter):
    _type = 'atom'
    _help_ref = 'atom_id'
class AtomName(Parameter):
    _type = 'name' # TODO: find out what _type means - are they used to anythin?
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
        # TODO: don't know where to get the zone setting from
        self.default_zone = self.const.DnsZone('uio')

    def get_help_strings(self):
        """Help strings are used by jbofh to give users explanations for groups
        of commands, commands and all command arguments (parameters). The
        arg_help's keys are referencing to either Parameters' _help_ref (TODO: or its
        _type in addition?)"""
        group_help = {
            'policy': 'Commands for handling host policies',
            # TODO: add 'host' here as well? We add commands in the host group,
            # but don't know what get_help_string which will be used at init...
            }

        command_help = {
            'policy': {
                'policy_atom_add': 'Create a new atom',
                'policy_atom_delete': 'Delete an atom',
                'policy_role_add': 'Create a new role',
                'policy_role_delete': 'Delete a role',
                'policy_add_member': 'Make a role/atom a member of a role',
                'policy_remove_member': 'Remove a role membership',
                'policy_list_members': 'List all members of a role',
                'policy_list_hosts': 'List all hosts with the given policy (atom/role)', 
                'policy_list_atoms': 'List all atoms by given filters',
                'policy_list_roles': 'List all roles by given filters',
                'policy_info': 'Show info about a policy, i.e. an atom or a role',
                },
            'host': {
                'host_policy_add': 'Give a host a policy (atom/role)',
                'host_policy_remove': 'Remove a policy from a host',
                'host_policy_list': 'List all policies associated with a host',
                },
            }

        arg_help = {
            'atom_id':
            ['atom', 'Atom',
             """The name or entity_id of an atom"""],
            'atom_name':
            ['atom_name', 'Atom name',
             """The name of the atom"""],
            'role_id':
            ['role', 'Role',
             """The name or entity_id of a role"""],
            'role_source':
            ['source_role', 'Source role',
             """The name or entity_id of an existing role to be used as source."""],
            'role_name':
            ['role_name', 'Role name',
             """The name of the role"""],
            'policy_id': 
            ['policy', 'Policy',
             """The name or entity_id of a policy, i.e. a role or an atom"""],
            'policy_target':
            ['target_policy', 'Target policy',
             """The policy (atom/role) to be used as the target of a relationship."""],
            'create_date':
            ['date', 'Create date',
             """The date the atom/role should be considered 'created'"""],
            'description':
            ['description', 'Description',
             """A description of what the atom/role is"""],
            'foundation':
            ['foundation', 'Foundation (url)',
             """An url to the foundation of the atom/role?"""],
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
        return self._get_component(role_id, Role)

    def _get_host(self, host_id):
        """Helper method for getting the DnsOwner for the given host ID, which
        can either be an IP address, an A record or a CName alias."""
        finder = Find(self.db, self.default_zone)

        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # host_id is an IP
            owner_id = finder.find_target_by_parsing(host_id, IP_NUMBER)
        else:
            owner_id = finder.find_target_by_parsing(host_id, DNS_OWNER)

        # Check if it is a Cname, if so: update the owner_id
        try:           
            cname_record = CNameRecord(self.db)
            cname_record.find_by_cname_owner_id(owner_id)
            owner_id = cname_record.target_owner_id
        except Errors.NotFoundError:
            pass

        dns_owner = DnsOwner.DnsOwner(self.db)
        try:
            dns_owner.find(owner_id)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown host: %s' % host_id)
        return dns_owner

    def _check_if_unused(self, comp):
        """Check if component is unused, i.e. not in any relationship or used as
        a policy for hosts. If it is in use, a CerebrumError is raised, telling
        where it is in use. Note that only one of the types of "usage" is
        explained."""
        tmp = tuple(row['dns_owner_name'] for row in
                    comp.search_hostpolicies(policy_id=comp.entity_id))
        if tmp:
            raise CerebrumError("Component is in use as policy for: %s" %
                                ', '.join(tmp))
        tmp = tuple(row['source_name'] for row in 
                    comp.search_relations(target_id=comp.entity_id))
        if tmp:
            raise CerebrumError("Component is used as target for: %s" %
                                ', '.join(tmp))
        tmp = tuple(row['target_name'] for row in 
                    comp.search_relations(source_id=comp.entity_id))
        if tmp:
            raise CerebrumError("Component is used as source for: %s" %
                                ', '.join(tmp))

    # TODO: we miss functionality for setting mutex relationships

    all_commands['policy_atom_add'] = Command(
            ('policy', 'atom_add'),
            AtomName(), SimpleString(help_ref='description'),
            SimpleString(help_ref='foundation'), CreateDate(optional=True),
            perm_filter='is_dns_superuser')
    def policy_atom_add(self, operator, name, description, foundation,
                        create_date=None):
        """Adds a new atom and its data. Its can only consist of lowercased,
        alpha numrice characters and -."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        atom = Atom(self.db)
        # validate data
        tmp = atom.illegal_attr(description)
        if tmp:
            raise CerebrumError('Illegal description: %s' % tmp)
        tmp = atom.illegal_attr(foundation)
        if tmp:
            raise CerebrumError('Illegal foundation: %s' % tmp)

        # check that name isn't already in use
        try:
            comp = self._get_component(name)
        except CerebrumError:
            pass
        else:
            # TODO: inform about type here
            print comp.entity_type
            raise CerebrumError('A policy already exists with name: %s' % name)
        atom.new(name, description, foundation, create_date)
        return "New atom %s created" % atom.component_name

    all_commands['policy_atom_delete'] = Command(
            ('policy', 'atom_delete'),
            AtomId(),
            perm_filter='is_dns_superuser')
    def policy_atom_delete(self, operator, atom_id):
        """Try to delete an atom if it hasn't been used in any policy or
        relationship."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        atom = self._get_atom(atom_id)
        self._check_if_unused(atom) # will raise CerebrumError

        name = atom.component_name
        atom.delete()
        atom.write_db()
        return "Atom %s deleted" % name

    all_commands['policy_role_add'] = Command(
            ('policy', 'role_add'),
            RoleName(), SimpleString(help_ref='description'),
            SimpleString(help_ref='foundation'), CreateDate(optional=True),
            perm_filter='is_dns_superuser')
    def policy_role_add(self, operator, name, description, foundation,
                        create_date=None):
        """Adds a new role and its data. Its can only consist of lowercased,
        alpha numrice characters and -."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = Role(self.db)
        # validate data
        tmp = role.illegal_attr(description)
        if tmp:
            raise CerebrumError('Illegal description: %s' % tmp)
        tmp = role.illegal_attr(foundation)
        if tmp:
            raise CerebrumError('Illegal foundation: %s' % tmp)

        # check that name isn't already in use
        try:
            comp = self._get_component(name)
        except CerebrumError:
            pass
        else:
            raise CerebrumError('A policy already exists with name: %s' % name)
        role.new(name, description, foundation, create_date)
        return "New role %s created" % role.component_name
    
    all_commands['policy_role_delete'] = Command(
            ('policy', 'role_delete'), RoleId(),
            perm_filter='is_dns_superuser')
    def policy_role_delete(self, operator, role_id):
        """Try to delete a given role if it's not in any relationship, or is in
        any policy."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        # Check if component is in use anywhere. The method will raise
        # CerebrumErrors if that's the case:
        self._check_if_unused(role)

        name = role.component_name
        role.delete()
        role.write_db()
        return "Role %s deleted" % name

    all_commands['policy_add_member'] = Command(
            ('policy', 'add_member'),
            RoleId(help_ref='role_source'), PolicyId(help_ref='policy_target'),
            perm_filter='is_dns_superuser')
    def policy_add_member(self, operator, role_id, member_id):
        """Try to add a given component as a member of a role."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        member = self._get_component(member_id)

        # TODO: check if already a member
        
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
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        member = self._get_component(member_id)

        # check if relationship do exists:
        rel = role.search_relations(source_id=role.entity_id,
                        target_id=member.entity_id,
                        relationship_code=self.const.hostpolicy_contains)
        if not tuple(rel):
            raise CerebrumError('%s is not a member of %s' % (
                        member.component_name, role.component_name))

        # TODO: need to cheeck any constraints here?

        role.remove_relationship(self.const.hostpolicy_contains, member.entity_id)
        role.write_db()
        return "Component %s no longer member of %s" % (member.component_name, 
                                                        role.component_name)

    all_commands['policy_list_members'] = Command(
            ('policy', 'list_members'),
            RoleId(),
            perm_filter='is_dns_superuser',
            # TODO
            fs=FormatSuggestion('%-20s', ('mem_name',), 
                hdr='%-20s' % ('Name',)))
    def policy_list_members(self, operator, role_id):
        """List out all members of a given role."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        role = self._get_role(role_id)
        # TODO: needs to be sorted "hierarkisk"
        ret = []
        for row in role.search_relations(source_id=role.entity_id,
                            relationship_code=self.const.hostpolicy_contains):
            ret.append({'mem_name': row['target_name']})
        return ret

    all_commands['host_policy_add'] = Command(
            ('host', 'policy_add'),
            HostId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def host_policy_add(self, operator, dns_owner_id, comp_id):
        """Give a host - dns owner - a policy, i.e. a role/atom."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        comp = self._get_component(comp_id)

        # check if already a member
        for row in comp.search_hostpolicies(policy_id=comp.entity_id,
                                            dns_owner_id=host.entity_id):
            raise CerebrumError('Host %s already has policy %s' %
                                (host.name, comp.component_name))

        # TODO: do check the constraints here! Tell what's wrong if so.

        comp.add_policy(host.entity_id)
        return "Policy %s added to host %s" % (comp.component_name,
                                               host.name)

    all_commands['host_policy_remove'] = Command(
            ('host', 'policy_remove'),
            HostId(), PolicyId(),
            perm_filter='is_dns_superuser')
    def host_policy_remove(self, operator, dns_owner_id, comp_id):
        """Remove a given policy from a given host."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        comp = self._get_comp(comp_id)

        # check that the comp is actually given to the host:
        if not tuple(comp.search_hostpolicies(policy_id=comp.entity_id,
                                              dns_owner_id=host.entity_id)):
            raise CerebrumError("Host %s doesn't have policy %s" %
                                (host.name, comp.component_name))
        # TODO: other checks here?

        comp.remove_policy(host.entity_id)
        return "Policy %s removed from host %s" % (comp.component_name,
                                                   host.name)

    all_commands['host_policy_list'] = Command(
            ('host', 'policy_list'),
            HostId(),
            fs=FormatSuggestion('%-20s %-40s', ('policy_name', 'desc'),
                hdr='%-20s %-40s' % ('Policy:', 'Description:')),
            perm_filter='is_dns_superuser')
    def host_policy_list(self, operator, dns_owner_id):
        """List all roles/atoms associated to a given host."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host = self._get_host(dns_owner_id)
        comp = PolicyComponent(self.db)
        ret = []
        for row in comp.search_hostpolicies(dns_owner_id=host.entity_id):
            comp.clear()
            comp.find(row['policy_id'])
            ret.append({'policy_name': row['policy_name'], 
                        'desc': comp.description})
        return ret

    all_commands['policy_list_hosts'] = Command(
            ('policy', 'list_hosts'),
            PolicyId(),
            fs=FormatSuggestion('%-20s', ('host_name',),
                hdr='%-20s' % ('Host',)),
            perm_filter='is_dns_superuser')
    def policy_list_hosts(self, operator, component_id):
        """List all hosts that has a given policy (role/atom)."""
        self.ba.assert_dns_superuser(operator.get_entity_id())
        comp = self._get_component(component_id)
        ret = []
        for row in comp.search_hostpolicies(policy_id=comp.entity_id):
            ret.append({'host_name': row['dns_owner_name']})
        return ret

    # TBD: Trengs det en kommando som lister hvilke roller en gitt policy inngår i?

    all_commands['policy_list_atoms'] = Command(
            ('policy', 'list_atoms'),
            SimpleString(), # TODO: add help text for "filters"
            fs=FormatSuggestion('%-20s %-30s', ('name', 'desc'),
                hdr='%-20s %-30s' % ('Name', 'Description'))
            )
    def policy_list_atoms(self, operator, filter):
        """Return a list of atoms that match the given filters."""
        # This method is available for everyone
        atom = Atom(self.db)
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
        for row in atom.search(name=filter): # TODO
            ret.append({'name': row['name'], 'desc': row['description']})
        return ret

    all_commands['policy_list_roles'] = Command(
            ('policy', 'list_roles'),
            SimpleString(),
            fs=FormatSuggestion('%-20s %-30s', ('name', 'desc'),
                hdr='%-20s %-30s' % ('Name', 'Description'))
            )
    def policy_list_roles(self, operator, filter):
        """Return a list of roles that match the given filters."""
        # This method is available for everyone
        role = Role(self.db)
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
        for row in role.search(): # name=filter): # TODO
            ret.append({'name': row['name'], 'desc': row['description']})
        return ret

    all_commands['policy_info'] = Command(
            ('policy', 'info'),
            RoleId(),
            fs=FormatSuggestion([
                ('Name:             %-30s', ('name',)),
                ('Description:      %-30s', ('desc',)),
                ('Foundation:       %-30s', ('foundation',)),
                ('Created:          %-30s', (format_day('createdate'),)),
                ('Type:             %-30s', ('type',)),
                # TODO: The definitions needs to be fixed...
                ('Relation:         %s (%s)', ('target_rel_name', 'target_rel_type'),
                    ('Direct relationships where this role is target:')),
                ('Relation:         %s (%s)', ('rel_name', 'rel_type'),
                    ('Direct relationships where this role is source:')),
                ]))
    def policy_info(self, operator, policy_id):
        """Return information about a policy component."""
        # This method is available for everyone
        comp = self._get_component(policy_id)
        ret = [{'name': comp.component_name},
               {'type': str(comp.entity_type)}, # TODO: how to map to the type's code_str?
               {'desc': comp.description},
               {'foundation': comp.foundation},
               {'createdate': comp.create_date},]
        # check what this component is in relationship with
        for row in comp.search_relations(target_id=comp.entity_id):
            ret.append({'target_rel_name': row['source_name'],
                        'target_rel_type': row['relationship_str']})
        # if this is a role, add direct relationships where this is the source
        if comp.entity_type == self.const.entity_hostpolicy_role:
            for row in comp.search_relations(source_id=comp.entity_id):
                ret.append({'rel_name': row['target_name'],
                            'rel_type': row['relationship_str']})
        return ret

    # TODO: host remove: Utvides til ukritisk å slette alle roller/atomer assosiert med maskinen.

    # TODO: host info: Utvides til å liste alle roller/atomer som er direkte
    # knyttet til host'en dersom det optional-parameteret policy er lagt til på
    # kommandoen.
