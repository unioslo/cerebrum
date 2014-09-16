# -*- coding: iso-8859-1 -*-
# Copyright 2002-2010 University of Oslo, Norway
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

"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""

import copy
import threading

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.Utils import Factory


class CodeValuePresentError(RuntimeError):

    """Error raised when an already existing code value is inserted."""
    pass

Database_class = Factory.get("Database")


class SynchronizedDatabase(Database_class):
    _db_proxy_lock = threading.RLock()

    def __init__(self, *args, **kwargs):
        super(SynchronizedDatabase, self).__init__(*args, **kwargs)

    def execute(self, operation, parameters=()):
        try:
            SynchronizedDatabase._db_proxy_lock.acquire()
            return super(SynchronizedDatabase, self).execute(operation, parameters)
        finally:
            SynchronizedDatabase._db_proxy_lock.release()

    # 2009-10-12 IVR This is a bit awkward.  A few of our daemons have a
    # constant object each (actually all of them do). The constant objects
    # have their own private DB connection (cf. get_sql() below). That db
    # connection exists parallel to the connection used by the code (legacy
    # issues. This should be reviewed once spine is gone).
    #
    # The problem with such a connection is that constants are used in a
    # read-only fashion. Futhermore a constants object never commits
    # explicitly, which in the end results in a transaction in the database
    # that has been started but has not (ever) been committed. The transaction
    # persists until the Constants object is deleted, which may be many weeks
    # apart for a daemon. That, in turn, stops vacuum analyze and the like
    # from deleting outdated rows.
    #
    # For now we force commit() for every query* operation. It is safe, since
    # the db connection is private. If we abandon this policy, the commits
    # must be yanked out (but then outstanding idle transactions won't be a
    # problem either).
    def query_1(self, query, params=()):
        try:
            SynchronizedDatabase._db_proxy_lock.acquire()
            return super(SynchronizedDatabase, self).query_1(query, params)
        finally:
            self.commit()
            SynchronizedDatabase._db_proxy_lock.release()

    def query(self, query, params=()):
        try:
            SynchronizedDatabase._db_proxy_lock.acquire()
            return super(SynchronizedDatabase, self).query(query, params)
        finally:
            self.commit()
            SynchronizedDatabase._db_proxy_lock.release()
    # end query
# end SynchronizedDatabase


class _CerebrumCode(DatabaseAccessor):

    """Abstract base class for accessing code tables in Cerebrum.

    The class needs a connection to the database (to enable constant
    insertion, deletion and such). However, such a connection should better be
    private, to avoid situations when it is inadvertently closed from
    outside. Hence the attribute _privata_db_proxy.

    Unfortunately, there may still be possibilities when such a private
    connection is exposed and closed. It does not happen often, but it is a
    possibility. To avoid subtle bugs, it has been decided to re-establish
    connection to the db, when it suddenly disappears. This is what the
    property sql is for. A new connection is created transparently. Client
    code (using constants) may simply assume that the connection always
    exists.
    """

    # multiple threads may share a constant object. All db_proxy manipulations
    # need to be protected.
    _db_proxy_lock = threading.Lock()
    _private_db_proxy = None

    def get_sql(self):
        try:
            _CerebrumCode._db_proxy_lock.acquire()
            try:
                _CerebrumCode._private_db_proxy.ping()
            except:
                _CerebrumCode._private_db_proxy = SynchronizedDatabase()
            return _CerebrumCode._private_db_proxy
        finally:
            _CerebrumCode._db_proxy_lock.release()

    def set_sql(self, db):
        try:
            _CerebrumCode._db_proxy_lock.acquire()
            try:
                db.ping()
                _CerebrumCode._private_db_proxy = db
            except:
                _CerebrumCode._private_db_proxy = SynchronizedDatabase()
        finally:
            _CerebrumCode._db_proxy_lock.release()
    sql = property(get_sql, set_sql, doc="private db connection")

    _lookup_table = None                # Abstract class.
    _lookup_code_column = 'code'
    _lookup_str_column = 'code_str'
    _lookup_desc_column = 'description'
    _code_sequence = '[:sequence schema=cerebrum name=code_seq op=next]'
    # How many of the arguments to the constructor are the key value?
    _key_size = 1

    # Should we postpone INSERTion of code value in this class until
    # some other code value class has been fully INSERTed (e.g. due to
    # foreign key constraint checks)?
    _insert_dependency = None

    # Turn constant objects into instance singletons: there can
    # only be one instance of a given state.
    #
    # The implementation is a bit tricky, since we need to avoid
    # lookup the integer code value of objects while initialising.

    def __new__(cls, *args, **kwargs):
        # Each instance is stored in the class variable _cache using
        # two keys: the integer value (code) and the string value
        # (code_str).  If the constructor key to the code table
        # contains more than value (_key_size > 1), a tuple of the
        # string values is used as key as well.
        #
        # The mapping from integer is delayed and filled in the first
        # time a constructor is called with an integer argument.  The
        # cache either contains all keys, or just the string (and
        # tuple) key.
        if cls.__dict__.get("_cache") is None:
            cls._cache = {}

        # If the key is composite and only one argument is given, it
        # _should_ be the code value as an integer of some sort, and
        # enter the else branch.
        if isinstance(args[0], (str, _CerebrumCode)):
            if cls._key_size > 1 and len(args) > 1:
                code = ()
                for i in range(cls._key_size):
                    if isinstance(args[i], int):
                        raise TypeError, "Arguments must be constants or str."
                    code += (str(args[i]), )
            else:
                code = str(args[0])
            if code in cls._cache:
                return cls._cache[code]
            new = DatabaseAccessor.__new__(cls)
            if cls._key_size > 1:
                # We must call __init__ explicitly to fetch code_str.
                # When __new__ is done, __init__ is called again by
                # Python.  Wasted effort, but not worth worrying
                # about.
                new.__init__(*args, **kwargs)
                cls._cache[str(new)] = new
        else:
            if cls._key_size > 1 and len(args) > 1:
                raise ValueError, ("When initialising a multi key constant, "
                                   "the first argument must be a CerebrumCode "
                                   "or string")
            # Handle PgNumeric and other integer-like types
            try:
                code = int(args[0])
            except ValueError:
                raise TypeError, "Argument 'code' must be int or str."
            if code in cls._cache:
                return cls._cache[code]

            # The cache may be incomplete, only containing code_str as
            # key.  So we make a new object based on the integer
            # value, and if it turns out the code was in the cache
            # after all, we throw away the new instance and use the
            # cached one instead.
            new = DatabaseAccessor.__new__(cls)
            new.__init__(*args, **kwargs)
            code_str = str(new)
            if code_str in cls._cache:
                cls._cache[code] = cls._cache[code_str]
                return cls._cache[code]
            cls._cache[code_str] = new

        cls._cache[code] = new
        return new

    # TBD: Should this take DatabaseAccessor args as well?  Maybe use
    # some kind of currying in Constants to avoid having to pass the
    # Database arg every time?
    def __init__(self, code, description=None, lang=None):
        # self may be an already initialised singleton.
        if isinstance(description, str):
            description = description.strip()
        self._desc = description
        if isinstance(code, str):
            # We can't initialise self.int here since the database is
            # unavailable while all the constants are defined, nor
            # would we want to, since we often never need the
            # information.
            if not hasattr(self, "int"):
                self.int = None
            self.str = code
        elif not hasattr(self, "int"):
            self.int = code
            self.str = self.sql.query_1("SELECT %s FROM %s WHERE %s=:code" %
                                        (self._lookup_str_column,
                                         self._lookup_table,
                                         self._lookup_code_column),
                                        {'code': code})
        self._lang = self._build_language_mappings(lang)
    # end __init__

    def _build_language_mappings(self, lang):
        "Build a dictionary holding this self's names in various languages."

        if not isinstance(lang, dict):
            return dict()

        # Now let's build the mapping. Ideally, we should check the strings
        # against existing language_code constants, but we simply cannot do this
        # from _CerebrumCode's ctor without introducing a circular dependency.
        return copy.deepcopy(lang)
    # end _build_language_mappings

    def lang(self, language):
        """Return self's name in the specified language.

        @type language: str, int or _LanguageCode instance.
        @param language:
          Language designation for which we are to retrieve the name.

        When no suitable name exists, return description (i.e. this method does
        not fail).
        """

        if language in self._lang:
            return self._lang[language]

        lang_kls = _LanguageCode
        key = None
        if isinstance(language, lang_kls):
            key = language.str
        elif isinstance(language, (long, int)):
            key = lang_kls(language).str
        elif isinstance(language, (str, unicode)):
            # Make sure that a string refers to a valid language code
            key = lang_kls(int(lang_kls(language))).str

        if key in self._lang:
            self._lang[language] = self._lang[key]
            return self._lang[language]

        # Hmm, do we want to cache the fact that 'language' does not exist as a
        # key? (so as to speed up subsequent 'misses'?)
        return self.description
    # end lang

    def __str__(self):
        return self.str

    def __repr__(self):
        int = ""
        if self.int is not None:
            int = " int=%d" % self.int
        return "<%(class)s instance code_str='%(str)s'%(int)s at %(id)s>" % {
            'class': self.__class__.__name__,
            'str': self.str,
            'int': int,
            'id': hex(id(self) & 2 ** 32 - 1)}  # Avoid FutureWarning in hex conversion

    def _get_description(self):
        if self._desc is None:
            self._desc = self.sql.query_1("SELECT %s FROM %s WHERE %s=:code" %
                                          (self._lookup_desc_column,
                                           self._lookup_table,
                                           self._lookup_code_column),
                                          {'code': int(self)})
        return self._desc
    description = property(_get_description, None, None,
                           "This code value's description.")

    def __int__(self):
        if not cereconf.CACHE_CONSTANTS:
            self.int = None

        if self.int is None:
            self.int = int(self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                            (self._lookup_code_column,
                                             self._lookup_table,
                                             self._lookup_str_column),
                                            self.__dict__))
        return self.int

    def __hash__(self):
        "Help method to be able to hash constants directly."
        return hash(self.__int__())

    def __eq__(self, other):
        if other is None:
            return False
        elif (
            # It should be OK to compare _CerebrumCode instances with
            # themselves or ints.
            isinstance(other, (int, _CerebrumCode))
            # The following test might catch a few more cases than we
            # really want to, e.g. comparison with floats.
            #
            # However, it appears to be the best alternative if we
            # want to support comparison with e.g. PgNumeric instances
            # without introducing a dependency on whatever database
            # driver module is being used.
                or hasattr(other, '__int__')):
            return self.__int__() == other.__int__()
        # This allows reflexive comparison (other.__eq__)
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal

    # Allow pickling of code values.
    def __getstate__(self):
        return int(self)

    def _pre_insert_check(self):
        try:
            # Attempt converting self into integer code value; this
            # should raise NotFoundError for not-yet-created code
            # values.
            code = int(self)
            # If conversion worked without raising NotFoundError, our
            # job has been done before.
            raise CodeValuePresentError, "Code value %r present." % self
        except Errors.NotFoundError:
            pass

    def _update_description(self, stats):
        if self._desc is None:
            return
        new_desc = self._desc
        # Force fetching the description from the database
        self._desc = None
        db_desc = self._get_description()
        if new_desc != db_desc:
            self._desc = new_desc
            stats['updated'] += 1
            stats['details'].append("Updated description for '%s': '%s'"
                                    % (self, new_desc))
            self.sql.execute("UPDATE %s SET %s=:desc WHERE %s=:code" %
                             (self._lookup_table, self._lookup_desc_column,
                              self._lookup_code_column),
                             {'desc': new_desc, 'code': self.int})

    def insert(self):
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, %(str_col)s, %(desc_col)s)
        VALUES
          (%(code_seq)s, :str, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'str': self.str,
             'desc': self._desc})

    def delete(self):
        """Delete itself, the constant, from db and cache."""
        if hasattr(self, '_cache'):
            if int(self) in self._cache:
                del self._cache[int(self)]
            if str(self) in self._cache:
                del self._cache[str(self)]
        self.sql.execute("""
        DELETE FROM %s
        WHERE %s=:code""" % (self._lookup_table, self._lookup_code_column),
                         {'code': int(self)})


class _LanguageCode(_CerebrumCode):

    "Language codes for Cerebrum."
    _lookup_table = '[:table schema=cerebrum name=language_code]'
    pass


class _EntityTypeCode(_CerebrumCode):

    "Mappings stored in the entity_type_code table"
    _lookup_table = '[:table schema=cerebrum name=entity_type_code]'
    pass


class _CerebrumCodeWithEntityType(_CerebrumCode):

    """Auxilliary class for code tables with an additional entity_type
    column.  Should not and can not be instantiated directly."""
    _insert_dependency = _EntityTypeCode

    def __init__(self, code, entity_type=None, description=None, lang=None):
        if entity_type is not None:
            if not isinstance(entity_type, _EntityTypeCode):
                entity_type = _EntityTypeCode(entity_type)
            self._entity_type = entity_type
        super(
            _CerebrumCodeWithEntityType,
            self).__init__(code,
                           description,
                           lang)

    def insert(self):
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (entity_type, %(code_col)s, %(str_col)s, %(desc_col)s)
        VALUES
          (:entity_type, %(code_seq)s, :str, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'entity_type': int(self.entity_type),
             'str': self.str,
             'desc': self._desc})

    def _get_entity_type(self):
        if not hasattr(self, '_entity_type'):
            self._entity_type = _EntityTypeCode(self.sql.query_1(
                """
                SELECT entity_type
                FROM %(table)s
                WHERE %(code_col)s = :code
                """ % {'table': self._lookup_table,
                       'code_col': self._lookup_code_column},
                {'code': int(self)}))
        return self._entity_type
    entity_type = property(_get_entity_type)


class _SpreadCode(_CerebrumCodeWithEntityType):

    """Code values for entity `spread`; table `entity_spread`."""
    _lookup_table = '[:table schema=cerebrum name=spread_code]'
    pass


class _ContactInfoCode(_CerebrumCode):

    "Mappings stored in the contact_info_code table"
    _lookup_table = '[:table schema=cerebrum name=contact_info_code]'
    pass


class _CountryCode(_CerebrumCode):

    """Interface to code values in the `country_code' table."""
    _lookup_table = '[:table schema=cerebrum name=country_code]'

    def __init__(self, code, country=None, phone_prefix=None,
                 description=None):
        if country is not None:
            self._country = country
            self._phone_prefix = phone_prefix
        super(_CountryCode, self).__init__(code, description)

    def insert(self):
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, %(str_col)s, country, phone_prefix, %(desc_col)s)
        VALUES
          (%(code_seq)s, :str, :country, :phone, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'str': self.str,
             'country': self._country,
             'phone': self._phone_prefix,
             'desc': self.description})

    def _fetch_column(self, col_name):
        attr_name = "_" + col_name
        if not hasattr(self, attr_name):
            self.__setattr__(attr_name, self.sql.query_1(
                """
                SELECT %(col_name)s
                FROM %(table)s
                WHERE %(code_col)s = :code
                """ % {'col_name': col_name,
                       'table': self._lookup_table,
                       'code_col': self._lookup_code_column},
                {'code': int(self)}))
        return getattr(self, attr_name)

    country = property(lambda (self): self._fetch_column("country"))
    phone_prefix = property(lambda (self): self._fetch_column("phone_prefix"))


class _AddressCode(_CerebrumCode):

    "Mappings stored in the address_code table"
    _lookup_table = '[:table schema=cerebrum name=address_code]'
    pass


class _GenderCode(_CerebrumCode):

    "Mappings stored in the gender_code table"
    _lookup_table = '[:table schema=cerebrum name=gender_code]'
    pass


class _EntityExternalIdCode(_CerebrumCodeWithEntityType):

    "Mappings stored in the entity_external_id_code table"
    _lookup_table = '[:table schema=cerebrum name=entity_external_id_code]'
    pass


class _PersonAffiliationCode(_CerebrumCode):

    "Mappings stored in the person_affiliation_code table"
    _lookup_table = '[:table schema=cerebrum name=person_affiliation_code]'
    pass


class _PersonAffStatusCode(_CerebrumCode):

    "Mappings stored in the person_aff_status_code table"
    # TODO: tror ikke dette er riktig?  I.E, pk=affiliation+status?
    _lookup_code_column = 'status'
    _lookup_str_column = 'status_str'
    _lookup_table = '[:table schema=cerebrum name=person_aff_status_code]'
    _insert_dependency = _PersonAffiliationCode
    _key_size = 2

    # The constructor accepts __init__(int) and
    # __init__(<one of str, int or _PersonAffiliationCode>, str [, str])
    def __init__(self, affiliation, status=None, description=None, lang=None):
        if status is None:
            try:
                code = int(affiliation)
            except ValueError:
                raise TypeError, ("Must pass integer when initialising " +
                                  "from code value")

            self.int = code
            (affiliation, status, description) = \
                self.sql.query_1("""
                         SELECT affiliation, %s, %s FROM %s
                         WHERE %s=:status""" % (self._lookup_str_column,
                                                self._lookup_desc_column,
                                                self._lookup_table,
                                                self._lookup_code_column),
                                 {'status': code})
        if isinstance(affiliation, _PersonAffiliationCode):
            self.affiliation = affiliation
        else:
            self.affiliation = _PersonAffiliationCode(affiliation)
        super(_PersonAffStatusCode, self).__init__(status, description, lang)

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("""
            SELECT %s FROM %s WHERE affiliation=:aff AND %s=:str""" %
                                            (self._lookup_code_column,
                                             self._lookup_table,
                                             self._lookup_str_column),
                                            {'str': self.str,
                                             'aff': int(self.affiliation)}))
        return self.int

    def __str__(self):
        return "%s/%s" % (self.affiliation, self.str)

    def _get_status(self):
        return self.str
    status_str = property(_get_status, None, None,
                          "The 'status_str' field of this code value.")

    def insert(self):
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (affiliation, %(code_col)s, %(str_col)s, %(desc_col)s)
        VALUES
          (:affiliation, %(code_seq)s, :str, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'affiliation': int(self.affiliation),
             'str': self.str,
             'desc': self._desc})


class _AuthoritativeSystemCode(_CerebrumCode):

    "Mappings stored in the authoritative_system_code table"
    _lookup_table = '[:table schema=cerebrum name=authoritative_system_code]'
    pass

class _OUPerspectiveCode(_CerebrumCode):

    "Mappings stored in the ou_perspective_code table"
    _lookup_table = '[:table schema=cerebrum name=ou_perspective_code]'
    pass


class _AccountCode(_CerebrumCode):

    "Mappings stored in the account_code table"
    _lookup_table = '[:table schema=cerebrum name=account_code]'
    pass


class _AccountHomeStatusCode(_CerebrumCode):

    "Mappings stored in the home_status_code table"
    _lookup_table = '[:table schema=cerebrum name=home_status_code]'
    pass


class _ValueDomainCode(_CerebrumCode):

    "Mappings stored in the value_domain_code table"
    _lookup_table = '[:table schema=cerebrum name=value_domain_code]'
    pass


class _EntityNameCode(_CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=entity_name_code]'
    pass


class _PersonNameCode(_CerebrumCode):

    "Mappings stored in the person_name_code table"
    _lookup_table = '[:table schema=cerebrum name=person_name_code]'
    pass


class _AuthenticationCode(_CerebrumCode):

    "Mappings stored in the value_domain_code table"
    _lookup_table = '[:table schema=cerebrum name=authentication_code]'
    pass


class _GroupMembershipOpCode(_CerebrumCode):

    "Mappings stored in the group_membership_op_code table"
    _lookup_table = '[:table schema=cerebrum name=group_membership_op_code]'
    pass


class _GroupVisibilityCode(_CerebrumCode):

    "Code values for groups' visibilities."
    _lookup_table = '[:table schema=cerebrum name=group_visibility_code]'


class _QuarantineCode(_CerebrumCode):

    "Mappings stored in quarantine_code table"
    _lookup_table = '[:table schema=cerebrum name=quarantine_code]'

    def __init__(self, code, description=None, duration=None):
        self.duration = duration
        super(_QuarantineCode, self).__init__(code, description)

    def insert(self):
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (duration, %(code_col)s, %(str_col)s, %(desc_col)s)
        VALUES
          (:duration, %(code_seq)s, :str, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'duration': self.duration,
             'str': self.str,
             'desc': self._desc})


class ConstantsBase(DatabaseAccessor):

    def __iterate_constants(self, const_type=None):
        """Iterate all of constants within this constants proxy object.

        This is a convenience method for internal usage.

        @type const_type: class or a sequence thereof
        @param const_type:
          Wanted constant types. This gives us a possibility to iterate, say,
          only EntityType constant objects.

        @rtype: generator
        @return:
          A generator yielding (in random order) constants of the specified
          type. If no type is specified, all constants will be yielded.
        """

        if const_type is None:
            const_type = _CerebrumCode

        for name in dir(self):
            attribute = getattr(self, name)
            if isinstance(attribute, const_type):
                yield attribute
    # end __iterate_constants

    def map_const(self, code):
        """Returns the Constant object as a reverse lookup on integer code.

        @param code:
          Constant's integer value.

        @rtype: _CerebrumCode instance or None.
        @return:
          A _CerebrumCode instance (i.e. a constant object) the integer code
          of which matches L{code}. If no match is found, return None.
        """

        for const_obj in self.__iterate_constants():
            if int(const_obj) == code:
                return const_obj
        return None
    # end map_const

    def initialize(self, update=True, delete=False):
        # {dependency1: {class: [object1, ...]},
        #  ...}
        order = {}
        for x in dir(self):
            attr = getattr(self, x)
            if isinstance(attr, _CerebrumCode):
                dep = attr._insert_dependency
                if not order.has_key(dep):
                    order[dep] = {}
                cls = type(attr)
                if not order[dep].has_key(cls):
                    order[dep][cls] = {}
                order[dep][cls][str(attr)] = attr
        if not order.has_key(None):
            raise ValueError, "All code values have circular dependencies."
        stats = {'total': 0, 'inserted': 0, 'updated': 0, 'details': []}
        if delete:
            stats['deleted'] = 0
        else:
            stats['superfluous'] = 0

        def insert(root, update, stats=stats):
            for cls in order[root].keys():
                cls_code_count = 0
                for code in order[root][cls].values():
                    stats['total'] += 1
                    cls_code_count += 1
                    try:
                        code._pre_insert_check()
                    except CodeValuePresentError:
                        if update:
                            code._update_description(stats)
                            continue
                        raise
                    code.insert()
                    stats['inserted'] += 1
                    stats['details'].append(
                        "Inserted code: %s ('%s')" %
                        (code, cls))
                rows = self._db.query(
                    """SELECT * FROM %s""" % cls._lookup_table)
                if cls_code_count != len(rows):
                    table_vals = [int(r[cls._lookup_code_column])
                                  for r in rows]
                    code_vals = [int(x) for x in order[root][cls].values()]
                    table_vals.sort()
                    code_vals.sort()
                    for c in table_vals:
                        if c not in code_vals:
                            if delete:
                                cls(c).delete()
                                stats['deleted'] += 1
                                stats['details'].append(
                                    "Deleted code: %s ('%s')" %
                                    (cls(c), cls))
                            else:
                                stats['superfluous'] += 1
                                stats['details'].append(
                                    "Superfluous code: %s ('%s')" %
                                    (cls(c), cls))
                del order[root][cls]
                if order.has_key(cls):
                    insert(cls, update)
            del order[root]

        insert(None, update)
        if order:
            raise ValueError, "Some code values have circular dependencies."
        return stats

    def __init__(self, database=None):
        # The database parameter is deprecated.
        # SH 2007-07-18 TDB: warn whenever this parameter is set.

        # initialize myself with the CerebrumCode db.connection
        # This makes Constants.commit() and such possible.

        super(ConstantsBase, self).__init__(_CerebrumCode.sql.fget(None))

    def fetch_constants(self, wanted_class, prefix_match=""):
        """Return all constant instances of wanted_class.  The list is
        sorted by the name of the constants.  If prefix_match is set,
        only return constants whose string representation starts with
        the given substring."""

        clist = list()
        for const_obj in self.__iterate_constants(wanted_class):
            if str(const_obj).startswith(prefix_match):
                clist.append(const_obj)

        return clist
    # end fetch_constants

    def human2constant(self, human_repr, const_type=None):
        """Map human representation of a const to _CerebrumCode.

        This method maps a human representation of a constant to the proper
        constant object (an instance of _CerebrumCode).

        The following human representations are supported:

          - A number, in which case it is interpreted as the int value of the
            constant object.
          - A string containing digits only (see above).
          - A string containing the attribute that is a member of self. This
            corresponds to referring to a constant by its symbolic name as
            defined in a suitable Constants.py.
          - A string containing the code_str. This corresponds to referring to
            a constant by its code_str.

        Beware! code_strs are NOT unique. If multiple constants match, it is
        undefined which constant object is returned! The only way to ensure
        sensible answer is to specify the specific constant type.

        @type const_type:
          One of the _CerebrumCode's subclasses or a sequence thereof.
        @param const_type:
          Permissible constant types.

        @rtype: an object that is a (sub)type of _CerebrumCode.
        @return:
          Suitable constant object, or None, if no object is found.
        """

        obj = None
        if isinstance(human_repr, int):
            obj = self.map_const(human_repr)
        elif isinstance(human_repr, str):

            # assume it's a textual representation of the code int...
            if human_repr.isdigit():
                obj = self.map_const(int(human_repr))

            # ok, that failed, so assume this is a constant name ...
            if obj is None and hasattr(self, human_repr):
                obj = getattr(self, human_repr)

            # ok, that failed too, we can only compare stringified version of
            # all proper constants with the parameter...
            if obj is None:
                for const_obj in self.__iterate_constants(const_type):
                    if str(const_obj) == human_repr:
                        obj = const_obj

        # Make sure it's of the right type...
        if obj is not None and const_type is not None:
            if not isinstance(obj, const_type):
                obj = None

        return obj
    # end human2constant
# end ConstantsBase


class CoreConstants(ConstantsBase):

    entity_person = _EntityTypeCode(
        'person',
        'Person - see table "cerebrum.person_info" and friends.')
    entity_ou = _EntityTypeCode(
        'ou',
        'Organizational Unit - see table "cerebrum.ou_info" and friends.')
    entity_account = _EntityTypeCode(
        'account',
        'User Account - see table "cerebrum.account_info" and friends.')
    entity_group = _EntityTypeCode(
        'group',
        'Group - see table "cerebrum.group_info" and friends.')
    entity_host = _EntityTypeCode('host', 'see table host_info')
    entity_disk = _EntityTypeCode('disk', 'see table disk_info')

    group_namespace = _ValueDomainCode(
        cereconf.ENTITY_TYPE_NAMESPACE['group'],
        'Default domain for group names')
    account_namespace = _ValueDomainCode(
        cereconf.ENTITY_TYPE_NAMESPACE['account'],
        'Default domain for account names')
    host_namespace = _ValueDomainCode(
        cereconf.ENTITY_TYPE_NAMESPACE['host'],
        'Default domain for host names')

    group_memberop_union = _GroupMembershipOpCode('union', 'Union')
    group_memberop_intersection = _GroupMembershipOpCode(
        'intersection', 'Intersection')
    group_memberop_difference = _GroupMembershipOpCode(
        'difference', 'Difference')

    language_nb = _LanguageCode("nb", "Bokmål")
    language_nn = _LanguageCode("nn", "Nynorsk")
    language_en = _LanguageCode("en", "English")
    language_de = _LanguageCode("de", "Deutsch")
    language_it = _LanguageCode("it", "Italiano")
    language_nl = _LanguageCode("nl", "Nederlands")
    language_sv = _LanguageCode("sv", "Svenska")
    language_sv = _LanguageCode("fr", "Français")
    language_ru = _LanguageCode("ru", "Russian")

    system_cached = _AuthoritativeSystemCode(
        'Cached',
        'Internally cached data',
        {"nb": "Internt cachede data",
         "en": "Internally cached data", })


class CommonConstants(ConstantsBase):

    quarantine_auto_no_aff = _QuarantineCode(
        'auto_no_aff', 'Ikke tilknyttet person, utestengt')
    auth_type_md5_crypt = _AuthenticationCode(
        'MD5-crypt',
        "MD5-derived password hash as implemented by crypt(3) on some Unix"
        " variants passed a `salt` that starts with '$1$'.  See <URL:http:"
        "//www.users.zetnet.co.uk/hopwood/crypto/scan/algs/md5crypt.txt>.")
    auth_type_sha256_crypt = _AuthenticationCode(
        'SHA-256-crypt',
        "SHA-256 derived password as implemented by crypt(3) in the GNU C library"
        " http://www.akkadia.org/drepper/SHA-crypt.txt")
    auth_type_sha512_crypt = _AuthenticationCode(
        'SHA-512-crypt',
        "SHA-512 derived password as implemented by crypt(3) in the GNU C library"
        " http://www.akkadia.org/drepper/SHA-crypt.txt")
    auth_type_crypt3_des = _AuthenticationCode(
        'crypt3-DES',
        "Password hash generated with the 'traditional' Unix crypt(3)"
        " algorithm, based on DES.  See <URL:http://www.users.zetnet.co.uk"
        "/hopwood/crypto/scan/ph.html#Traditional-crypt3>.")
    auth_type_pgp_crypt = _AuthenticationCode(
        'PGP-crypt',
        "PGP-encrypt the password so that we later can get at the plaintext "
        "password if we want to populate new backends.  The secret key "
        "should be stored offline.")
    auth_type_md4_nt = _AuthenticationCode(
        'MD4-NT',
        "MD4-derived password hash with Microsoft-added security.  "
        "Requires the smbpasswd module to be installed.")
    auth_type_ha1_md5 = _AuthenticationCode(
        'HA1-MD5',
        "Used in digest access authentication as specified in RFC 2617. "
        "Is an unsalted MD5 digest hash over 'username:realm:password'. "
        "See <http://tools.ietf.org/html/rfc2617#section-3.2.2.2>")
    auth_type_plaintext = _AuthenticationCode(
        'plaintext',
        "Plaintext passwords. Usefull for installations where non-encrypted "
        "passwords need to be used and exported. Use with care!")
    auth_type_ssha = _AuthenticationCode(
        'SSHA',
        "A salted SHA1-encrypted password. More info in RFC 2307 and at "
        "<URL:http://www.openldap.org/faq/data/cache/347.html>")
    auth_type_md5_unsalt = _AuthenticationCode(
        'md5-unsalted',
        "Unsalted MD5-crypt. Use with care!")

    contact_phone = _ContactInfoCode('PHONE', 'Phone')
    contact_phone_private = _ContactInfoCode('PRIVPHONE',
                                             "Person's private phone number")
    contact_fax = _ContactInfoCode('FAX', 'Fax')
    contact_email = _ContactInfoCode('EMAIL', 'Email')
    contact_url = _ContactInfoCode('URL', 'URL')
    contact_mobile_phone = _ContactInfoCode('MOBILE', 'Mobile phone')
    contact_private_mobile = _ContactInfoCode(
        'PRIVATEMOBILE', 'Private mobile phone')

    address_post = _AddressCode('POST', 'Post address')
    address_post_private = _AddressCode('PRIVPOST',
                                        "Person's private post address")
    address_street = _AddressCode('STREET', 'Street address')

    gender_male = _GenderCode('M', 'Male')
    gender_female = _GenderCode('F', 'Female')
    gender_unknown = _GenderCode('X', 'Unknown gender')

    group_visibility_all = _GroupVisibilityCode('A', 'All')
    group_visibility_none = _GroupVisibilityCode('N', 'None')
    group_visibility_internal = _GroupVisibilityCode('I', 'Internal')

    name_first = _PersonNameCode('FIRST', 'First name')
    name_last = _PersonNameCode('LAST', 'Last name')
    name_full = _PersonNameCode('FULL', 'Full name')

    name_personal_title = _PersonNameCode(
        'PERSONALTITLE', 'Persons personal title',
        {"nb": "Personlig tittel",
         "en": "Personal title", },)
    name_work_title = _PersonNameCode('WORKTITLE', 'Persons work title',
                                      {"nb": "Arbeidstittel",
                                       "en": "Work title", },)

    personal_title = _EntityNameCode(
        'PERSONALTITLE', "Person's personal title",
        {"nb": "Personlig tittel",
         "en": "Personal title", },)
    work_title = _EntityNameCode('WORKTITLE', "Person's work title",
                                 {"nb": "Arbeidstittel",
                                  "en": "Work title", },)

    ou_name = _EntityNameCode("OU name", "OU name",
                              {"nb": "Stedsnavn",
                               "en": "OU name", })
    ou_name_acronym = _EntityNameCode("OU acronym", "OU acronym",
                                      {"nb": "Akronym",
                                       "en": "Acronym", })
    ou_name_short = _EntityNameCode("OU short", "OU short name",
                                    {"nb": "Kortnavn",
                                     "en": "Short name", })
    ou_name_long = _EntityNameCode("OU long", "OU long name",
                                   {"nb": "Navn",
                                    "en": "Full name", })
    ou_name_display = _EntityNameCode("OU display", "OU display name",
                                      {"nb": "Fremvisningsnavn",
                                       "en": "Display name", })

    system_manual = _AuthoritativeSystemCode('Manual', 'Manual registration')

    # bootstrap_account is of this type:
    account_program = _AccountCode('programvare', 'Programvarekonto')
    home_status_not_created = _AccountHomeStatusCode(
        'not_created', 'Not created')
    home_status_create_failed = _AccountHomeStatusCode(
        'create_failed', 'Creation failed')
    home_status_on_disk = _AccountHomeStatusCode(
        'on_disk', 'Currently on disk')
    home_status_archived = _AccountHomeStatusCode(
        'archived', 'Has been archived')
    home_status_pending_restore = _AccountHomeStatusCode(
        'pending_restore', 'Pending restore')


class Constants(CoreConstants, CommonConstants):

    CerebrumCode = _CerebrumCode
    EntityType = _EntityTypeCode
    Spread = _SpreadCode
    ContactInfo = _ContactInfoCode
    Country = _CountryCode
    Address = _AddressCode
    Gender = _GenderCode
    EntityExternalId = _EntityExternalIdCode
    PersonName = _PersonNameCode
    PersonAffiliation = _PersonAffiliationCode
    PersonAffStatus = _PersonAffStatusCode
    AuthoritativeSystem = _AuthoritativeSystemCode
    OUPerspective = _OUPerspectiveCode
    Account = _AccountCode
    AccountHomeStatus = _AccountHomeStatusCode
    ValueDomain = _ValueDomainCode
    Authentication = _AuthenticationCode
    GroupMembershipOp = _GroupMembershipOpCode
    GroupVisibility = _GroupVisibilityCode
    Quarantine = _QuarantineCode
    LanguageCode = _LanguageCode
    EntityNameCode = _EntityNameCode

class ExampleConstants(Constants):

    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    affiliation_employee = _PersonAffiliationCode('EMPLOYEE', 'Employed')
    affiliation_status_employee_valid = _PersonAffStatusCode(
        affiliation_employee, 'VALID', 'Valid')

    affiliation_student = _PersonAffiliationCode('STUDENT', 'Student')
    affiliation_status_student_valid = _PersonAffStatusCode(
        affiliation_student, 'VALID', 'Valid')


def main():
    from Cerebrum.Utils import Factory
    from Cerebrum import Errors

    Cerebrum = Factory.get('Database')()
    co = Constants(Cerebrum)

    skip = dir(Cerebrum)
    skip.append('map_const')
    for x in filter(lambda x: x[0] != '_' and not x in skip, dir(co)):
        try:
            print "co.%s: %s = %d" % (x, getattr(co, x), getattr(co, x))
        except Errors.NotFoundError:
            print "NOT FOUND: co.%s" % x
    print "Map '7' back to str: %s" % co.map_const(7)

if __name__ == '__main__':
    main()

# arch-tag: 187248cd-c3e9-4817-b93e-e6da2a4a53e8
