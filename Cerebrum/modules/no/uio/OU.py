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

""" UiO specific extension to the default Cerebrum OU class.  The
following additional properties are defined:

  - fakultet
  - institutt
  - avdeling
  - institusjon
  - katalog_merke
"""

from Cerebrum.OU import OU

# Let's hope there's no need to access the module called "OU" further
# down...
class OU(OU):
    def __init__(self, database):
        """

        """
        super(OU, self).__init__(database)
        self.clear()

    def clear(self):
        "Clear all attributes associating instance with a DB entity."

        self.ou_id = self.institusjon = self.fakultet = self.institutt = None
        self.avdeling = self.katalog_merke = None

        super(OU, self).clear()

    def populate(self, name, fakultet, institutt, avdeling,
            institusjon=185, katalog_merke='T',acronym=None,
            short_name=None, display_name=None, sort_name=None):
        
        "Set instance's attributes without referring to the Cerebrum DB."

        self.fakultet = int(fakultet)   # is int in database: str(39) != int(39)
        self.institutt = int(institutt)
        self.avdeling = int(avdeling)
        self.institusjon = int(institusjon)
        self.katalog_merke = katalog_merke

        super(OU, self).populate(name, acronym, short_name, display_name, sort_name)

        self.__write_db = True

    def __eq__(self, other):
        if other == None: return False
        assert isinstance(other, OU)

        identical = super(OU, self).__eq__(other)
        if(not identical):
            return identical

        identical = ((other.fakultet == self.fakultet) and
                     (other.institutt == self.institutt) and
                     (other.avdeling == self.avdeling) and
                     (other.institusjon == self.institusjon) and
                     (other.katalog_merke == self.katalog_merke))

        return identical

    def __str__(self):
        return "institusjon=%s, stedkode=%s-%s-%s, km=%s" % (
            self.institusjon, self.fakultet, self.institutt,
            self.avdeling, self.katalog_merke)

    def write_db(self, as_object=None):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If `as_object' isn't specified (or is None), the instance is
        written as a new entry to the Cerebrum database.  Otherwise,
        the object overwrites the Entity entry corresponding to the
        instance `as_object'.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method.

        """
        assert self.__write_db

        super(OU, self).write_db(as_object)

        if as_object is None:
            self.execute("""
            INSERT INTO cerebrum.stedkode
                (ou_id, institusjon, fakultet, institutt, avdeling, katalog_merke)
            VALUES (:ou_id, :institusjon, :fak, :institutt, :avd, :kat_merke)""",
                         {'ou_id' : self.ou_id, 'institusjon' : self.institusjon,
                          'fak' : self.fakultet, 'institutt' : self.institutt,
                          'avd' : self.avdeling, 'kat_merke' : self.katalog_merke})
        else:
            ou_id = as_object.ou_id
            self.execute("""
            UPDATE cerebrum.stedkode SET institusjon=:institusjon, fakultet=:fak,
                 institutt=:institutt, avdeling=:avd, katalog_merke=:kat_merke
            WHERE ou_id=:ou_id""",
                         {'institusjon' : self.institusjon, 'fak' : self.fakultet,
                          'institutt' : self.institutt, 'avd' : self.avdeling,
                          'kat_merke' : self.katalog_merke, 'ou_id' : self.ou_id})

        self.__write_db = False

    def delete(self):
        raise "Delete not implemented"
        pass

    def find_stedkode(self, fakultet, institutt, avdeling, institusjon=185):
        (self.ou_id, self.institusjon, self.fakultet, self.institutt,
         self.avdeling, self.katalog_merke) = \
        self.query_1("""
        SELECT ou_id, institusjon, fakultet, institutt, avdeling, katalog_merke
        FROM cerebrum.stedkode
        WHERE institusjon = :institusjon AND fakultet = :fak AND
              institutt = :institutt AND avdeling = :avd""",
                     {'institusjon' : institusjon, 'fak' : fakultet,
                      'institutt' : institutt, 'avd' : avdeling})

    def add_stedkode(self, fakultet, institutt, avdeling, institusjon=185,
                     katalog_merke='T'):
        return self.execute("""
        INSERT INTO cerebrum.stedkode
          (ou_id, institusjon, fakultet, institutt, avdeling, katalog_merke)
        VALUES (:ou_id, :institusjon, :fak, :institutt, :avd, :kat_merke)""",
                            {'ou_id' : self.ou_id, 'institusjon' : institusjon,
                             'fak' : fakultet, 'institutt' : institutt, 'avd' : avdeling,
                             'kat_merke' : katalog_merke})
