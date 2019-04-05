# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import Stedkode

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)


class StedkodeMixin(Stedkode.Stedkode):
    """ UiT specific Stedkode functionality"""

    def get_name(self, domain):
        self.EntityName.get_name(self, domain)

    def find_by_perspective_old(self, ou_id, perspective):
        """
        Associate the object with the OU whose identifier is OU_ID and
        perspective as given.

        If OU_ID isn't an existing OU identifier,
        NotFoundError is raised."""
        self.__super.find(ou_id)
        (self.ou_id, self.name, self.acronym, self.short_name,
         self.display_name) = self.query_1("""
        SELECT oi.ou_id, oi.name, oi.acronym, oi.short_name, oi.display_name
        FROM [:table schema=cerebrum name=ou_info] oi,
             [:table schema=cerebrum name=ou_structure] os
        WHERE oi.ou_id=:ou_id AND oi.ou_id = os.ou_id
        AND os.perspective=:perspective""",
                                           {'ou_id': ou_id,
                                            'perspective': perspective})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_perspective(self, ou_id, perspective):
        name_variant = co.ou_name
        # perspective = co.perspective_fs
        self.__super.find(ou_id)
        (self.ou_id, self.name) = self.query_1(
            """SELECT os.ou_id, eln.name
            FROM [:table schema=cerebrum name=entity_language_name] eln,
                 [:table schema=cerebrum name=ou_structure] os
            WHERE eln.name_variant=:name_variant_1
            AND eln.entity_id = os.ou_id
            AND os.ou_id=:ou_id_1
            AND os.perspective=:perspective_1""",
            {'name_variant_1': name_variant, 'ou_id_1': ou_id,
             'perspective_1': perspective})

        try:
            name_variant = co.ou_name_acronym
            self.acronym = self.query_1(
                """SELECT eln.name
                FROM [:table schema=cerebrum name=entity_language_name] eln,
                     [:table schema=cerebrum name=ou_structure] os
                WHERE eln.name_variant=:name_variant_1
                AND eln.entity_id = os.ou_id
                AND os.ou_id=:ou_id_1
                AND os.perspective=:perspective_1""",
                {'name_variant_1': name_variant, 'ou_id_1': ou_id,
                 'perspective_1': perspective})
        except Errors.NotFoundError:
            self.acronym = ""

        try:
            name_variant = co.ou_name_short
            self.short_name = self.query_1(
                """SELECT eln.name
                FROM [:table schema=cerebrum name=entity_language_name] eln,
                     [:table schema=cerebrum name=ou_structure] os
                WHERE eln.name_variant=:name_variant_1
                AND eln.entity_id = os.ou_id
                AND os.ou_id=:ou_id_1
                AND os.perspective=:perspective_1""",
                {'name_variant_1': name_variant, 'ou_id_1': ou_id,
                 'perspective_1': perspective})
        except Errors.NotFoundError:
            self.short_name = ""

        try:
            name_variant = co.ou_name_display
            self.display_name = self.query_1(
                """SELECT eln.name
                FROM [:table schema=cerebrum name=entity_language_name] eln,
                     [:table schema=cerebrum name=ou_structure] os
                WHERE eln.name_variant=:name_variant_1
                AND eln.entity_id = os.ou_id
                AND os.ou_id=:ou_id_1
                AND os.perspective=:perspective_1""",
                {'name_variant_1': name_variant, 'ou_id_1': ou_id,
                 'perspective_1': perspective})
        except Errors.NotFoundError:
            self.display_name = ""

        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []
