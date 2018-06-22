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
"""This is the bofhd functionality that is available for the TSD project.

Many of the commands are simply copied from UiO's command base and renamed for
the project, while other commands are changed to comply with the project.

Idealistically, we would move the basic commands into a super class, so we
could instead use inheritance, but unfortunately we don't have that much time.

Note that there are different bofhd extensions. One is for administrative
tasks, i.e. the superusers in TSD, and one is for the end users. End users are
communicating with bofhd through a web site, so that bofhd should only be
reachable from the web host.

NOTE:

Using the @superuser decorator instead of calling self.ba.is_superuser(userid)
is only used in this file so far, so if you are an experienced bofhd developer,
ba.is_superuser is not missing, it's still here, but in a different form.
"""
from __future__ import unicode_literals

import json
from functools import wraps, partial

from mx import DateTime

import six

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.modules import EntityTrait
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd import cmd_param as cmd
from Cerebrum.modules.bofhd import bofhd_contact_info
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod
from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.dns import IPv6Subnet
from Cerebrum.modules.dns import Subnet
from Cerebrum.modules.dns.bofhd_dns_cmds import HostId
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as uio_base
from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough,
                                              RigidPasswordNotGoodEnough,
                                              PhrasePasswordNotGoodEnough)
from Cerebrum.modules.tsd.bofhd_auth import TsdBofhdAuth, TsdContactAuth
from Cerebrum.modules.tsd import bofhd_help
from Cerebrum.modules.tsd import Gateway
from Cerebrum.modules.username_generator.generator import UsernameGenerator


def format_day(field):
    return field + "date:yyyy-MM-dd"


def date_to_string(date):
    """Takes a DateTime-object and formats a standard ISO-datestring
    from it.

    Custom-made for our purposes, since the standard XMLRPC-libraries
    restrict formatting to years after 1899, and we see years prior to
    that.
    """
    if not date:
        return "<not set>"
    return "%04i-%02i-%02i" % (date.year, date.month, date.day)


class ProjectID(cmd.Parameter):
    """Bofhd Parameter for specifying a project ID."""
    _type = 'projectID'
    _help_ref = 'project_id'


class ProjectName(cmd.Parameter):
    """Bofhd Parameter for specifying a project name."""
    _type = 'projectName'
    _help_ref = 'project_name'


class ProjectLongName(cmd.Parameter):
    """Bofhd Parameter for specifying a project's long (full) name."""
    _type = 'projectLongName'
    _help_ref = 'project_longname'


class ProjectShortName(cmd.Parameter):
    """Bofhd Parameter for specifying a project's short name."""
    _type = 'projectShortName'
    _help_ref = 'project_shortname'


class ProjectPrice(cmd.Parameter):
    """Bofhd parameter for specifying project's price group.
    Initial spec: price: "UIO" | "UH" | "OTHER"
    """
    _type = 'projectPrice'
    _help_ref = 'project_price'


class ProjectInstitution(cmd.Parameter):
    """Bofhd parameter for specifying project's institution.
    Initial spec:
        institution: "UIO" | "HSØ" | "HIOA" | "UIT" | "NTNU" | "OTHER"
    """
    _type = 'projectInstitution'
    _help_ref = 'project_institution'


class ProjectHpc(cmd.Parameter):
    """Bofhd parameter for specifying if project has hpc flag.
    Initial spec:
        HPC: "HPC_YES" | "HPC_NO"
    """
    _type = 'projectHpc'
    _help_ref = 'project_hpc'


class ProjectMetadata(cmd.Parameter):
    """Bofhd parameter for specifying project metadata."""
    _type = 'jsonObject'
    _help_ref = 'project_metadata'


class GroupDescription(cmd.SimpleString):
    """Bofhd Parameter for specifying a group description."""
    _type_ = 'groupDescription'
    _help_ref_ = 'group_description'

    def __init__(self, help_ref="string_description"):
        super(GroupDescription, self).__init__(help_ref=help_ref)


class ProjectStatusFilter(cmd.Parameter):
    """Bofhd Parameter for filtering on projects' status.

    A project could have status not-approved, frozen or active. More status
    types are probably needed in the future.
    """
    _type = 'projectStatusFilter'
    _help_ref = 'project_statusfilter'


class SubnetParam(cmd.Parameter):
    """A subnet, e.g. 10.0.0.0/16"""
    _type = 'subnet'
    _help_ref = 'subnet'


class SubnetSearchType(cmd.Parameter):
    """A subnet search type."""
    _type = 'searchType'
    _help_ref = 'subnet_search_type'


class FnMatchPattern(cmd.Parameter):
    """A pattern given to fnmatch."""
    _type = 'pattern'
    _help_ref = 'fnmatch_pattern'


class VLANParam(cmd.Parameter):
    """A VLAN number"""
    _type = 'vlan'
    _help_ref = 'vlan'


class VMType(cmd.Parameter):
    """Bofhd Parameter for specifying projects' VM-type."""
    _type = 'vmType'
    _help_ref = 'vm_type'


class TSDBofhdExtension(BofhdCommonMethods):
    """Superclass for common functionality for TSD's bofhd servers."""

    all_commands = {}
    hidden_commands = {}
    parent_commands = True
    authz = TsdBofhdAuth

    def __init__(self, *args, **kwargs):
        super(TSDBofhdExtension, self).__init__(*args, **kwargs)
        self.external_id_mappings = {}
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr

        # The client talking with the TSD gateway
        self.__gateway = None

    @property
    def gateway(self):
        if self.__gateway is None:
            self.__gateway = Gateway.GatewayClient(logger=self.logger)
        return self.__gateway

    @classmethod
    def get_help_strings(cls):
        """Return all help messages for TSD."""
        return (bofhd_help.group_help,
                bofhd_help.command_help,
                bofhd_help.arg_help)

    def _get_entity(self, entity_type=None, ident=None):
        """Return a suitable entity subclass for the specified entity_id.

        Overridden to be able to return TSD projects by their project ID or
        entity_id.
        """
        if ident and entity_type == 'project':
            return self._get_project(ident)
        if ident and entity_type == 'host':
            return self._get_host(ident)
        return super(TSDBofhdExtension, self)._get_entity(entity_type, ident)

    def _get_project(self, projectid):
        """Return a project's OU by its name, if found.

        We identify project's by their acronym name, which is not handled
        uniquely in the database, so we could be up for integrity errors, e.g.
        if two projects are called the same. This should be handled by TSD's OU
        class.

        @type projectid: string or integer
        @param projectid: The project id or the entity_id of the project. Must
            match one and only one OU.

        @raise CerebrumError: If no project OU with the given acronym name was
            found, or if more than one project OU was found.
        """
        ou = self.OU_class(self.db)
        try:
            ou.find_by_tsd_projectid(projectid)
            return ou
        except Errors.NotFoundError:
            pass
        if projectid.isdigit():
            try:
                ou.find(projectid)
                return ou
            except Errors.NotFoundError:
                pass
        raise CerebrumError('Could not find project: {projectid}'.format(
            projectid=projectid))

    def _get_host(self, host_id):
        """Helper method for getting the DnsOwner for the given host ID.

        The given L{host_id} could be an IP or IPv6 address or a CName alias.

        @rtype: Cerebrum.modules.dns.DnsOwner/DnsOwner
        @return: An instance of the matching DnsOwner.
        """
        finder = dns.Utils.Find(self.db,
                                self.const.DnsZone(getattr(cereconf,
                                                           'DNS_DEFAULT_ZONE',
                                                           'uio')))
        if ':' not in host_id and host_id.split('.')[-1].isdigit():
            # host_id is an IP
            owner_id = finder.find_target_by_parsing(host_id, dns.IP_NUMBER)
        else:
            owner_id = finder.find_target_by_parsing(host_id, dns.DNS_OWNER)

        # Check if it is a Cname, if so: go to the cname's owner_id
        try:
            cname_record = dns.CNameRecord.CNameRecord(self.db)
            cname_record.find_by_cname_owner_id(owner_id)
        except Errors.NotFoundError:
            pass
        else:
            owner_id = cname_record.target_owner_id

        dns_owner = dns.DnsOwner.DnsOwner(self.db)
        try:
            dns_owner.find(owner_id)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown host: {host_id}'.format(
                host_id=host_id))
        return dns_owner

    def _get_ou(self, ou_id=None, stedkode=None):
        """Override to change the use of L{stedkode} to check the acronym.

        In TSD, we do not use L{stedkode}, but we do have some unique IDs
        stored as acronyms. To avoid having to change too much, we just
        override the stedkode reference so we don't have to override each
        method that fetches an OU by its stedkode.
        """
        if ou_id is not None:
            return super(TSDBofhdExtension, self)._get_ou(ou_id, stedkode)
        return self._get_project(stedkode)

    def _format_ou_name(self, ou, include_short_name=True):
        """Return a human readable name for a given OU (project).

        We have project ID, which is used internally, and projectname, that is
        used externally in Nettskjema. Example on output:

                p25
                p01 (tsd)
                p14 (cancer2)
                p02 (<Not Set>)

        @type ou: OU
        @param ou: The given OU (project) to return the name for.

        @type include_short_name: bool
        @param include_short_name: If a short name of the OU should be returned
            as well. If False, only the project ID is returned.

        @rtype: string (unicode)
        @return: The human readable string that identifies the OU.
        """
        if not include_short_name:
            return ou.get_project_id()
        name = ou.get_project_name()
        return "%s (%s)" % (ou.get_project_id(), name)

    #
    # user password
    #
    all_commands['user_password'] = cmd.Command(
        ('user', 'password'),
        cmd.AccountName(),
        cmd.AccountPassword(optional=True))

    def user_password(self, operator, accountname, password=None):
        """Set password for a user. A modified version of UiO's command."""
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)

        # TSD specific behaviour: Raise error if user isn't approved or
        # shouldn't be in AD or the GW:
        if not account.is_approved():
            raise CerebrumError("User is not approved: %s" % accountname)

        if password is None:
            password = account.make_passwd(accountname)
        else:
            # this is a bit complicated, but the point is that
            # superusers are allowed to *specify* passwords for other
            # users if cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS=True
            # otherwise superusers may change passwords by assigning
            # automatic passwords only.
            if self.ba.is_superuser(operator.get_entity_id()):
                if (operator.get_entity_id() != account.entity_id and
                        not cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS):
                    raise CerebrumError("Superuser cannot specify passwords "
                                        "for other users")
            elif operator.get_entity_id() != account.entity_id:
                raise CerebrumError("Cannot specify password for another user")
        try:
            check_password(password, account, structured=False)
        except RigidPasswordNotGoodEnough as e:
            raise CerebrumError('Bad password: {err_msg}'.format(
                err_msg=six.text_type(e)))
        except PhrasePasswordNotGoodEnough as e:
            raise CerebrumError('Bad passphrase: {err_msg}'.format(
                err_msg=six.text_type(e)))
        except PasswordNotGoodEnough as e:
            raise CerebrumError('Bad password: {err_msg}'.format(err_msg=e))

        ret_msgs = ['Password altered']
        # Set password for all person's accounts:
        ac = Factory.get('Account')(self.db)
        for row in ac.search(owner_id=account.owner_id):
            ac.clear()
            ac.find(row['account_id'])
            ac.set_password(password)
            try:
                ac.write_db()
            except self.db.DatabaseError as m:
                raise CerebrumError("Database error: %s" % m)
            # Remove "weak password" quarantine
            for r in ac.get_entity_quarantine():
                if r['quarantine_type'] in (
                        self.const.quarantine_autopassord,
                        self.const.quarantine_svakt_passord):
                    ac.delete_entity_quarantine(int(r['quarantine_type']))
            ac.write_db()
            ret_msgs.append("New password for: %s" % ac.account_name)
            if ac.is_deleted():
                ret_msgs.append("Warning: user is deleted: %s" %
                                ac.account_name)
            elif ac.is_expired():
                ret_msgs.append("Warning: user is expired: %s" %
                                ac.account_name)
            elif ac.get_entity_quarantine(only_active=True):
                ret_msgs.append("Warning: user in quarantine: %s" %
                                ac.account_name)

        # Only store one of the account's password. Not necessary to store all
        # of them, as it's the same.
        operator.store_state("user_passwd",
                             {'account_id': int(account.entity_id),
                              'password': password})
        ret_msgs.append("Please use misc list_password to print or view the"
                        " new password.")
        return "\n".join(ret_msgs)

    def _group_add_entity(self, operator, src_entity, member_type, dest_group):
        """Helper method for adding a given entity to given group.

        @type operator:
        @param operator:

        @type src_entity: Entity
        @param src_entity: The entity to add as a member.

        @type member_type: String or entity_type
        @param member_type: The type of entity being added (account or group).

        @type dest_group: Group
        @param dest_group: The group the member should be added to.
        """
        if operator:
            self.ba.can_add_group_member(operator.get_entity_id(),
                                         src_entity,
                                         member_type, dest_group)

        src_name = self._get_entity_name(src_entity.entity_id,
                                         src_entity.entity_type)
        # Make the error message for the most common operator error more
        # friendly.  Don't treat this as an error, useful if the operator has
        # specified more than one entity.
        if dest_group.has_member(src_entity.entity_id):
            return "%s is already a member of %s" % (src_name,
                                                     dest_group.group_name)
        # Make sure that the src_entity does not have dest_group as a member
        # already, to avoid a recursion at export
        if src_entity.entity_type == self.const.entity_group:
            for row in src_entity.search_members(
                    member_id=dest_group.entity_id,
                    member_type=self.const.entity_group,
                    indirect_members=True,
                    member_filter_expired=False):
                if row['group_id'] == src_entity.entity_id:
                    return ("Recursive memberships are not allowed"
                            " (%s is member of %s)" % (dest_group, src_name))
        # This can still fail, e.g., if the entity is a member with a different
        # operation.
        try:
            dest_group.add_member(src_entity.entity_id)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        # TODO: If using older versions of NIS, a user could only be a member
        # of 16 group. You might want to be warned about this - Or is this only
        # valid for UiO?
        return "OK, added %s to %s" % (src_name, dest_group.group_name)

    #
    # group add_member
    #
    # This command has previously been available as add_member, but has
    # been renamed to group_multi_add due to the fact that Brukerinfo uses
    # group_multi_add in every instance. This avoids having two identical
    # commands with different names.
    all_commands['group_multi_add'] = cmd.Command(
        ("group", "add_member"),
        cmd.MemberType(),
        cmd.MemberName(),
        cmd.GroupName())

    def group_multi_add(self, operator, member_type, src_name, dest_group):
        """
        Method for adding an entity to a given group. Raises an exception if
        the entity is of type person, which is not allowed in TSD.

        @type operator:
        @param operator:

        @type src_name: String
        @param src_name: The name/id of the entity to add as the member.

        @type dest_group: String
        @param dest_group: The name/id of the group the member should be added
            to.

        @type member_type: String or EntityTypeCode (CerebrumCode)
        @param member_type: The EntityType of the member.
        """
        if member_type in ("person", self.const.entity_group):
            raise CerebrumError("Can't handle persons in project groups")
        elif member_type in ("group", self.const.entity_group):
            src_entity = self._get_group(src_name)
        elif member_type in ("account", self.const.entity_account):
            src_entity = self._get_account(src_name)
        else:
            raise CerebrumError('Unknown entity type: %s' % member_type)

        dest_group = self._get_group(dest_group)

        return self._group_add_entity(operator,
                                      src_entity,
                                      member_type,
                                      dest_group)

    #
    # group remove_member
    #
    # This command has previously been available as remove_member, but has
    # been renamed to group_multi_remove due to the fact that Brukerinfo uses
    # group_multi_remove in every instance. This avoids having two identical
    # commands with different names.
    all_commands['group_multi_remove'] = cmd.Command(
        ("group", "remove_member"),
        cmd.MemberType(),
        cmd.MemberName(),
        cmd.GroupName(),
        perm_filter='can_alter_group')

    def group_multi_remove(self, operator, member_type, src_name, dest_group):
        """Remove a member from a given group.

        @type operator:
        @param operator:

        @type member_type: String or EntityTypeCode (CerebrumCode)
        @param member_type: The entity_type of the member.

        @type src_name: String
        @param src_name: The name/id of the entity to remove as member.

        @type dest_group: String
        @param dest_group: The name/id of the group the member should be
                           removed from.
        """
        if member_type in ("group", self.const.entity_group):
            src_entity = self._get_group(src_name)
        elif member_type in ("account", self.const.entity_account):
            src_entity = self._get_account(src_name)
        elif member_type in ("person", self.const.entity_person):
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError('Unknown entity type: %s' % member_type)
        dest_group = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, dest_group)

    def _group_remove_entity(self, operator, member, group):
        """Helper method for removing a member from a group.

        @type operator:
        @param operator:

        @type member: Entity
        @param member: The member to remove

        @type group: Group
        @param group: The group to remove the member from.
        """
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member_name = self._get_entity_name(member.entity_id,
                                            member.entity_type)
        if not group.has_member(member.entity_id):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = Utils.Factory.get('PosixUser')(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError("Can't remove %s from primary group %s"
                                        % (member_name, group.group_name))
            except Errors.NotFoundError:
                pass
        try:
            group.remove_member(member.entity_id)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)


def superuser(fn):
    """Decorator for checking that methods are being executed as operator.

    The first argument of the decorated function must be "self" and the second
    must be "operator".  If operator is not superuser a CerebrumError will be
    raised.
    """
    if fn.func_dict.get('assert_superuser_wrapper'):
        return fn

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if len(args) < 2:
            raise CerebrumError(
                'Decorated functions must have self and operator as the first'
                ' arguments')
        self = args[0]
        operator = args[1]
        userid = operator.get_entity_id()
        if not self.ba.is_superuser(userid):
            raise CerebrumError('Only superuser is allowed to do this!')
        else:
            self.logger.debug2("OK, current user is superuser.")
            return fn(*args, **kwargs)
    wrapper.func_dict['assert_superuser_wrapper'] = True
    return wrapper


class _Project:
    """Helper class for project information that has an entity_id, name and a
    list of quarantine types.

    Since the coupling of projects and quarantines are encapsulated here, there
    is less to keep track of and less room for potential bugs.

    First and foremost it avoids code duplication for bofhd functions that list
    projects.


    Examples:

    Filtering by certain quarantines can look a bit like this:

        filtered_projects = [project for project in project_list
                             if project.has_quarantine(q)]


    Returning the filtered/sorted data can look a bit like this:

        return [project.as_dict(['entity_id', 'name'])
                for project in filtered_projects]
    """

    def __init__(self, const, entity_id, name, pid=None):
        """Initialize the _Project object with an entity_id and a name.
        Quarantines are added with the add_quarantine method.
        """
        # The const object, used for converting quaratines to strings
        self.const = const
        # The entity_id, as a number
        self.id = entity_id
        # The project name, as a string
        self.name = name
        # Quarantines, stores as id's to quarantine types
        self.quarantines = []
        # Project ID
        self.pid = pid

    def add_quarantine(self, quarantine_type):
        """Add a quarantine to the list of quarantines."""
        self.quarantines.append(int(quarantine_type))

    def has_quarantine(self, quarantine_type):
        """Check if this project has the given quarantine type."""
        return int(quarantine_type) in self.quarantines

    def quarantine_string(self):
        """Convert the list of quarantine identifiers to a string"""
        return ", ".join(
            map(six.text_type, map(self.const.Quarantine, self.quarantines)))

    def as_dict(self, keynames):
        """ Get project data as dict.

        :param sequence keynames:
            A sequence of fields to include in the result.
        """
        d = {}
        for key in keynames:
            # both 'id' and 'entity_id' are allowed
            if key in ["id", "entity_id"]:
                d[key] = six.text_type(self.id)
            elif key == "quars":
                d['quars'] = self.quarantine_string()
            else:
                d[key] = six.text_type(getattr(self, key))
        return d


class _Projects:
    """
    Project collection.

    Helper class for making it easy to search, filter, sort and return project
    data.
    """

    def __init__(self, logger, const, ou, exact_match=False, filter=None):
        """Make self.projects a list of _Project objects which each contain
        entity_id, name and a list of quarantine types.
        """
        # A dictionary that maps entity_ids to _Project objects
        self.projects = {}
        self.filter = filter
        self._fix_filter()

        # Perform the queries
        project_structs = ou.search_tsd_projects(name=self.filter)
        quarantine_structs = ou.list_entity_quarantines(
            entity_types=const.entity_ou,
            only_active=True)

        # Fill in a dictionary of Project objects.
        # Projects is a dictionary on the form {entity_id: project_object}
        self.projects = dict(
            (p['entity_id'], _Project(const, p['entity_id'], p['name']))
            for p in project_structs)

        # Fill in with project IDs:
        for row in ou.search_external_ids(entity_type=const.entity_ou,
                                          id_type=const.externalid_project_id):
            if row['entity_id'] in self.projects:
                self.projects[row['entity_id']].pid = row['external_id']

        # Fill in the quarantine information into the Project objects
        for quarantine_struct in quarantine_structs:
            quarantine_entity_id = quarantine_struct['entity_id']
            if quarantine_entity_id in self.projects:
                project = self.projects[quarantine_entity_id]
                quarantine_type = quarantine_struct['quarantine_type']
                project.add_quarantine(quarantine_type)

    def _fix_filter(self):
        """Massage the filter string so that also searches for 'ø*' is possible.
        Also uses * instead of an empty filter.
        """
        if self.filter is None:
            # Don't do anything
            return
        if not self.filter:
            # List everything if no filter is specified
            self.filter = "*"

    def set_project_list(self, project_list):
        """Takes a list of _project objects and returns a dictionary on the form
        {'entity_id':_project_object}.
        """
        self.projects = dict([(project.id, project)
                              for project in project_list])

    def filter_by_quarantine(self, quarantine_type):
        """Filter out projects that does not have the given quarantine_type."""
        filtered = [p for p in self.projects.values()
                    if p.has_quarantine(quarantine_type)]
        self.set_project_list(filtered)

    def results_sorted_by_name(self, keynames):
        """ Get projects as a list of dicts, sorted by project name. """
        names_and_keys = [(project.name, project.id)
                          for project in self.projects.values()]
        sorted_keys = [name_and_key[1]
                       for name_and_key in sorted(names_and_keys)]
        return [self.projects[key].as_dict(keynames) for key in sorted_keys]

    def results_sorted_by_pid(self, keynames):
        """ Get projects as a list of dicts, sorted by project id. """
        pids_and_keys = [(project.pid, project.id)
                         for project in self.projects.values()]
        # TODO: numerical sort instead of alphabetic
        sorted_keys = [name_and_key[1]
                       for name_and_key in sorted(pids_and_keys)]
        return [self.projects[key].as_dict(keynames) for key in sorted_keys]

    def results(self, keynames):
        """ Get projects as a list of dicts. """
        return [project.as_dict(keynames)
                for project in self.projects.values()]


admin_uio_helpers = [
    '_entity_info',
    '_fetch_member_names',
    '_format_changelog_entry',
    '_format_from_cl',
    '_get_access_id',
    '_get_access_id_group',
    '_get_affiliation_statusid',
    '_get_affiliationid',
    '_get_auth_op_target',
    '_get_cached_passwords',
    '_get_disk',
    '_get_opset',
    '_get_posix_account',
    '_get_shell',
    '_grant_auth',
    '_list_access',
    '_manipulate_access',
    '_person_create_externalid_helper',
    '_remove_auth_role',
    '_remove_auth_target',
    '_revoke_auth',
    '_validate_access',
    '_validate_access_group',
    'user_set_owner_prompt_func',
]


admin_copy_uio = [
    'access_grant',
    'access_group',
    'access_list',
    'access_list_opsets',
    'access_revoke',
    'access_show_opset',
    'entity_history',
    'group_delete',
    'group_demote_posix',
    'group_info',
    'group_list',
    'group_list_expanded',
    'group_memberships',
    'group_promote_posix',
    'group_search',
    'group_set_description',
    'group_set_expire',
    'misc_affiliations',
    'misc_clear_passwords',
    'misc_list_passwords',
    'misc_verify_password',
    'ou_info',
    'ou_search',
    'ou_tree',
    'person_accounts',
    'person_affiliation_add',
    'person_affiliation_remove',
    'person_create',
    'person_find',
    'person_info',
    'person_set_bdate',
    'person_set_id',
    'person_get_id',
    'person_set_name',
    'quarantine_disable',
    'quarantine_list',
    'quarantine_remove',
    'quarantine_set',
    'quarantine_show',
    'spread_add',
    'spread_list',
    'spread_remove',
    'trait_info',
    'trait_list',
    'trait_remove',
    'trait_set',
    'trait_types',
    'user_affiliation_add',
    'user_affiliation_remove',
    'user_demote_posix',
    'user_find',
    'user_history',
    'user_info',
    'user_set_expire',
    'user_set_owner',
]


def _apply_superuser(commands, replace=True):
    """Require superuser for commands.

    Class wrapper that wraps the functions for the given commands with the
    `superuser` wrapper, and tries to set the `perm_filter` to 'is_superuser'
    for that command.
    """
    # This is a hack that is needed because TSD-bofh *is* a giant hack
    # It is needed to:
    #   wrap commands from uio
    #   wrap commands inherited from BofhdCommonMethods, that *aren't*
    #       overridden in AdminBofhdExtension
    def wrapper(cls):
        for command in commands:
            if command in getattr(cls, 'all_commands') and not replace:
                # Already defined directly in class, so don't alter
                continue
            if getattr(cls, command):
                # Function exists, wrap function
                setattr(cls, command, superuser(getattr(cls, command)))
                # Find Command and set perm_filter
                for base in cls.mro():
                    desc = getattr(base, 'all_commands', {})
                    if command in desc:
                        if desc[command] is not None:
                            desc[command].perm_filter = 'is_superuser'
                        break
        return cls
    return wrapper


@_apply_superuser(
    [fn_name for cls in TSDBofhdExtension.mro()
     for fn_name in getattr(cls, 'all_commands', {}).keys()
     if fn_name not in cereconf.TSD_ALLOWED_ENDUSER_COMMANDS],
    replace=False)
@_apply_superuser(
    [fn_name for fn_name in admin_copy_uio
     if fn_name not in cereconf.TSD_ALLOWED_ENDUSER_COMMANDS])
@copy_command(
    uio_base,
    'all_commands', 'all_commands',
    commands=admin_copy_uio)
@copy_func(
    uio_base,
    methods=admin_uio_helpers + admin_copy_uio)
@copy_func(
    BofhdUserCreateMethod,
    methods=['_user_create_set_account_type']
)
class AdministrationBofhdExtension(TSDBofhdExtension):
    """The bofhd commands for the TSD project's system administrators.

    Here you have the commands that should be available for the superusers."""

    # Commands that should be publicised for an operator, e.g. in jbofh:
    all_commands = {}

    # Commands that are available, but not publicised, as they are normally
    # called through other systems, e.g. Brukerinfo. It should NOT be used as a
    # security feature - thus you have security by obscurity.
    hidden_commands = {}

    #
    # project create
    #
    all_commands['project_create'] = cmd.Command(
        ('project', 'create'),
        ProjectName(),
        ProjectLongName(),
        ProjectShortName(),
        cmd.Date(help_ref='project_start_date'),
        cmd.Date(help_ref='project_end_date'),
        ProjectPrice(),
        ProjectInstitution(),
        VMType(),
        ProjectHpc(),
        ProjectMetadata(),
        VLANParam(optional=True),
        perm_filter='is_superuser')

    @superuser
    def project_create(self, operator, projectname, longname, shortname,
                       startdate, enddate, price, inst, vm_type,
                       hpc, meta, vlan=None):
        """Create a new TSD project.

        :param BofhdSession operator:
            The operator's Session, i.e. the user which executes the command.
        :param int vlan:
            If given, sets what VLAN the project's subnet should be set in.
        """
        start = self._parse_date(startdate)
        end = self._parse_date(enddate)

        if end < DateTime.now():
            raise CerebrumError("End date of project has passed: %s"
                                % six.text_type(end).split()[0])
        elif end < start:
            raise CerebrumError(
                "Project can not end before it has begun: from %s to %s" %
                (six.text_type(start).split()[0],
                 six.text_type(end).split()[0]))

        try:
            meta = json.loads(meta)
        except ValueError as e:
            raise CerebrumError('Project metadata must be a valid json: {}'.
                                format(e))
        if not isinstance(meta, dict):
            raise CerebrumError('Project metadata must be a dictionary')

        hpc = self._parse_hpc_yesno(hpc)

        if vm_type not in cereconf.TSD_VM_TYPES:
            raise CerebrumError("Invalid VM-type.")

        ou = self.OU_class(self.db)

        try:
            pid = ou.create_project(projectname)
        except Errors.CerebrumError as e:
            raise CerebrumError(e)

        # Storing the names:
        ou.add_name_with_language(name_variant=self.const.ou_name_long,
                                  name_language=self.const.language_en,
                                  name=longname)
        if shortname:
            ou.add_name_with_language(name_variant=self.const.ou_name_short,
                                      name_language=self.const.language_en,
                                      name=shortname)
        ou.write_db()

        # Storing start date
        ou.add_entity_quarantine(qtype=self.const.quarantine_project_start,
                                 creator=operator.get_entity_id(),
                                 start=DateTime.now(),
                                 end=start,
                                 description='Initial start set by superuser')
        # Storing end date
        ou.add_entity_quarantine(qtype=self.const.quarantine_project_end,
                                 creator=operator.get_entity_id(), start=end,
                                 description='Initial end set by superuser')

        # set metadata traits
        ou.populate_trait(self.const.trait_project_price, strval=price)
        ou.populate_trait(self.const.trait_project_institution, strval=inst)
        ou.populate_trait(self.const.trait_project_hpc, strval=hpc)

        # Set trait for vm_type
        ou.populate_trait(self.const.trait_project_vm_type, strval=vm_type)

        ou.write_db()
        try:
            ou.setup_project(operator.get_entity_id(), vlan)
        except Errors.CerebrumError as e:
            raise CerebrumError(e)

        self._set_project_metadata(operator, ou, meta)

        return 'New project created: {pid}'.format(pid=pid)

    #
    # project setup
    #
    all_commands['project_setup'] = cmd.Command(
        ('project', 'setup'),
        ProjectID(),
        VLANParam(optional=True),
        perm_filter='is_superuser')

    @superuser
    def project_setup(self, operator, project_id):
        """
        Run the setup procedure for a project, updating configuration to
        current settings.

        :param operator: An BofhdSession-instance of the current user session.
        :type  operator: BofhdSession
        :param project_id: Project ID for the given project.
        :type  project_id: str (unicode)

        :returns: A statement that the operation was successful.
        :rtype: str (unicode)
        """

        op_id = operator.get_entity_id()
        ou = self.OU_class(self.db)

        try:
            ou.find_by_tsd_projectid(project_id)
        except Errors.CerebrumError:
            raise CerebrumError("Could not find project '%s'" % project_id)

        ou.setup_project(op_id)

        return 'OK, project reconfigured according to current settings.'

    #
    # project terminate
    #
    all_commands['project_terminate'] = cmd.Command(
        ('project', 'terminate'),
        ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_terminate(self, operator, projectid):
        """Terminate a project by removed almost all of it.

        All information about the project gets deleted except its acronym, to
        avoid reuse of the ID.
        """
        project = self._get_project(projectid)
        # TODO: delete person affiliations?
        # TODO: delete accounts
        project.terminate()
        # self.gateway.delete_project(projectid)
        return 'Project terminated: {projectid}'.format(projectid=projectid)

    #
    # project approve
    #
    all_commands['project_approve'] = cmd.Command(
        ('project', 'approve'),
        ProjectID(),
        VLANParam(optional=True),
        perm_filter='is_superuser')

    @superuser
    def project_approve(self, operator, projectid, vlan=None):
        """Approve an existing project that is not already approved. A project
        is created after we get metadata for it from the outside world, but is
        only visible inside of Cerebrum. When a superuser approves the project,
        it gets spread to AD and gets set up properly.
        """
        project = self._get_project(projectid)
        success_msg = 'Project approved: {projectid}'.format(
            projectid=projectid)

        # Check if the project was already approved
        if not project.get_entity_quarantine(
                only_active=True,
                qtype=self.const.quarantine_not_approved):
            # raise CerebrumError(
            #     'Project already approved (no not_approved quarantine)')
            return success_msg + " (already approved, not changing anything)"

        project.delete_entity_quarantine(self.const.quarantine_not_approved)
        project.write_db()
        try:
            project.setup_project(operator.get_entity_id(), vlan)
        except Errors.CerebrumError as e:
            raise CerebrumError(e)

        if not project.get_entity_quarantine(only_active=True):
            # Active project only if no other quarantines
            # self.gateway.create_project(projectid)
            pass

        self.logger.info(success_msg)
        return success_msg

    #
    # project reject
    #
    all_commands['project_reject'] = cmd.Command(
        ('project', 'reject'),
        ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_reject(self, operator, projectid):
        """Reject a project that is not approved yet.

        All information about the project gets deleted, since it hasn't been
        exported out of Cerebrum yet.
        """
        project = self._get_project(projectid)
        if not project.get_entity_quarantine(
                only_active=True,
                qtype=self.const.quarantine_not_approved):
            raise CerebrumError('Can not reject approved projects, you may '
                                'wish to terminate it instead.')
        project.terminate()
        project.delete()
        try:
            # Double check that project doesn't exist in Gateway.
            # Will raise exception if it's okay.
            self.gateway.delete_project(projectid)
        except Exception:
            pass
        return 'Project deleted: {projectid}'.format(projectid=projectid)

    #
    # project set_enddate
    #
    all_commands['project_set_enddate'] = cmd.Command(
        ('project', 'set_enddate'),
        ProjectID(),
        cmd.Date(),
        perm_filter='is_superuser')

    @superuser
    def project_set_enddate(self, operator, projectid, enddate):
        """Set the end date for a project."""
        project = self._get_project(projectid)
        qtype = self.const.quarantine_project_end
        end = self._parse_date(enddate)
        # The quarantine needs to be removed before it could be added again
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        project.add_entity_quarantine(qtype=qtype,
                                      creator=operator.get_entity_id(),
                                      description='Reset lifetime for project',
                                      start=end)
        project.write_db()
        # If set in the past, the project is now frozen
        if end < DateTime.now():
            # TODO
            # self.gateway.freeze_project(projectid)
            pass
        return 'Project {projectid} updated to end: {date_string}'.format(
            projectid=projectid,
            date_string=date_to_string(end))

    #
    # project set_projectname
    #
    all_commands['project_set_projectname'] = cmd.Command(
        ('project', 'set_projectname'),
        ProjectID(),
        ProjectName(),
        perm_filter='is_superuser')

    @superuser
    def project_set_projectname(self, operator, projectid, projectname):
        """Set the project name for a project."""
        ou = self._get_project(projectid)
        ou.add_name_with_language(name_variant=self.const.ou_name_acronym,
                                  name_language=self.const.language_en,
                                  name=projectname)
        ou.write_db()
        return 'Project {project_id} updated with name: {project_name}'.format(
            project_id=ou.get_project_id(),
            project_name=ou.get_project_name())

    #
    # project set_longname
    #
    all_commands['project_set_longname'] = cmd.Command(
        ('project', 'set_longname'),
        ProjectID(),
        ProjectLongName(),
        perm_filter='is_superuser')

    @superuser
    def project_set_longname(self, operator, projectid, longname):
        """Set the project name for a project."""
        ou = self._get_project(projectid)
        ou.add_name_with_language(name_variant=self.const.ou_name_long,
                                  name_language=self.const.language_en,
                                  name=longname)
        ou.write_db()
        return 'Project {project_id} updated with long name: {lname}'.format(
            project_id=ou.get_project_id(),
            lname=longname)

    #
    # project set_shortname
    #
    all_commands['project_set_shortname'] = cmd.Command(
        ('project', 'set_shortname'),
        ProjectID(),
        ProjectShortName(),
        perm_filter='is_superuser')

    @superuser
    def project_set_shortname(self, operator, projectid, shortname):
        """Set the project name for a project."""
        ou = self._get_project(projectid)
        ou.add_name_with_language(name_variant=self.const.ou_name_short,
                                  name_language=self.const.language_en,
                                  name=shortname)
        ou.write_db()
        return 'Project {project_id} updated with short name: {sname}'.format(
            project_id=ou.get_project_id(),
            sname=shortname)

    #
    # project set_price
    #
    all_commands['project_set_price'] = cmd.Command(
        ('project', 'set_price'),
        ProjectID(),
        ProjectPrice(),
        perm_filter='is_superuser')

    @superuser
    def project_set_price(self, operator, projectid, price):
        proj = self._get_project(projectid)
        status = proj.populate_trait(self.const.trait_project_price,
                                     strval=price)
        proj.write_db()
        return 'Project price {} to {}'.format('set' if status == 'INSERT'
                                               else 'changed',
                                               price)

    #
    # project set_institution
    #
    all_commands['project_set_institution'] = cmd.Command(
        ('project', 'set_institution'),
        ProjectID(),
        ProjectInstitution(),
        perm_filter='is_superuser')

    @superuser
    def project_set_institution(self, operator, projectid, institution):
        proj = self._get_project(projectid)
        status = proj.populate_trait(self.const.trait_project_institution,
                                     strval=institution)
        proj.write_db()
        return 'Project institution {} to {}'.format(
            'set' if status == 'INSERT' else 'changed',
            institution)

    @staticmethod
    def _parse_hpc_yesno(hpc):
        if hpc.lower() in ['hpc_yes', 'yes', 'true', 'y',
                           'j', '1', 't', 's', '+']:
            return 'HPC_YES'
        elif hpc.lower() in ['hpc_no', 'no', 'false',
                             'n', '0', 'f', 'u', '-', 'nil']:
            return 'HPC_NO'
        else:
            raise CerebrumError('HPC must be HPC_YES or HPC_NO')

    #
    # project set_hpc
    #
    all_commands['project_set_hpc'] = cmd.Command(
        ('project', 'set_hpc'),
        ProjectID(),
        ProjectHpc(),
        perm_filter='is_superuser')

    @superuser
    def project_set_hpc(self, operator, projectid, hpc):
        hpc = self._parse_hpc_yesno(hpc)
        proj = self._get_project(projectid)
        status = proj.populate_trait(self.const.trait_project_hpc,
                                     strval=hpc)
        proj.write_db()
        return 'Project hpc {} to {}'.format('set' if status == 'INSERT'
                                             else 'changed',
                                             hpc)

    @staticmethod
    def _get_project_metadata(project):
        """Get a project's metadata field (use EntityNote)."""
        for note in sorted(filter(lambda x: x['subject'] == 'project_metadata',
                                  project.get_notes()),
                           reverse=True,
                           key=lambda x: x['note_id']):
            return json.loads(note['description'])

    @staticmethod
    def _set_project_metadata(operator, project, metadata):
        """Set a project's metadata"""
        project.add_note(operator.get_entity_id(),
                         'project_metadata',
                         json.dumps(metadata, sort_keys=True))

    @staticmethod
    def _add_project_metadata_field(operator, project, key, value):
        meta = AdministrationBofhdExtension._get_project_metadata(project)
        if key not in meta:
            if value == '':
                return 'not set'
            ret = 'inserted'
        elif value == '':
            ret = 'unset'
        elif meta[key] != value:
            ret = 'updated'
        else:
            return 'not changed'
        if value == '':
            del meta[key]
        else:
            meta[key] = value
        AdministrationBofhdExtension._set_project_metadata(operator,
                                                           project,
                                                           meta)
        return ret

    #
    # project set_metadata
    #
    all_commands['project_set_metadata'] = cmd.Command(
        ('project', 'set_metadata'),
        ProjectID(),
        cmd.SimpleString(help_ref='project_metadata'),
        cmd.SimpleString(),
        perm_filter='is_superuser')

    @superuser
    def project_set_metadata(self, operator, projectid, key, value):
        proj = self._get_project(projectid)
        status = self._add_project_metadata_field(operator, proj, key, value)
        return 'Value for {} {}'.format(key, status)

    #
    # project freeze
    #
    all_commands['project_freeze'] = cmd.Command(
        ('project', 'freeze'),
        ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_freeze(self, operator, projectid):
        """Freeze a project."""
        project = self._get_project(projectid)
        when = DateTime.now()

        # The quarantine needs to be removed before it could be added again
        qtype = self.const.quarantine_frozen
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        project.add_entity_quarantine(qtype=qtype,
                                      creator=operator.get_entity_id(),
                                      description='Project freeze',
                                      start=when)
        project.write_db()
        success_msg = 'Project {projectid} is now frozen'.format(
            projectid=projectid)
        try:
            self.gateway.freeze_project(projectid)
        except Gateway.GatewayException as e:
            self.logger.warn("From GW: %s", e)
            success_msg += " (bad result from GW)"
        # Freeze all affiliated acconts:
        # (This functionality was first developed for update_user_freeze.py)
        account = Factory.get('Account')(self.db)
        account_rows = account.list_accounts_by_type(
            ou_id=project.entity_id,
            affiliation=self.const.affiliation_project,
            filter_expired=True,
            account_spread=self.const.spread_gateway_account)
        for account_row in account_rows:
            account.clear()
            account.find(account_row['account_id'])
            if account.has_autofreeze_quarantine:
                if when != account.autofreeze_quarantine_start:
                    # autofreeze quarantine exists for this account
                    # but its start_date is not the same as the one for the
                    # project's freeze quarantine.
                    # Remove the existing quarantine before adding a new one
                    account.remove_autofreeze_quarantine()
                else:
                    # autofreeze quarantine exists for this account
                    # and its start_date is the same as the one for the
                    # project's freeze quarantine. No need to do anything
                    continue
                # add new quarantine using the peoject's freeze-start_date
            account.add_autofreeze_quarantine(
                creator=operator.get_entity_id(),
                description='Auto set due to project-freeze',
                start=when)
            try:
                # N.B. If project_freeze ever supports freeze start-date in the
                # future, the following check prevents bofhd from updating
                # the gateway with project.freeze start-date in the future when
                # there is an active quarantine on this account
                quars = account.get_entity_quarantine(
                    filter_disable_until=True)
                if quars:
                    quars.sort(key=lambda v: v['start_date'])
                if not quars or when < quars[0]['start_date']:
                    # no quarantines or freeze.date < lowest startdate
                    self.gateway.freeze_user(projectid,
                                             account.account_name,
                                             when)
                # else: update_user_freeze.py will make the right decisions
            except Gateway.GatewayException as e:
                self.logger.warn("From GW: %s", e)
                success_msg += " (bad freeze_user result from GW)"
        return success_msg

    #
    # project unfreeze
    #
    all_commands['project_unfreeze'] = cmd.Command(
        ('project', 'unfreeze'),
        ProjectID(),
        perm_filter='is_superuser')

    @superuser
    def project_unfreeze(self, operator, projectid):
        """Unfreeze a project."""
        project = self._get_project(projectid)

        # Remove the quarantine
        qtype = self.const.quarantine_frozen
        for row in project.get_entity_quarantine(qtype):
            project.delete_entity_quarantine(qtype)
            project.write_db()
        success_msg = 'Project {projectid} is now unfrozen'.format(
            projectid=projectid)
        # Only unthaw projects without quarantines
        if not project.get_entity_quarantine(only_active=True):
            try:
                self.gateway.thaw_project(projectid)
            except Gateway.GatewayException as e:
                self.logger.warn("From GW: %s", e)
                success_msg += ' (bad result from GW)'
        else:
            success_msg += ' (project still with other quarantines)'
        # Unfreeze all affiliated acconts:
        # (This functionality was first developed for update_user_freeze.py)
        account = Factory.get('Account')(self.db)
        account_rows = account.list_accounts_by_type(
            ou_id=project.entity_id,
            affiliation=self.const.affiliation_project,
            filter_expired=True,
            account_spread=self.const.spread_gateway_account)
        for account_row in account_rows:
            account.clear()
            account.find(account_row['account_id'])
            if account.has_autofreeze_quarantine:
                account.remove_autofreeze_quarantine()
                # Do not send thaw_user to the gateway, since the account
                # may have other active quarantines
                # unfreeze is rarely extremely urgent, so we
                # let the scheduled job gateway_update.py deal with that
        return success_msg

    #
    # project list
    #
    all_commands['project_list'] = cmd.Command(
        ('project', 'list'),
        ProjectStatusFilter(optional=True),
        fs=cmd.FormatSuggestion(
            '%-11s %-16s %-10s %s', ('pid', 'name', 'entity_id', 'quars'),
            hdr='%-11s %-16s %-10s %s' % ('Project ID', 'Name', 'Entity-Id',
                                          'Quarantines')
        ),
        perm_filter='is_superuser')

    @superuser
    def project_list(self, operator, filter=None):
        """List out all projects by their acronym and status."""
        projects = _Projects(self.logger, self.const, self.OU_class(self.db),
                             exact_match=False, filter=filter)
        return projects.results_sorted_by_name(['pid', 'name', 'entity_id',
                                                'quars'])

    #
    # project unapproved
    #
    all_commands['project_unapproved'] = cmd.Command(
        ('project', 'unapproved'),
        fs=cmd.FormatSuggestion(
            '%-10s %-16s %-10s', ('pid', 'name', 'entity_id'),
            hdr='%-10s %-16s %-10s' % ('ProjectID', 'Name', 'Entity-Id')
        ),
        perm_filter='is_superuser')

    @superuser
    def project_unapproved(self, operator, filter=None):
        """List all projecs with the 'not_approved' quarantine."""

        projects = _Projects(self.logger,
                             self.const,
                             self.OU_class(self.db),
                             exact_match=False,
                             filter=filter)
        projects.filter_by_quarantine(self.const.quarantine_not_approved)
        return projects.results_sorted_by_pid(['pid', 'name', 'entity_id'])

    #
    # project info
    #
    all_commands['project_info'] = cmd.Command(
        ('project', 'info'),
        ProjectID(),
        fs=cmd.FormatSuggestion([
            ("Project ID:       %s\n"
             "Project name:     %s\n"
             "Entity ID:        %d\n"
             "Long name:        %s\n"
             "Short name:       %s\n"
             "Start date:       %s\n"
             "End date:         %s\n"
             "Quarantines:      %s\n"
             "Spreads:          %s",
             ('project_id', 'project_name', 'entity_id', 'long_name',
              'short_name', 'start_date', 'end_date', 'quarantines',
              'spreads')),
            ('REK-number:       %s', ('rek',)),
            ('Price:            %s', ('price',)),
            ('Institution:      %s', ('institution',)),
            ('Hpc:              %s', ('hpc',)),
            ('Metadata:         %s', ('metadata',)),
            ('VM-type:          %s', ('vm_type',)),
            ('VLAN, Subnet:     %-4s, %s', ('vlan_number', 'subnet')),
        ]),
        perm_filter='is_superuser')

    @superuser
    def project_info(self, operator, projectid):
        """Display information about a specified project using ou_info.

        The reason for the semi-sub method is to be able to specify the OU with
        the projectid instead of entity_id. This could probably be handled in
        a much better way.
        """
        project = self._get_project(projectid)
        try:
            pid = project.get_project_id()
        except Errors.NotFoundError:
            pid = '<Missing>'
        ret = {
            'project_id': pid,
            'project_name': project.get_project_name(),
            'entity_id': project.entity_id,
        }
        quars = [self.const.Quarantine(r['quarantine_type']) for r in
                 project.get_entity_quarantine(only_active=True)]
        ret['quarantines'] = ', '.join(six.text_type(q) for q in quars)
        ret['spreads'] = ', '.join(
            six.text_type(self.const.Spread(s['spread'])) for s in
            project.get_spread())
        # Start and end dates:
        ret['start_date'] = '<Not Set>'
        for row in project.get_entity_quarantine(
                self.const.quarantine_project_start):
            ret['start_date'] = date_to_string(row['end_date'])
        ret['end_date'] = '<Not Set>'
        for row in project.get_entity_quarantine(
                self.const.quarantine_project_end):
            ret['end_date'] = date_to_string(row['start_date'])
        # Names:
        ret['long_name'] = '<Not Set>'
        for row in project.search_name_with_language(
                entity_id=project.entity_id,
                name_variant=self.const.ou_name_long):
            ret['long_name'] = row['name']
        ret['short_name'] = '<Not Set>'
        for row in project.search_name_with_language(
                entity_id=project.entity_id,
                name_variant=self.const.ou_name_short):
            ret['short_name'] = row['name']
        ret = [ret, ]
        # REK number
        trait = project.get_trait(self.const.trait_project_rek)
        if trait:
            ret.append({'rek': trait['strval']})
        else:
            ret.append({'rek': '<Not Set>'})
        # Price
        trait = project.get_trait(self.const.trait_project_price)
        if trait:
            ret.append({'price': trait['strval']})
        # Institution
        trait = project.get_trait(self.const.trait_project_institution)
        if trait:
            ret.append({'institution': trait['strval']})
        else:
            ret.append({'institution': '<Not Set>'})
        # HPC
        trait = project.get_trait(self.const.trait_project_hpc)
        if trait:
            ret.append({'hpc': trait['strval']})
        # Metadata
        meta = self._get_project_metadata(project)
        if meta is not None:
            ret.append({'metadata': json.dumps(meta)})
        # VM type
        trait = project.get_trait(self.const.trait_project_vm_type)
        if trait:
            # TODO: how should we store this?
            ret.append({'vm_type': trait['strval']})
        else:
            ret.append({'vm_type': '<Not Set>'})

        # Subnets
        def _subnet_info(subnet_id):
            try:
                sub = Subnet.Subnet(self.db)
                sub.find(subnet_id)
                return {
                    'subnet': '%s/%s' % (sub.subnet_ip, sub.subnet_mask),
                    'vlan_number': six.text_type(sub.vlan_number)
                }
            except dns.Errors.SubnetError:
                sub = IPv6Subnet.IPv6Subnet(self.db)
                sub.find(subnet_id)
                compress = dns.IPv6Utils.IPv6Utils.compress
                return {
                    'subnet': '%s/%s' % (compress(sub.subnet_ip),
                                         sub.subnet_mask),
                    'vlan_number': six.text_type(sub.vlan_number)
                }

        subnets = [_subnet_info(x['entity_id']) for x in
                   project.get_project_subnets()]
        for subnet in sorted(subnets, key=lambda x: x['subnet']):
            ret.append(subnet)

        return ret

    #
    # project metadata
    #
    all_commands['project_metadata'] = cmd.Command(
        ('project', 'metadata'),
        ProjectID(),
        fs=cmd.FormatSuggestion('%-10s%-10s', ('key', 'value'),
                                '{:10}{:10}'.format('Field', 'Value')),
        perm_filter='is_superuser')

    def project_metadata(self, operator, project_id):
        project = self._get_project(project_id)
        ret = []
        for key, val in sorted((self._get_project_metadata(project) or {})
                               .items()):
            ret.append(dict(key=key, value=val))
        return ret

    #
    # project affiliate_entity
    #
    all_commands['project_affiliate_entity'] = cmd.Command(
        ('project', 'affiliate_entity'),
        ProjectID(),
        cmd.EntityType(),
        cmd.Id(help_ref='id:target:group'),
        perm_filter='is_superuser')

    @superuser
    def project_affiliate_entity(self, operator, projectid, etype, ent):
        """Affiliate a given entity with a project. This is a shortcut command
        for helping the TSD-admins instead of using L{trait_set}. Some entity
        types doesn't even work with trait_set, like DnsOwners."""
        ou = self._get_project(projectid)

        # A mapping of what trait to set for what entity type:
        co = self.const
        type2trait = {
            co.entity_group: co.trait_project_group,
            co.entity_dns_owner: co.trait_project_host,
            co.entity_dns_subnet: co.trait_project_subnet,
            co.entity_dns_ipv6_subnet: co.trait_project_subnet6,
        }

        ent = self._get_entity(entity_type=etype, ident=ent)
        if ent.entity_type in (co.entity_person, co.entity_account):
            raise CerebrumError("Use 'person/user affiliation_add'"
                                " for persons/users")
        try:
            trait_type = type2trait[ent.entity_type]
        except KeyError:
            raise CerebrumError("Command does not handle entity type: %s" %
                                co.EntityType(ent.entity_type))
        self.logger.debug("Try to affiliate %s (entity_type %s) with trait:"
                          " %s", ent, ent.entity_type, trait_type)
        # Forcing EntityTrait, since not all instances have this. TBD: Should
        # rather add EntityTrait to cereconf.CLASS_ENTITY instead, but don't
        # know the consequences of that.
        if not isinstance(ent, EntityTrait.EntityTrait):
            entity_id = ent.entity_id
            ent = EntityTrait.EntityTrait(self.db)
            ent.find(entity_id)
        ent.populate_trait(trait_type, target_id=ou.entity_id,
                           date=DateTime.now())
        ent.write_db()
        return 'Entity affiliated with project: {project_id}'.format(
            project_id=ou.get_project_id())

    #
    # project set_vm_type
    #
    all_commands['project_set_vm_type'] = cmd.Command(
        ('project', 'set_vm_type'),
        ProjectID(),
        VMType(),
        perm_filter='is_superuser')

    @superuser
    def project_set_vm_type(self, operator, project_id, vm_type):
        """
        Changes the type of VM-host(s) for the given project.

        :param operator: An BofhdSession-instance of the current user session.
        :type  operator: BofhdSession
        :param project_id: Project ID for the given project.
        :type  project_id: str (unicode)
        :param vm_type: The new setting for VM-host(s) for the project.
        :type  vm_type: str (unicode)

        :returns: A statement that the operation was successful.
        :rtype: str (unicode)
        """
        project = self._get_project(project_id)
        op_id = operator.get_entity_id()

        if vm_type not in cereconf.TSD_VM_TYPES:
            raise CerebrumError("Invalid VM-type")

        project.populate_trait(code='project_vm_type', strval=vm_type)
        project.write_db()
        project.setup_project(op_id)

        return 'OK, vm_type for {project_id} changed to {vm_type}.'.format(
            project_id=project_id,
            vm_type=vm_type)

    #
    # project list_hosts
    #
    all_commands['project_list_hosts'] = cmd.Command(
        ('project', 'list_hosts'),
        ProjectID(),
        fs=cmd.FormatSuggestion(
            [('%-30s %-8s %-20s %-20s', ('name', 'os', 'contact', 'comment'))],
            hdr='%-30s %-8s %-20s %-20s' % ('Name', 'OS', 'Contact', 'Comment')
        ),
        perm_filter='is_superuser')

    @superuser
    def project_list_hosts(self, operator, projectid):
        """List hosts by project."""
        project = self._get_project(projectid)
        ent = EntityTrait.EntityTrait(self.db)
        dnsowner = dns.DnsOwner.DnsOwner(self.db)
        hostinfo = dns.HostInfo.HostInfo(self.db)
        hosts = []

        for row in ent.list_traits(code=self.const.trait_project_host,
                                   target_id=project.entity_id):
            owner_id = row['entity_id']
            dnsowner.clear()
            dnsowner.find(owner_id)
            host = {'name': dnsowner.name}

            for key, trait in (('comment', self.const.trait_dns_comment),
                               ('contact', self.const.trait_dns_contact)):
                trait = dnsowner.get_trait(trait)
                value = trait.get('strval') if trait else None
                host[key] = value or '<not set>'

            try:
                hostinfo.clear()
                hostinfo.find_by_dns_owner_id(owner_id)
                _, hostinfo_os = hostinfo.hinfo.split("\t", 1)
            except Errors.NotFoundError:
                hostinfo_os = '<not set>'
            finally:
                host['os'] = hostinfo_os

            hosts.append(host)

        # Sort by name
        return sorted(hosts, key=lambda x: x['name']) or 'No hosts found'

    def _person_affiliation_add_helper(self,
                                       operator,
                                       person,
                                       ou,
                                       aff,
                                       aff_status):
        """Helper-function for adding an affiliation to a person with permission
        checking. Person is expected to be a person object, while ou, aff and
        aff_status should be the textual representation from the client.
        """
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)

        # Assert that the person already have the affiliation
        has_aff = False
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] == aff_status:
                    has_aff = True
                elif a['source_system'] == self.const.system_manual:
                    raise CerebrumError("Person has conflicting aff_status "
                                        "for this OU/affiliation combination")

        if not has_aff:
            self.ba.can_add_affiliation(operator.get_entity_id(),
                                        person,
                                        ou,
                                        aff,
                                        aff_status)
            person.add_affiliation(ou.entity_id,
                                   aff,
                                   self.const.system_manual,
                                   aff_status)
            person.write_db()

        return ou, aff, aff_status

    #
    # User commands

    # user_create_prompt_func_helper
    # TODO: need to remove unwanted functionality, e.g. affiliations
    def _user_create_prompt_func_helper(self, ac_type, session, *args):
        """A prompt_func on the command level should return

            {'prompt': message_string, 'map': dict_mapping}

        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list.
        """
        all_args = list(args[:])

        if not all_args:
            return {'prompt': "Person identification",
                    'help_ref': "user_create_person_id"}
        arg = all_args.pop(0)
        if arg.startswith("group:"):
            group_owner = True
        else:
            group_owner = False
        if not all_args or group_owner:
            if group_owner:
                group = self._get_group(arg.split(":")[1])
                if all_args:
                    all_args.insert(0, group.entity_id)
                else:
                    all_args = [group.entity_id]
            else:
                c = self._find_persons(arg)
                map_list = [(("%-8s %s", "Id", "Name"), None)]
                for i in range(len(c)):
                    person = self._get_person("entity_id", c[i]['person_id'])
                    map_list.append((
                        ("%8i %s", int(c[i]['person_id']),
                         person.get_name(self.const.system_cached,
                                         self.const.name_full)),
                        int(c[i]['person_id'])))
                if not len(map_list) > 1:
                    raise CerebrumError("No persons matched")
                return {'prompt': "Choose person from list",
                        'map': map_list,
                        'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        if not group_owner:
            person = self._get_person("entity_id", owner_id)
            existing_accounts = []
            account = self.Account_class(self.db)
            for r in account.list_accounts_by_owner_id(person.entity_id):
                account = self._get_account(r['account_id'], idtype='id')
                if account.expire_date:
                    exp = date_to_string(account.expire_date)
                else:
                    exp = '<not set>'
                existing_accounts.append("%-10s %s" % (account.account_name,
                                                       exp))
            if existing_accounts:
                existing_accounts = "Existing accounts:\n%-10s %s\n%s\n" % (
                    "uname", "expire", "\n".join(existing_accounts))
            else:
                existing_accounts = ''
            if existing_accounts:
                if not all_args:
                    return {'prompt': "%sContinue? (y/n)" % existing_accounts}
                yes_no = all_args.pop(0)
                if not yes_no == 'y':
                    raise CerebrumError("Command aborted at user request")
            if not all_args:
                map_list = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map_list.append((("%s", name),
                                     {'ou_id': int(aff['ou_id']),
                                      'aff': int(aff['affiliation'])}))
                if not len(map_list) > 1:
                    raise CerebrumError("Person has no affiliations."
                                        " Try person affiliation_add")
                return {'prompt': 'Choose affiliation from list',
                        'map': map_list}
            affiliation = all_args.pop(0)
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type'}
            all_args.pop(0)
        if ac_type == 'PosixUser':
            if not all_args:
                return {'prompt': "Shell", 'default': 'bash'}
            all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = Factory.get('PosixUser')(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last)]
                    ou = self._get_ou(ou_id=affiliation['ou_id'])
                    uname_generator = UsernameGenerator()
                    # create a validation callable (function)
                    vfunc = partial(posix_user.validate_new_uname,
                                    self.const.account_namespace,
                                    owner_id=owner_id)
                    sugg = uname_generator.suggest_unames(
                        self.const.account_namespace,
                        fname,
                        lname,
                        maxlen=cereconf.USERNAME_MAX_LENGTH,
                        prefix='%s-' % ou.get_project_id(),
                        validate_func=vfunc)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError("Too many arguments")

    # user_create_prompt_func
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser',
                                                    session,
                                                    *args)

    #
    # user create
    #
    all_commands['user_create'] = cmd.Command(
        ('user', 'create'),
        prompt_func=user_create_prompt_func,
        fs=cmd.FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')

    def user_create(self, operator, *args):
        """Creating a new account."""

        # TODO: remove functionality not needed in TSD! This method is copied
        # from UiA, and needs to be modified

        if args[0].startswith('group:'):
            group_id, np_type, shell, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
        else:
            if len(args) == 5:
                idtype, person_id, affiliation, shell, uname = args
            else:
                idtype, person_id, yes_no, affiliation, shell, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None

        # Systems in TSD does not accept accounts in uppercase - would get in
        # huge trouble!
        if uname != uname.lower():
            raise CerebrumError("Account names cannot contain capital letters")

        # TODO: Add a check for personal accounts to have the project name as a
        # prefix?
        # if owner_type == self.const.entity_person:
        #    ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
        #    ou = self._get_ou(ou_id=ou_id)
        #    pid = ou.get_project_id()
        #    if not uname.startswith(pid):
        #        raise CerebrumError('Username must have projectid as prefix')

        posix_user = Factory.get('PosixUser')(self.db)
        if not posix_user.validate_new_uname(
                domain=self.const.account_namespace,
                uname=uname,
                owner_id=owner_id):
            # in case the user overrides the suggested username
            raise CerebrumError('This Account name is already taken')
        # TODO: disk?
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        posix_user.clear()
        self.ba.can_create_user(operator.get_entity_id(), owner_id, None)

        # TODO: get the project's standard dfg's entity_id and use that
        if owner_type == self.const.entity_person:
            ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
            self._get_ou(ou_id=ou_id)  # make sure it exists

        posix_user.populate(uid, None, None, shell,
                            name=uname,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            np_type=np_type,
                            creator_id=operator.get_entity_id(),
                            expire_date=None)
        try:
            posix_user.write_db()
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            posix_user.write_db()
            if posix_user.owner_type == self.const.entity_person:
                self._user_create_set_account_type(posix_user,
                                                   owner_id,
                                                   ou_id,
                                                   affiliation)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            posix_user.add_spread(self.const.Spread(spread))
        operator.store_state("new_account_passwd",
                             {'account_id': int(posix_user.entity_id),
                              'password': passwd})
        return "Ok, created %s, UID: %s" % (posix_user.account_name, uid)

    #
    # user generate_otpkey
    #
    all_commands['user_generate_otpkey'] = cmd.Command(
        ('user', 'generate_otpkey'),
        cmd.AccountName(),
        cmd.SimpleString(help_ref='otp_type', optional=True))

    def user_generate_otpkey(self, operator, accountname, otp_type=None):
        account = self._get_account(accountname)
        self.ba.can_generate_otpkey(operator.get_entity_id(), account)

        # User must be approved first, to exist in the GW
        if not account.is_approved():
            raise CerebrumError("User is not approved: %s" % accountname)

        try:
            uri = account.regenerate_otpkey(otp_type)
        except Errors.CerebrumError as e:
            raise CerebrumError("Failed generating OTP-key: %s" % e)

        # Generate a list of all the accounts for the person
        ac = Factory.get('Account')(self.db)
        ou = self.OU_class(self.db)
        ac_list = {}
        for row in account.search(owner_id=account.owner_id,
                                  spread=self.const.spread_gateway_account):
            ac.clear()
            ac.find(row['account_id'])
            actypes = ac.get_account_types()
            if len(actypes) < 1:
                continue
            if len(actypes) > 1:
                raise CerebrumError('Incorrect number of project'
                                    ' affiliations: %s' % row['name'])
            ou.clear()
            ou.find(actypes[0]['ou_id'])
            ac_list[row['name']] = ou.get_project_id()

        msg = uri + '\n'

        # Send all to gateway:
        for name, pid in ac_list.iteritems():
            try:
                self.gateway.user_otp(pid, name, uri)
            except Gateway.GatewayException as e:
                self.logger.warn("OTP failed for %s: %s", name, e)
                msg += '\nFailed updating GW for: %s' % name
            else:
                msg += '\nUpdated GW for: %s' % name
        return msg

    #
    # user approve
    #
    all_commands['user_approve'] = cmd.Command(
        ('user', 'approve'),
        cmd.AccountName(),
        perm_filter='is_superuser')

    def user_approve(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError('Only superusers could approve users')

        ac = self._get_account(accountname)

        if ac.owner_type != self.const.entity_person:
            raise CerebrumError('Non-personal account, use: quarantine remove')

        rows = ac.list_accounts_by_type(
            account_id=ac.entity_id,
            affiliation=(self.const.affiliation_project,
                         self.const.affiliation_pending))
        if not rows:
            raise CerebrumError('Account not affiliated with any project')

        if len(rows) != 1:
            raise CerebrumError('Account has more than one affiliation')

        ou = self._get_ou(rows[0]['ou_id'])
        if not ou.is_approved():
            raise CerebrumError('Project not approved: %s' %
                                ou.get_project_id())

        # Update the person affiliation, if not correct:
        pe = Factory.get('Person')(self.db)
        pe.find(ac.owner_id)

        if pe.list_affiliations(pe.entity_id, ou_id=ou.entity_id,
                                affiliation=self.const.affiliation_pending):
            pe.delete_affiliation(ou.entity_id, self.const.affiliation_pending,
                                  self.const.system_nettskjema)

        if not pe.list_affiliations(
                pe.entity_id,
                ou_id=ou.entity_id,
                affiliation=self.const.affiliation_project):
            pe.populate_affiliation(
                source_system=self.const.system_manual,
                ou_id=ou.entity_id,
                affiliation=self.const.affiliation_project,
                status=self.const.affiliation_status_project_member)

        pe.write_db()

        # Update the account's affiliation:
        try:
            ac.del_account_type(ou.entity_id, self.const.affiliation_pending)
        except Errors.NotFoundError:
            pass
        ac.set_account_type(ou.entity_id, self.const.affiliation_project)
        ac.write_db()

        # Remove the quarantine, if set:
        if ac.get_entity_quarantine(self.const.quarantine_not_approved,
                                    only_active=True):
            ac.delete_entity_quarantine(self.const.quarantine_not_approved)
            ac.write_db()

        # Promote posix
        pu = Factory.get('PosixUser')(self.db)

        try:
            pu.find(ac.entity_id)
        except Errors.NotFoundError:
            pu.clear()
            uid = pu.get_free_uid()
            pu.populate(uid, None, None, self.const.posix_shell_bash,
                        parent=ac,
                        creator_id=operator.get_entity_id())
            pu.write_db()

        return 'Approved {account_name} for project {project_id}'.format(
            account_name=ac.account_name,
            project_id=ou.get_project_id())

    #
    # user delete
    #
    all_commands['user_delete'] = cmd.Command(
        ("user", "delete"),
        cmd.AccountName(),
        perm_filter='can_delete_user')

    def user_delete(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError("User is already deleted")
        pu = Factory.get('PosixUser')(self.db)
        try:
            pu.find(account.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            pu.delete_posixuser()
            pu.write_db()
        account.deactivate()
        account.write_db()
        return 'User {account_name} is deactivated'.format(
            account_name=account.account_name)

    #
    # user unapproved
    #
    all_commands['user_unapproved'] = cmd.Command(
        ('user', 'unapproved'),
        fs=cmd.FormatSuggestion(
            '%-10d %-16s %s', ('entity_id', 'username', 'created'),
            hdr='%-10s %-16s %s' % ('Entity-Id', 'Username', 'Created')
        ),
        perm_filter='is_superuser')

    @superuser
    def user_unapproved(self, operator):
        """
        List all users with the 'not_approved' quarantine
        """
        ac = Factory.get('Account')(self.db)
        q_list = ac.list_entity_quarantines(
            entity_types=self.const.entity_account,
            quarantine_types=self.const.quarantine_not_approved,
            only_active=True)
        unapproved_users = list()
        for q_element in q_list:
            ac.clear()
            ac.find(q_element['entity_id'])
            unapproved_users.append({'entity_id': q_element['entity_id'],
                                     'username': ac.account_name,
                                     'created': ac.created_at})
        # sort by account name
        unapproved_users.sort(key=lambda x: x['username'])
        return unapproved_users

    #
    # group create
    #
    all_commands['group_create'] = cmd.Command(
        ("group", "create"),
        ProjectID(),
        cmd.GroupName(),
        GroupDescription(),
        perm_filter='is_superuser')

    @superuser
    def group_create(self, operator, project, group, description):
        """Method for creating a new group"""
        self.logger.debug2("group create start")
        ou = self._get_project(project)
        groupname = '%s-%s' % (project, group)

        gr = Utils.Factory.get('PosixGroup')(self.db)
        name_error = gr.illegal_name(groupname)
        if name_error:
            raise CerebrumError("Illegal name: {!s}".format(name_error))

        # Check that no account exists with the same name. Necessary for AD:
        ac = self.Account_class(self.db)
        try:
            ac.find_by_name(groupname)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError('An account exists with name: %s' % groupname)

        self.ba.can_create_group(operator.get_entity_id())
        gr.populate(creator_id=operator.get_entity_id(),
                    visibility=self.const.group_visibility_all,
                    name=groupname,
                    description=description)

        gr.write_db()

        # Connect group to project:
        gr.populate_trait(code=self.const.trait_project_group,
                          target_id=ou.entity_id,
                          date=DateTime.now())
        gr.write_db()

        if not tuple(ou.get_entity_quarantine(only_active=True)):
            for spread in cereconf.BOFHD_NEW_GROUP_SPREADS:
                gr.add_spread(self.const.Spread(spread))
        return "Group %s created, group_id=%s, GID=%s" % (
            gr.group_name, gr.entity_id, gr.posix_gid)

    def _spread_sync_group(self, account, group=None):
        """Override from UiO to support personal file groups in TSD.

        This should rather be done automatically by the PosixUser mixin class
        for TSD, and UiO, but that requires some refactoring of bofhd. We don't
        know the consequences of that quite yet.
        """
        if account.np_type or account.owner_type == self.const.entity_group:
            return
        pu = Factory.get('PosixUser')(self.db)
        try:
            pu.find(account.entity_id)
        except Errors.NotFoundError:
            return
        # The PosixUser class should handle most of the functionality
        pu.write_db()

    #
    # Host commands
    #
    all_commands['host_list_projects'] = cmd.Command(
        ('host', 'list_projects'),
        HostId(),
        fs=cmd.FormatSuggestion(
            [('%-30s %-10s %-12s', ('name', 'project_id', 'project_name'),)],
            hdr='%-30s %-10s %-12s' % ('Name', 'Project ID', 'Project name')),
        perm_filter='is_superuser')

    @superuser
    def host_list_projects(self, operator, host_id):
        """List projects by host."""
        host = self._get_host(host_id)
        ent = EntityTrait.EntityTrait(self.db)
        project = self.OU_class(self.db)
        projects = []

        for row in ent.list_traits(code=self.const.trait_project_host,
                                   entity_id=host.entity_id):
            project.clear()
            project.find(row['target_id'])
            projects.append({
                'name': host.name,
                'project_id': project.get_project_id(),
                'project_name': project.get_project_name(),
            })

        # Sort by project ID
        return sorted(projects, key=lambda x: x['project_id']) or \
            'No projects found for this host'

    #
    # Subnet commands

    def _get_all_subnets(self):
        """Fetch all subnets in a human-readable format.

        :rtype: list
        :returns: A list with a dictionary per subnet
        """
        ou = self.OU_class(self.db)
        # Project entity ID -> external project ID
        ent2ext = dict((x['entity_id'], x['external_id']) for x in
                       ou.list_external_ids(
                           id_type=self.const.externalid_project_id))

        # Subnet -> external project ID
        subnet2project = {}
        for row in ou.list_traits(code=(self.const.trait_project_subnet6,
                                        self.const.trait_project_subnet)):
            subnet2project[row['entity_id']] = ent2ext.get(row['target_id'])

        # IPv4
        subnet = Subnet.Subnet(self.db)
        subnets = []
        for row in subnet.search():
            subnets.append({
                'subnet': '%s/%s' % (row['subnet_ip'], row['subnet_mask']),
                'vlan_number': six.text_type(row['vlan_number']),
                'project_id': subnet2project.get(row['entity_id']),
                'description': row['description']})

        # IPv6
        subnet6 = IPv6Subnet.IPv6Subnet(self.db)
        compress = dns.IPv6Utils.IPv6Utils.compress
        for row in subnet6.search():
            subnets.append({
                'subnet': '%s/%s' % (compress(row['subnet_ip']),
                                     row['subnet_mask']),
                'vlan_number': six.text_type(row['vlan_number']),
                'project_id': subnet2project.get(row['entity_id']),
                'description': row['description']})
        return subnets

    #
    # subnet list
    #
    all_commands['subnet_list'] = cmd.Command(
        ('subnet', 'list'),
        fs=cmd.FormatSuggestion([
            ('%-30s %6s %7s %s', ('subnet', 'vlan_number', 'project_id',
                                  'description',),)],
            hdr='%-30s %6s %7s %s' % ('Subnet', 'VLAN', 'Project',
                                      'Description')),
        perm_filter='is_superuser')

    @superuser
    def subnet_list(self, operator):
        """Return a list of all subnets."""
        # Sort by subnet
        return sorted(self._get_all_subnets(), key=lambda x: x['subnet'])

    #
    # subnet search
    #
    all_commands['subnet_search'] = cmd.Command(
        ("subnet", "search"),
        SubnetSearchType(),
        FnMatchPattern(),
        fs=cmd.FormatSuggestion([
            ('%-30s %6s %7s %s', ('subnet', 'vlan_number', 'project_id',
                                  'description',),)],
            hdr='%-30s %6s %7s %s' % ('Subnet', 'VLAN',
                                      'Project', 'Description')),
        perm_filter='is_superuser')

    @superuser
    def subnet_search(self, operator, search_type, pattern):
        """Wildcard search for subnets.

        :type search_type: str
        :param search_type: filter subnets by this key

        :type pattern: str
        :param pattern: wildcard search pattern
        """
        from fnmatch import fnmatch

        type2key = {
            'subnet': 'subnet',
            'vlan': 'vlan_number',
            'project': 'project_id',
            'description': 'description',
        }

        if search_type not in type2key.keys():
            raise CerebrumError("Unknown search type (%s)" % search_type)

        # Fetch and filter subnets
        subnets = self._get_all_subnets()
        key = type2key[search_type]
        results = [sn for sn in subnets if fnmatch(sn[key], pattern)]

        # Sort by subnet
        return sorted(results, key=lambda x: x['subnet']) or 'No matches found'

    #
    # subnet create
    #
    #   all_commands['subnet_create'] = cmd.Command(
    #      ("subnet", "create"),
    #      SubnetParam(), cmd.Description(), Vlan(),
    #      perm_filter='is_superuser')

    @superuser
    def subnet_create(self, operator, subnet, description, vlan):
        """Create a new subnet, if the range is not already reserved.

        TODO: Should it be possible to specify a range, or should we find one
        randomly?
        """
        subnet = Subnet.Subnet(self.db)
        subnet.populate(subnet, description=description, vlan=vlan)

        # TODO: more checks?
        subnet.write_db(perform_checks=True)
        return 'Subnet created: {subnet}'.format(subnet=subnet)

    def add_subnet(subnet, description, vlan, perform_checks=True):
        pass


uio_helpers = [
    '_entity_info',
    '_fetch_member_names',
    '_group_add',
    '_group_remove',
]

copy_hidden = filter(
    lambda x: x in cereconf.TSD_ALLOWED_ENDUSER_COMMANDS,
    [
        'access_list_alterable',
        'get_constant_description',
    ]
)

copy_uio = filter(
    lambda x: x in cereconf.TSD_ALLOWED_ENDUSER_COMMANDS,
    [
        'group_info',
        'group_list',
        'group_memberships',
        'group_set_description',
        'misc_affiliations',
        'misc_check_password',
        'misc_verify_password',
        'spread_list',
        'user_info',
    ]
)


@copy_command(
    uio_base,
    'hidden_commands', 'hidden_commands',
    commands=copy_hidden)
@copy_command(
    uio_base,
    'all_commands', 'all_commands',
    commands=copy_uio)
@copy_func(
    uio_base,
    methods=uio_helpers + copy_uio + copy_hidden)
class EnduserBofhdExtension(TSDBofhdExtension):
    """The bofhd commands for the end users of TSD.

    End users are Project Administrators (PA), which should have full control
    of their project, and Project Members (PM) which have limited privileges.
    """

    all_commands = {}
    hidden_commands = {}
    parent_commands = True

    @classmethod
    def list_commands(cls, attr):
        commands = super(EnduserBofhdExtension, cls).list_commands(attr)
        # Filter out all commands that are not explicitly allowed (needed
        # because superclasses may define additional commands)
        filtered = dict(
            (name, cmd) for name, cmd in commands.iteritems()
            if name in cereconf.TSD_ALLOWED_ENDUSER_COMMANDS)
        return filtered


class ContactCommands(bofhd_contact_info.BofhdContactCommands):
    authz = TsdContactAuth
