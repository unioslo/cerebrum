#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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
This file is part of the Cerebrum framework.

It provides an extension to the core Cerebrum Person class that is specific
to human resources system (LT) at the University of Oslo. Specifically, the
following additional information is provided:

- employment records (tilsetting)
- temporary employment records (bilag). People with such records are
  referred to as 'temps' in this module.
- guest records (gjest)
- role records (rolle)
- reservation records (reservasjon)
- leaves of absence records (permisjon)
"""

import sys
import string
import types

# FIXME: Eh, how safe/sane/correct is this?
from mx.DateTime import DateTime
from mx.DateTime import strptime

import xml
import xml.sax

import cerebrum_path
import cereconf

from Cerebrum import Person


_TILSETTINGS_SCHEMA = "[:table schema=cerebrum name=lt_tilsetting]"
_BILAGS_SCHEMA = "[:table schema=cerebrum name=lt_bilag]"
_GJEST_SCHEMA = "[:table schema=cerebrum name=lt_gjest]"
_RESERVASJONS_SCHEMA = "[:table schema=cerebrum name=lt_reservasjon]"
_PERMISJONS_SCHEMA = "[:table schema=cerebrum name=lt_permisjon]"
_ROLLE_SCHEMA = "[:table schema=cerebrum name=lt_rolle]"
_STILLINGSKODE_SCHEMA = "[:table schema=cerebrum name=lt_stillingskode]"
_GJESTETYPEKODE_SCHEMA = "[:table schema=cerebrum name=lt_gjestetypekode]"





class PersonLTMixin(Person.Person):
    """
    This class provides an UiO-specific extension to the core Person class.

    It provides an interface to the personnel system at UiO - LT.

    A few implementation notes:

    * PersonLTMixin offers several populate_* methods. These methods collect
      all (LT) attributes relevant for a particular person. Once a
      collection is done, the caller should call write_db() to synchronize
      the object with the database content.

      NB! The collection of values resulting from multiple populate_* calls
      is assumed to contain the *exact* image of data in LT. That is,
      write_db() must be called *after* *all* attributes have been
      populate_*'ed (otherwise we risk deleting useful information from
      Cerebrum). E.g.:

      # do NOT do this
      person.find(...)
      person.populate_tilsetting(...)  # attribute A
      person.write_db()
      person.populate_tilsetting(...)  # attribute B
      person.write_db()                # nukes A, writes B

      ... but rather do this:

      # M.O.:
      person.find(...)
      person.populate_tilsetting(...)  # attribute A
      person.populate_tilsetting(...)  # attribute B
      person.write_db()                # both A and B are written to Cerebrum

    * Since the attributes stored in self need to be compared to the
      corresponding attributes stored in the database, we need a safe way of
      ensuring that the 'same' attributes are compared. This is achieved by
      converting the information in the db into a dictionary D in the code (in
      _write_*-methods), and comparing D with a corresponding dictionary in
      self constructed with a suitable populate_* method.

      _make_*_key() methods can be used to construct the keys for such
      dictionaries.

      NB! Full comparison has not been implemented yet. However, the keys
      are compared correctly (worst case we write to the db a bit more often
      than necessary).

    * Do not change method/attribute names, since there is a correspondence
      between attribute names and table column names in the database.

    * get_*/list_* do not cache any values in the PersonLTMixin object. They
      fetch all data rows every time from the database

    * A typical populate-synchronize cycle would run like this:

      obj.populate_rolle(...)
      obj.populate_rolle(...)
      obj.write_db()
      |
      +--> obj.__super.write_db()
      |
      +--> obj._write_rolle(...)
           |
           +--> obj._write_attribute(...)

      _write_attribute() is the method doing the actual synchronization. All
      other _write_* methods simply prepare its arguments.

    * All populate_* methods accept a number of attributes originating from
      LT. However, all kinds of conversions (such as fnr -> person_id,
      (fak,ins,grp) -> ou_id) have to be performed by the module using this
      class. This class deals only with types found directly in the tables
      in mod_lt.sql

    * FIXME: The module has assumes that dates in the db are represented as
      mx.DateTime.DateTime objects by the DB-API.

    """

    __write_attr__ = ("tilsetting",
                      "bilag",
                      "gjest",
                      "rolle",
                      "reservert",
                      "permisjon",)



    def clear(self):
        """
        Reset all the ``mark_update''-relevant attributes of an object
        to their default values.
        """
        
        self.__super.clear()
        self.clear_class(PersonLTMixin)
        self.__updated = []
    # end clear

    

    # 
    # All _make_*_key routines are used to ensure that certain values are
    # guaranteed to be of the same type.
    # 
    def _make_tilsetting_key(self, tilsettings_id):
        return int(tilsettings_id)
    # end _make_tilsetting_key


    # FIXME: institusjon?
    def populate_tilsetting(self, tilsettings_id,
                            ou_id,
                            stillingskode,
                            dato_fra, dato_til,
                            andel):
        """
        Adjoin an employment (tilsetting) item.
        """

        # NB! stillingskode and ou_id must be located by the caller (this
        # method is not aware of where the data comes from, and thus has no
        # other choice but to operate with values as they should be inserted
        # into the proper table in mod_lt)

        key = self._make_tilsetting_key(tilsettings_id)

        if self.tilsetting is None:
            self.tilsetting = {}
        elif self.tilsetting.has_key(key):
            raise ValueError(("Duplicate tilsetting entry for " +
                              "(person_id, tilsettings_id) = (%s,%s)") %
                             (self.entity_id, key))
        # fi

        # New employment is a dictionary of (name, value) pairs, where name
        # corresponds to a column in the database table
        if dato_til is not None:
            dato_til = strptime(dato_til, "%Y%m%d")
        # fi
        self.tilsetting[key] = {
            "tilsettings_id" : int(tilsettings_id),
            "person_id"      : self.entity_id,
            "ou_id"          : int(ou_id),
            "stillingskode"  : int(stillingskode),
            "dato_fra"       : strptime(dato_fra, "%Y%m%d"),
            "dato_til"       : dato_til,
            "andel"          : int(andel)
        }
    # end populate_tilsetting



    def _make_bilag_key(self, ou_id):
        return int(ou_id)
    # end _make_bilag_key



    def populate_bilag(self, ou_id, dato):
        """
        Adjoin a temporary engagement record (bilag)
        """

        key = self._make_bilag_key(ou_id)
        dato = strptime(dato, "%Y%m%d")

        if self.bilag is None:
            self.bilag = {}
        elif self.bilag.has_key(key):
            # later payment date is populated
            if self.bilag[key]["dato"] < dato:
                pass
            # we have the latest date already
            elif self.bilag[key]["dato"] > dato:
                return
            # we have an exact replica
            else:
                raise ValueError(("Duplicate bilag entry for " +
                                  "(person_id, ou_id) = (%s,%s)") %
                                 (self.entity_id, key))
            # fi
        # fi

        self.bilag[key] = {
            "person_id" : int(self.entity_id),
            "ou_id"     : int(ou_id),
            "dato"      : dato,
        }
    # end populate_bilag



    def _make_gjest_key(self, ou_id, dato_fra):

        if type(dato_fra) is types.StringType:
            dato_fra = strptime(dato_fra, "%Y%m%d")
        # fi

        return (int(ou_id), dato_fra)
    # end _make_gjest_key
    


    def populate_gjest(self, ou_id, dato_fra, gjestetypekode, dato_til):
        """
        Adjoin a guest (gjest) record.
        """

        key = self._make_gjest_key(ou_id, dato_fra)
        
        if self.gjest is None:
            self.gjest = {}
        elif self.gjest.has_key(key):
            raise ValueError(("Duplicate gjest entry for " +
                             "(person_id, key) = (%s,%s)") %
                             (self.entity_id, key))
        # fi

        if dato_til is not None:
            dato_til = strptime(dato_til, "%Y%m%d")
        # fi
        self.gjest[key] = {
            "person_id"      : int(self.entity_id),
            "ou_id"          : int(ou_id),
            "dato_fra"       : strptime(dato_fra, "%Y%m%d"),
            "gjestetypekode" : int(gjestetypekode),
            "dato_til"       : dato_til,
        }
    # end populate_gjest



    def _make_permisjon_key(self, tilsettings_id, permisjonskode,
                            dato_fra, dato_til, lonstatuskode):
        
        if type(dato_fra) is types.StringType:
            dato_fra = strptime(dato_fra, "%Y%m%d")
        # fi
        if type(dato_til) is types.StringType:
            dato_til = strptime(dato_til, "%Y%m%d")
        # fi
        permisjonskode = int(permisjonskode)
        tilsettings_id = int(tilsettings_id)
        lonstatuskode = int(lonstatuskode)

        return (tilsettings_id, permisjonskode,
                dato_fra, dato_til, lonstatuskode)
    # end _make_permisjon_key
    
        

    def populate_permisjon(self, tilsettings_id, permisjonskode,
                           dato_fra, dato_til, andel, lonstatuskode):
        """
        Adjoin a permisjon (leave of absence) record.
        """

        key = self._make_permisjon_key(tilsettings_id, permisjonskode,
                                       dato_fra, dato_til, lonstatuskode)
        if self.permisjon is None:
            self.permisjon = {}
        elif self.permisjon.has_key(key):
            raise ValueError(("Duplicate permisjon entry for " +
                             "(person_id, key) = (%s,%s)") %
                             (self.entity_id, key))
        # fi

        self.permisjon[key] = {
            "tilsettings_id"	: int(tilsettings_id),
            "person_id"         : int(self.entity_id),
            "permisjonskode"    : int(permisjonskode),
            "dato_fra"          : strptime(dato_fra, "%Y%m%d"),
            "dato_til"          : strptime(dato_til, "%Y%m%d"),
            "andel"             : int(andel),
            "lonstatuskode"     : int(lonstatuskode),
        }
    # end populate_permisjon



    def populate_reservert(self, reservert):
        """
        Adjoin a reservation (reservert) record.
        """

        if hasattr(self, "reservert") and self.reservert is not None:
            raise ValueError(("Duplicate reservert entry for " +
                             "(person_id) = (%s)") % (self.entity_id))
        # fi

        self.reservert = bool(reservert)
    # end populate_reservert



    def _make_rolle_key(self, ou_id, rollekode):
        return (int(ou_id), int(rollekode))
    # end _make_rolle_key
    


    def populate_rolle(self, ou_id, rollekode, dato_fra, dato_til):
        """
        Adjoin a role record.
        """

        key = self._make_rolle_key(ou_id, rollekode)

        if self.rolle is None:
            self.rolle = {}
        elif self.rolle.has_key(key):
            raise ValueError(("Duplicate rolle entry for " +
                              "(person_id, key) = (%s,%s)") %
                             (self.entity_id, key))
        # fi

        if dato_til is not None:
            dato_til = strptime(dato_til, "%Y%m%d")
        # fi

        self.rolle[key] = {
            "person_id"	: int(self.entity_id),
            "ou_id"     : int(ou_id),
            "rollekode" : int(rollekode),
            "dato_fra"  : strptime(dato_fra, "%Y%m%d"),
            "dato_til"  : dato_til,
        }
    # end populate_rolle
        


    def write_db(self):
        """
        Synchronize the object's content with the database 
        """

        ret = self.__super.write_db()
        if not self.__updated:
            return ret
        # fi

        local_updates = None
        for name in [ "tilsetting" , "bilag",
                      "gjest", "rolle", "reservert", "permisjon" ]:
            if hasattr(self, name) and getattr(self, name) is not None:
                next = getattr(self, "_write_" + name)()
                # This would preserve local_ret == False
                local_updates = next or local_updates
            # fi
        # od

        #
        # Three different return values:
        # - None (no information was updated),
        # - False (no sync necessary)
        # - True (something got written to the database
        if ret is None:
            return local_updates
        elif local_updates is None:
            return ret
        else:
            return ret or local_updates
        # fi
    # end write_db



    def delete(self):
        """
        Remove person from:

        _TILSETTINGS_SCHEMA, _BILAGS_SCHEMA, _GJEST_SCHEMA,
        _RESERVASJONS_SCHEMA, _PERMISJONS_SCHEMA, _ROLLE_SCHEMA

        This is this class' part of the deletion of a person
        entity. superclasses and/or siblings fix the rest through super/mro.
        """

        for schema in (_PERMISJONS_SCHEMA, _TILSETTINGS_SCHEMA, _BILAGS_SCHEMA,
                       _GJEST_SCHEMA, _RESERVASJONS_SCHEMA, _ROLLE_SCHEMA):
            self.execute("""
                         DELETE FROM
                           %s
                         WHERE
                           person_id = :person_id
                         """ % schema,
                         {"person_id" : int(self.entity_id)})
        # od

        self.__super.delete()
    # end delete



    def get_bilag(self):
        return self.list_bilag(self.entity_id)
    # end get_bilag



    def get_tilsetting(self, timestamp = None):
        return self.list_tilsetting(self.entity_id, timestamp)
    # end get_tilsetting



    def get_gjest(self, timestamp = None):
        return self.list_gjest(self.entity_id, timestamp)
    # end get_gjest

    

    def get_reservert(self):
        # FIXME: should 'reservert' be converted to boolean type?
        return self.list_reservert(self.entity_id)
    # end get_reservert



    def get_permisjon(self, timestamp=None, tilsettings_id=None):
        return self.list_permisjon(self.entity_id, timestamp, tilsettings_id)
    # end get_permisjon
    


    def get_rolle(self, timestamp=None):
        return self.list_rolle(self.entity_id, timestamp)
    # end get_rolle
    


    def list_bilag(self, person_id):
        """
        List all temporary employment (bilag) records for PERSON_ID.
        """

        return self.query("""
                          SELECT person_id, ou_id, dato
                          FROM %s
                          WHERE person_id = :person_id
                          """ % _BILAGS_SCHEMA,
                          {"person_id" : self.entity_id})
    # end list_bilag
    


    def _make_timestamp_clause(self, timestamp):
        """
        A help function for several list_* methods operating with dates
        around TIMESTAMP.

        This function returns a tuple (SQL, bind-params), where SQL is an
        addition to an sql where-clause and bind-params is a dictionary with
        bind parameters for such a clause
        """

        if timestamp is None:
            return "", {}
        # fi

        time_clause = """
                      AND dato_fra <= :timestamp
                      AND ((dato_til is null) OR
                           (:timestamp <= dato_til))
                      """
        return time_clause, {"timestamp" : strptime(timestamp, "%Y%m%d")}
    # end _make_timestamp_clause

        

    def list_tilsetting(self, person_id = None, timestamp = None):
        """
        List all employment (tilsetting) records for PERSON_ID.

        If TIMESTAMP is not None (it must be a string in the format
        'YYYYMMDD'), report employment records with dato_fra <= TIMESTAMP <=
        dato_til only.
        """

        values = dict()
        person_clause = ""
        if person_id is not None:
            values["person_id"] = int(person_id)
            person_clause = " AND t.person_id = :person_id "
        # fi
        
        time_clause, extra_vars = self._make_timestamp_clause(timestamp)
        values.update(extra_vars)

        return self.query("""
                          SELECT
                            t.tilsettings_id, t.person_id,
                            t.ou_id, t.stillingskode,
                            t.dato_fra, t.dato_til,
                            t.andel,
                            s.code_str, s.hovedkategori, s.tittel
                          FROM
                            %s t,
                            %s s
                          WHERE
                            t.stillingskode = s.code 
                            %s
                            %s
                          """ % (_TILSETTINGS_SCHEMA,
                                 _STILLINGSKODE_SCHEMA,
                                 person_clause,
                                 time_clause),
                          values)
    # end list_tilsetting



    def list_gjest(self, person_id, timestamp = None):
        """
        List all guest (gjest) records for PERSON_ID

        If TIMESTAMP is not None (it must be a string in the format
        'YYYYMMDD'), report guest records with dato_fra <= TIMESTAMP <=
        dato_til only.
        """

        values = {"person_id" : int(person_id)}
        time_clause, extra_vars = self._make_timestamp_clause(timestamp)
        values.update(extra_vars)

        return self.query("""
                          SELECT
                            g.person_id, g.ou_id, g.dato_fra,
                            g.gjestetypekode, g.dato_til,
                            c.code_str, c.tittel
                          FROM
                            %s g,
                            %s c
                          WHERE
                            g.person_id = :person_id AND
                            g.gjestetypekode = c.code
                            %s
                          """ % (_GJEST_SCHEMA,
                                 _GJESTETYPEKODE_SCHEMA,
                                 time_clause),
                          values)
    # end list_gjest



    def list_reservert(self, person_id):
        """
        List all reservation (reservert) records for PERSON_ID (There can be
        at most one)
        """

        return self.query("""
                          SELECT person_id, reservert
                          FROM %s
                          WHERE person_id = :person_id
                          """ % _RESERVASJONS_SCHEMA,
                          {"person_id" : person_id})
    # end list_reservert



    def list_permisjon(self, person_id, timestamp = None,
                       tilsettings_id = None):
        """
        List all leaves of absence (permisjon) records for PERSON_ID

        If TIMESTAMP is not None (it must be a string in the format
        'YYYYMMDD'), report leave records with dato_fra <= TIMESTAMP <=
        dato_til only.

        If TILSETTINGS_ID is not None, list only those leaves of absence
        pertinent to a particular employment (tilsetting).
        """

        values = {"person_id" : int(person_id)}
        time_clause, extra_vars = self._make_timestamp_clause(timestamp)
        values.update(extra_vars)
        
        emp_clause = ""
        if tilsettings_id is not None:
            emp_clause = " AND tilsettings_id = :tilsettings_id "
            values["tilsettings_id"] = int(tilsettings_id)
        # fi

        return self.query("""
                          SELECT tilsettings_id, person_id,
                                 permisjonskode, dato_fra, dato_til, andel,
                                 lonstatuskode
                          FROM %s
                          WHERE person_id = :person_id
                                %s
                                %s
                          """ % (_PERMISJONS_SCHEMA,
                                 time_clause,
                                 emp_clause),
                          values)
    # end list_permisjon



    def list_rolle(self, person_id, timestamp = None):
        """
        List all role records for PERSON_ID.

        If TIMESTAMP is not None (it must be a string in the format
        'YYYYMMDD'), report role records with dato_fra <= TIMESTAMP <=
        dato_til only.
        """

        values = {"person_id" : int(person_id)}
        time_clause, extra_vars = self._make_timestamp_clause(timestamp)
        values.update(extra_vars)

        return self.query("""
                          SELECT person_id, ou_id, rollekode,
                                 dato_fra, dato_til
                          FROM %s
                          WHERE person_id = :person_id
                                %s
                          """ % (_ROLLE_SCHEMA, time_clause),
                          values)
    # end list_rolle



    def _write_attribute(self,
                         old_state,
                         new_state,
                         update_sql,
                         insert_sql,
                         delete_sql):
        """
        This function performs a generic synchronization of one of the
        __write_attr__ attributes (called A) against the authoritative
        source (LT).
        
        old_state represents Cerebrum's current information for this
        person's A. It is used destructively!

        new_state represents LT's current information for this persons's A.

        After the update, Cerebrum should be an exact replica of the LT's
        information.

        FIXME: document {old,new}_state's structure

        The update is performed through the following stages:

        old_state = OS
        new_state = NS

        * For each item I in NS:
          - If I exists in OS and OS[I] == I, then skip I. Remove OS[I].
            This is an item that existed in Cerebrum and did not change.
            
          - If I exists in OS and OS[I] != I, update OS[I] with I. Remove
            OS[I].
            This is an item that existed in Cerebrum but changed in LT.
          
          - If I does not exist in OS, insert new I into the database.

        * For each item J that is left in OS:
          - Remove J from the database, since this item does no longer exist
            in LT.

        Various *_sql contain sql statements to run in case of update,
        insert or delete. NB! delete_sql can contain an ordered sequence of
        SQL staments to run (this comes in handy when certain rows have to
        be removed before others due to foreign key constraints)
        """

        #
        # FIXME: Protect (try-except) the db-operations

        db_update = False
        for key, value in new_state.items():

            # This item exists already in Cerebrum.
            # We assume the LT's values are to replace Cerebrum's
            if old_state.has_key(key):
                self.execute( update_sql, value )
                db_update = True

                del old_state[ key ]

            # New entry
            else:
                self.execute( insert_sql, value )
                db_update = True
            # fi
        # od

        # Now, all updates have been written to the db. Whatever is left in
        # old_state is the information from Cerebrum that no longer exists
        # in LT. It should be deleted.
        for key, value in old_state.items():
            if type(delete_sql) is types.StringType:
                delete_sql = [ delete_sql ]
            # fi

            for statement in delete_sql:
                self.execute( statement, value )
            # od
            db_update = True
        # od

        return db_update
    # end _write_attribute

    
            
    def _write_tilsetting(self):
        """
        Perform an update of this person's employment (tilsetting) records.

        This method simply prepares a few arguments for
        _write_attribute. The actual synchronization lies there
        """

        # First, fetch all the old information
        current_employment = {}
        for item in self.get_tilsetting():
            # coerse db_row to a dictionary
            d = item._dict()
            key = self._make_tilsetting_key(item["tilsettings_id"])
            current_employment[key] = d
        # od

        update_sql = """
                     UPDATE %s
                     SET ou_id = :ou_id,
                         stillingskode = :stillingskode,
                         dato_fra = :dato_fra,
                         dato_til = :dato_til,
                         andel = :andel
                     WHERE
                         tilsettings_id = :tilsettings_id AND
                         person_id = :person_id
                     """ % _TILSETTINGS_SCHEMA
        
        insert_sql = """
                     INSERT INTO %s
                       (tilsettings_id, person_id, ou_id, stillingskode,
                        dato_fra, dato_til, andel)
                     VALUES
                       (:tilsettings_id, :person_id, :ou_id,
                        :stillingskode, :dato_fra, :dato_til, :andel)
                     """ % _TILSETTINGS_SCHEMA

        delete_prerequisite = """
                              DELETE FROM %s
                              WHERE
                                tilsettings_id = :tilsettings_id AND
                                person_id = :person_id
                              """ % _PERMISJONS_SCHEMA  

        delete_sql = """
                     DELETE FROM %s
                     WHERE
                       tilsettings_id = :tilsettings_id AND
                       person_id = :person_id
                     """ % _TILSETTINGS_SCHEMA

        return self._write_attribute( current_employment,
                                      self.tilsetting,
                                      update_sql,
                                      insert_sql,
                                      [ delete_prerequisite, delete_sql ] )
    # end _write_tilsetting



    def _write_bilag(self):
        """
        Perform an update of this person's bilag records.

        The update is a synchronization in the same fashion as
        _write_tilsetting.
        """

        # FIXME: We should register only the *latest* bilag for a given
        # (person,OU). This does *not* happen yet.

        current_bilag = {}
        for item in self.get_bilag():
            d = item._dict()
            key = self._make_bilag_key(item["ou_id"])
            # FIXME: what if 'dato' field in Cerebrum is more recent than
            # the one being populated in?
            current_bilag[key] = d
        # od

        # Ugh! _write_attribute has no predicate for update/insert/delete


        update_sql = """
                     UPDATE %s
                     SET dato = :dato
                     WHERE
                       person_id = :person_id AND
                       ou_id = :ou_id
                     """ % _BILAGS_SCHEMA

        insert_sql = """
                     INSERT INTO %s
                       (person_id, ou_id, dato)
                     VALUES
                       (:person_id, :ou_id, :dato)
                    """ % _BILAGS_SCHEMA

        delete_sql = """
                     DELETE FROM %s
                     WHERE
                        person_id = :person_id AND
                        ou_id = :ou_id
                     """ % _BILAGS_SCHEMA

        return self._write_attribute(current_bilag,
                                     self.bilag,
                                     update_sql, insert_sql, delete_sql)
    # end _write_bilag



    def _write_permisjon(self):
        """
        Perform an update of this person's permisjon records

        The update is a synchronization in the same fashion as
        _write_tilsetting.
        """

        current = {}
        for item in self.get_permisjon():
            d = item._dict()
            key = self._make_permisjon_key(d["tilsettings_id"],
                                           d["permisjonskode"],
                                           d["dato_fra"], d["dato_til"],
                                           d["lonstatuskode"])
            current[key] = d
        # od
        
        pk_expression = """
                        tilsettings_id = :tilsettings_id AND
                        person_id = :person_id AND
                        permisjonskode = :permisjonskode AND
                        dato_fra = :dato_fra AND
                        dato_til = :dato_til AND
                        lonstatuskode = :lonstatuskode
                        """
        schema = _PERMISJONS_SCHEMA
        
        update_sql = """
                     UPDATE %(schema)s
                     SET andel = :andel
                     WHERE %(pk_expression)s
                     """ % locals()

        insert_sql = """
                     INSERT INTO %(schema)s
                       (tilsettings_id, person_id, permisjonskode,
                        dato_fra, dato_til, andel, lonstatuskode)
                     VALUES
                       (:tilsettings_id, :person_id, :permisjonskode,
                        :dato_fra, :dato_til, :andel, :lonstatuskode)
                     """ % locals()

        delete_sql = """
                     DELETE FROM %(schema)s
                     WHERE %(pk_expression)s
                     """ % locals()

        return self._write_attribute(current,
                                     self.permisjon,
                                     update_sql,
                                     insert_sql,
                                     delete_sql)
    # end _write_permisjon
    


    def _write_gjest(self):
        """
        Perform an update of this person's gjest records

        The update is a synchronization in the same fashion as
        _write_tilsetting.
        """

        current_guest = dict()
        for item in self.get_gjest():
            d = item._dict()
            key = self._make_gjest_key(item["ou_id"], item["dato_fra"])
            current_guest[key] = d
        # od

        update_sql = """
                     UPDATE %s
                     SET gjestetypekode = :gjestetypekode,
                         dato_til = :dato_til
                     WHERE
                       person_id = :person_id AND
                       ou_id = :ou_id AND
                       dato_fra = :dato_fra
                     """ % _GJEST_SCHEMA

        insert_sql = """
                     INSERT INTO %s
                       (person_id, ou_id, dato_fra, gjestetypekode, dato_til)
                     VALUES
                       (:person_id, :ou_id, :dato_fra,
                        :gjestetypekode, :dato_til)
                    """ % _GJEST_SCHEMA

        delete_sql = """
                     DELETE FROM %s
                     WHERE
                        person_id = :person_id AND
                        ou_id = :ou_id AND
                        dato_fra = :dato_fra
                     """ % _GJEST_SCHEMA

        return self._write_attribute(current_guest,
                                     self.gjest,
                                     update_sql, insert_sql, delete_sql)
    # end _write_guest



    def _write_rolle(self):
        """
        Perform an update of this person's role records.

        The update is a synchronization similar to _write_tilsetting.
        """

        current_state = dict()
        for item in self.get_rolle():
            d = item._dict()
            key = self._make_rolle_key(item["ou_id"], item["rollekode"]) 
            current_state[key] = d
        # od

        schema = _ROLLE_SCHEMA
        pk_expression = """
                        person_id = :person_id AND
                        ou_id = :ou_id AND
                        rollekode = :rollekode
                        """

        update_sql = """
                     UPDATE %(schema)s
                     SET dato_fra = :dato_fra, dato_til = :dato_til
                     WHERE %(pk_expression)s
                     """ % locals()

        insert_sql = """
                     INSERT INTO %(schema)s
                       (person_id, ou_id, rollekode, dato_fra, dato_til)
                     VALUES
                       (:person_id, :ou_id, :rollekode, :dato_fra, :dato_til)
                    """ % locals()

        delete_sql = """
                     DELETE FROM %(schema)s
                     WHERE %(pk_expression)s
                     """ % locals()

        return self._write_attribute(current_state,
                                     self.rolle,
                                     update_sql, insert_sql, delete_sql)
    # end _write_rolle
        


    def _write_reservert(self):
        """
        Perform an update of this person's RESERVERT status.

        The update is a synchronization similar to _write_tilsetting.
        """

        # CURRENT_STATE/NEW_STATE look a bit odd, since _write_attribute is
        # designed primarily for multivalued attributes.

        current_state = dict()
        current_reservation = self.get_reservert()
        if current_reservation:
            current_state["reservert"] = {
                "person_id" : self.entity_id,
                "reservert" : current_reservation[0].reservert
                }
        # fi

        # self.reservert is guaranteed to be set at this point
        new_state = dict()
        new_state["reservert"] = {
            "person_id" : self.entity_id,
            "reservert" : {True : "T", False : "F"}[self.reservert]
        }

        update_sql = """
                     UPDATE %s
                     SET reservert = :reservert
                     WHERE person_id = :person_id 
                     """ % _RESERVASJONS_SCHEMA

        insert_sql = """
                     INSERT INTO %s (person_id, reservert)
                     VALUES (:person_id, :reservert)
                    """ % _RESERVASJONS_SCHEMA

        # Is this necessary, at all?
        delete_sql = """
                     DELETE FROM %s
                     WHERE person_id = :person_id
                     """ % _RESERVASJONS_SCHEMA

        return self._write_attribute(current_state,
                                     new_state,
                                     update_sql, insert_sql, delete_sql)
    # end _write_reservert



    def wipe_mod_lt(self):
        """
        This function deletes all data from non-code tables in mod_lt.

        Since we sync with LT on daily basis, the easiest way to drop all
        stale records, is by dropping *all* the records in mod_lt. It is
        safe to do that, provided that the session looks like this:

        transaction start
        wipe_mod_lt
        <load all new data>
        commit / rollback
        """

        for schema in (_PERMISJONS_SCHEMA, _RESERVASJONS_SCHEMA,
                       _ROLLE_SCHEMA, _GJEST_SCHEMA, _BILAGS_SCHEMA,
                       _TILSETTINGS_SCHEMA):
            self.execute("DELETE FROM %s" % schema)
        # od 
    # end wipe_mod_lt



    def list_frida_persons(self):
        """
        Return a list of person_ids eligible for FRIDA output.

        This method is not necessary, strictly speaking. However, it speeds
        up FRIDA export by a factor of about 9 and reduces the memory
        footprint by a factor of about 8 compared to naive db lookups.

        NB! Do *NOT* (I repeat, do *NOT*) use this method, unless you have
        the proper indices built in the database.
        """
        import time

        now = time.strftime("%Y%m%d")
        time_clause, values = self._make_timestamp_clause(now)

        query = """
                SELECT
                  p.person_id
                FROM
                  [:table schema=cerebrum name=person_info] p
                WHERE
                  EXISTS (SELECT
                            *
                          FROM
                            %s t
                          WHERE
                            p.person_id = t.person_id
                            %s)
                  OR EXISTS (SELECT
                               *
                             FROM
                               %s g
                             WHERE p.person_id = g.person_id
                             %s)
                """ % (_TILSETTINGS_SCHEMA,
                       time_clause,
                       _GJEST_SCHEMA,
                       time_clause)
        return self.query(query, values)
    # end list_frida_persons
# end PersonLTMixin
