# Copyright 2002 University of Oslo, Norway
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

"""

from Cerebrum.OU import \
     OU

class OU(OU):
    def __init__(self, database):
        """

        """
        super(OU, self).__init__(database)
        self._clear()

    def _clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.ou_id = self.institusjon = self.fakultet = self.institutt = self.avdeling = self.katalog_merke = None

    def get_sko(self, fakultet, institutt, avdeling, institusjon=113):
        (self.ou_id, self.institusjon, self.fakultet, self.institutt,
        self.avdeling, self.katalog_merke) = self.query_1("""
        SELECT ou_id, institusjon, fakultet,  institutt, avdeling, katalog_merke
        FROM cerebrum.stedkode
        WHERE institusjon=:1 AND fakultet=:2 AND institutt=:3 AND avdeling=:4""",
                              institusjon, fakultet, institutt, avdeling)
        return 1

    def add_sko(self, fakultet, institutt, avdeling, institusjon=113, katalog_merke='T'):
        self.execute("""
        INSERT INTO cerebrum.stedkode
          (ou_id, institusjon, fakultet, institutt, avdeling, katalog_merke)
        VALUES (:1, :2, :3, :4, :5, :6)""",
                     self.entity_id, institusjon, fakultet, institutt, avdeling, katalog_merke)
