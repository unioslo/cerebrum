# -*- coding: iso8859-1 -*-
#
# Copyright 2003, 2004 University of Oslo, Norway
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
This module implements a few extensions to the standard Cerebrum classes;
extensions that are specific to the HiA SAP human resources system.

Specifically, the OU core class is extended with:

  * forretningsområdekode (fo_kode/gsber)
  * organisasjonsenhet (orgeh/sap_orgeh)

These fields uniquely identify an OU, and this module provides the mapping
between (orgeh, fo_kode) and ou_id. None of these attributes are cached
within the object (since not all OUs have a SAP id).

The Person core class is extended with:

  * fo_kode
  * sprak
  * permisjonskode
  * permisjonsandel
  * tilsetting
  * rolle

(The last two attributes can have multiple values). *None* of these
attributes are cached within the object. I.e. an explicit get/list call is
required to fetch them. PersonSAPMixin is very similar to PersonLTMixin.
"""

import cereconf

from Cerebrum import OU
from Cerebrum import Person
from Cerebrum import Errors

from mx.DateTime import DateTime
from mx.DateTime import strptime

import types
import string





_SAP_OU_SCHEMA = "[:table schema=cerebrum name=sap_OU]"
_SAP_PERSON_SCHEMA = "[:table schema=cerebrum name=sap_person]"
_SAP_TILSETTING_SCHEMA = "[:table schema=cerebrum name=sap_tilsetting]"
_SAP_ROLLE_SCHEMA = "[:table schema=cerebrum name=sap_rolle]"
_SAP_STILLINGSTYPE_SCHEMA = "[:table schema=cerebrum name=sap_stillingstype]"
_SAP_LONNSTITTEL_SCHEMA = "[:table schema=cerebrum name=sap_lonnstittel]"
_SAP_UTVALG_SCHEMA = "[:table schema=cerebrum name=sap_utvalg]"
_PERSON_EXTERNAL_ID_SCHEMA = "[:table schema=cerebrum name=person_external_id]"





class PersonSAPMixin(Person.Person):
    """
    This clas provides a HiA-specific extension to the core Person class.
    """

    __singlevalued_attr__ = ("fo_kode",
                             "sprak",
                             "permisjonskode",
                             "permisjonsandel",)
    __multivalued_attr__ = ("tilsetting",
                            "rolle",)
    __write_attr__ = __singlevalued_attr__ + __multivalued_attr__

    
    def clear(self):
        """
        Reset all the ``mark_update''-relevat attributes of an object to
        their default values.
        """
        
        self.__super.clear()
        self.clear_class(PersonSAPMixin)
        self.__updated = []
    # end clear



    def write_db(self):
        """
        Synchronize SELF with the database.
        """

        ret = self.__super.write_db()

        if not self.__updated:
            return ret
        # fi

        local_updates = self._write_singlevalued_attributes()
            
        for name in self.__multivalued_attr__:
            if name in self.__updated:
                tmp = getattr(self, "_write_" + name)()
                if tmp is not None:
                    local_updates = local_updates or tmp
                # fi
            # fi
        # od

        # Mark this object as synchronized
        self.__updated = []

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



    def get_person_sap_info(self):
        return self.list_person_sap_info(self.entity_id)
    # end get_person_sap_info



    def list_person_sap_info(self, entity_id):
        """
        Returns a db_row with person-specific singlevalued SAP attributes:

        fo_kode, sprak, permisjonskode, permisjonsandel.
        """

        return self.query_1("""
                            SELECT
                              person_id, fo_kode, sprak,
                              permisjonskode, permisjonsandel
                            FROM
                              %s
                            WHERE
                              person_id = :person_id
                            """ % _SAP_PERSON_SCHEMA,
                            {"person_id" : entity_id})
    # end list_person_sap_info



    def _make_tilsetting_key(self, ou_id, funksjonstittel):
        """
        Make a unique key distinguishing between various tilsetting records
        for a given person.
        """
        
        return (int(ou_id), int(funksjonstittel))
    # end _make_tilsetting_key



    def populate_tilsetting(self, ou_id, lonnstittel, funksjonstittel,
                            stillingstype,
                            dato_fra = None, dato_til = None,
                            andel = None):
        
        key = self._make_tilsetting_key(ou_id, funksjonstittel)
        # C's ?:-operator
        dato_fra = dato_fra and strptime(dato_fra, "%Y%m%d") or dato_fra
        dato_til = dato_til and strptime(dato_til, "%Y%m%d") or dato_til
        if andel:
            andel = float(andel)
            assert 0 <= andel <= 100, \
                   "andel must be a percentage (between 0 and 100)"
        # fi
        
        value = {"person_id"       : int(self.entity_id),
                 "ou_id"           : int(ou_id),
                 "lonnstittel"     : int(lonnstittel),
                 "funksjonstittel" : int(funksjonstittel),
                 "stillingstype"   : stillingstype,
                 "dato_fra"	   : dato_fra,
                 "dato_til"        : dato_til,
                 "andel"           : float(andel),}
        self._populate_multivalued_attribute("tilsetting",
                                              key,
                                              value)
    # end populate_tilsetting



    def get_tilsetting(self):
        return self.list_tilsetting(self.entity_id)
    # end get_tilsetting



    def list_tilsetting(self, person_id):
        """
        List all tilsetting (employment) records for a given PERSON_ID.
        """

        # 
        # Humans are seldomly interested in numeric values; thus a 4-way
        # join. FIXME: we might such things as gsber/fo_kode.
        return self.query("""
                          SELECT
                            t.person_id, t.ou_id,
                            t.dato_fra, t.dato_til,
                            t.andel,
                            t.lonnstittel,
                            t.funksjonstittel,
                            t.stillingstype,
                            st.code_str as stillingstypekode,
                            lt.code_str as lonnstittelkode
                          FROM
                            %s t,   /* tilsetting */
                            %s st,  /* stillingstype */
                            %s lt   /* lønnstittel */
                          WHERE
                            t.person_id = :person_id AND
                            st.code = t.stillingstype AND
                            lt.code = t.lonnstittel
                          """ % (_SAP_TILSETTING_SCHEMA,
                                 _SAP_STILLINGSTYPE_SCHEMA,
                                 _SAP_LONNSTITTEL_SCHEMA),
                          {"person_id" : person_id})
    # end list_tilsetting
    


    def _write_tilsetting(self):
        """
        Perform an update of this person's tilsetting (employment) records.
        """

        # First, fetch all the old information
        current_state = {}
        for item in self.get_tilsetting():
            # coerse db_row to a dictionary
            d = item._dict()
            key = self._make_tilsetting_key(item["ou_id"], item["funksjonstittel"])
            current_state[key] = d
        # od

        pk_expression = """
                        person_id = :person_id AND
                        ou_id = :ou_id AND
                        funksjonstittel = :funksjonstittel 
                        """

        update_sql = """
                     UPDATE
                       %s
                     SET
                       lonnstittel = :lonnstittel, stillingstype = :stillingstype,
                       dato_fra = :dato_fra, dato_til = :dato_til, andel = :andel
                     WHERE
                       %s
                     """ % (_SAP_TILSETTING_SCHEMA, pk_expression)
        
        insert_sql = """
                     INSERT INTO
                       %s(person_id, ou_id, lonnstittel, funksjonstittel,
                          stillingstype, dato_fra, dato_til, andel)
                     VALUES
                       (:person_id, :ou_id, :lonnstittel, :funksjonstittel,
                        :stillingstype, :dato_fra, :dato_til, :andel)
                     """ % (_SAP_TILSETTING_SCHEMA)

        delete_sql = """
                     DELETE FROM
                       %s
                     WHERE
                       %s
                     """ % (_SAP_TILSETTING_SCHEMA, pk_expression)

        return self._write_multivalued_attribute(current_state,
                                                 self.tilsetting,
                                                 update_sql,
                                                 insert_sql, delete_sql)
    # end _write_tilsetting



    def _make_rolle_key(self, utvalg):
        """
        Make a unique key distinguishing between various utvalg records for
        a given person.
        """

        return int(utvalg)
    # end _make_rolle_key



    def populate_rolle(self, utvalg,
                       dato_fra = None, dato_til = None,
                       utvalgsrolle = None):
        """
        Adjoin a SAP rolle (role) record.
        """

        key = self._make_rolle_key(utvalg)
        dato_fra = dato_fra and strptime(dato_fra, "%Y%m%d") or dato_fra
        dato_til = dato_til and strptime(dato_til, "%Y%m%d") or dato_til
        self._populate_multivalued_attribute("rolle",
                                              key,
                                              {"person_id" : int(self.entity_id),
                                               "utvalg"    : int(utvalg),
                                               "dato_fra"  : dato_fra,
                                               "dato_til"  : dato_til,
                                               "utvalgsrolle" : utvalgsrolle,})
    # end populate_rolle



    def get_rolle(self):
        return self.list_rolle(self.entity_id)
    # end get_rolle



    def list_rolle(self, person_id):
        """
        List all rolle (role) records held by PERSON_ID.
        """

        return self.query("""
                          SELECT
                            r.person_id, r.utvalg,
                            r.dato_fra, r.dato_til,
                            r.utvalgsrolle,
                            u.code_str
                          FROM
                            %s r,  /* sap_rolle */
                            %s u   /* sap_utvalg */
                          WHERE
                            r.person_id = :person_id AND
                            u.code = r.utvalg
                          """ % (_SAP_ROLLE_SCHEMA,
                                 _SAP_UTVALG_SCHEMA),
                          {"person_id" : person_id})
    # end list_rolle
    


    def _write_rolle(self):
        """
        Perform an update of this person's rolle (role) records.
        """

        current_state = dict()
        for item in self.get_rolle():
            d = item._dict()
            key = self._make_rolle_key(d["utvalg"])
            current_state[key] = d
        # od

        pk_expression = """
                        person_id = :person_id AND
                        utvalg = :utvalg
                        """

        update_sql = """
                     UPDATE
                       %s
                     SET
                       dato_fra = :dato_fra,
                       dato_til = :dato_til,
                       utvalgsrolle = :utvalgsrolle
                     WHERE
                       %s
                     """ % (_SAP_ROLLE_SCHEMA, pk_expression)
        insert_sql = """
                     INSERT INTO
                       %s(person_id, utvalg, dato_fra, dato_til, utvalgsrolle)
                     VALUES
                       (:person_id, :utvalg, :dato_fra, :dato_til, :utvalgsrolle)
                     """ % _SAP_ROLLE_SCHEMA
        delete_sql = """
                     DELETE FROM
                       %s
                     WHERE
                       %s
                     """ % (_SAP_ROLLE_SCHEMA, pk_expression)

        return self._write_multivalued_attribute(current_state,
                                                 self.rolle,
                                                 update_sql,
                                                 insert_sql, delete_sql)
    # end _write_rolle



    def populate_permisjon(self, permisjonskode, permisjonsandel):
        """
        Adjoin a SAP permisjon (leave of absence) record.
        """

        self._populate_singlevalued_attribute("permisjonskode",
                                               int(permisjonskode))
        assert 0 <= int(permisjonsandel) <= 100, \
               "permisjonsandel must be a percentage (between 0 and 100)"
        
        self._populate_singlevalued_attribute("permisjonsandel",
                                               int(permisjonsandel))
    # end populate_permisjon



    def populate_sprak(self, sprakkode):
        """
        Adjoin a SAP språk (language) record.
        """

        self._populate_singlevalued_attribute("sprak", int(sprakkode))
    # end populate_sprak()



    def populate_forretningsomrade(self, fo_kode):
        """
        Adjoin a SAP forretningsområdekode record.
        """

        self._populate_singlevalued_attribute("fo_kode", int(fo_kode))
    # end 


    def _sap_record_exists(self):
        """
        This method checks whether SELF.ENTITY_ID has any entries in
        _SAP_PERSON_SCHEMA.

        This method exists for internal use only.
        """

        try:
            self.query_1("""
                        SELECT
                          '1'
                        FROM
                          %s
                        WHERE
                          person_id = :person_id
                       """ % _SAP_PERSON_SCHEMA,
                       { "person_id" : self.entity_id })
            return True
        except Errors.NotFoundError:
            return False
        # yrt
    # end _sap_record_exists



    def _write_singlevalued_attributes(self):
        """
        Synchronize all updated singlevalued attributes with the database
        """
        attr_to_db = { "fo_kode" : "fo_kode",
                       "sprak"   : "sprak",
                       "permisjonskode" : "permisjonskode",
                       "permisjonsandel" : "permisjonsandel" }

        sql_params = { "person_id" : self.entity_id }
        attr_list = list()
        for attr_name in self.__singlevalued_attr__:
            if attr_name in self.__updated:
                db_name = attr_to_db[attr_name]
                attr_list.append((attr_name, db_name))
                sql_params[db_name] = getattr(self, attr_name)
            # fi
        # od

        if not attr_list:
            return None
        # fi

        if self._sap_record_exists():
            update_values = string.join(map(lambda x: "%s=:%s" % (x[1], x[1]),
                                            attr_list),
                                        ",")
            self.execute("""
                         UPDATE
                           %s
                         SET
                           %s
                         WHERE
                           person_id = :person_id
                         """ % (_SAP_PERSON_SCHEMA, update_values),
                         sql_params)
        else:
            insert_attrs = map(lambda x: x[1], attr_list) + ["person_id"]
            insert_names = string.join(insert_attrs, ",")
            insert_values = string.join([(":"+x) for x in insert_attrs], ",")

            self.execute("""
                          INSERT INTO
                            %s ( %s )
                          VALUES
                            ( %s )
                          """ % (_SAP_PERSON_SCHEMA,
                                 insert_names, insert_values),
                          sql_params)
        # fi

        return True
    # end _write_singlevalued_attributes



    def _populate_singlevalued_attribute(self, name, value):
        """
        This method adds a new attribute NAME to a person object associated
        with SELF and ensures that there is at most one instance of that
        attribute.
        """

        if name not in PersonSAPMixin.__write_attr__:
            raise AttributeError, \
                  "Unknown attribute %s in %s" % (name, self.__class__.__name__)
        # fi

        if hasattr(self, name) and getattr(self, name) is not None:
            raise AttributeError, \
              "Duplicate '%s' attribute for person_id = %s" % (name,
                                                               self.entity_id)
        # fi

        setattr(self, name, value)
    # end _populate_singlevalued_attribute



    def _write_multivalued_attribute(self, old_state, new_state,
                                      update_sql, insert_sql, delete_sql):
        """
        This function performs a generic synchronization of one of the
        multivalued attributes (call it A) in SELF with Cerebrum.
        
        old_state represents Cerebrum's current information for this
        person's A. It is used destructively!

        new_state represents SAP's current information for this persons's A.

        After the update, Cerebrum should be an exact replica of the SAP's
        information (provided that SELF is populated from SAP :))

        FIXME: document {old,new}_state's structure

        The update is performed through the following stages:

        old_state = OS
        new_state = NS

        * For each item I in NS:
          - If I exists in OS and OS[I] == I, then skip I. Remove OS[I].
            This is an item that existed in Cerebrum and did not change.
            
          - If I exists in OS and OS[I] != I, update OS[I] with I. Remove
            OS[I].
            This is an item that existed in Cerebrum but changed in SAP.
          
          - If I does not exist in OS, insert new I into the database.

        * For each item J that is left in OS:
          - Remove J from the database, since this item does no longer exist
            in SAP.

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
            # We assume the SAP's values are to replace Cerebrum's
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
        # in SAP. It should be deleted.
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
    # end _write_multivalued_attribute



    def _populate_multivalued_attribute(self, attribute, key, value):
        """
        This method adds a new 'value' for ATTRIBUTE.

        The values are distinguished from each other by KEY.

        They are all stored in a dictionary called ATTRIBUTE.

        Each KEY must be unique.

        VALUE is assumed to be a dictionary.
        """

        if attribute not in PersonSAPMixin.__write_attr__:
            raise AttributeError, \
                  "Unknown attribute %s in %s" % (attribute,
                                                  self.__class__.__name__)
        # fi

        if not hasattr(self, attribute) or getattr(self, attribute) is None:
            setattr(self, attribute, dict())
        elif getattr(self, attribute).has_key(key):
            raise AttributeError, \
                  "Duplicate %s entry for (person_id, key) = (%s, %s)" % \
                  (attribute, self.entity_id, key)
        # fi

        getattr(self, attribute)[ key ] = value
    # end _populate_multivalued_attribute

# end class PersonSAPMixin





class OUSAPMixin(OU.OU):
    """
    This class provides a HiA-specific extension to the core OU class.
    """

    __write_attr__ = ("orgeh",
                      "fo_kode",)

    def clear(self):
        self.__super.clear()
        self.clear_class(OUSAPMixin)
        self.__updated = []
    # end clear



    def populate_SAP_id(self, orgeh, fo_kode):
        """
        Register an SAP id for the OU currently associated with SELF.
        """

        # FIXME is this the proper way?
        if not hasattr(self, "entity_id"):
            raise ValueError("Cannot register SAP ids for unknown Cerebrum ids")
        # fi

        if getattr(self, "orgeh") or getattr(self, "fo_kode"):
            raise ValueError("Duplicate orgeh/fo_kode entry for ou_id = %s"
                             % self.entity_id)
        # fi

        assert 0 <= int(fo_kode) <= 9999, \
               "Illegal SAP gsber/fo kode: %s" % fo_kode

        self.orgeh = int(orgeh)
        self.fo_kode = int(fo_kode)
    # end populate_sap_id



    def write_db(self):
        """
        Synchronize the object's content with the database.
        """

        # Let all superclasses synchronize
        ret = self.__super.write_db()

        # If there are no local updates, then we are done
        if not self.__updated:
            return ret
        # fi

        sql_parameters = {"ou_id"   : self.entity_id,
                          "orgeh"   : self.orgeh,
                          "fo_kode" : self.fo_kode,}

        try:
            old_sap_id = self.get_SAP_id()

            # No change in SAP id occured
            if old_sap_id == (self.orgeh, self.fo_kode):
                update_status = ret
            else:
                self.execute("""
                             UPDATE %s
                             SET
                               orgeh = :orgeh, fo_kode = :fo_kode
                             WHERE
                               ou_id = :ou_id
                             """ % _SAP_OU_SCHEMA,
                             sql_parameters)
                update_status = True
            # fi
        except Errors.NotFoundError:
            self.execute("""
                         INSERT INTO %s
                           (ou_id, orgeh, fo_kode)
                         VALUES
                           (:ou_id, :orgeh, :fo_kode)
                         """ % _SAP_OU_SCHEMA,
                         sql_parameters)
            update_status = True
        # yrt

        self.__updated = []
        return update_status
    # end write_db



    def get_SAP_id(self):
        """
        Return a SAP id belonging to self.ENTITY_ID (this is the inverse of
        find_by_SAP_id, in a certain sense)

        NB! The return value a tuple (orgeh, fo_kode) with two *ints* (when
        such an ID exists). If no SAP id can be found, an
        Errors.NotFoundError is thrown.

        NB! The returned value for fo_kode is the *internal* Cerebrum
        fo_kode value. It is *NOT* the value we see from SAP.
        """

        row = self.query_1("""
                           SELECT
                             orgeh, fo_kode
                           FROM
                             %s
                           WHERE
                             ou_id = :ou_id
                           """ % _SAP_OU_SCHEMA,
                               { "ou_id" : self.entity_id })
        return (int(row["orgeh"]), int(row["fo_kode"]))
    # end get_SAP_id
        


    def find_by_SAP_id(self, orgeh, fo_kode):
        """
        Locate an OU, given its SAP identification.
        """

        ou_id = self.query_1("""
                             SELECT
                               ou_id
                             FROM
                               %s
                             WHERE
                               orgeh = :orgeh AND fo_kode = :fo_kode
                             """ % _SAP_OU_SCHEMA,
                             {"orgeh"   : orgeh,
                              "fo_kode" : int(fo_kode)})
        self.find(ou_id)
    # end find_sap_id
# end class OUSAPMixin
        
# arch-tag: d8a4ad24-1982-472b-8da5-a0571c95adea
