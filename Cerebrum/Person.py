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

import pprint
pp = pprint.PrettyPrinter(indent=4)

class PersonName(object):
    "Mixin class for Person"

    def __init__(self):
        assert isinstance(Person, self)
        self.clear()

    def clear(self):
        self._pn_affect_source = None
        self._pn_affect_types = None
        self._name_info = {}

    def __eq__(self, other):
        if self._pn_affect_source == None:
            return True
        assert isinstance(other, PersonName)
        for type in self._pn_affect_types:
            other_name = other.get_name(self._pn_affect_source, type)
            my_name = self._name_info.get(type, None)
            if my_name != other_name:
                return False
        return True

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
        INSERT INTO cerebrum.person_name (person_id, name_variant, source_system, name)
        VALUES (:p_id, :n_variant, :s_system, :name)""",
                     {'p_id' : self.person_id, 'n_variant' : int(variant),
                      's_system' : int(source_system), 'name' : name})

    def get_person_name_codes(self):
        return self.query("SELECT code, description FROM person_name_code")

    def get_name(self, source_system, variant):
        """Return the name with the given variant"""

        return self.query_1("""SELECT name FROM person_name
            WHERE person_id=:p_id AND name_variant=:n_variant AND source_system=:s_system""",
                            {'p_id' : self.person_id, 'n_variant' : int(variant),
                             's_system' : int(source_system)})

    def affect_names(self, source, *types):
        self._pn_affect_source = source
        if types == None: raise "Not implemented"
        self._pn_affect_types = types

    def populate_name(self, type, name):
        self._name_info[type] = name

    def write_db(self, as_object=None):
        # If affect_names has not been called, we don't care about
        # names

        if self._pn_affect_source == None: return

        for type in self._pn_affect_types:
            try:
                if not self._compare_names(type, as_object):
                    n = self._name_info.get(type)
                    self.execute("""
                    UPDATE cerebrum.person_name
                    SET name=:name
                    WHERE person_id=:p_id AND source_system=:s_system AND
                       name_variant=:n_variant""",
                                 {'name' : self._name_info[type], 'p_id' : as_object.person_id,
                                  's_system' : int(self._pn_affect_source),
                                  'n_variant' : int(type)})
            except KeyError, msg:
                # Note: the arg to a python exception must be casted to str :-(
                if str(msg) == "MissingOther":
                    if self._name_info.has_key(type):
                        self._set_name(self._pn_affect_source, type, self._name_info[type])
                elif str(msg) == "MissingSelf":
                    self.execute("""DELETE cerebrum.person_name
                                    WHERE person_id=:p_id AND source_system=:s_system
                                          AND name_variant=:n_variant""",
                                 {'p_id' : as_object.person_id,
                                  's_system' : int(self._pn_affect_source),
                                  'n_variant' : int(type)})
                else:
                    raise
            
class PersonAffiliation(object):
    "Mixin class for Person"

    def __eq__(self, other):
        if self._pa_affect_source == None:
            return True

        for affect_type in self._pa_affect_types:
            other_aff = other.get_affiliations(source_system=self._pa_affect_source,
                                               affiliation=affect_type)
            other_dict = {}
            for t in other_aff:
                other_dict[t.ou_id] = t.status
            for t_ou_id, t_status in self._pa_affiliations.get(affect_type, []):
                if other_dict.has_key(t_ou_id):
                    if other_dict[t_ou_id] != int(t_status):
                        return False
                    del other_dict[t_ou_id]
            if len(other_dict) != 0:
                return False
        return True

    def clear(self):
        self._pa_affect_source = None
        self._pa_affiliations = {}

    def affect_affiliations(self, source, *types):
        self._pa_affect_source = source
        if types == None: raise "Not implemented"
        self._pa_affect_types = types

    def populate_affiliation(self, ou_id, affiliation, status):
        self._pa_affiliations[affiliation] = self._pa_affiliations.get(affiliation, []) + [(ou_id, status)]

    def write_db(self, as_object=None):
        if self._pa_affect_source == None: return
        other = {}
        for affect_type in self._pa_affect_types:
            if as_object != None:
                t = as_object.get_affiliations(source_system=self._pa_affect_source, affiliation=affect_type)
                for t_ss, t_ou_id, t_affiliation, t_status in t:
                    other["%d-%d" % (t_ou_id, t_affiliation)] = t_status
                    
            for ou_id, status in self._pa_affiliations[affect_type]:
                key = "%d-%d" % (ou_id, affect_type)
                if not other.has_key(key):
                    self.execute("""
                    INSERT INTO cerebrum.person_affiliation (person_id, ou_id, affiliation,
                       source_system, status, create_date, last_date)
                    VALUES (:p_id, :ou_id, :affiliation, :s_system, :status,
                            SYSDATE, SYSDATE)""",
                                 {'p_id' : self.person_id, 'ou_id' : ou_id,
                                  'affiliation' : int(affect_type),
                                  's_system' : int(self._pa_affect_source),
                                  'status' : int(status)})

                elif other[key] != int(status):
                    self.execute("""
                    UPDATE cerebrum.person_affiliation SET status=:status
                    WHERE person_id=:p_id AND ou_id=:ou_id AND affiliation=:affiliation
                          AND source_system=:s_system""",
                                 {'status' : int(status), 'p_id' : self.person_id,
                                  'ou_id' : ou_id, 'affiliation' : int(affect_type),
                                  's_system' : int(self._pa_affect_source)})
                if other.has_key(key): del other[key]
            for k in other.keys():
                # TODO: We don't delete affiliations, we mark them as deleted
                ou_id, affect_type = k.split('-')
                self.execute("""
                   DELETE cerebrum.person_affiliation
                   WHERE person_id=:p_id AND ou_id=:ou_id AND affiliation=:affiliation
                         AND source_system=:s_system""",
                             {'p_id' : self.person_id, 'ou_id' : int(ou_id),
                              'affiliation' : int(affect_type),
                              's_system' : int(self._pa_affect_source)})

    def get_affiliations(self, source_system=None, affiliation=None, ou_id=None):
        qry = """SELECT source_system, ou_id, affiliation, status
                 FROM cerebrum.person_affiliation WHERE person_id=:p_id"""
        params = {'p_id' : self.person_id}
        for v in ('source_system', 'affiliation', 'ou_id'):
            val = locals().get(v, None)
            if val != None:
                qry += " AND %s=:%s" % (v, v)
                params["%s" % v] = int(val)
        return self.query(qry, params)

class Person(Entity, EntityContactInfo, EntityAddress,
             EntityQuarantine, PersonName, PersonAffiliation):
    
    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.birth_date = None
        self.gender = None
        self.description = None
        self.deceased = None
        PersonName.clear(self)
        super(Person, self).clear()
        PersonAffiliation.clear(self)
        self._external_id= ()

    def populate(self, birth_date, gender, description=None, deceased='F'):
        "Set instance's attributes without referring to the Cerebrum DB."
        self.birth_date = birth_date
        self.gender = gender
        self.description = description
        self.deceased = deceased

        super(Person, self).populate(self.constants.entity_person)
        self.__write_db = True

        
##     def __ne__(self, other):
##         return not self.__eq__(other)

    def __eq__(self, other):
        """Ovveride the == test for objects.

        Note that None != the empty string ''"""
        assert isinstance(other, Person)
        identical = super(Person, self).__eq__(other)
        if not identical:
            if self._debug_eq: print "Person.super.__eq__ = %s" % identical
            return identical

        identical = EntityAddress.__eq__(self, other)
        if self._debug_eq: print "EntityAddress.__eq__ = %s" % identical
        if not identical: return False

        identical = PersonAffiliation.__eq__(self, other)
        if self._debug_eq: print "PersonAffiliation.__eq__ = %s" % identical
        if not identical: return False

        identical = PersonName.__eq__(self, other)
        if self._debug_eq: print "PersonName.__eq__ = %s" % identical
        if not identical: return False

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
            self.person_id = super(Person, self).new(int(self.constants.entity_person))

            self.execute("""
            INSERT INTO cerebrum.person_info (entity_type, person_id,
               export_id, birth_date, gender, deceased, description)
            VALUES (:e_type, :p_id, :exp_id, :b_date, :gender, :deceased, :desc)""",
                         {'e_type' : int(self.constants.entity_person),
                          'p_id' : self.person_id, 'exp_id' : 'exp-'+str(self.person_id),
                          'b_date' : self.birth_date, 'gender' : int(self.gender),
                          'deceased' : 'F', 'desc' : self.description})
            # print "X: %s" % str(self._external_id)
            for t_ss, t_type, t_id in self._external_id:
                self._set_external_id(t_ss, t_type, t_id)
        else:
            self.person_id = as_object.person_id
            
            self.execute("""
            UPDATE cerebrum.person_info SET export_id=:exp_id, birth_date=:b_date,
               gender=:gender, deceased=:deceased, description=:desc
            WHERE person_id=:p_id""",
                         {'exp_id' : 'exp-'+str(self.person_id), 'b_date' : self.birth_date,
                          'gender' : int(self.gender), 'deceased' : 'F',
                          'desc' : self.description, 'p_id' : self.person_id})

        EntityAddress.write_db(self, as_object)
        PersonAffiliation.write_db(self, as_object)
        PersonName.write_db(self, as_object)
        self.__write_db = False

        # TODO: Handle external_id

    def new(self, birth_date, gender, description=None, deceased='F'):
        """Register a new person.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """

        Person.populate(self, birth_date, gender, description, deceased)
        Person.write_db(self)
        Person.find(self, self.person_id)
        return self.person_id
    
    def find(self, person_id):
        """Associate the object with the person whose identifier is person_id.

        If person_id isn't an existing entity identifier,
        NotFoundError is raised.

        """
        (self.person_id, self.export_id, self.birth_date, self.gender,
         self.deceased, self.description) = self.query_1(
            """SELECT person_id, export_id, birth_date, gender,
                      deceased, description
               FROM cerebrum.person_info
               WHERE person_id=:p_id""", {'p_id' : person_id})
        super(Person, self).find(person_id)


    def populate_external_id(self, source_system, id_type, external_id):
        self._external_id += ((source_system, id_type, external_id),)

    def _set_external_id(self, source_system, id_type, external_id):
        self.execute("""
        INSERT INTO cerebrum.person_external_id(person_id, id_type, source_system, external_id)
        VALUES (:p_id, :id_type, :s_system, :ext_id)""",
                     {'p_id' : self.person_id, 'id_type' : int(id_type),
                      's_system' : int(source_system), 'ext_id' : external_id})

        pass

    def find_by_external_id(self, id_type, external_id):
        person_id = self.query_1("""
        SELECT person_id
        FROM cerebrum.person_external_id
        WHERE id_type=:id_type AND external_id=:ext_id""",
                                 {'id_type' : int(id_type), 'ext_id' : external_id})
        self.find(person_id)
        return person_id
