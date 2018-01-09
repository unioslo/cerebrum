#!/usr/bin/env python
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
"""OU mixin for the TSD project.

A TSD project is stored as an OU, which then needs some extra functionality,
e.g. by using the acronym as a unique identifier - the project name - and the
project ID stored as an external ID. When a project has finished, we will
delete all details about the project, except the project's OU and its external
ID and acronym, to avoid reuse of the project ID and name for later projects.
"""
import re
import itertools
from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.database import DatabaseError
from Cerebrum.OU import OU
from Cerebrum.Utils import Factory
from Cerebrum.modules import dns
from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent
from Cerebrum.modules.EntityTrait import EntityTrait

from Cerebrum.modules.tsd import TSDUtils


class TsdProjectMixin(OU):
    u""" Adds the idea of an OU as a project.

    In TSD, OUs are 'projects' that we use to bind entities together. This
    mixin adds:

    project IDs
        Each OU/project is given a unique, generated project ID, e.g. 'p08'.
        This ID uniquely identifies a project. We use EntityExternalId to store
        the project Id.

    project acronyms
        Each OU/project must be given a unique short name, or acronym, e.g.
        'my-proj'. This name uniquely identifies a project. We use
        EntityNameWithLanguage to store the project acronym under the language
        'english'.
    """

    def get_next_free_project_id(self):
        u""" Return a procjet_id for use with a new project. """
        for number in itertools.count():
            candidate = 'p%02d' % number
            if not list(
                self.list_external_ids(
                    id_type=self.const.externalid_project_id,
                    external_id=candidate)):
                return candidate

    def get_project_id(self):
        u""" Get the project ID of this project. """
        ret = self.get_external_id(id_type=self.const.externalid_project_id)
        if ret:
            return ret[0]['external_id']
        raise Errors.NotFoundError(
            'Mandatory project ID not found for %s' % self.entity_id)

    @property
    def project_id(self):
        u""" The project id of this project/ou. """
        try:
            return self.get_project_id()
        except Errors.NotFoundError:
            raise AttributeError("OU (%r) is missing project id!",
                                 self.entity_id)

    def get_project_name(self):
        """Shortcut for getting the given OU's project name."""
        try:
            project_name = self.get_name_with_language(
                self.const.ou_name_acronym,
                self.const.language_en)
        except Errors.CerebrumError:
            project_name = '<Not Set>'
        return project_name

    @property
    def project_name(self):
        u""" The project name for this project/ou. """
        return self.get_project_name()

    @property
    def project_int(self):
        u""" The project id as an int.

        Example:
            p01 -> 1
            p29 -> 29
        """
        return int(self.project_id[1:])

    def find_by_tsd_projectid(self, project_id):
        u""" Finds Project OU by project id.

        This is a L{find}-method, it will populate this entity with any project
        it finds.

        :param str project_id: The project ID to find.

        :raise NotFoundError: If project_id is not found.
        """
        return self.find_by_external_id(
            entity_type=self.const.entity_ou,
            id_type=self.const.externalid_project_id,
            external_id=project_id)

    def find_by_tsd_projectname(self, project_name):
        u""" Finds Project OU by project name.

        This is a L{find}-method, it will populate this entity with any project
        it finds.

        :param str project_name: The short-name of the project to find.

        :raise NotFoundError:
            If the project is not found.
        :raise TooManyRowsError:
            If multiple projects matches the name (should not be possible).
        """
        matched = self.search_tsd_projects(name=project_name, exact_match=True)
        if not matched:
            raise Errors.NotFoundError(u"Unknown project: %s" % project_name)
        if len(matched) != 1:
            raise Errors.TooManyRowsError(
                u"Found several OUs with given name: %s" % project_name)
        return self.find(matched[0]['entity_id'])

    def populate_external_id(self, source_system, id_type, external_id):
        u"""Sets external id for project.

        This overrides the parent method to add uniqueness for project IDs.

        :see: EntityExternalId.populate_external_id
        """
        # Check that the ID is not in use
        if id_type == self.const.externalid_project_id:
            for row in self.list_external_ids(id_type=id_type,
                                              external_id=external_id):
                raise Errors.CerebrumError(u"Project ID already in use")

        return super(TsdProjectMixin, self).populate_external_id(
            source_system, id_type, external_id)

    def search_tsd_projects(self, name=None, exact_match=True):
        u"""Search method for finding projects by given input.

        :param str name: The project name.
        :param bool exact_match:
            If it should search for the exact name, or through an sql query
            with LIKE.

        :return list:
            Returns a list of all matching project `db_rows` (see
            L{search_name_with_languate}).
        """
        return self.search_name_with_language(
            entity_type=self.const.entity_ou,
            name_variant=self.const.ou_name_acronym,
            name=name, exact_match=exact_match)

    def add_name_with_language(self, name_variant, name_language, name):
        u"""Adds name to project.

        This overrides the parent method to add verification of names.

        :see: EntityNameWithLanguage.add_name_with_language
        """
        if name_variant == self.const.ou_name_acronym:
            # TODO: Do we accept *changing* project names?

            # Validate the format of the acronym. The project name is used as a
            # prefix for other entities, like accounts, groups and machines, so
            # we need to be careful.
            self._validate_project_name(name)
            matched = self.search_tsd_projects(name=name, exact_match=True)
            if any(r['name'] == name for r in matched):
                raise Errors.CerebrumError('Acronym already in use: %s' % name)
        return super(TsdProjectMixin, self).add_name_with_language(
            name_variant, name_language, name)

    def _validate_project_name(self, name):
        """Check if a given project name is valid.

        Project names are used to identify project entities in other systems,
        so we need to enforce some limits to avoid potential problems.

        Requirements
        ------------
        Can not contain spaces
            TODO: Why?

        Can not contain commas.
            This is due to AD's way of identifying objects. Example:
            CN=username,OU=projectname,DC=tsd,DC=uio,DC=no.

        Can not contain the SQL wildcards ? and %.
            This is a convenience limit, to be able to use Cerebrum's existing
            API without modifications.

        Can not contain control characters.

        Can not contain characters outside of ASCII.
            This is to avoid unexpected encoding issues.

        TBD: A maximum length in the name?
            AD probably has a limit. As a prefix, it should be a bit less than
            AD's limit.

        In practice, we only accept regular alphanumeric characters in ASCII,
        in addition to some punctuation characters, like colon, dash and
        question marks. This would need to be extended in the future.

        :param str name:
            The name to check.

        :raise Errors.CerebrumError:
            If the given project name was not accepted
        """
        m = re.search('[^A-Za-z0-9_\-:;\*"\'\#\&\=!\?]', name)
        if m:
            raise Errors.CerebrumError(
                'Invalid characters in projectname: %s' % m.group())
        if len(name) < 3:
            raise Errors.CerebrumError('Project name too short')
        if len(name) > 8:  # TBD: or 6?
            raise Errors.CerebrumError('Project name is too long')
        return True

    def create_project(self, project_name):
        """ Create a new project in TSD.

        Note that this method calls `write_db`.

        :param str project_name:
            A unique, short project name to use to identify the project.
            This is not the *project ID*, which is created automatically.

        :return str:
            The generated project ID for the new project.
        """
        # Check if given project name is already in use:
        if tuple(self.search_tsd_projects(name=project_name,
                                          exact_match=True)):
            raise Errors.CerebrumError(
                'Project name already taken: %s' % project_name)
        self.populate()
        self.write_db()
        # Set a generated project ID
        self.affect_external_id(self.const.system_cached,
                                self.const.externalid_project_id)
        pid = self.get_next_free_project_id()
        self.populate_external_id(self.const.system_cached,
                                  self.const.externalid_project_id, pid)
        self.write_db()
        # Set the project name
        self.add_name_with_language(name_variant=self.const.ou_name_acronym,
                                    name_language=self.const.language_en,
                                    name=project_name)
        self.write_db()
        return pid


class OULockMixin(OU):
    u""" Adds methods to lock OUs.

    This mixin uses EntityQuarantine to lock OUs. The following quarantine
    locks exists:

    Approve
        All new projects should have an active quarantine (not_approved) until
        manually approved.

    Expire
        All projects should get an expire date on approval. This expire_date is
        stored as a delayed quarantine (project_end).

    Freeze
        All prjects can get a 'freeze' quarantine to temporarily lock the
        project (e.g. for setting a delayed start date).
    """

    def is_approved(self):
        u""" Check if this project has been approved by TSD-admins.

        The approval is registered through a quarantine.

        @rtype: bool
        @return: True if the project is approved.
        """
        return not tuple(self.get_entity_quarantine(
            qtype=self.const.quarantine_not_approved,
            only_active=True))

    @property
    def expire_date(self):
        """The projects expire date."""
        # TODO: Should we define a setter or a deleter?
        quars = self.get_entity_quarantine(
            qtype=self.const.quarantine_project_end)
        if quars:
            return quars[0]['start_date']
        else:
            return None

    @property
    def has_freeze_quarantine(self):
        """ If this project is currently frozen.

        :return bool:
            True if the OU (Project) has freeze quarantine(s),
            False otherwise.
        """
        return bool(
            self.get_entity_quarantine(
                qtype=self.const.quarantine_frozen))

    @property
    def freeze_quarantine_start(self):
        """ Start date of any freeze quarantine on the project.

        :rtype: mx.DateTime, NoneType
        :return:
            Return the start_date (mx.DateTime) of the freeze quarantine
            (Note: None will be returned in a case of no freeze-quarantines
            for the OU (Project). Hence mx.DateTime return value is a proof
            that the OU (Project) has at least one autofreeze-quarantine,
            while return value None is not a proof of the opposite
        """
        frozen_quarantines = self.get_entity_quarantine(
            qtype=self.const.quarantine_frozen)
        if frozen_quarantines:
            return frozen_quarantines[0]['start_date']
        return None


class OUAffiliateMixin(OU):
    u""" Adds the ability to affiliate entities with OU.

    A project affiliation is stored as an EntityTrait on the affiliated entity,
    with this OU as 'target'.

    Trait types and supported entitiy types are listed in
    L{_get_affiliate_trait}.
    """

    def _get_affiliate_trait(self, etype):
        u""" Get trait used to affiliate an entity with this project.

        :type etype:
            Constants.EntityType, int, str
        :param entity_type:
            The entity type
        """
        type2trait = {
            self.const.entity_group:
                self.const.trait_project_group,
            self.const.entity_dns_owner:
                self.const.trait_project_host,
            self.const.entity_dns_subnet:
                self.const.trait_project_subnet,
            self.const.entity_dns_ipv6_subnet:
                self.const.trait_project_subnet6,
        }
        entity_type = (
            etype if isinstance(etype, self.const.EntityType)
            else self.const.human2constant(etype, self.const.EntityType))
        try:
            return type2trait[entity_type]
        except KeyError:
            raise Errors.CerebrumError(
                u"Entity type %s (%r) cannot be affilated with project." %
                (entity_type, etype))

    def get_affiliated_entities(self, entity_type):
        u""" Gets entities that are affiliated with this project.

        :type etype:
            Constants.EntityType, int, str
        :param entity_type:
            The entity type

        :returns generator:
            Returns the same `db_rows` as EntityTrait.list_traits.

        :see:
            EntityTrait.list_traits
        """
        # TDB: Support lookup of multiple entity types?
        trait = self._get_affiliate_trait(entity_type)
        for row in self.list_traits(code=trait, target_id=self.entity_id):
            yield row

    def is_affiliated_entity(self, entity):
        u""" Check if entity is affiliated with project.

        :param Entity entity:
            An entity to check

        :return bool:
            Returns True if entity is affiliated with project
        """
        try:
            trait_code = self._get_affiliate_trait(entity.entity_type)
        except Errors.CerebrumError:
            return False

        try:
            trait = EntityTrait(self._db)
            trait.find(entity.entity_id)
            return trait.get_trait(trait_code)['target_id'] == self.entity_id
        except Errors.NotFoundError:
            return False
        except TypeError:
            return False

    def affiliate_entity(self, entity):
        u""" Affiliate an entity with this project.

        :type entity: Group, DnsOwner, DnsSubnet, DnsSubnet6
        :param entity:
            An entity to affiliate with this project

        """
        trait_code = self._get_affiliate_trait(entity.entity_type)
        trait = EntityTrait(self._db)
        trait.find(entity.entity_id)
        trait.populate_trait(trait_code,
                             target_id=self.entity_id,
                             date=DateTime.now())
        trait.write_db()


class TsdDefaultEntityMixin(TsdProjectMixin, OUAffiliateMixin):
    u""" Create and affiliate entities with project.

    Project group
        A group that is affiliated with a project.

    Project person
        A person that is affiliated with a project

    Project user
        TODO

    A project group given a group name that consists of a 'base name' that is
    prefixed with the project id.

    Each created group is automatically affiliated with the project OU.
    """

    def apply_spreads(self, entity, spreads):
        u""" Find spreads and add to entity.

        :param EntitySpread entity:
            A populated entity with spread-support.

        :param list spreads:
            A list of spreads (Constants.Spread, int, str).
        """
        for spread in [s if isinstance(s, self.const.Spread)
                       else self.const.Spread(s)
                       for s in (spreads or [])]:
            if not entity.has_spread(spread):
                entity.add_spread(spread)

    def _project_entity_name(self, basename):
        u""" Get real entity name from base name. """
        return '-'.join((self.project_id, basename)).lower()

    def get_project_group(self, basename):
        u""" Get a project group from its basename. """
        gr = Factory.get('Group')(self._db)
        gr.find_by_name(self._project_entity_name(basename))
        return gr

    def create_project_group(self, creator_id, basename,
                             description=None):
        u""" Create or update a project group.

        :param int creator_id:
            The creator that we create this group on behalf of.
        :param str basename:
            The group base name. The actual group name will be prefixed with
            the project ID of this project.
        :param str description:
            The group description.

        :return Group:
            The created or updated group.
        """
        name = self._project_entity_name(basename)
        description = ('Group %r' % self._project_entity_name(basename)
                       if description is None else description)
        gr = Factory.get('PosixGroup')(self._db)
        try:
            gr.find_by_name(name)
            if gr.description != description:
                gr.description = description
                gr.write_db()
        except Errors.NotFoundError:
            gr.populate(creator_id, self.const.group_visibility_all,
                        name, description)
            gr.write_db()

        if not self.is_affiliated_entity(gr):
            self.affiliate_entity(gr)
        return gr

    def update_project_group_members(self, basename, selectors=()):
        u""" Update group based on selector.

        :param str basename:
            The basename for the group to update.

        :param tuple selectors:
            A list of string selectors to find new members to add
            (default: None, will fetch membership selectors from config).

            Each selector is a string that consists of a ':'-separated
            member-type and member-selector. The following
            member-types and member-selectors are supported:

            - 'group:<basename>'
            - 'person_aff:<affiliation>'
            - 'person_aff:<affiliation>/<aff-status>'

            Example

                ('group:admin-group',
                 'person_aff:PROJECT',
                 'person_aff:PROJECT/member', )
        """
        gr = self.get_project_group(basename)
        selectors = (selectors or ())

        def _aff_accounts(aff, status):
            pe = Factory.get('Person')(self._db)
            ac = Factory.get('Account')(self._db)
            for p_row in pe.list_affiliations(
                    ou_id=self.entity_id,
                    affiliation=aff,
                    status=status,
                    fetchall=False):
                for a_row in ac.list_accounts_by_type(
                        person_id=p_row['person_id'],
                        ou_id=self.entity_id,
                        fetchall=False):
                    yield a_row['account_id']

        for selector in selectors:
            memtype, memvalue = selector.split(':')

            if memtype.lower() == 'group':
                member = self.get_project_group(memvalue)
                if not gr.has_member(member.entity_id):
                    gr.add_member(member.entity_id)

            elif memtype.lower() == 'person_aff':
                # Fetch the correct affiliation, handle both a single
                # "AFFILIATION" and the "AFFILIATION/status" format:
                aff, status = self.const.get_affiliation(memvalue)
                for account_id in _aff_accounts(aff, status):
                    if not gr.has_member(account_id):
                        gr.add_member(account_id)

            else:
                raise Exception(
                    u"Unknown member type %r in selector %r" %
                    (memtype, selector))
        gr.write_db()

    def create_project_user(self, creator_id, basename,
                            fname=None, lname=None, gender=None, bdate=None,
                            shell='bash', affiliation=None):
        u""" Create a personal account affiliated with this project.

        Will also create a person to own the account.

        Names
            The special values "<pid>" and "<pname>" for `fname` or `lname`
            will be replaced with the project id and project name,
            respectively.  If a name is not given, the `basename` value will be
            used.

        :param int creator_id:
            The entity_id of the account that runs this method.

        :param str basename:
            The username base name. The actual username will be prefixed with
            the project ID of this project.

        :param str fname:
            The given name of the person that should own this account.

        :param str lname:
            The surname of the person that should own this account.

        :type gender: Gender, str, NoneType
        :param gender:
            The gender of the person that should own this account. If None,
            "X" (unknown) will be used.

        :type: bdate: mx.DateTime, str, NoneType
        :param bdate:
            The birth date for the person that should own this acocunt. If
            given as string, the expected format is yyyy-mm-dd.

        :type shell: PosixShell, str, NoneType
        :param shell:
            The shell for the account. If None, 'bash' will be set.

        :type affiliation: PersonAffiliation, PersonAffStatus, str, NoneType
        :param affiliation:
            An affiliation to give the person that owns the account. If string,
            the expected format is "AFFILIATION" or "AFFILIATION/status".

        :return PosixUser:
            Returns the created account.
        """
        names = {'<pid>': self.project_id, '<pname>': self.project_name}

        # Check arguments
        username = self._project_entity_name(basename)
        fname = names.get(fname) or fname or basename
        lname = names.get(lname) or lname or basename
        gender = (self.const.human2constant(str(gender), self.const.Gender)
                  or self.const.gender_unknown)
        shell = (self.const.human2constant(str(shell), self.const.PosixShell)
                 or self.const.posix_shell_bash)
        bdate = (DateTime.Parser.DateFromString(bdate, formats=('ymd1', ))
                 if bdate and not isinstance(bdate, DateTime.DateTimeType)
                 else bdate)
        aff, status = self.const.get_affiliation(affiliation)

        # TODO: Should this not be in Account.illegal_name?
        if username != username.lower():
            raise Errors.CerebrumError(
                u"Account names cannot contain capital letters")

        person = Factory.get('Person')(self._db)
        user = Factory.get('PosixUser')(self._db)
        password = user.make_passwd(username)
        try:
            user.find_by_name(username)
        except Errors.NotFoundError:
            person.populate(bdate, gender,
                            description='Owner of %r' % username)
            person.write_db()

            uid = user.get_free_uid()
            user.populate(
                uid, None, None, shell,
                name=username,
                owner_type=self.const.entity_person,
                owner_id=person.entity_id,
                np_type=None,
                creator_id=creator_id,
                expire_date=None)
            user.write_db()
            user.set_password(password)
            user.write_db()
        else:
            person.find(user.owner_id)

        # Update person names and affiliations.
        person.affect_names(self.const.system_manual,
                            self.const.name_first,
                            self.const.name_last)
        person.populate_name(self.const.name_first, fname)
        person.populate_name(self.const.name_last, lname)
        if affiliation:
            person.populate_affiliation(self.const.system_manual,
                                        ou_id=self.entity_id,
                                        affiliation=aff,
                                        status=status)
        person.write_db()

        # Update user aff/account type
        user.set_account_type(self.entity_id, self.const.affiliation_project)
        user.write_db()

        if not self.is_affiliated_entity(user.pg):
            self.affiliate_entity(user.pg)
        return user


class OUTSDMixin(TsdDefaultEntityMixin,
                 TsdProjectMixin,
                 OUAffiliateMixin,
                 OULockMixin,
                 EntityTrait):
    u""" Mixin of OU for TSD. """

    def setup_project(self, creator_id, vlan=None):
        """Set up an approved project properly.

        By setting up a project we mean:

         - Create the required project groups, according to config.
         - Reserve a vlan and subnet for the project.
         - Create the required project machines.

        More setup should be added here in the future, as this method should be
        called from all imports and jobs that creates TSD projects.

        Note that the given OU must have been set up with a proper project ID,
        stored as an `external_id`, and a project name, stored as an acronym,
        before this method could be called. The project must already be
        approved for this to happen, i.e. not in quarantine.

        :param int creator_id:
            The creator of the project. Either the `entity_id` of the
            administrator that created the project or a system user.

        :param int vlan:
            If given, sets the VLAN number to give to the project's subnets.
        """
        if not self.is_approved():
            raise Errors.CerebrumError("Project is not approved, cannot setup")

        # DNS and hosts
        self._setup_project_dns(creator_id, vlan)
        self._setup_project_hosts(creator_id)

        # Users and groups
        self._setup_project_users(creator_id)
        self._setup_project_groups(creator_id)

        # Posix?
        self._setup_project_posix(creator_id)

    def _setup_project_users(self, creator_id):
        u""" Create or update project users.

        This will ensure that users given in `cereconf.TSD_PROJECT_USERS`
        exists and are tied to this project.

        :param int creator_id:
            The entity_id we are operating on behalf of.
        """
        for basename, settings in getattr(cereconf, 'TSD_PROJECT_USERS',
                                          dict()).iteritems():
            user = self.create_project_user(
                creator_id,
                basename,
                fname=settings.get('first_name', basename),
                lname=settings.get('last_name', basename),
                gender=settings.get('gender'),
                bdate=settings.get('birth_date'),
                shell=settings.get('shell', 'bash'),
                affiliation=settings.get('affiliation'))

            self.apply_spreads(user, settings.get('spreads', []))

    def _setup_project_groups(self, creator_id):
        u""" Create or update project groups.

        This will ensure that groups given in `cereconf.TSD_PROJECT_GROUPS`
        exists and are tied to this project. It will also add members based on
        the 'member' setting of each group in `cereconf.TSD_PROJECT_GROUPS`.

        :param int creator_id:
            The entity_id we are operating on behalf of.
        """
        # Create groups
        for basename, settings in getattr(cereconf, 'TSD_PROJECT_GROUPS',
                                          dict()).iteritems():
            group = self.create_project_group(
                creator_id,
                basename,
                description=settings.get('description'))
            self.apply_spreads(group, settings.get('spreads', []))

        # Update group members
        for basename, settings in getattr(cereconf, 'TSD_PROJECT_GROUPS',
                                          dict()).iteritems():
            self.update_project_group_members(
                basename,
                selectors=settings.get('members', ()))

    def get_next_free_vlan(self):
        """Get the first VLAN number that is not in use.

        :rtype: int
        :return: An available VLAN number not used by anyone.

        :raise Errors.CerebrumError: If no VLAN is available.
        """
        taken_vlans = set()
        subnet = dns.Subnet.Subnet(self._db)
        for row in subnet.search():
            taken_vlans.add(row['vlan_number'])
        subnet6 = dns.IPv6Subnet.IPv6Subnet(self._db)
        for row in subnet6.search():
            taken_vlans.add(row['vlan_number'])
        # TODO: Do we need a max value?
        for min, max in getattr(cereconf, 'VLAN_RANGES', ()):
            i = min
            while i <= max:
                if i not in taken_vlans:
                    return i
                i += 1
        raise Errors.CerebrumError("No free VLAN left")

    def _setup_project_dns(self, creator_id, vlan=None):
        """Setup a new project's DNS info, like subnet and VLAN.

        :param int creator_id:
            The entity_id for the user who executes this.

        :param int vlan:
            If given, overrides what VLAN number to set for the project's
            subnets, as long as it is within one of the ranges defined
            in `cereconf.VLAN_RANGES`.
            If set to None, the first free VLAN will be chosen.
        """
        projectid = self.get_project_id()
        if not vlan:
            try:
                # Check if a VLAN is already assigned
                sub = dns.Subnet.Subnet(self._db)
                sub.find(self.ipv4_subnets.next())
                vlan = sub.vlan_number
            except:
                vlan = self.get_next_free_vlan()
        try:
            vlan = int(vlan)
        except ValueError:
            raise Errors.CerebrumError('VLAN not valid: %s' % (vlan,))
        # Checking if the VLAN is in one of the ranges
        for min, max in getattr(cereconf, 'VLAN_RANGES', ()):
            if min <= vlan <= max:
                break
        else:
            raise Errors.CerebrumError('VLAN out of range: %s' % vlan)

        # TODO: Find a better way for mapping between project ID and VLAN:
        intpid = self.project_int
        subnetstart, subnet6start = self._generate_subnets_for_project_id(
            project_id=intpid)

        for cls, start, my_subnets in (
                (dns.Subnet.Subnet, subnetstart, self.ipv4_subnets),
                (dns.IPv6Subnet.IPv6Subnet, subnet6start, self.ipv6_subnets)):
            sub = cls(self._db)
            try:
                sub.find(start)
            except dns.Errors.SubnetError:
                sub.populate(start, "Subnet for project %s" % projectid, vlan)
                sub.write_db()
            else:
                if sub.entity_id not in my_subnets:
                    raise Exception("Subnet %s exists, but does not belong"
                                    " to %s" % (start, projectid))
            if not self.is_affiliated_entity(sub):
                self.affiliate_entity(sub)

        # TODO: Reserve 10 PTR addresses in the start of the subnet!

    def _generate_subnets_for_project_id(self, project_id):
        """Calculate which IPv4 and IPv6 subnets should be assigned
        to a project.

        :param int project_id:
            The entity ID of the project.

        :rtype: tuple of strings
        :return: The (ipv4, ipv6) subnet.
        """
        # This algorithm will only work until we hit project number 32768,
        # at that point the subnets will be invalid, like: 10.256.0.0/24
        if project_id > 32767:
            raise Errors.CerebrumError(
                'Project ID cannot be higher than 32767')
        # we start at 10.128.0.0/24 for project_id=0
        n = 32768 + project_id
        # second octet, third octet
        quotient, remainder = divmod(n, 256)
        return (cereconf.SUBNET_START % (quotient, remainder),
                cereconf.SUBNET_START_6 % hex(n)[2:])

    def _setup_project_hosts(self, creator_id):
        """Setup the hosts initially needed for the given project."""
        projectid = self.get_project_id()
        host = dns.HostInfo.HostInfo(self._db)
        dns_owner = dns.DnsOwner.DnsOwner(self._db)
        vm_trait = self.get_trait(self.const.trait_project_vm_type)

        if vm_trait:
            vm_type = vm_trait['strval']
        else:  # Set win as default if trait is not set.
            vm_type = 'win_vm'

        if vm_type in ('win_vm', 'win_and_linux_vm'):
            # Create a Windows host for the whole project if it doesn't exist
            hostname = '%s-win01.tsd.usit.no.' % projectid
            hinfo = 'IBM-PC\tWINDOWS'
            host_dns_owner = None
            try:
                host.find_by_name(hostname)
            except Errors.NotFoundError:
                host_dns_owner = self._populate_dnsowner(hostname)
                try:
                    host.find_by_dns_owner_id(host_dns_owner.entity_id)
                except Errors.NotFoundError:
                    host.populate(host_dns_owner.entity_id, hinfo)

            if host_dns_owner is None:
                dns_owner.find_by_name(hostname)
                host_dns_owner = dns_owner

            host.hinfo = hinfo
            host.write_db()

            for comp in getattr(cereconf, 'TSD_HOSTPOLICIES_WIN', ()):
                TSDUtils.add_host_to_policy_component(self._db,
                                                      host_dns_owner.entity_id,
                                                      comp)

        if vm_type in ('linux_vm', 'win_and_linux_vm'):
            host.clear()
            # Create a Linux host for the whole project if it doesn' exist
            hostname = '%s-tl01-l.tsd.usit.no.' % projectid
            hinfo = 'IBM-PC\tLINUX'
            host_dns_owner = None
            try:
                host.find_by_name(hostname)
            except Errors.NotFoundError:
                host_dns_owner = self._populate_dnsowner(hostname)
                try:
                    host.find_by_dns_owner_id(host_dns_owner.entity_id)
                except Errors.NotFoundError:
                    host.populate(host_dns_owner.entity_id, hinfo)

            if host_dns_owner is None:
                dns_owner.clear()
                dns_owner.find_by_name(hostname)
                host_dns_owner = dns_owner

            host.hinfo = hinfo
            host.write_db()

            for comp in getattr(cereconf, 'TSD_HOSTPOLICIES_LINUX', ()):
                TSDUtils.add_host_to_policy_component(self._db,
                                                      host_dns_owner.entity_id,
                                                      comp)

            # Add CNAME-record for connecting via thinlinc-proxy
            cname_record_name = '%s-tl01-l.tl.tsd.usit.no.' % projectid
            TSDUtils.add_cname_record(self._db,
                                      cname_record_name,
                                      cereconf.TSD_THINLINC_PROXY,
                                      fail_on_exists=False)

    def _setup_project_posix(self, creator_id):
        u""" Upgrade non-posix entities.

        This makes all non-posix accounts tied to this project into posix
        accounts.
        """
        ac = Factory.get('Account')(self._db)
        pu = Factory.get('PosixUser')(self._db)
        for row in ac.list_accounts_by_type(
                ou_id=self.entity_id,
                affiliation=self.const.affiliation_project):
            ac.clear()
            ac.find(row['account_id'])
            pu.clear()
            try:
                pu.find(ac.entity_id)
            except Errors.NotFoundError:
                pu.clear()
                uid = pu.get_free_uid()
                pu.populate(uid, None, None, self.const.posix_shell_bash,
                            parent=ac, creator_id=creator_id)
                pu.write_db()

    def _populate_dnsowner(self, hostname):
        """Create or update a DnsOwner connected to the given project.

        The DnsOwner is given a trait, to affiliate it with this project-OU.

        This should rather be put in the DNS module, but due to its complexity,
        its weird layout, and my lack of IQ points to understand it, I started
        just using its API instead.

        :param str hostname: The given *FQDN* for the host.

        :rtype: DnsOwner object
        :return:
            The DnsOwner object that is created or updated.
        """
        dns_owner = dns.DnsOwner.DnsOwner(self._db)
        dnsfind = dns.Utils.Find(self._db, cereconf.DNS_DEFAULT_ZONE)
        ipv6number = dns.IPv6Number.IPv6Number(self._db)
        aaaarecord = dns.AAAARecord.AAAARecord(self._db)
        ipnumber = dns.IPNumber.IPNumber(self._db)
        arecord = dns.ARecord.ARecord(self._db)

        try:
            dns_owner.find_by_name(hostname)
        except Errors.NotFoundError:
            # TODO: create owner here?
            dns_owner.populate(self.const.DnsZone(cereconf.DNS_DEFAULT_ZONE),
                               hostname)
            dns_owner.write_db()
        # Affiliate with project:
        dns_owner.populate_trait(self.const.trait_project_host,
                                 target_id=self.entity_id)
        dns_owner.write_db()
        for (subnets, ipnum, record, ipstr) in (
                (self.ipv6_subnets, ipv6number, aaaarecord, "IPv6"),
                (self.ipv4_subnets, ipnumber, arecord, "IPv4")):
            # TODO: check if dnsowner already has an ip address.
            try:
                ip = dnsfind.find_free_ip(subnets.next(), no_of_addrs=1)[0]
            except StopIteration:
                raise Errors.NotFoundError("No %s-subnet for project %s" %
                                           (ipstr, self.get_project_id()))
            ipnum.populate(ip)
            ipnum.write_db()
            record.populate(dns_owner.entity_id, ipnum.entity_id)
            record.write_db()
        return dns_owner

    def get_project_subnets(self):
        """Get the subnets that are affiliated with the given project.

        This is mostly a wrapper around `list_traits` for fetching the
        affiliations traits for subnets, as that is how
        subnet-to-project-affiliations are represented.

        Both IPv4 and IPv6 subnets are returned. The type could be identified
        by each returned element's item `entity_type` (and `code`, as it's two
        different trait types).

        :rtype: generator
        :return: A list of traits db-rows for each subnet. Each element's
            values that might be relevant are `entity_id`, `entity_type`,
            `code` and `date`. The other values might not be used.
        """
        for row in self.get_affiliated_entities(
                self.const.entity_dns_subnet):
            yield row
        for row in self.get_affiliated_entities(
                self.const.entity_dns_ipv6_subnet):
            yield row

    @property
    def ipv4_subnets(self):
        u""" Generator that lists the IPv4 subnets for this project. """
        return (row['entity_id'] for row
                in self.get_affiliated_entities(
                    self.const.entity_dns_subnet))

    @property
    def ipv6_subnets(self):
        u""" Generator that lists the IPv6 subnets for this project. """
        return (row['entity_id'] for row
                in self.get_affiliated_entities(
                    self.const.entity_dns_ipv6_subnet))

    def get_pre_approved_persons(self):
        """Get a list of pre approved persons by their fnr.

        This is a list of persons that has already been granted access to a
        project, but have not asked for the access yet. The list is stored in a
        trait, but is automatically split by spaces for ease of use.

        @rtype: set
        @return: A set of identifiers for each pre approved person.
        """
        tr = self.get_trait(self.const.trait_project_persons_accepted)
        if tr is None:
            return set()
        return set(tr['strval'].split(','))

    def add_pre_approved_persons(self, ids):
        """Pre approve persons to the project by their external IDs.

        The list of pre approved persons for the project gets extended with the
        new list.

        @type ids: iterator
        @param ids: All the external IDs for all the pre approved persons.
        """
        approvals = self.get_pre_approved_persons()
        approvals.update(ids)
        self.populate_trait(code=self.const.trait_project_persons_accepted,
                            date=DateTime.now(), strval=','.join(approvals))
        return True

    def terminate(self):
        """Remove all of a project, except its project ID and name (acronym).

        The project's entities are deleted by this method, so use with care!

        For the OU object, it does almost the same as L{delete} except from
        deleting the entity itself.
        """
        self.write_db()
        ent = EntityTrait(self._db)
        ac = Factory.get('Account')(self._db)
        pu = Factory.get('PosixUser')(self._db)
        # Delete PosixUsers
        for row in ac.list_accounts_by_type(ou_id=self.entity_id,
                                            filter_expired=False):
            try:
                pu.clear()
                pu.find(row['account_id'])
                pu.delete_posixuser()
            except Errors.NotFoundError:
                # not a PosixUser
                continue
        # Remove all project's groups
        gr = Factory.get('Group')(self._db)
        for row in gr.list_traits(code=self.const.trait_project_group,
                                  target_id=self.entity_id):
            gr.clear()
            gr.find(row['entity_id'])
            gr.delete()
        # Delete all users
        for row in ac.list_accounts_by_type(ou_id=self.entity_id):
            ac.clear()
            ac.find(row['account_id'])
            ac.delete()
        # Remove every trace of person affiliations to the project:
        pe = Factory.get('Person')(self._db)
        for row in pe.list_affiliations(ou_id=self.entity_id,
                                        include_deleted=True):
            pe.clear()
            pe.find(row['person_id'])
            pe.nuke_affiliation(ou_id=row['ou_id'],
                                affiliation=row['affiliation'],
                                source=row['source_system'],
                                status=row['status'])
            pe.write_db()
        # Remove all project's DnsOwners (hosts):
        dnsowner = dns.DnsOwner.DnsOwner(self._db)
        policy = PolicyComponent(self._db)
        update_helper = dns.IntegrityHelper.Updater(self._db)
        for row in ent.list_traits(code=self.const.trait_project_host,
                                   target_id=self.entity_id):
            # TODO: Could we instead update the Subnet classes to use
            # Factory.get('Entity'), and make use of EntityTrait there to
            # handle this?
            owner_id = row['entity_id']
            ent.clear()
            ent.find(owner_id)
            ent.delete_trait(row['code'])
            ent.write_db()
            # Remove the links to policies if hostpolicy is used
            for prow in policy.search_hostpolicies(dns_owner_id=owner_id):
                policy.clear()
                policy.find(prow['policy_id'])
                policy.remove_from_host(owner_id)
            # delete the DNS owner
            update_helper.full_remove_dns_owner(owner_id)
        # Delete all subnets
        subnet = dns.Subnet.Subnet(self._db)
        subnet6 = dns.IPv6Subnet.IPv6Subnet(self._db)
        for row in ent.list_traits(code=(self.const.trait_project_subnet6,
                                         self.const.trait_project_subnet),
                                   target_id=self.entity_id):
            ent.clear()
            ent.find(row['entity_id'])
            ent.delete_trait(row['code'])
            ent.write_db()
            if row['code'] == self.const.trait_project_subnet:
                subnet.clear()
                subnet.find(row['entity_id'])
                subnet.delete()
            if row['code'] == self.const.trait_project_subnet6:
                subnet6.clear()
                subnet6.find(row['entity_id'])
                subnet6.delete()
        # Remove all data from the OU except for:
        # The project ID and project name
        for tr in tuple(self.get_traits()):
            self.delete_trait(tr)
        for row in self.get_spread():
            self.delete_spread(row['spread'])
        for row in self.get_contact_info():
            self.delete_contact_info(row['source_system'],
                                     row['contact_type'])
        for row in self.get_entity_address():
            self.delete_entity_address(row['source_system'],
                                       row['address_type'])
        for row in self.search_name_with_language(entity_id=self.entity_id):
            # The project name must not be removed, to avoid reuse
            if row['name_variant'] == self.const.ou_name_acronym:
                continue
            self.delete_name_with_language(row['name_variant'])
        self.write_db()
