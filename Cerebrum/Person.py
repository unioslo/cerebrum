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

"""

import cereconf
from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityAddress, EntityQuarantine
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum import Account


class Person(EntityContactInfo, EntityAddress, EntityQuarantine, Entity):

    __read_attr__ = ('__in_db', '_affil_source', '__affil_data')
    __write_attr__ = ('birth_date', 'gender', 'description', 'deceased')

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        for attr in Person.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in Person.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

        # TODO: The following attributes are currently not in
        #       Person.__slots__, which means they will stop working
        #       once all Entity classes have been ported to use the
        #       mark_update metaclass.
        self._external_id= ()
        # Person names:
        self._pn_affect_source = None
        self._pn_affect_types = None
        self._name_info = {}

    def populate(self, birth_date, gender, description=None, deceased='F',
                 parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_person)
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
        self.birth_date = birth_date
        self.gender = gender
        self.description = description
        self.deceased = deceased

    def __eq__(self, other):
        """Define == operator for Person objects."""
        assert isinstance(other, Person)
        identical = self.__super.__eq__(other)
        if not identical:
            if cereconf.DEBUG_COMPARE:
                print "Person.super.__eq__ = %s" % identical
            return False

# The affiliation comparison stuff below seems to suffer from bitrot
# -- and with the current write_db() API, I'm not sure that we really
# *need* this functionality in __eq__().
#
##         if hasattr(self, '_affil_source'):
##             source = self._affil_source
##             for affected_affil in self._pa_affected_affiliations:
##                 other_dict = {}
##                 for t in other.get_affiliations():
##                     if t.source_system == source:
##                         # Not sure why this casting to int is required
##                         # on PostgreSQL
##                         other_dict[int(t.ou_id)] = t.status
##                 for t_ou_id, t_status in \
##                         self._pa_affiliations.get(affected_affil, []):
##                     # Not sure why this casting to int is required on
##                     # PostgreSQL
##                     t_ou_id = int(t_ou_id)
##                     if other_dict.has_key(t_ou_id):
##                         if other_dict[t_ou_id] <> t_status:
##                             if cereconf.DEBUG_COMPARE:
##                                 print "PersonAffiliation.__eq__ = %s" % False
##                             return False
##                         del other_dict[t_ou_id]
##                 if len(other_dict) != 0:
##                     if cereconf.DEBUG_COMPARE:
##                         print "PersonAffiliation.__eq__ = %s" % False
##                     return False
        if cereconf.DEBUG_COMPARE:
            print "PersonAffiliation.__eq__ = %s" % identical
        if not identical:
            return False

        if self._pn_affect_source is not None:
            for type in self._pn_affect_types:
                other_name = other.get_name(self._pn_affect_source, type)
                my_name = self._name_info.get(type, None)
                if my_name != other_name:
                    identical = False
                    break
        if cereconf.DEBUG_COMPARE:
            print "PersonName.__eq__ = %s" % identical
        if not identical:
            return False

        identical = ((other.birth_date == self.birth_date) and
                     (other.gender == int(self.gender)) and
                     (other.description == self.description) and
                     (other.deceased == self.deceased))
        if cereconf.DEBUG_COMPARE:
            print "Person.__eq__ = %s" % identical
        return identical

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method.

        """
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
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

        # Handle PersonAffiliations
        if hasattr(self, '_affil_source'):
            source = self._affil_source
            db_affil = {}
            for t_ou_id, t_affiliation, t_source, t_status in \
                    self.get_affiliations():
                if source == t_source:
                    idx = "%d:%d:%d" % (t_ou_id, t_affiliation, t_status)
                    db_affil[idx] = True
            pop_affil = self.__affil_data
            for idx in pop_affil.keys():
                if db_affil.has_key(idx):
                    del db_affil[idx]
                else:
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.add_affiliation(ou_id, affil, source, status)
            for idx in db_affil.keys():
                ou_id, affil, status = [int(x) for x in idx.split(":")]
                self.delete_affiliation(ou_id, affil, source, status)

        # If affect_names has not been called, we don't care about
        # names
        if self._pn_affect_source is not None:
            for type in self._pn_affect_types:
                try:
                    if not self._compare_names(type, self):
                        n = self._name_info.get(type)
                        self.execute("""
                        UPDATE [:table schema=cerebrum name=person_name]
                        SET name=:name
                        WHERE
                          person_id=:p_id AND
                          source_system=:src AND
                          name_variant=:n_variant""",
                                     {'name': self._name_info[type],
                                      'p_id': self.entity_id,
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
                                     {'p_id': self.entity_id,
                                      'src': int(self._pn_affect_source),
                                      'n_variant': int(type)})
                    else:
                        raise

        # TODO: Handle external_id
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def new(self, birth_date, gender, description=None, deceased='F'):
        """Register a new person."""
        self.populate(birth_date, gender, description, deceased)
        self.write_db()
        self.find(self.entity_id)

    def find(self, person_id):
        """Associate the object with the person whose identifier is person_id.

        If person_id isn't an existing entity identifier,
        NotFoundError is raised.

        """
        self.__super.find(person_id)
        (self.export_id, self.birth_date, self.gender,
         self.deceased, self.description) = self.query_1(
            """SELECT export_id, birth_date, gender,
                      deceased, description
               FROM [:table schema=cerebrum name=person_info]
               WHERE person_id=:p_id""", {'p_id': person_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

    def populate_external_id(self, source_system, id_type, external_id):
        self._external_id += ((source_system, id_type, external_id),)
        self.__updated = True

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
        return self.query("""
        SELECT person_id FROM [:table schema=cerebrum name=person_info]
        WHERE to_date(birth_date, 'YYYY-MM-DD')=:bdate""", locals())

    def find_by_external_id(self, id_type, external_id, source_system):
        person_id = self.query_1("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_external_id]
        WHERE id_type=:id_type AND
              external_id=:ext_id AND
              source_system=:src""", {'id_type': int(id_type),
                                      'ext_id': external_id,
                                      'src': int(source_system)})
        self.find(person_id)

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

    def list_person_name_codes(self):
        return self.query("""
        SELECT code, description
        FROM [:table schema=cerebrum name=person_name_code]""")

    def list_person_affiliation_codes(self):
        return self.query("""
        SELECT code, code_str, description
        FROM [:table schema=cerebrum name=person_affiliation_code]""")

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
        self.__updated = True

    def populate_affiliation(self, source_system, ou_id=None,
                             affiliation=None, status=None):
        if not hasattr(self, '_affil_source'):
            self._affil_source = source_system
            self.__affil_data = {}
        elif self._affil_source <> source_system:
            raise ValueError, \
                  "Can't populate multiple `source_system`s w/o write_db()."
        if ou_id is None:
            return
        idx = "%d:%d:%d" % (ou_id, affiliation, status)
        self.__affil_data[idx] = True

    def get_affiliations(self):
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

    def get_accounts(self):
        acc = Account.Account(self._db)
        return acc.list_accounts_by_owner_id(self.entity_id)


    def list_persons(self):
        """Return all person ids."""
        return self.query("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]""")
        
