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

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.OU import OU

class OUTSDMixin(OU):
    """Mixin of OU for TSD. Projects in TSD are stored as OUs, which then has to
    be unique."""

    def add_name_with_language(self, name_variant, name_language, name):
        """Override to be able to check that the acronym is not already used.

        """
        if name_variant == self.const.ou_name_acronym:
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
