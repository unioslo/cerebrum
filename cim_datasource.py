#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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

# import phonenumbers
# from Cerebrum.Utils import Factory
# from Cerebrum.Errors import NotFoundError

import cerebrum_path
import cereconf

from Cerebrum.modules.cim.datasource import CIMDataSource

class CIMDataSourceUit(CIMDataSource):
    """
    This class provides a UiT-specific extension to the CIMDataSource class.
    """

    def get_person_data(self, person_id):
        """
        Builds a dict according to the CIM-WS schema, using info stored in
        Cerebrum's database about the given person.

        :param int person_id: The person's entity_id in Cerebrum
        :return: A dict with person data, with entries adhering to the
                 CIM-WS-schema.
        :rtype: dict
        """
        # TODO: move 'CIM_SYSTEM_LOOKUP_ORDER' to cereconf
        CIM_SYSTEM_LOOKUP_ORDER = ['system_paga', 'system_fs', 'system_x']

        orig_auth_system = self.authoritative_system
        person = None

        # get data about person using CIM_SYSTEM_LOOKUP_ORDER to determine source_system to use
        for sys in CIM_SYSTEM_LOOKUP_ORDER:
            source_system = getattr(self.co, sys)
            self.authoritative_system = source_system

            try:
                person = super(CIMDataSourceUit, self).get_person_data(person_id)
            except IndexError:
                person = None

            if person != None:
                # TODO later: ?? do I need to check result? e.g. ou stuff for students and sysX persons...
                break

        # TODO later: add dist_list stuff

            # Doing things like this might be a problem when we add students:
            # What if a person is a student, but has a (small) part-time job at UiT.
            # person would get cim_spread because of the student-status, but
            # PAGA would be used as source_system...
            # 
            # example of special case to consider:
            # krs025 (Kristin Solberg): student, but also has ansatt and tilknyttet affiliations (from FS and SysX)
            #                           ansatt and tilknyttet at IKM, student at HSL

        # set authoritative_system back to what it was at beginning of method
        self.authoritative_system = orig_auth_system

        return person


