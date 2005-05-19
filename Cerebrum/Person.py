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

"""

import cereconf
from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityAddress, EntityQuarantine, \
     EntityExternalId
from Cerebrum import Utils
from Cerebrum import Errors

class MissingOtherException(Exception): pass
class MissingSelfException(Exception): pass


class Person(EntityContactInfo, EntityExternalId, EntityAddress,
             EntityQuarantine, Entity):
    __read_attr__ = ('__in_db', '_affil_source', '__affil_data')
    __write_attr__ = ('birth_date', 'gender', 'description', 'deceased')

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        self.clear_class(Person)
        self.__updated = []

        # TODO: The following attributes are currently not in
        #       Person.__slots__, which means they will stop working
        #       once all Entity classes have been ported to use the
        #       mark_update metaclass.
        # Person names:
        self._pn_affect_source = None
        self._pn_affect_variants = None
        self._name_info = {}

    def delete(self):
        # Remove person from person_name, person_affiliation,
        # person_affiliation_source, person_info. Super will remove
        # the entity from the mix-in classes
        for r in self.get_all_names():
            self._delete_name(r['source_system'], r['name_variant'])
        for r in self.get_affiliations(include_deleted=True):
            self.nuke_affiliation(r['ou_id'], r['affiliation'],
                                  r['source_system'], r['status'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_info]
        WHERE person_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

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
            for type in self._pn_affect_variants:
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
        if self.__updated:
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
                self._db.log_change(self.entity_id, self.const.person_create, None)
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
                self._db.log_change(self.entity_id, self.const.person_update, None)
        else:
            is_new = None

        # Handle PersonAffiliations
        if hasattr(self, '_affil_source'):
            source = self._affil_source
            # db_affil is used to see if the exact affiliation exists
            # (or did exist earlier, and is marked as deleted)
            db_affil = {}
            # db_prim is used to see if a row with that primary key
            # exists.
	    db_prim = {}
            for row in self.get_affiliations(include_deleted = True):
                if source == row['source_system']:
                    idx = "%d:%d:%d" % (row['ou_id'], row['affiliation'], row['status'])
                    db_affil[idx] = row['deleted_date']
		    db_prim['%s:%s' % (row['ou_id'], row['affiliation'])] = idx
            pop_affil = self.__affil_data
            for prim in pop_affil.keys():
                idx = "%s:%d" % (prim, pop_affil[prim])
                if db_affil.has_key(idx):
                    # this affiliation, including status, exists in the
                    # database already, but we may have to resurrect it
                    # if it's deleted.
                    if db_affil[idx] is not None:
                        ou_id, affil, status = [int(x) for x in idx.split(":")]
                        self.add_affiliation(ou_id, affil, source, status)
                    del db_affil[idx]
                else:
                    # this may be a completely new affiliation, or just a
                    # change in status.
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.add_affiliation(ou_id, affil, source, status)
                    if is_new <> 1:
                        is_new = False
                    if db_prim.has_key(prim):
                        # it was only a change of status.  make sure
                        # the loop below won't delete the affiliation.
                        del db_affil[db_prim[prim]]
            # delete all the remaining affiliations.  some of them
            # are already marked as deleted.
            for idx in db_affil.keys():
                if db_affil[idx] is None:
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.delete_affiliation(ou_id, affil, source)
                    if is_new <> 1:
                        is_new = False

        # If affect_names has not been called, we don't care about
        # names
        if self._pn_affect_source is not None:
            updated_name = False
            for variant in self._pn_affect_variants:
                try:
                    if not self._compare_names(variant, self):
                        n = self._name_info.get(variant)
                        self._update_name(self._pn_affect_source, variant, self._name_info[variant])
                        is_new = False
                        updated_name = True
                except MissingOtherException:
                    if self._name_info.has_key(variant):
                        self._set_name(self._pn_affect_source, variant,
                                       self._name_info[variant])
                        if is_new <> 1:
                            is_new = False
                        updated_name = True
                except MissingSelfException:
                    self._delete_name(self._pn_affect_source, variant)
                    is_new = False
                    updated_name = True
            if updated_name:
                self._update_cached_names()
            # Clear affect_name() settings
            self._pn_affect_source = None
            self._pn_affect_variants = None
            self._name_info = {}

        del self.__in_db
        self.__in_db = True
        self.__updated = []
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
        self.__updated = []

    def find_persons_by_bdate(self, bdate):
        return self.query("""
        SELECT person_id FROM [:table schema=cerebrum name=person_info]
        WHERE to_date(birth_date, 'YYYY-MM-DD')=:bdate""", locals())


    def find_persons_by_name(self, name, case_sensitive=True):
        if case_sensitive:
            where = "name LIKE :name"
        else:
            name = name.lower()
            where = "LOWER(name) LIKE :name"
        return self.query("""
        SELECT DISTINCT person_id FROM [:table schema=cerebrum name=person_name]
        WHERE """ + where, locals())

    def find_by_export_id(self, export_id):
        person_id = self.query_1("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        WHERE export_id=:export_id""", locals())
        self.find(person_id)

    def _compare_names(self, type, other):
        """Returns True if names are equal.

        self must be a populated object."""

        try:
            tmp = other.get_name(self._pn_affect_source, type)
            if len(tmp) == 0:
                raise KeyError
        except:
            raise MissingOtherException 
        try:
            myname = self._name_info[type]
        except:
            raise MissingSelfException
#        if isinstance(myname, unicode):
#            return unicode(tmp, 'iso8859-1') == myname
        return tmp == myname

    def _set_name(self, source_system, variant, name):
        # Class-internal use only
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=person_name]
          (person_id, name_variant, source_system, name)
        VALUES (:p_id, :n_variant, :src, :name)""",
                     {'p_id': self.entity_id,
                      'n_variant': int(variant),
                      'src': int(source_system),
                      'name': name})
        self._db.log_change(self.entity_id, self.const.person_name_add, None,
                            change_params={'src': int(source_system),
                                           'name': name,
                                           'name_variant': int(variant)})

    def _delete_name(self, source, variant):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_name]
        WHERE
          person_id=:p_id AND
          source_system=:src AND
          name_variant=:n_variant""",
                     {'p_id': self.entity_id,
                      'src': int(source),
                      'n_variant': int(variant)})
        self._db.log_change(self.entity_id,
                            self.const.person_name_del, None,
                            change_params={'src': int(source),
                            'name_variant': int(variant)})

    def _update_name(self, source_system, variant, name):
        # Class-internal use only
        self.execute("""
        UPDATE [:table schema=cerebrum name=person_name]
        SET name=:name
        WHERE
          person_id=:p_id AND
          source_system=:src AND
          name_variant=:n_variant""",
                     {'name': name,
                      'p_id': self.entity_id,
                      'src': int(source_system),
                      'n_variant': int(variant)})
        self._db.log_change(self.entity_id, self.const.person_name_mod, None,
                            change_params={'src': int(source_system),
                                           'name': name,
                                           'name_variant': int(variant)})

    def _update_cached_names(self):
        """Update cache of person's names.

        The algorithm for constructing the cached name values looks
        for the first source system in cereconf.SYSTEM_LOOKUP_ORDER
        with enough data to construct a full name for the person.

        Once a full name has been established (either an actual
        registered full name or a source system in which both first
        and last name is registered), the search through the source
        systems continues until a first and last name pair matching
        the full name is found.

        If no such first and last name pair is found, split the full
        name to guess at those name variants.

        Persons with no first name _must_ be registered with an
        explicit first name of "": a single-word full name is not
        trusted.

        A ValueError is raised if no cacheworthy name variants are
        found for the person."""

        # The keys in this dict tells us which name variants should be
        # kept in the cache.  The corresponding values will be set as
        # we walk through the name data from the authoritative source
        # systems.
        cached_name = {
            'name_first': None,
            'name_last': None,
            'name_full': None
            }
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            source = getattr(self.const, ss)
            names = {}
            for ntype in cached_name.keys():
                try:
                    names[ntype] = self.get_name(source,
                                                 getattr(self.const, ntype))
                except Errors.NotFoundError:
                    continue
            if not names:
                # This source system had no name data on this person.
                continue
            gen_full = None
            if 'name_first' in names and 'name_last' in names:
                if names['name_first'] == '':
                    gen_full = names['name_last']
                else:
                    gen_full = names['name_first']+' '+names['name_last']
            if cached_name['name_full'] is None:
                if 'name_full' in names:
                    cached_name['name_full'] = names['name_full']
                elif gen_full:
                    cached_name['name_full'] = gen_full
                else:
                    # None of the source systems this far have
                    # presented us with enough data to form a full
                    # name.
                    continue
            # Here, we know that cached_name['name_full'] is set to
            # the person's proper full name; if gen_full is set, we
            # know the current source system has good values for first
            # and last name, too.
            if gen_full == cached_name['name_full']:
                cached_name['name_first'] = names['name_first']
                cached_name['name_last'] = names['name_last']
            if None not in cached_name.values():
                # All name variants in cached_name are present; we're
                # ready to start updating the database.
                break
        else:
            # Couldn't find proper data for caching of all name
            # variants.  If there is cacheable data for full name, our
            # last, best hope for getting cached first- and last names
            # is to chop the full name apart.
            if cached_name['name_full'] is not None:
                name_parts = cached_name['name_full'].split()
                if len(name_parts) >= 2:
                    last_name = name_parts.pop()
                    if 'name_last' not in cached_name:
                        cached_name['name_last'] = last_name
                    if 'name_first' not in cached_name:
                        cached_name['name_first'] = " ".join(name_parts)

        # TBD: When we're unable to find cacheable data, it would
        #      probably be more correct to update the cache (that is,
        #      remove any previously cached values, in the for loop
        #      below), before issuing a warning/raising an exception
        #      to signal that there is no cacheable name data for this
        #      person.
        #
        #      However, that behaviour would represent a bigger change
        #      from how the cache has worked until now; some persons
        #      would end up without any cached fullname, which could
        #      lead to other scripts breaking.
        #
        #      So, until we have the resources to do proper testing on
        #      such a more correct change, we'll live with this hack.
        if not [n for n in cached_name if cached_name[n] is not None]:
            # We have no cacheable name variants.
            raise ValueError, "No cacheable name for %d / %r" % (
                self.entity_id, self._name_info)
        sys_cache = self.const.system_cached
        for ntype, name in cached_name.items():
            name_type = getattr(self.const, ntype)
            try:
                old_name = self.get_name(sys_cache, name_type)
                if name is None:
                    self._delete_name(sys_cache, name_type)
                elif old_name != name:
                    self._update_name(sys_cache, name_type, name)
            except Errors.NotFoundError:
                if name is not None:
                    self._set_name(sys_cache, name_type, name)

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

    def get_all_names(self):
        # TBD: It may be a misdesign that we have this method.  Could
        # change get_name's args into optional keyword args to this
        # method for the same effect (like get_external_id).
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=person_name]
        WHERE person_id=:p_id""",
                            {'p_id': self.entity_id})

    def affect_names(self, source, *variants):
        self._pn_affect_source = source
        if variants is None:
            raise NotImplementedError
        self._pn_affect_variants = variants

    def populate_name(self, variant, name):
        if (not self._pn_affect_source or
            str(variant) not in ["%s" % v for v in self._pn_affect_variants]):
            raise ValueError, "Improper API usage, must call affect_names()"
        self._name_info[variant] = name

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
        idx = "%d:%d" % (ou_id, affiliation)
        self.__affil_data[idx] = int(status)

    def get_affiliations(self, include_deleted=False):
        return self.list_affiliations(self.entity_id,
                                      include_deleted = include_deleted)

    def list_affiliations(self, person_id=None, source_system=None,
                          affiliation=None, status=None, ou_id=None,
                          include_deleted=False, fetchall = True):
        where = []
        for t in ('person_id', 'affiliation', 'source_system', 'status', \
								'ou_id'):
            val = locals()[t]
            if val is not None:
                if isinstance(val, (list, tuple)):
                    where.append("%s IN (%s)" %
                                 (t, ", ".join(map(str, map(int, val)))))
                else:
                    where.append("%s = %d" % (t, val))
        if not include_deleted:
            where.append("(deleted_date IS NULL OR deleted_date > [:now])")
        where = " AND ".join(where)
        if where:
            where = "WHERE " + where

        return self.query("""
        SELECT person_id, ou_id, affiliation, source_system, status,
          deleted_date, create_date
        FROM [:table schema=cerebrum name=person_affiliation_source]
        %s""" % where, fetchall = fetchall)

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
            SELECT 'yes' AS yes
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
            self._db.log_change(self.entity_id,
                                self.const.person_aff_add, None)
        try:
            self.query_1("""
            SELECT 'yes' AS yes
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            self.execute("""
            UPDATE [:table schema=cerebrum name=person_affiliation_source]
            SET status=:status, last_date=[:now], deleted_date=NULL
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            self._db.log_change(self.entity_id,
                                self.const.person_aff_src_mod, None)
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation_source]
              (person_id, ou_id, affiliation, source_system, status)
            VALUES (:p_id, :ou_id, :affiliation, :source, :status)""",
                         binds)
            self._db.log_change(self.entity_id,
                                self.const.person_aff_src_add, None)

    def delete_affiliation(self, ou_id, affiliation, source):
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'p_id': self.entity_id,
                 }
        self.execute("""
        UPDATE [:table schema=cerebrum name=person_affiliation_source]
        SET deleted_date=[:now]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", binds)
        self._db.log_change(self.entity_id,
                            self.const.person_aff_src_del, None)
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
        self._db.log_change(self.entity_id,
                            self.const.person_aff_src_del, None)
        remaining_affiliations = self.query("""
        SELECT 'yes' AS yes
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
            self._db.log_change(self.entity_id,
                                self.const.person_aff_del, None)

    def get_accounts(self, filter_expired=True):
        acc = Utils.Factory.get('Account')(self._db)
        return acc.list_accounts_by_owner_id(self.entity_id,
                                             filter_expired=filter_expired)

    def get_primary_account(self):
        """Returns the account_id of SELF.entity_id's primary account"""
        acc = Utils.Factory.get("Account")(self._db)
        # get_account_types returns its results sorted
        accounts = acc.get_account_types(all_persons_types=True,
                                         owner_id=self.entity_id)
        if accounts:
            return accounts[0]["account_id"]
        else:
            return None

    def getdict_external_id2primary_account(self, id_type):
        """
        Returns a dictionary mapping all existing external ids of given
        ID_TYPE to the corresponding primary account.
        
        This is a *convenience* function. The very same thing can be
        accomplished with get_primary_account() + Account.find() and a
        suitable number of database lookups
        """

        result = dict()

        # NB! outer joins are not necessary here. Not displaying FNRs with
        # missing accounts is quite alright.
        for row in self.query("""
            SELECT
              DISTINCT eei.external_id, en.entity_name
            FROM
              [:table schema=cerebrum name=entity_external_id] eei,
              [:table schema=cerebrum name=account_type] at,
              [:table schema=cerebrum name=entity_name] en
            WHERE
              eei.id_type = :id_type AND
              eei.entity_type = [:get_constant name=entity_person] AND
              eei.entity_id = at.person_id AND
              at.priority = (SELECT
                               min(at2.priority)
                             FROM
                               [:table schema=cerebrum name=account_type] at2
                             WHERE
                               at2.person_id = eei.entity_id) AND
              at.account_id = en.entity_id
            """, {"id_type" : int(id_type)}):
            result[row["external_id"]] = row["entity_name"]
        # od

        return result
    # end getdict_external_id2primary_account


    def list_persons(self):
        """Return all persons' person_id and birth_date."""
        return self.query("""
        SELECT person_id, birth_date
        FROM [:table schema=cerebrum name=person_info]""")


    def list_persons_name(self, source_system=None, name_type=None):
        type_str = ""
        if name_type == None:
            type_str = "= %d" % int(self.const.name_full)
        elif isinstance(name_type, list):
            type_str = "IN (%d" % int(name_type[0])
            for tuple in name_type[1:]:
                type_str += ", %d" % int(tuple)
            type_str += ")"
        else:
            type_str = "= %d" % int(name_type)
        if source_system:
            type_str += " AND source_system = %d" % int(source_system)

        return self.query("""
        SELECT DISTINCT person_id, name_variant, name
        FROM [:table schema=cerebrum name=person_name]
        WHERE name_variant %s""" % type_str)


    def getdict_persons_names(self, source_system=None, name_types=None):
        if name_types is None:
            name_types = self.const.name_full
        if isinstance(name_types, (list, tuple)):
            selection = "IN (%s)" % ", ".join(map(str, map(int, name_types)))
        else:
            selection = "= %d" % int(name_types)
        if source_system is not None:
            selection += " AND source_system = %d" % int(source_system)
        result = {}
        for id, variant, name in self.query("""
        SELECT DISTINCT person_id, name_variant, name
        FROM [:table schema=cerebrum name=person_name]
        WHERE name_variant %s""" % selection):
            id   = int(id)
            info = result.get(id)
            if info is None:
                result[id] = {int(variant): name}
            else:
                info[int(variant)] = name
        return result


    def list_persons_atype_extid(self, spread=None, include_quarantines=False,idtype=None):
        """Multiple join to increase performance on LDAP-dump.

        TBD: Maybe this should be nuked in favor of pure dumps like
             list_persons."""
        efrom = ecols = ""
        if include_quarantines:
            efrom = """
            LEFT JOIN [:table schema=cerebrum name=entity_quarantine] eq
              ON at.account_id=eq.entity_id"""
            ecols = ", eq.quarantine_type"
        if spread is not None:
            efrom += """
            JOIN [:table schema=cerebrum name=entity_spread] es
              ON pi.person_id=es.entity_id AND es.spread=:spread"""
	if idtype:
	    efrom += """
	    JOIN [:table schema=cerebrum name=entity_external_id] eei
            ON pi.person_id = eei.entity_id AND eei.id_type=:idtype AND
               eei.entity_type = [:get_constant name=entity_person]"""
	else:
	    efrom += """
	    JOIN [:table schema=cerebrum name=entity_external_id] eei
            ON pi.person_id = eei.entity_id AND
               eei.entity_type = [:get_constant name=entity_person]""" 

        return self.query("""
        SELECT DISTINCT pi.person_id, pi.birth_date, at.account_id, eei.external_id,
          at.ou_id, at.affiliation %(ecols)s
	FROM
          [:table schema=cerebrum name=person_info] pi
          JOIN [:table schema=cerebrum name=account_type] at
            ON at.person_id = pi.person_id AND
               at.priority = (
                 SELECT MIN(priority)
                 FROM [:table schema=cerebrum name=account_type] at2
                 WHERE at2.person_id = pi.person_id)
	  %(efrom)s
          """ % locals(), {'spread': spread,'idtype': idtype}, fetchall=False)


    def search(self, spread=None, name=None, description=None,
               exclude_deceased=False):
        """Retrieves a list over Persons filtered by the given criterias.
        
        Returns a list of tuples with the info (person_id, name, description).
        If no criteria is given, all persons are returned. ``name`` and
        ``description`` should be strings if given. ``spread`` can be either
        string or int. Wildcards * and ? are expanded for "any chars" and
        "one char"."""

        def prepare_string(value):
            value = value.replace("*", "%")
            value = value.replace("?", "_")
            value = value.lower()
            return value

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=person_info] pi")
        tables.append("[:table schema=cerebrum name=person_name] pn")
        where.append("pi.person_id=pn.person_id")

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("pi.person_id=es.entity_id")
            where.append("es.entity_type=:entity_type")
            try:
                spread = int(spread)
            except (TypeError, ValueError):
                spread = prepare_string(spread)
                tables.append("[:table schema=cerebrum name=spread_code] sc")
                where.append("es.spread=sc.code")
                where.append("LOWER(sc.code_str) LIKE :spread")
            else:
                where.append("es.spread=:spread")

        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(pn.name) LIKE :name")

        if description is not None:
            description = prepare_string(description)
            where.append("LOWER(pi.description) LIKE :description")
        
        if exclude_deceased:
            where.append("pi.deceased LIKE F")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT pi.person_id AS person_id,
                pn.name AS name, pi.description AS description
        FROM %s %s""" % (','.join(tables), where_str),
            {'spread': spread, 'entity_type': int(self.const.entity_person),
             'name': name, 'description': description})

# arch-tag: 10f7dbc0-0edf-466d-ab33-ba0c84c5a2b3
