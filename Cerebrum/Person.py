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

from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityAddress, EntityQuarantine
from Cerebrum import OU
from Cerebrum import Utils
from Cerebrum import Errors


class Person(EntityContactInfo, EntityAddress, EntityQuarantine, Entity):

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        super(Person, self).clear()
        self.birth_date = None
        self.gender = None
        self.description = None
        self.deceased = None
        self._external_id= ()
        # Person names:
        self._pn_affect_source = None
        self._pn_affect_types = None
        self._name_info = {}
        # Person affiliations:
        self._pa_affect_source = None
        self._pa_affiliations = {}
        self._pa_affected_affiliations = ()

    def populate(self, birth_date, gender, description=None, deceased='F'):
        "Set instance's attributes without referring to the Cerebrum DB."
        self.birth_date = birth_date
        self.gender = gender
        self.description = description
        self.deceased = deceased

        Entity.populate(self, self.const.entity_person)
        self.__write_db = True

    def __eq__(self, other):
        """Define == operator for Person objects."""
        assert isinstance(other, Person)
        identical = super(Person, self).__eq__(other)
        if not identical:
            if self._debug_eq: print "Person.super.__eq__ = %s" % identical
            return False

        affected_source = self._pa_affect_source
        if affected_source is not None:
            for affected_affil in self._pa_affected_affiliations:
                other_dict = {}
                for t in other.get_affiliations(simple=False):
                    if t.source_system == affected_source:
                        # Not sure why this casting to int is required
                        # on PostgreSQL
                        other_dict[int(t.ou_id)] = t.status
                for t_ou_id, t_status in \
                        self._pa_affiliations.get(affected_affil, []):
                    # Not sure why this casting to int is required on
                    # PostgreSQL
                    t_ou_id = int(t_ou_id)
                    if other_dict.has_key(t_ou_id):
                        if other_dict[t_ou_id] <> t_status:
                            if self._debug_eq:
                                print "PersonAffiliation.__eq__ = %s" % False
                            return False
                        del other_dict[t_ou_id]
                if len(other_dict) != 0:
                    if self._debug_eq:
                        print "PersonAffiliation.__eq__ = %s" % False
                    return False
        if self._debug_eq: print "PersonAffiliation.__eq__ = %s" % identical
        if not identical:
            return False

        if self._pn_affect_source is not None:
            for type in self._pn_affect_types:
                other_name = other.get_name(self._pn_affect_source, type)
                my_name = self._name_info.get(type, None)
                if my_name != other_name:
                    identical = False
                    break
        if self._debug_eq: print "PersonName.__eq__ = %s" % identical
        if not identical:
            return False

        identical = ((other.birth_date == self.birth_date) and
                     (other.gender == int(self.gender)) and
                     (other.description == self.description) and
                     (other.deceased == self.deceased))
        if self._debug_eq: print "Person.__eq__ = %s" % identical
        return identical

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
        super(Person, self).write_db(as_object)
        self.person_id = self.entity_id
        if as_object is None:
            self.person_id = super(Person, self).new(
                int(self.const.entity_person))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_info]
              (entity_type, person_id, export_id, birth_date, gender,
               deceased, description)
            VALUES
              (:e_type, :p_id, :exp_id, :b_date, :gender, :deceased, :desc)""",
                         {'e_type': int(self.const.entity_person),
                          'p_id': self.entity_id,
                          'exp_id': 'exp-'+str(self.entity_id),
                          'b_date': self.birth_date,
                          'gender': int(self.gender),
                          'deceased': 'F',
                          'desc': self.description})
            # print "X: %s" % str(self._external_id)
            for t_ss, t_type, t_id in self._external_id:
                self._set_external_id(t_ss, t_type, t_id)
        else:
            self.person_id = as_object.person_id
            self.execute("""
            UPDATE [:table schema=cerebrum name=person_info]
            SET export_id=:exp_id, birth_date=:b_date, gender=:gender,
                deceased=:deceased, description=:desc
            WHERE person_id=:p_id""",
                         {'exp_id': 'exp-'+str(self.entity_id),
                          'b_date': self.birth_date,
                          'gender': int(self.gender),
                          'deceased': 'F',
                          'desc': self.description,
                          'p_id': self.entity_id})

        affected_source = self._pa_affect_source
        if affected_source is not None:
            other = {}
            if as_object is not None:
                for t_ou_id, t_affiliation, t_source, t_status in \
                        as_object.get_affiliations(simple=False):
                    if affected_source == t_source:
                        other["%d-%d" % (t_ou_id, t_affiliation)] = t_status
            for affected_affil in self._pa_affected_affiliations:
                for ou_id, status in self._pa_affiliations[affected_affil]:
                    key = "%d-%d" % (ou_id, affected_affil)
                    if not other.has_key(key) or other[key] <> status:
                        self.add_affiliation(ou_id, affected_affil,
                                             affected_source, status)
                    if other.has_key(key):
                        del other[key]
                for key in other.keys():
                    ou_id, affected_affil = key.split('-')
                    status = other[key]
                    self.delete_affiliation(ou_id, affected_affiliation,
                                            affected_source, status)

        # If affect_names has not been called, we don't care about
        # names
        if self._pn_affect_source is not None:
            for type in self._pn_affect_types:
                try:
                    if not self._compare_names(type, as_object):
                        n = self._name_info.get(type)
                        self.execute("""
                        UPDATE [:table schema=cerebrum name=person_name]
                        SET name=:name
                        WHERE
                          person_id=:p_id AND
                          source_system=:src AND
                          name_variant=:n_variant""",
                                     {'name': self._name_info[type],
                                      'p_id': as_object.person_id,
                                      'src': int(self._pn_affect_source),
                                      'n_variant': int(type)})
                except KeyError, msg:
                    # Note: the arg to a python exception must be
                    # casted to str :-(
                    if str(msg) == "MissingOther":
                        if self._name_info.has_key(type):
                            self._set_name(self._pn_affect_source, type,
                                           self._name_info[type])
                    elif str(msg) == "MissingSelf":
                        self.execute("""
                        DELETE FROM [:table schema=cerebrum name=person_name]
                        WHERE
                          person_id=:p_id AND
                          source_system=:src AND
                          name_variant=:n_variant""",
                                     {'p_id': as_object.person_id,
                                      'src': int(self._pn_affect_source),
                                      'n_variant': int(type)})
                    else:
                        raise
        
        self.__write_db = False
        # TODO: Handle external_id

    def new(self, birth_date, gender, description=None, deceased='F'):
        """Register a new person.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """
        Person.populate(self, birth_date, gender, description, deceased)
        Person.write_db(self)
        Person.find(self, self.entity_id)
        return self.entity_id

    def find(self, person_id):
        """Associate the object with the person whose identifier is person_id.

        If person_id isn't an existing entity identifier,
        NotFoundError is raised.

        """
        (self.person_id, self.export_id, self.birth_date, self.gender,
         self.deceased, self.description) = self.query_1(
            """SELECT person_id, export_id, birth_date, gender,
                      deceased, description
               FROM [:table schema=cerebrum name=person_info]
               WHERE person_id=:p_id""", {'p_id': person_id})
        super(Person, self).find(person_id)

    def populate_external_id(self, source_system, id_type, external_id):
        self._external_id += ((source_system, id_type, external_id),)

    def _set_external_id(self, source_system, id_type, external_id):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=person_external_id]
          (person_id, id_type, source_system, external_id)
        VALUES (:p_id, :id_type, :src, :ext_id)""",
                     {'p_id': self.entity_id,
                      'id_type': int(id_type),
                      'src': int(source_system),
                      'ext_id': external_id})

    def find_persons_by_bdate(self, bdate):
        # TBD: Should the keep_entries() call really be here?
        return Utils.keep_entries(self.query("""
        SELECT person_id FROM [:table schema=cerebrum name=person_info]
        WHERE to_char(birth_date, 'YYYY-MM-DD')=:bdate""", locals()))

    def find_by_external_id(self, id_type, external_id):
        person_id = self.query_1("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_external_id]
        WHERE id_type=:id_type AND external_id=:ext_id""",
                                 {'id_type': int(id_type),
                                  'ext_id': external_id})
        self.find(person_id)
        return person_id

    def _compare_names(self, type, other):
        """Returns True if names are equal.

        self must be a populated object."""

        try:
            tmp = other.get_name(self._pn_affect_source, type)
            if len(tmp) == 0:
                raise KeyError
        except:
            raise KeyError, "MissingOther"
        try:
            myname = self._name_info[type]
        except:
            raise KeyError, "MissingSelf"
        return tmp == myname

    def _set_name(self, source_system, variant, name):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=person_name]
          (person_id, name_variant, source_system, name)
        VALUES (:p_id, :n_variant, :src, :name)""",
                     {'p_id': self.entity_id,
                      'n_variant': int(variant),
                      'src': int(source_system),
                      'name': name})

    def get_person_name_codes(self):
        return self.query("""
        SELECT code, description
        FROM [:table schema=cerebrum name=person_name_code]""")

    def get_name(self, source_system, variant):
        """Return the name with the given variant"""
        return self.query_1("""
        SELECT name
        FROM [:table schema=cerebrum name=person_name]
        WHERE
          person_id=:p_id AND
          name_variant=:n_variant AND
          source_system=:src""",
                            {'p_id': self.entity_id,
                             'n_variant': int(variant),
                             'src': int(source_system)})

    def affect_names(self, source, *types):
        self._pn_affect_source = source
        if types is None:
            raise NotImplementedError
        self._pn_affect_types = types

    def populate_name(self, type, name):
        self._name_info[type] = name

    def affect_affiliations(self, source, *types):
        self._pa_affect_source = source
        if types is None:
            raise NotImplementedError
        self._pa_affected_affiliations = types

    def populate_affiliation(self, ou_id, affiliation, status):
        self._pa_affiliations[affiliation] = \
            self._pa_affiliations.get(affiliation, []) + [(ou_id, status)]

    def get_affiliations(self, simple=True):
        if simple:
            return self.query("""
            SELECT ou_id, affiliation
            FROM [:table schema=cerebrum name=person_affiliation]
            WHERE person_id=:p_id""", {'p_id': self.entity_id})
        else:
            return self.query("""
            SELECT ou_id, affiliation, source_system, status
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE person_id=:p_id""", {'p_id': self.entity_id})

    def add_affiliation(self, ou_id, affiliation, source, status):
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'status': int(status),
                 'p_id': self.entity_id,
                 }
        # If needed, add to table 'person_affiliation'.
        try:
            self.query_1("""
            SELECT 'yes'
            FROM [:table schema=cerebrum name=person_affiliation]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation""", binds)
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation]
              (person_id, ou_id, affiliation)
            VALUES (:p_id, :ou_id, :affiliation)""", binds)
        try:
            self.query_1("""
            SELECT 'yes'
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation_source]
              (person_id, ou_id, affiliation, source_system, status)
            VALUES (:p_id, :ou_id, :affiliation, :source, :status)""",
                         binds)
        except Errors.NotFoundError:
            self.execute("""
            UPDATE [:table schema=cerebrum name=person_affiliation_source]
            SET status=:status, last_date=[:now], deleted_date=NULL
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)

    def delete_affiliation(self, ou_id, affiliation, source, status):
        self.execute("""
        UPDATE [:table schema=cerebrum name=person_affiliation_source]
        SET deleted_date=[:now]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", locals())
        # This method doesn't touch table 'person_affiliation', nor
        # does it try to do any actual deletion of rows from table
        # 'person_affiliation_source'; these tasks are in the domain
        # of various database cleanup procedures.

    def nuke_affiliation(self, ou_id, affiliation, source, status):
        p_id = self.entity_id
        # This method shouldn't be used lightly; see
        # .delete_affiliation().
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", locals())
        remaining_affiliations = self.query("""
        SELECT 'yes'
        FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation""", locals())
        if not remaining_affiliations:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=person_affiliation]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation""", locals())
