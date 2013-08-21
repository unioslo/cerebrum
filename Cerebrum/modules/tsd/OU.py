#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
e.g. by using the acronym as a unique identifier. When a project has finished,
we will delete all details about the project, except the project's OU, to be
able to reserve the name of the project, which is stored in the acronym.

"""

import re
from mx import DateTime

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.OU import OU
from Cerebrum.Utils import Factory
from Cerebrum.modules.dns import Subnet

class OUTSDMixin(OU):
    """Mixin of OU for TSD. Projects in TSD are stored as OUs, which then has to
    be unique.

    """
    def find_by_tsd_projectname(self, project_name):
        """TSD specific helper method for finding an OU by the project's name.

        In TSD, each project is stored as an OU, with the acronym as the unique
        project name. 

        TODO: All project OUs could be stored under the same OU, if we need
        other OUs than project OUs.

        """
        matched = self.search_tsd_projects(name=project_name)
        if not matched:
            raise Errors.NotFoundError("Unknown project: %s" % project_name)
        if len(matched) != 1:
            raise Errors.TooManyRowsError("Found more than one OU with given name")
        return self.find(matched[0]['entity_id'])

    def search_tsd_projects(self, name=None, exact_match=False):
        """Search method for finding projects by given input.

        TODO: Only project name is in use for now. Fix it if we need more
        functionality.

        @type name: string
        @param name: The project name.

        @type exact_match: bool
        @param exact_match: If it should search for the exact name, or through
            an sql query with LIKE.

        @rtype: db-rows
        @return: TODO: what db elements do we need?

        """
        # TBD: filter out OU's that are not project OU's, if we need other OUs.
        return self.search_name_with_language(entity_type=self.const.entity_ou,
                                    name_variant=self.const.ou_name_acronym,
                                    # TODO: name_language=self.const.language_en
                                    name=name, exact_match=exact_match)

    def _validate_project_name(self, name):
        """Check if a given project name is valid.

        Project names are used as prefix for most of the project's entities,
        like accounts, groups and machines. We need to make sure that the name
        doesn't cause problems for e.g. AD.

        Some requirements:

        - Can not contain spaces. TODO: Why?

        - Can not contain commas. This is due to AD's way of identifying
          objects. Example: CN=username,OU=projectname,DC=tsd,DC=uio,DC=no.

        - Can not contain the SQL wildcards ? and %. This is a convenience
          limit, to be able to use Cerebrum's existing API without
          modifications.

        - Can not contain control characters.

        - Should not contains characters outside of ASCII. This is due to
          Cerebrum's lack of unicode support, and to avoid unexpected encoding
          issues.

        - TBD: A maximum length in the name? AD probably has a limit. As a
          prefix, it should be a bit less than AD's limit.

        In practice, we only accept regular alphanumeric characters in ASCII, in
        addition to some punctuation characters, like colon, dash and question
        marks. This would need to be extended in the future.

        """
        # TODO: whitelisting accepted characters, might want to extend the list
        # with characters I've forgotten:
        m = re.search('[^A-Za-z0-9_\-:;\*"\'\#\&\=!\?]', name)
        if m:
            raise Errors.CerebrumError('Invalid characters in projectname: %s' %
                                m.group())
        if len(name) < 3:
            raise Errors.CerebrumError('Project name too short')
        if len(name) > 8: # TBD: or 6?
            raise Errors.CerebrumError('Project name is too long')
        return True

    def get_project_name(self):
        """Shortcut for getting the given OU's project ID."""
        return self.get_name_with_language(self.const.ou_name_acronym,
                                           self.const.language_en)

    def add_name_with_language(self, name_variant, name_language, name):
        """Override to be able to verify project names (acronyms).

        """
        if name_variant == self.const.ou_name_acronym:
            # TODO: Do we accept *changing* project names?

            # Validate the format of the acronym. The project name is used as a
            # prefix for other entities, like accounts, groups and machines, so
            # we need to be careful.
            self._validate_project_name(name)

            # TODO: check name_language too
            matched = self.search_name_with_language(
                                    entity_type=self.const.entity_ou,
                                    name_variant=self.const.ou_name_acronym,
                                    # TODO: name_language
                                    name=name)
            if any(r['name'] == name for r in matched):
                raise CerebrumError('Acronym already in use')
        return self.__super.add_name_with_language(name_variant, name_language,
                                                   name)

    def setup_project(self, creator_id):
        """Set up an approved project properly.

        By setting up a project we mean:

         - Create the required project groups, according to config.
         - Reserve a vlan and subnet for the project.
         - Create the required project machines.

        More setup should be added here in the future, as this method should be
        called from all imports and jobs that creates TSD projects.

        Note that the given OU must have been set up with a proper project name,
        stored as an acronym, before this method could be called. The project
        must already be approved for this to happen.

        @type creator_id: int
        @param creator_id:
            The creator of the project. Either the entity_id of the
            administrator that created the project or a system user.

        """
        if self.get_entity_quarantine(type=self.const.quarantine_not_approved, only_active=True):
            raise Errors.CerebrumError("Project is quarantined, cannot setup")

        projectid = self.get_project_name()
        gr = Factory.get("PosixGroup")(self._db)

        def _create_group(groupname, desc, trait):
            """Helper function for creating a group.
            
            @type groupname: string
            @param groupname: The name of the new group. Gets prefixed by the
                project-ID.

            @type desc: string
            @param desc: The description that should get stored at the new
                group.

            @type trait: TraitConstant
            @param trait: The type of trait that should be stored at the group,
                to affiliate the group with the current project. The
                L{target_id} gets set to the project, i.e. L{self}.

            """
            groupname = ''.join((projectid, groupname))
            gr.clear()
            try:
                gr.find_by_name(groupname)
            except Errors.NotFoundError:
                gr.clear()
                gr.populate(creator_id, self.const.group_visibility_all,
                            groupname, desc)
                gr.write_db()
                # Each group is linked to the project by a project trait:
                gr.populate_trait(trait, target_id=self.entity_id,
                                  date=DateTime.now())
                gr.write_db()
            else:
                self.logger.warn("Project group already existed: %s", groupname)
                return False
            return True

        # Create project groups
        for suffix, desc in getattr(cereconf, 'TSD_PROJECT_ROLEGROUPS', ()):
            _create_group(suffix, desc, self.const.trait_project_group)

        # TODO: Create action groups

        # TODO: Create resource groups

        # Subnet and VLAN
        subnet = Subnet.Subnet(self._db)
        #TODO

        # Machines:
        #TODO

        # Disks:
        #TODO

        # TODO: Add accounts to the various groups:
        ac = Factory.get('Account')(self._db)
        gr.clear()
        #gr.find_by_name('%s_member' % projectid)
        #for row in ac.list_accounts_by_type(ou_id=self.entity_id):
        #    pass

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
        return set(tr['strval'].split())

    def add_pre_approved_persons(self, ids):
        """Pre approve persons to the project by their external IDs.

        The list of pre approved persons for the project gets extended with the
        new list.

        @type ids: iterator
        @param ids: All the external IDs for all the pre approved persons.

        """
        approvals = self.get_pre_approved_persons()
        approvals.update(ids)
        # TODO: check if this works!
        self.populate_trait(code=self.const.trait_project_persons_accepted,
                            date=DateTime.now(), strval=' '.join(approvals))
        return True

    def terminate(self):
        """Remove all of a project, except its acronym.
        
        Note that you would have to delete accounts and other project entitites
        as well.

        """
        # TODO
        self.write_db()
        pass
