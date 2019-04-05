# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

"""
UiT implementation of OU
"""
from Cerebrum import Errors
from Cerebrum.OU import OU


class OUMixin(OU):
    """
    UiT override of OU. expired_before is added as an extra
    parameter to the overriden methods in this file. The default
    behaviour is to exclude all entitites that are expired at the
    time of the query."""

    def find(self, ou_id):
        try:
            (self.landkode, self.institusjon, self.fakultet, self.institutt,
             self.avdeling,) = self.query_1("""
             SELECT landkode, institusjon, fakultet, institutt, avdeling
             FROM [:table schema=cerebrum name=stedkode]
             WHERE ou_id = :ou_id""", locals())
        except Errors.NotFoundError:
            OU.find(self, ou_id)
        else:
            # use supers find function
            self.__super.find(ou_id)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def list_all_with_perspective(self, perspective):
        return self.query("""
        SELECT os.ou_id, eln.name
        FROM [:table schema=cerebrum name=ou_structure] os,
             [:table schema=cerebrum name=entity_language_name] eln
        WHERE os.perspective=:perspective
        AND os.ou_id = eln.entity_id""",
                          {'perspective': int(perspective)})

    def get_structure_mappings(self, perspective, filter_expired=False):
        """
        Return list of ou_id -> parent_id connections in ``perspective``
        optionally filtering the results on expiry."""
        ou_list = super(OUMixin, self).get_structure_mappings(perspective)

        if filter_expired:
            # get list of expired ou_ids
            res = self.query("""
                   SELECT entity_id
                   FROM [:table schema=cerebrum name=entity_expire]""")
            expired_ous = []
            for entry in res:
                expired_ous.append(entry['entity_id'])

            # need to work on a copy of ou_list so that we don't mess up the
            # for-loop
            ou_list_filtered = list(ou_list)
            for ou in ou_list:
                if ou['ou_id'] in expired_ous:
                    # remove expired ou from the list
                    ou_list_filtered.remove(ou)

            return ou_list_filtered
        else:
            return ou_list
    # end get_structure_mappings
