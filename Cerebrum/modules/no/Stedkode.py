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

"""Norwegian higher education-specific OU extension.

This module implements extensions to the standard Cerebrum OU class
that are specific to the higher education sector in Norway.  The
following additional properties are defined:

  - fakultet
  - institutt
  - avdeling
  - institusjon
  - katalog_merke
"""

from Cerebrum import Utils
from Cerebrum.OU import OU
import cereconf

class Stedkode(OU):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('landkode', 'institusjon', 'fakultet', 'institutt',
                      'avdeling', 'katalog_merke')

    def __init__(self, database):
        """

        """
        self.__super.__init__(database)
        self.clear()

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(Stedkode)
        self.__updated = []

    def populate(self, name, fakultet, institutt, avdeling,
                 institusjon=None, landkode=0, katalog_merke='F', acronym=None,
                 short_name=None, display_name=None, sort_name=None,
                 parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            self.__super.populate(name, acronym, short_name,
                                  display_name, sort_name)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.landkode = int(landkode)
        self.fakultet = int(fakultet)
        self.institutt = int(institutt)
        self.avdeling = int(avdeling)
        self.institusjon = int(institusjon)
        self.katalog_merke = katalog_merke

    def __eq__(self, other):
        assert isinstance(other, Stedkode), `other`
        identical = self.__super.__eq__(other)
        if not identical:
            return False
        identical = ((other.fakultet == self.fakultet) and
                     (other.institutt == self.institutt) and
                     (other.avdeling == self.avdeling) and
                     (other.institusjon == self.institusjon) and
                     (other.landkode == self.landkode) and
                     (other.katalog_merke == self.katalog_merke))
        return identical

    def __str__(self):
        return "landkode=%s, institusjon=%s, stedkode=%s-%s-%s, km=%s" % (
            self.landkode, self.institusjon, self.fakultet, self.institutt,
            self.avdeling, self.katalog_merke)

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If `as_object' isn't specified (or is None), the instance is
        written as a new entry to the Cerebrum database.  Otherwise,
        the object overwrites the Entity entry corresponding to the
        instance `as_object'.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=stedkode]
              (ou_id, landkode, institusjon, fakultet, institutt, avdeling,
               katalog_merke)
            VALUES
              (:ou_id, :landkode, :institusjon, :fakultet, :institutt,
               :avdeling, :katalog_merke)""",
                         {'ou_id': self.entity_id,
                          'landkode': self.landkode,
                          'institusjon': self.institusjon,
                          'fakultet': self.fakultet,
                          'institutt': self.institutt,
                          'avdeling': self.avdeling,
                          'katalog_merke': self.katalog_merke})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=stedkode]
            SET landkode=:landkode, institusjon=:institusjon,
                fakultet=:fakultet, institutt=:institutt,
                avdeling=:avdeling, katalog_merke=:katalog_merke
            WHERE ou_id=:ou_id""",
                         {'ou_id': self.entity_id,
                          'landkode': int(self.landkode),
                          'institusjon': int(self.institusjon),
                          'fakultet': int(self.fakultet),
                          'institutt': int(self.institutt),
                          'avdeling': int(self.avdeling),
                          'katalog_merke': self.katalog_merke})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        raise NotImplementedError

    def find(self, ou_id):
        self.__super.find(ou_id)
        (self.landkode, self.institusjon, self.fakultet, self.institutt,
         self.avdeling, self.katalog_merke) = self.query_1("""
        SELECT landkode, institusjon, fakultet, institutt, avdeling, katalog_merke
        FROM [:table schema=cerebrum name=stedkode]
        WHERE ou_id = :ou_id""", locals())
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_stedkode(self, fakultet, institutt, avdeling, institusjon,
                      landkode=0):
        if institusjon is None:   # Temporary to trap old code
            raise ValueError, "You must specify institusjon"
        ou_id = self.query_1("""
        SELECT ou_id FROM [:table schema=cerebrum name=stedkode]
        WHERE
          landkode = :landkode AND
          institusjon = :institusjon AND
          fakultet = :fakultet AND
          institutt = :institutt AND
          avdeling = :avdeling""", locals())
        self.find(ou_id)

    def get_stedkoder(self, landkode=0,
                      institusjon=cereconf.DEFAULT_INSTITUSJONSNR,
                      fakultet=None, institutt=None, avdeling=None):
        sql = """
        SELECT ou_id, landkode, institusjon, fakultet, institutt, avdeling
        FROM [:table schema=cerebrum name=stedkode]
        WHERE
          landkode = :landkode AND
          institusjon = :institusjon """
        if fakultet is not None:
            sql += "AND fakultet = :fakultet "
        if institutt is not None:
            sql += "AND institutt = :institutt "
        if avdeling is not None:
            sql += "AND avdeling = :avdeling "
        return self.query(sql, locals())

    def get_stedkoder_by_name(self, pattern):
        # TODO: it may be better to use 'sort_name', but it's meant to
        # mirror 'name', not 'short_name'.  also, in our DB,
        # 'sort_name' has been initialised to be an exact copy of
        # 'name', so it's kind of useless right now.
        return self.query("""
        SELECT ou_id
        FROM [:table schema=cerebrum name=ou_info]
        WHERE
          lower(short_name) LIKE :pattern""", locals())
