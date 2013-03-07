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

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.OU import OU

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

    def search_tsd_projects(self, name=None):
        """Search method for finding projects by given input.

        TODO: Only project name is in use for now. Fix it if we need more
        functionality.

        @type name: string
        @param name: The project name.

        @rtype: db-rows
        @return: TODO: what db elements do we need?

        """
        # TBD: filter out OU's that are not project OU's, if we need other OUs.
        return self.search_name_with_language(entity_type=self.const.entity_ou,
                                    name_variant=self.const.ou_name_acronym,
                                    # TODO: name_language=self.const.language_en
                                    name=name, exact_match=True)

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
        if len(m) > 1024: # TBD:
            raise Errors.CerebrumError('Project name is too long')
        return True

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
