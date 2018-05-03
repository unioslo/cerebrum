#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2018 University of Oslo, Norway
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
import re

import cereconf
from six import (string_types as string,  # standard Python module?!?
                 text_type as text,
                 python_2_unicode_compatible)
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import context


def _uchlp(arg):
    """'Anything' to text (unicode)"""
    if isinstance(arg, text):
        return arg
    if isinstance(arg, bytes):
        try:
            return arg.decode('UTF-8')
        except UnicodeDecodeError:
            return arg.decode('latin-1')
    if isinstance(arg, _CerebrumCode):
        return text(arg)
    raise TypeError('Arguments must be constants or strings')


class CodeValuePresentError(RuntimeError):
    """Error raised when an already existing code value is inserted."""
    pass

Database_class = Factory.get("DBDriver")  # Don't need changelog and stuff


class SynchronizedDatabase(Database_class):
    _db_proxy_lock = threading.RLock()

    def __init__(self, *args, **kwargs):
        super(SynchronizedDatabase, self).__init__(*args, **kwargs)

    def execute(self, operation, parameters=()):
        try:
            SynchronizedDatabase._db_proxy_lock.acquire()
            return super(SynchronizedDatabase, self).execute(operation,
                                                             parameters)
        finally:
            SynchronizedDatabase._db_proxy_lock.release()

    # 2009-10-12 IVR This is a bit awkward.  A few of our daemons have a
    # constant object each (actually all of them do). The constant objects
    # have their own private DB connection (cf. sql() below). That db
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


@python_2_unicode_compatible
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

    @property
    def sql(self):
        """Private db connection"""
        with _CerebrumCode._db_proxy_lock:
            try:
                _CerebrumCode._private_db_proxy.ping()
            except:
                _CerebrumCode._private_db_proxy = SynchronizedDatabase()
            return _CerebrumCode._private_db_proxy

    @sql.setter
    def sql(self, db):
        with _CerebrumCode._db_proxy_lock:
            try:
                db.ping()
                _CerebrumCode._private_db_proxy = db
            except:
                _CerebrumCode._private_db_proxy = SynchronizedDatabase()

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
        if isinstance(args[0], (string, _CerebrumCode)):
            if cls._key_size > 1 and len(args) > 1:
                code = tuple(map(_uchlp, args[:cls._key_size]))
            else:
                code = _uchlp(args[0])
            if code in cls._cache:
                return cls._cache[code]
            new = DatabaseAccessor.__new__(cls)
            if cls._key_size > 1:
                # We must call __init__ explicitly to fetch code_str.
                # When __new__ is done, __init__ is called again by
                # Python.  Wasted effort, but not worth worrying
                # about.
                new.__init__(*args, **kwargs)
                cls._cache[text(new)] = new
        else:
            if cls._key_size > 1 and len(args) > 1:
                raise ValueError("When initialising a multi key constant, "
                                 "the first argument must be a CerebrumCode "
                                 "or string")
            # Handle PgNumeric and other integer-like types
            try:
                code = int(args[0])
            except ValueError:
                raise TypeError("Argument 'code' must be int or string.")
            if code in cls._cache:
                return cls._cache[code]

            # The cache may be incomplete, only containing code_str as
            # key.  So we make a new object based on the integer
            # value, and if it turns out the code was in the cache
            # after all, we throw away the new instance and use the
            # cached one instead.
            new = DatabaseAccessor.__new__(cls)
            new.__init__(*args, **kwargs)
            code_str = text(new)
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
        if isinstance(description, string):
            description = description.strip()

        # Let's try to keep the value unicode internally
        if isinstance(description, bytes):
            # Try to decode as utf-8, latin-1
            try:
                description = description.decode('utf-8')
            except UnicodeDecodeError:
                description = description.decode('latin-1')

        self._desc = description

        if isinstance(code, string):
            # We can't initialise self.int here since the database is
            # unavailable while all the constants are defined, nor
            # would we want to, since we often never need the
            # information.
            if not hasattr(self, "int"):
                self.int = None
            self.str = code
        elif not hasattr(self, "int"):
            self.int = code
            try:
                self.str = self.sql.query_1(
                    "SELECT %s FROM %s WHERE %s=:code" %
                    (self._lookup_str_column,
                     self._lookup_table,
                     self._lookup_code_column),
                    {'code': code})
            except Errors.NotFoundError:
                raise Errors.NotFoundError('Constant %r' % self)
        if hasattr(self, 'str') and isinstance(self.str, bytes):
            try:
                self.str = self.str.decode('UTF-8')
            except UnicodeDecodeError:
                self.str = self.str.decode('latin-1')
        self._lang = self._build_language_mappings(lang)

    @property
    def _desc(self):
        """ the internal cached description value. """
        try:
            value = self.__desc
        except AttributeError:
            value = None

        if value is None or isinstance(value, text):
            return value
        raise AttributeError("no valid _desc set")

    @_desc.setter
    def _desc(self, value):
        if value is None or isinstance(value, text):
            self.__desc = value
        else:
            raise ValueError("_desc must be unicode or None")

    def _build_language_mappings(self, lang):
        "Build a dictionary holding this self's names in various languages."

        if not isinstance(lang, dict):
            return dict()

        # Now let's build the mapping. Ideally, we should check the strings
        # against existing language_code constants, but we simply cannot do
        # this from _CerebrumCode's ctor without introducing a circular
        # dependency.
        return copy.deepcopy(lang)

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
        elif isinstance(language, string):
            # Make sure that a string refers to a valid language code
            key = lang_kls(int(lang_kls(language))).str

        if key in self._lang:
            self._lang[language] = self._lang[key]
            return self._lang[language]

        # Hmm, do we want to cache the fact that 'language' does not exist as a
        # key? (so as to speed up subsequent 'misses'?)
        return self.description

    def __str__(self):
        return self.str

    def __repr__(self):
        return "<{class} instance{str}{int} at {id}>".format(**{
            'class': self.__class__.__name__,
            'str': ("" if getattr(self, 'str', None) is None
                    else " code_str=" + self.str.encode('UTF-8')),
            'int': ("" if getattr(self, 'int', None) is None
                    else " code=" + str(self.int)),
            'id': hex(id(self) & 2 ** 32 - 1)})

    @property
    def description(self):
        """ This code value's description. """
        if self._desc is None:
            desc = self.sql.query_1(
                """
                SELECT {0._lookup_desc_column}
                FROM {0._lookup_table}
                WHERE {0._lookup_code_column}=:code
                """.format(self),
                {'code': int(self)})

            # Decode and cache
            if isinstance(desc, bytes):
                try:
                    self._desc = desc.decode(self.sql.encoding)
                except Exception:
                    # UnicodeDecodeError, or TypeError (desc is None)
                    self._desc = None
            else:
                self._desc = desc

        return self._desc

    def __int__(self):
        if not cereconf.CACHE_CONSTANTS:
            self.int = None

        if self.int is None:
            try:
                self.int = int(
                    self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                     (self._lookup_code_column,
                                      self._lookup_table,
                                      self._lookup_str_column),
                                     {'str': self.str}))
            except Errors.NotFoundError:
                raise Errors.NotFoundError('Constant %r' % self)
        return self.int

    def __hash__(self):
        "Help method to be able to hash constants directly."
        return hash(self.__int__())

    def __eq__(self, other):
        if other is None:
            return False

        # It should be OK to compare _CerebrumCode instances with
        # themselves or ints.

        # The other.__int__ test might catch a few more cases than we
        # really want to, e.g. comparison with floats.
        #
        # However, it appears to be the best alternative if we
        # want to support comparison with e.g. PgNumeric instances
        # without introducing a dependency on whatever database
        # driver module is being used.
        elif (isinstance(other, (int, _CerebrumCode)) or
              hasattr(other, '__int__')):
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
        """State for pickle"""
        return int(self)

    def __setstate__(self, state):
        """Called from pickle.load(s)"""
        try:
            self.__init__(state)
        except Errors.NotFoundError:
            # Trying to unpickle a deleted code should not be an error
            self.str = None
            pass

    def _pre_insert_check(self):
        try:
            # Attempt converting self into integer code value; this
            # should raise NotFoundError for not-yet-created code
            # values.
            int(self)
            # If conversion worked without raising NotFoundError, our
            # job has been done before.
            raise CodeValuePresentError("Code value %r present." % self)
        except Errors.NotFoundError:
            pass

    def update(self):
        """
        Main method for updating constants in Cerebrum database, used for
        calling the necessary internal update methods. Can be overridden by
        some types of subclasses that have specific needs.

        :returns: a list of strings that contains details of updates that were
                  made, or None if no updates occured.
        :rtype: list or None
        """
        return self._update_description()

    def _update_description(self):
        """
        Updates the description for the given constant in Cerebrum database.

        :returns: a list with a string containing details about the update
                  if an update was made, otherwise None.
        :rtype: list or None
        """
        if self._desc is None:
            return
        new_desc = self._desc
        # Force fetching the description from the database
        self._desc = None
        db_desc = self.description
        if new_desc != db_desc:
            self._desc = new_desc
            self.sql.execute(
                """
                UPDATE {0._lookup_table}
                SET {0._lookup_desc_column}=:desc
                WHERE {0._lookup_code_column}=:code
                """.format(self),
                {'desc': new_desc,
                 'code': self.int})
            return ["Updated description for '{0}': "
                    "{1}".format(str(self), repr(new_desc))]

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

    @property
    def country(self):
        return self._fetch_column("country")

    @property
    def phone_prefix(self):
        return self._fetch_column("phone_prefix")


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


@python_2_unicode_compatible
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
                raise TypeError('Must pass integer when initialising '
                                'from code value')

            self.int = code
            try:
                (affiliation, status, description) = self.sql.query_1(
                    """ SELECT affiliation, %s, %s FROM %s
                    WHERE %s=:status""" % (
                        self._lookup_str_column,
                        self._lookup_desc_column,
                        self._lookup_table,
                        self._lookup_code_column),
                    {'status': code})
            except Errors.NotFoundError:
                raise Errors.NotFoundError('Constant %r' % self)
        if isinstance(affiliation, _PersonAffiliationCode):
            self.affiliation = affiliation
        else:
            self.affiliation = _PersonAffiliationCode(affiliation)
        super(_PersonAffStatusCode, self).__init__(status, description, lang)

    def __repr__(self):
        return "<%(class)s instance%(aff)s%(str)s%(int)s at %(id)s>" % {
            'class': self.__class__.__name__,
            'str': ("" if getattr(self, 'str', None) is None
                    else " code_str=%r" % self.str),
            'int': ("" if getattr(self, 'int', None) is None
                    else " code=%d" % self.int),
            'aff': ("" if getattr(self, 'affiliation', None) is None
                    else " affiliation=%r" % self.affiliation),
            'id': hex(id(self) & 2 ** 32 - 1)}

    def __int__(self):
        if self.int is None:
            try:
                self.int = int(
                    self.sql.query_1(
                        """SELECT %s FROM %s
                        WHERE affiliation=:aff AND %s=:str""" % (
                            self._lookup_code_column,
                            self._lookup_table,
                            self._lookup_str_column),
                        {'str': self.str,
                         'aff': int(self.affiliation)}))
            except Errors.NotFoundError:
                raise Errors.NotFoundError('Constant %r' % self)
        return self.int

    def __str__(self):
        return u"{}/{}".format(self.affiliation, self.str)

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


@python_2_unicode_compatible
class _ChangeTypeCode(_CerebrumCode):
    _lookup_code_column = 'change_type_id'
    # _lookup_str_column = 'status_str'
    _lookup_table = '[:table schema=cerebrum name=change_type]'
    # _insert_dependency = _PersonAffiliationCode
    _lookup_desc_column = 'msg_string'
    _key_size = 2

    """Identifies the type of change in the change-log.  category +
    type identifies the type of change.  The split is done to emulate
    the behaviour of the two-parts bofh commands.

    msg_string is a string that can be used to format a textly
    representation of the change (typically for showing a user).  It
    may contain %%(subject)s and %%(dest)s where the names of these
    entities should be inserted.

    format may contain information about how information from
    change_params should be displayed.  It contains a tuple of strings
    that may contain %%(type:key)s, which will result in key being
    formatted as type.
    """
    # TODO: the formatting is currently done by bofhd_uio_cmds.py.  It
    # would make more sense to do it here, but then we need some
    # helper classes for efficient conversion from entity_id to names
    # etc.

    # The constructor accepts the numeric code value, or a pair
    # of strings (category, type) identifying the constant code.
    def __init__(self, category, type=None, msg_string=None, format=None):
        if type is None:
            # Not the category, but the numeric code value
            try:
                # Handle PgNumeric etc.
                self.int = int(category)
            except ValueError:
                raise TypeError("Must pass integer when initialising "
                                "from code value")
            try:
                self.category, self.type = self.sql.query_1(
                    """SELECT category, type
                    FROM %s
                    WHERE %s = :code""" % (self._lookup_table,
                                           self._lookup_code_column),
                    {'code': self.int})
            except Errors.NotFoundError:
                raise Errors.NotFoundError('Constant %r' % self)
        else:
            self.category = category
            self.type = type
            if not hasattr(self, "int"):
                self.int = None

        # The code object may have been initialised explicitly
        # already.  If we initialise the object based on code value
        # alone, don't nuke those extra attributes.
        if not hasattr(self, "msg_string") or msg_string is not None:
            self.msg_string = msg_string
        if not hasattr(self, "format") or format is not None:
            self.format = format
        super(_ChangeTypeCode, self).__init__(category, type)

    def __repr__(self):
        return "<%(class)s instance%(cat)s%(type)s%(str)s%(int)s at %(id)s>" % {
            'class': self.__class__.__name__,
            'str': ("" if getattr(self, 'str', None) is None
                    else " code_str=%r" % self.str),
            'int': ("" if getattr(self, 'int', None) is None
                    else " code=%d" % self.int),
            'cat': ("" if getattr(self, 'category', None) is None
                    else " category=%r" % self.category),
            'type': ("" if getattr(self, 'type', None) is None
                     else " type=%r" % self.type),
            'id': hex(id(self) & 2 ** 32 - 1)}

    def __str__(self):
        return u"{}:{}".format(self.category, self.type)

    def __int__(self):
        if self.int is None:
            try:
                self.int = int(
                    self.sql.query_1(
                        """SELECT change_type_id
                        FROM [:table schema=cerebrum name=change_type]
                        WHERE category=:category AND type=:type""",
                        {'category': self.category,
                         'type': self.type}))
            except Errors.NotFoundError:
                raise Errors.NotFoundError('Constant %r' % self)
        return self.int

    def insert(self):
        self._pre_insert_check()
        self.sql.execute("""
                         INSERT INTO {code_table}
                           ({code_col}, category, type, {desc_col})
                         VALUES
                           ({code_seq}, :category, :type, :desc)"""
                         .format(code_table=self._lookup_table,
                                 code_col=self._lookup_code_column,
                                 desc_col=self._lookup_desc_column,
                                 code_seq=self._code_sequence),
                         {'category': self.category,
                          'type': self.type,
                          'desc': self.msg_string})

    def format_message(self, subject, dest):
        """Format self.msg_string with subject and dest.

        :type subject: unicode or ascii bytes
        :param subject: subject entity_name

        :type dest: unicode or ascii bytes
        :param dest: destination entity_name

        :rtype: unicode
        :return: Formatted string
        """
        if self.msg_string is None:
            return '{}, subject {}, destination {}'.format(
                text(self),
                subject,
                dest)
        return self.msg_string % {
            'subject': subject,
            'dest': dest}

    param_formatters = {}

    @classmethod
    def formatter(cls, param_type):
        def fun(fn):
            cls.param_formatters[param_type] = fn
            return fn
        return fun

    def format_params(self, params):
        """ Format self.format with params from change_params.

        :type params: dict or dict-like mapping, basestr, or None
        :param params:  change_params as dict or json string

        :rtype: unicode
        :return: Formatted string
        """
        from Cerebrum.utils import json
        if isinstance(params, string):
            params = json.loads(params)

        def helper():
            for f in self.format:
                repl = {}
                for part in re.findall(r'%\([^\)]+\)s', f):
                    fmt_key = part[2:-2]
                    if fmt_key not in repl:
                        fmt_type, key = fmt_key.split(':')
                        try:
                            repl['%({}:{})s'.format(fmt_type, key)] = \
                                self.param_formatters.get(fmt_type)(
                                    self.sql,
                                    params.get(key, None))
                        except:
                            pass
                if any(repl.values()):
                    for k, v in repl.items():
                        f = f.replace(k, v)
                yield f

        if self.format:
            return ', '.join(helper())


@_ChangeTypeCode.formatter('string')
@_ChangeTypeCode.formatter('date')
@_ChangeTypeCode.formatter('timestamp')
def format_cl_string(co, s):
    return text(s)


@_ChangeTypeCode.formatter('entity')
def format_cl_entity(co, e):
    with context.entity.entity(e) as ent:
        try:
            ret = ent.get_subclassed_object()
        except ValueError:
            ret = ent
        return text(ret)


@_ChangeTypeCode.formatter('homedir')
def format_cl_homedir(co, e):
    return 'homedir_id:{}'.format(e)


@_ChangeTypeCode.formatter('disk')
def format_cl_disk(co, d):
    disk = Factory.get('Disk')(co._db)
    try:
        disk.find(d)
        return disk.path
    except Errors.NotFoundError:
        return 'deleted_disk:{}'.format(d)


def _get_code(get, code, fallback=False):
    def f(get):
        try:
            return 1, text(get(code))
        except Errors.NotFoundError:
            if fallback:
                return 2, fallback
            else:
                return 2, text(code)
    if not isinstance(get, (tuple, list)):
        get = [get]
    return text(sorted(map(f, get))[0][1])


@_ChangeTypeCode.formatter('spread_code')
def format_cl_spread(co, code):
    return _get_code(co.Spread, code)


@_ChangeTypeCode.formatter('ou')
def format_cl_ou(co, val):
    with context.entity.ou(val) as ou:
        return text(ou)


@_ChangeTypeCode.formatter('affiliation')
def format_cl_aff(co, val):
    return _get_code(co.PersonAffiliation, val)


@_ChangeTypeCode.formatter('int')
def format_cl_int(co, val):
    return text(val)


@_ChangeTypeCode.formatter('bool')
def format_cl_bool(co, val):
    if val == 'F':
        return text(False)
    return text(val)


@_ChangeTypeCode.formatter('home_status')
def format_cl_home_status(co, val):
    return _get_code(co.AccountHomeStatus, val)


@_ChangeTypeCode.formatter('source_system')
def format_cl_source(co, val):
    return _get_code(co.AuthoritativeSystem, val)


@_ChangeTypeCode.formatter('name_variant')
def format_cl_name_variant(co, val):
    return _get_code((co.PersonName, co.EntityNameCode), val)


@_ChangeTypeCode.formatter('value_domain')
def format_cl_value_domain(co, val):
    return _get_code(co.ValueDomain, val)


@_ChangeTypeCode.formatter('extid')
def format_cl_external_id(co, val):
    return _get_code(co.EntityExternalId, val)


@_ChangeTypeCode.formatter('quarantine_type')
def format_cl_quarantine_type(co, val):
    return _get_code(co.Quarantine, val)


@_ChangeTypeCode.formatter('id_type')
def format_cl_id_type(co, val):
    return _get_code(co.ChangeType, val)


class ConstantsBase(DatabaseAccessor):
    def __iterate_constants(self, const_type=None):
        """Iterate all of constants within this constants proxy object.

        This is a convenience method for internal usage.

        :type const_type: class or a sequence thereof
        :param const_type:
          Wanted constant types. This gives us a possibility to iterate, say,
          only EntityType constant objects.

        :rtype: generator
        :return:
          A generator yielding (in random order) constants of the specified
          type. If no type is specified, all constants will be yielded.
        """

        if const_type is None:
            const_type = _CerebrumCode

        for name in dir(self):
            attribute = getattr(self, name)
            if isinstance(attribute, const_type):
                yield attribute

    def map_const(self, code):
        """Returns the Constant object as a reverse lookup on integer code.

        :param int code:
          Constant's integer value.

        :rtype: _CerebrumCode instance or None.
        :return:
          A _CerebrumCode instance (i.e. a constant object) the integer code
          of which matches `code`. If no match is found, return None.
        """

        for const_obj in self.__iterate_constants():
            if int(const_obj) == code:
                return const_obj
        return None

    def _get_dependency_order(self):
        # {dependency1: {class: [object1, ...]},
        #  ...}
        order = {}
        for x in dir(self):
            attr = getattr(self, x)
            if isinstance(attr, _CerebrumCode):
                dep = attr._insert_dependency
                if dep not in order:
                    order[dep] = {}
                cls = type(attr)
                if cls not in order[dep]:
                    order[dep][cls] = {}
                order[dep][cls][text(attr)] = attr
        return order

    def _get_superfluous_codes(self):
        order = self._get_dependency_order()
        root = None
        for cls in order[root].keys():
            rows = self._db.query("SELECT * FROM {}".format(cls._lookup_table))
            table_vals = [int(r[cls._lookup_code_column]) for r in rows]
            code_vals = [int(x) for x in order[root][cls].values()]
            for code in table_vals:
                if code not in code_vals:
                    name = text(cls(code))
                    yield cls, code, name

    def initialize(self, update=True, delete=False):
        order = self._get_dependency_order()
        if None not in order:
            raise ValueError("All code values have circular dependencies.")
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
                            update_results = code.update()
                            if update_results is not None:
                                stats['updated'] += 1
                                stats['details'].extend(update_results)
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
                                tmp_cls_c = text(cls(c))
                                cls(c).delete()
                                stats['deleted'] += 1
                                stats['details'].append(
                                    "Deleted code: %s ('%s')" %
                                    (tmp_cls_c, cls))
                            else:
                                stats['superfluous'] += 1
                                stats['details'].append(
                                    "Superfluous code: %s ('%s')" %
                                    (cls(c), cls))
                del order[root][cls]
                if cls in order:
                    insert(cls, update)
            del order[root]

        insert(None, update)
        if order:
            raise ValueError("Some code values have circular dependencies.")
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

    def cache_constants(self):
        u""" Do a lookup on every constant, to cause caching of values. """
        for const_obj in self.__iterate_constants(None):
            int(const_obj)

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
        if isinstance(human_repr, (int, long)):
            obj = self.map_const(human_repr)
        elif isinstance(human_repr, string):
            if isinstance(human_repr, bytes):
                try:
                    human_repr = human_repr.decode('UTF-8')
                except UnicodeDecodeError:
                    human_repr = human_repr.decode('latin-1')
            # ok, that failed, so assume this is a constant attribute name ...
            try:
                if hasattr(self, human_repr):
                    obj = getattr(self, human_repr)
            except UnicodeError:
                # PY2 does not like non-ascii attribute names
                pass
            # ok, that failed too, we can only compare stringified version of
            # all proper constants with the parameter...
            if obj is None:
                for const_obj in self.__iterate_constants(const_type):
                    if text(const_obj) == human_repr:
                        obj = const_obj
            # assume it's a textual representation of the code int...
            if obj is None and human_repr.isdigit():
                obj = self.map_const(int(human_repr))
        # Make sure it's of the right type...
        if obj is not None and const_type is not None:
            if not isinstance(obj, const_type):
                obj = None
        return obj


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
    entity_host = _EntityTypeCode(
        'host',
        'see table host_info')
    entity_disk = _EntityTypeCode(
        'disk',
        'see table disk_info')

    group_namespace = _ValueDomainCode(
        cereconf.ENTITY_TYPE_NAMESPACE['group'],
        'Default domain for group names')
    account_namespace = _ValueDomainCode(
        cereconf.ENTITY_TYPE_NAMESPACE['account'],
        'Default domain for account names')
    host_namespace = _ValueDomainCode(
        cereconf.ENTITY_TYPE_NAMESPACE['host'],
        'Default domain for host names')

    group_memberop_union = _GroupMembershipOpCode(
        'union',
        'Union')
    group_memberop_intersection = _GroupMembershipOpCode(
        'intersection',
        'Intersection')
    group_memberop_difference = _GroupMembershipOpCode(
        'difference',
        'Difference')

    language_nb = _LanguageCode("nb", u"Bokmål")
    language_nn = _LanguageCode("nn", "Nynorsk")
    language_en = _LanguageCode("en", "English")
    language_de = _LanguageCode("de", "Deutsch")
    language_it = _LanguageCode("it", "Italiano")
    language_nl = _LanguageCode("nl", "Nederlands")
    language_sv = _LanguageCode("sv", "Svenska")
    language_sv = _LanguageCode("fr", u"Français")
    language_ru = _LanguageCode("ru", "Russian")

    system_cached = _AuthoritativeSystemCode(
        'Cached',
        'Internally cached data',
        {"nb": "Internt cachede data",
         "en": "Internally cached data", })


class CommonConstants(ConstantsBase):

    auth_type_md5_crypt = _AuthenticationCode(
        'MD5-crypt',
        "MD5-derived password hash as implemented by crypt(3) on some Unix"
        " variants passed a `salt` that starts with '$1$'.  See <URL:http:"
        "//www.users.zetnet.co.uk/hopwood/crypto/scan/algs/md5crypt.txt>.")
    auth_type_sha256_crypt = _AuthenticationCode(
        'SHA-256-crypt',
        'SHA-256 derived password as implemented by crypt(3) in '
        'the GNU C library http://www.akkadia.org/drepper/SHA-crypt.txt')
    auth_type_sha512_crypt = _AuthenticationCode(
        'SHA-512-crypt',
        'SHA-512 derived password as implemented by crypt(3) in '
        'the GNU C library http://www.akkadia.org/drepper/SHA-crypt.txt')
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

    contact_phone = _ContactInfoCode(
        'PHONE',
        'Phone')
    contact_phone_private = _ContactInfoCode(
        'PRIVPHONE',
        "Person's private phone number")
    contact_fax = _ContactInfoCode(
        'FAX',
        'Fax')
    contact_email = _ContactInfoCode(
        'EMAIL',
        'Email')
    contact_url = _ContactInfoCode(
        'URL',
        'URL')
    contact_mobile_phone = _ContactInfoCode(
        'MOBILE',
        'Mobile phone')
    contact_private_mobile = _ContactInfoCode(
        'PRIVATEMOBILE',
        'Private mobile phone')
    contact_private_mobile_visible = _ContactInfoCode(
        'PRIVMOBVISIBLE',
        'Private mobile phone (visible in directories)')

    address_post = _AddressCode(
        'POST',
        'Post address')
    address_post_private = _AddressCode(
        'PRIVPOST',
        "Person's private post address")
    address_street = _AddressCode(
        'STREET',
        'Street address')

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
        'PERSONALTITLE',
        'Persons personal title',
        {"nb": "Personlig tittel",
         "en": "Personal title", })
    name_work_title = _PersonNameCode(
        'WORKTITLE',
        'Persons work title',
        {"nb": "Arbeidstittel",
         "en": "Work title", })

    personal_title = _EntityNameCode(
        'PERSONALTITLE',
        "Person's personal title",
        {"nb": "Personlig tittel",
         "en": "Personal title", })
    work_title = _EntityNameCode(
        'WORKTITLE',
        "Person's work title",
        {"nb": "Arbeidstittel",
         "en": "Work title", })

    ou_name = _EntityNameCode(
        "OU name",
        "OU name",
        {"nb": "Stedsnavn",
         "en": "OU name", })
    ou_name_acronym = _EntityNameCode(
        "OU acronym",
        "OU acronym",
        {"nb": "Akronym",
         "en": "Acronym", })
    ou_name_short = _EntityNameCode(
        "OU short",
        "OU short name",
        {"nb": "Kortnavn",
         "en": "Short name", })
    ou_name_long = _EntityNameCode(
        "OU long",
        "OU long name",
        {"nb": "Navn",
         "en": "Full name", })
    ou_name_display = _EntityNameCode(
        "OU display",
        "OU display name",
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

    def get_affiliation(self, aff_hint):
        u""" Get an affiliation from hint.

        Utility function to look up affiliation and affiliation status from
        strings. Example:

        >>> Constants().get_affiliation('MY_AFFILIATION')
        >>> Constants().get_affiliation('MY_AFFILIATION/my_status')

        :type aff_hint: str, _PersonAffiliation, _PersonAffStatus
        :param aff_hint:
            The affiliation we want to look up.

        :return tuple:
            Returns a tuple with the affiliation and affiliation status.
            Affiliation status may be None.

        :raise NotFoundError:
            If the affiliation or affiliation status doesn't exist.
        """
        if isinstance(aff_hint, self.PersonAffiliation):
            int(aff_hint)
            return aff_hint, None
        if isinstance(aff_hint, self.PersonAffStatus):
            int(aff_hint)
            return aff_hint.affiliation, aff_hint
        try:
            aff_str, status_str = aff_hint.split('/')
        except ValueError:
            aff = self.PersonAffiliation(aff_hint)
            int(aff)
            return aff, None
        else:
            aff = self.PersonAffiliation(aff_str)
            status = self.PersonAffStatus(aff, status_str)
            int(aff)
            int(status)
            return aff, status


# TODO: CLConstants are typically included in the CLASS_CONSTANTS definition.
#       This is probably a hack that is done to make makedb create and update
#       the constants in the database.
#       We need to clean up all use of CLConstants from the CLASS_CONSTANTS
#       object.

# TODO: CLConstants should inherit from ConstantsBase.
class CLConstants(Constants):

    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    ChangeType = _ChangeTypeCode

    # Group changes

    group_add = _ChangeTypeCode(
        'e_group', 'add', 'added %(subject)s to %(dest)s')
    group_rem = _ChangeTypeCode(
        'e_group', 'rem', 'removed %(subject)s from %(dest)s')
    group_create = _ChangeTypeCode(
        'e_group', 'create', 'created %(subject)s')
    group_mod = _ChangeTypeCode(
        'e_group', 'mod', 'modified %(subject)s')
    group_destroy = _ChangeTypeCode(
        'e_group', 'destroy', 'destroyed %(subject)s')

    # Account changes

    account_create = _ChangeTypeCode(
        'e_account', 'create', 'created %(subject)s')
    account_delete = _ChangeTypeCode(
        'e_account', 'delete', 'deleted %(subject)s')
    account_mod = _ChangeTypeCode(
        'e_account', 'mod', 'modified %(subject)s',
        ("new owner=%(entity:owner_id)s",
         "new expire_date=%(date:expire_date)s"))
    account_password = _ChangeTypeCode(
        'e_account', 'password', 'new password for %(subject)s')
    account_password_token = _ChangeTypeCode(
        'e_account', 'passwordtoken', 'password token sent for %(subject)s',
        ('phone_to=%(string:phone_to)s',))
    account_destroy = _ChangeTypeCode(
        'e_account', 'destroy', 'destroyed %(subject)s')
    # TODO: account_move is obsolete, remove it
    account_move = _ChangeTypeCode(
        'e_account', 'move', '%(subject)s moved',
        ('from=%(string:old_host)s:%(string:old_disk)s,'
         'to=%(string:new_host)s:%(string:new_disk)s,', ))
    account_home_updated = _ChangeTypeCode(
        'e_account', 'home_update', 'home updated for %(subject)s',
        ('old=%(homedir:old_homedir_id)s',
         'old_home=%(string:old_home)s',
         'old_disk_id=%(disk:old_disk_id)s',
         'spread=%(spread_code:spread)s'))
    account_home_added = _ChangeTypeCode(
        'e_account', 'home_added', 'home added for %(subject)s',
        ('spread=%(spread_code:spread)s', 'home=%(string:home)s'))
    account_home_removed = _ChangeTypeCode(
        'e_account', 'home_removed', 'home removed for %(subject)s',
        ('spread=%(spread_code:spread)s', 'home=%(string:home)s'))

    # Spread changes

    spread_add = _ChangeTypeCode(
        'spread', 'add', 'add spread for %(subject)s',
        ('spread=%(spread_code:spread)s',))
    spread_del = _ChangeTypeCode(
        'spread', 'delete', 'delete spread for %(subject)s',
        ('spread=%(spread_code:spread)s',))
    account_type_add = _ChangeTypeCode(
        'ac_type', 'add', 'ac_type add for account %(subject)s',
        ('ou=%(ou:ou_id)s, aff=%(affiliation:affiliation)s, '
         'pri=%(int:priority)s',))
    account_type_mod = _ChangeTypeCode(
        'ac_type', 'mod', 'ac_type mod for account %(subject)s',
        ('old_pri=%(int:old_pri)s, old_pri=%(int:new_pri)s',))
    account_type_del = _ChangeTypeCode(
        'ac_type', 'del', 'ac_type del for account %(subject)s',
        ('ou=%(ou:ou_id)s, aff=%(affiliation:affiliation)s',))

    # AccountHomedir changes

    homedir_remove = _ChangeTypeCode(
        'homedir', 'del', 'homedir del for account %(subject)s',
        ('id=%(int:homedir_id)s',))
    homedir_add = _ChangeTypeCode(
        'homedir', 'add', 'homedir add for account %(subject)s',
        ('id=%(int:homedir_id)s', 'home=%(string:home)s'))
    homedir_update = _ChangeTypeCode(
        'homedir', 'update', 'homedir update for account %(subject)s',
        ('id=%(int:homedir_id)s',
         'home=%(string:home)s', 'status=%(home_status:status)s'))

    # Disk changes

    disk_add = _ChangeTypeCode('disk', 'add', 'new disk %(subject)s')
    disk_mod = _ChangeTypeCode('disk', 'mod', 'update disk %(subject)s')
    disk_del = _ChangeTypeCode('disk', 'del', "delete disk %(subject)s")

    # Host changes

    host_add = _ChangeTypeCode('host', 'add', 'new host %(subject)s')
    host_mod = _ChangeTypeCode('host', 'mod', 'update host %(subject)s')
    host_del = _ChangeTypeCode('host', 'del', 'del host %(subject)s')

    # OU changes

    ou_create = _ChangeTypeCode(
        'ou', 'create', 'created OU %(subject)s')
    ou_mod = _ChangeTypeCode(
        'ou', 'mod', 'modified OU %(subject)s')
    ou_unset_parent = _ChangeTypeCode(
        'ou', 'unset_parent', 'parent for %(subject)s unset',
        ('perspective=%(int:perspective)s',))
    ou_set_parent = _ChangeTypeCode(
        'ou', 'set_parent', 'parent for %(subject)s set to %(dest)s',
        ('perspective=%(int:perspective)s',))
    ou_del = _ChangeTypeCode(
        'ou', 'del', 'deleted OU %(subject)s')

    # Person changes

    person_create = _ChangeTypeCode(
        'person', 'create', 'created %(subject)s')
    person_update = _ChangeTypeCode(
        'person', 'update', 'update %(subject)s')
    person_name_del = _ChangeTypeCode(
        'person', 'name_del', 'del name for %(subject)s',
        ('src=%(source_system:src)s, ' +
         'variant=%(name_variant:name_variant)s',))
    person_name_add = _ChangeTypeCode(
        'person', 'name_add', 'add name for %(subject)s',
        ('name=%(string:name)s, src=%(source_system:src)s, ' +
         'variant=%(name_variant:name_variant)s',))
    person_name_mod = _ChangeTypeCode(
        'person', 'name_mod', 'mod name for %(subject)s',
        ('name=%(string:name)s, src=%(source_system:src)s, ' +
         'variant=%(name_variant:name_variant)s',))

    # Entity changes

    entity_add = _ChangeTypeCode(
        'entity', 'add', 'add entity %(subject)s')
    entity_del = _ChangeTypeCode(
        'entity', 'del', 'del entity %(subject)s')
    entity_name_add = _ChangeTypeCode(
        'entity_name', 'add', 'add entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
    entity_name_mod = _ChangeTypeCode(
        'entity_name', 'mod', 'mod entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
    entity_name_del = _ChangeTypeCode(
        'entity_name', 'del', 'del entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
    entity_cinfo_add = _ChangeTypeCode(
        'entity_cinfo', 'add', 'add entity_cinfo for %(subject)s')
    entity_cinfo_del = _ChangeTypeCode(
        'entity_cinfo', 'del', 'del entity_cinfo for %(subject)s')
    entity_addr_add = _ChangeTypeCode(
        'entity_addr', 'add', 'add entity_addr for %(subject)s')
    entity_addr_del = _ChangeTypeCode(
        'entity_addr', 'del', 'del entity_addr for %(subject)s')
    entity_note_add = _ChangeTypeCode(
        'entity_note', 'add', 'add entity_note for %(subject)s',
        ('note_id=%(int:note_id)s',))
    entity_note_del = _ChangeTypeCode(
        'entity_note', 'del', 'del entity_note for %(subject)s',
        ('note_id=%(int:note_id)s',))
    entity_ext_id_del = _ChangeTypeCode(
        'entity', 'ext_id_del', 'del ext_id for %(subject)s',
        ('src=%(source_system:src)s, type=%(extid:id_type)s',))
    entity_ext_id_mod = _ChangeTypeCode(
        'entity', 'ext_id_mod', 'mod ext_id for %(subject)s',
        ('value=%(string:value)s, src=%(source_system:src)s, ' +
         'type=%(extid:id_type)s',))
    entity_ext_id_add = _ChangeTypeCode(
        'entity', 'ext_id_add', 'add ext_id for %(subject)s',
        ('value=%(string:value)s, src=%(source_system:src)s, ' +
         'type=%(extid:id_type)s',))

    # PersonAffiliation changes

    person_aff_add = _ChangeTypeCode(
        'person', 'aff_add', 'add aff for %(subject)s')
    person_aff_mod = _ChangeTypeCode(
        'person', 'aff_mod', 'mod aff for %(subject)s')
    person_aff_del = _ChangeTypeCode(
        'person', 'aff_del', 'del aff for %(subject)s')
    person_aff_src_add = _ChangeTypeCode(
        'person', 'aff_src_add', 'add aff_src for %(subject)s')
    person_aff_src_mod = _ChangeTypeCode(
        'person', 'aff_src_mod', 'mod aff_src for %(subject)s')
    person_aff_src_del = _ChangeTypeCode(
        'person', 'aff_src_del', 'del aff_src for %(subject)s')

    # Quarantine changes

    quarantine_add = _ChangeTypeCode(
        'quarantine', 'add', 'add quarantine for %(subject)s',
        ('type=%(quarantine_type:q_type)s',))
    quarantine_mod = _ChangeTypeCode(
        'quarantine', 'mod', 'mod quarantine for %(subject)s',
        ('type=%(quarantine_type:q_type)s',))
    quarantine_del = _ChangeTypeCode(
        'quarantine', 'del', 'del quarantine for %(subject)s',
        ('type=%(quarantine_type:q_type)s',))
    quarantine_refresh = _ChangeTypeCode(
        'quarantine', 'refresh', 'refresh quarantine for %(subject)s')

    # TBD: Is it correct to have posix_demote in this module?

    posix_demote = _ChangeTypeCode(
        'posix', 'demote', 'demote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_demote = _ChangeTypeCode(
        'posix', 'group-demote', 'group demote posix %(subject)s',
        ('gid=%(int:gid)s',))
    posix_promote = _ChangeTypeCode(
        'posix', 'promote', 'promote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_promote = _ChangeTypeCode(
        'posix', 'group-promote', 'group promote posix %(subject)s',
        ('gid=%(int:gid)s',))

    # Guest functionality

    guest_create = _ChangeTypeCode(
        'guest', 'create', 'created guest %(dest)s',
        ('mobile=%(string:mobile)s, name=%(string:name)s, '
         'owner_id=%(string:owner)s', ))


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
    for x in filter(lambda x: x[0] != '_' and x not in skip, dir(co)):
        if type(getattr(co, x)) == type or callable(getattr(co, x)):
            continue
        if not isinstance(getattr(co, x), co.CerebrumCode):
            continue
        try:
            print "FOUND: co.%s:" % x
            print "  strval: %r" % str(getattr(co, x))
            print "  intval: %d" % int(getattr(co, x))
        except Errors.NotFoundError:
            print "NOT FOUND: co.%s" % x
        except Exception, e:
            print "ERROR: co.%s - %r" % (x, e)
    print "Map '7' back to str: %s" % co.map_const(7)


if __name__ == '__main__':
    main()
