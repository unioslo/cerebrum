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

"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Errors


class CodeValuePresentError(RuntimeError):
    """Error raised when an already existing code value is inserted."""
    pass


class _CerebrumCode(DatabaseAccessor):
    """Abstract base class for accessing code tables in Cerebrum."""

    _lookup_table = None                # Abstract class.
    _lookup_code_column = 'code'
    _lookup_str_column = 'code_str'
    _lookup_desc_column = 'description'
    _code_sequence = '[:sequence schema=cerebrum name=code_seq op=next]'

    # Should we postpone INSERTion of code value in this class until
    # some other code value class has been fully INSERTed (e.g. due to
    # foreign key constraint checks)?
    _insert_dependency = None

    # TBD: Should this take DatabaseAccessor args as well?  Maybe use
    # some kind of currying in Constants to avoid having to pass the
    # Database arg every time?
    def __init__(self, code, description=None):
        self.int = None
        if isinstance(description, str):
            description = description.strip()
        self._desc = description
        if type(code) is int:
            self.int = code
            self.str = self.sql.query_1("SELECT %s FROM %s WHERE %s=:code" %
                                        (self._lookup_str_column,
                                         self._lookup_table,
                                         self._lookup_code_column),
                                        {'code': code})
        elif type(code) is str:
            self.str = code
        else:
            raise TypeError, "Argument 'code' must be int or str."

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
            'id': hex(id(self))}

    def _get_description(self):
        if self._desc is None:
            self._desc = self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                          (self._lookup_desc_column,
                                           self._lookup_table,
                                           self._lookup_str_column),
                                          self.__dict__)
        return self._desc
    description = property(_get_description, None, None,
                           "This code value's description.")

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                            (self._lookup_code_column,
                                             self._lookup_table,
                                             self._lookup_str_column),
                                            self.__dict__))
        return self.int

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
        # We want to allow the reflexive comparison (other.__eq__) a
        # chance at this, too.  Hopefully NotImplementedError (as
        # opposed to TypeError) is the correct way to indicate that.
        raise NotImplementedError, "Don't know how to compare %s to %s" % \
              (repr(type(self).__name__), repr(other))

    def __ne__(self, other): return not self.__eq__(other)

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


class _EntityTypeCode(_CerebrumCode):
    "Mappings stored in the entity_type_code table"
    _lookup_table = '[:table schema=cerebrum name=entity_type_code]'
    pass

class _SpreadCode(_CerebrumCode):
    """Code values for entity `spread`; table `entity_spread`."""
    _lookup_table = '[:table schema=cerebrum name=spread_code]'
    _insert_dependency = _EntityTypeCode

    def __init__(self, code, entity_type=None, description=None):
        if entity_type is not None:
            self.entity_type = entity_type
        super(_SpreadCode, self).__init__(code, description)

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

    def entity_type(self):
        return _EntityTypeCode(self.sql.query_1("""
        SELECT entity_type
        FROM %(table)s
        WHERE %(code_col)s = :code""" % {
            'table': self._lookup_table,
            'code_col': self._lookup_code_column},
                                                {'code': int(self)}))

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
            self.country = country
            self.phone_prefix = phone_prefix
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
                          'country': self.country,
                          'phone': self.phone_prefix,
                          'desc': self.description})

    def country(self):
        if self.country is None:
            self.country = self._get_column('country')
        return self.country

    def phone_prefix(self):
        if self.phone_prefix is None:
            self.phone_prefix = self._get_column('phone_prefix')
        return self.phone_prefix

    def _get_column(self, col_name):
        return self.query_1("""
        SELECT %(col_name)s
        FROM %(table)s
        WHERE %(code_col)s = :code""" % {
            'col_name': col_name,
            'table': self._lookup_table,
            'code_col': self._lookup_code_column},
                            {'code': int(self)})

class _AddressCode(_CerebrumCode):
    "Mappings stored in the address_code table"
    _lookup_table = '[:table schema=cerebrum name=address_code]'
    pass

class _GenderCode(_CerebrumCode):
    "Mappings stored in the gender_code table"
    _lookup_table = '[:table schema=cerebrum name=gender_code]'
    pass

class _PersonExternalIdCode(_CerebrumCode):
    "Mappings stored in the person_external_id_code table"
    _lookup_table = '[:table schema=cerebrum name=person_external_id_code]'
    pass

class _PersonNameCode(_CerebrumCode):
    "Mappings stored in the person_name_code table"
    _lookup_table = '[:table schema=cerebrum name=person_name_code]'
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

    def __init__(self, affiliation, status, description=None):
        self.affiliation = affiliation
        super(_PersonAffStatusCode, self).__init__(status, description)

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("""
            SELECT %s FROM %s WHERE affiliation=:aff AND %s=:str""" %
                                            (self._lookup_code_column,
                                             self._lookup_table,
                                             self._lookup_str_column),
                                            {'str': self.str,
                                             'aff' : int(self.affiliation)}))
        return self.int

    ## Should __str__ be overriden as well, to indicate both
    ## affiliation and status?

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
    "Mappings stored in the ou_perspective_code table"
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

class _AuthenticationCode(_CerebrumCode):
    "Mappings stored in the value_domain_code table"
    _lookup_table = '[:table schema=cerebrum name=authentication_code]'
    pass

class _GroupMembershipOpCode(_CerebrumCode):
    "Mappings stored in the ou_perspective_code table"
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

    def map_const(self, num):
        skip = list(dir(_CerebrumCode.sql))
        skip.extend(("map_const", "initialize"))
        for x in filter(lambda x: x[0] != '_' and not x in skip, dir(self)):
            v = getattr(self, x)
            if int(v) == num:
                return v
        return None

    def initialize(self, update=True):
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
                    order[dep][cls] = []
                order[dep][cls].append(attr)
        if not order.has_key(None):
            raise ValueError, "All code values have circular dependencies."
        stats = {'total': 0, 'inserted': 0}
        def insert(root, update, stats=stats):
            for cls in order[root].keys():
                cls_code_count = 0
                for code in order[root][cls]:
                    stats['total'] += 1
                    cls_code_count += 1
                    try:
                        code._pre_insert_check()
                    except CodeValuePresentError:
                        if update:
                            continue
                        raise
                    code.insert()
                    stats['inserted'] += 1
                del order[root][cls]
                table_code_count = self._db.query_1(
                    """SELECT count(*) FROM %s""" % cls._lookup_table)
                if cls_code_count <> table_code_count:
                    raise RuntimeError, \
                          ("Number of %s code attributes (%d)"
                           " differs from number of %s rows (%d)") % (
                        cls.__name__, cls_code_count,
                        cls._lookup_table, table_code_count)
                if order.has_key(cls):
                    insert(cls, update)
            del order[root]
        insert(None, update)
        if order:
            raise ValueError, "Some code values have circular dependencies."
        return (stats['inserted'], stats['total'])

    def __init__(self, database):
        super(ConstantsBase, self).__init__(database)

        # TBD: Works, but is icky -- _CerebrumCode or one of its
        # superclasses might use the .sql attribute themselves for
        # other purposes; should be cleaned up.
        _CerebrumCode.sql = database

    def fetch_constants(self, wanted_class):
        """Return all constant instances of wanted_class."""
        clist = []
        for name in dir(self):
            const = getattr(self, name)
            if isinstance(const, wanted_class):
                clist.append(const)
        return clist


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

    group_namespace = _ValueDomainCode(cereconf.DEFAULT_GROUP_NAMESPACE,
                                       'Default domain for group names')
    account_namespace = _ValueDomainCode(cereconf.DEFAULT_ACCOUNT_NAMESPACE,
                                         'Default domain for account names')

    group_memberop_union = _GroupMembershipOpCode('union', 'Union')
    group_memberop_intersection = _GroupMembershipOpCode(
        'intersection', 'Intersection')
    group_memberop_difference = _GroupMembershipOpCode(
        'difference', 'Difference')

    system_cached = _AuthoritativeSystemCode('Cached',
                                             'Internally cached data')


class CommonConstants(ConstantsBase):

    auth_type_md5_crypt = _AuthenticationCode(
        'MD5-crypt',
        "MD5-derived password hash as implemented by crypt(3) on some Unix"
        " variants passed a `salt` that starts with '$1$'.  See <URL:http:"
        "//www.users.zetnet.co.uk/hopwood/crypto/scan/algs/md5crypt.txt>.")
    auth_type_crypt3_des = _AuthenticationCode(
        'crypt3-DES',
        "Password hash generated with the 'traditional' Unix crypt(3)"
        " algorithm, based on DES.  See <URL:http://www.users.zetnet.co.uk"
        "/hopwood/crypto/scan/ph.html#Traditional-crypt3>.")

    contact_phone = _ContactInfoCode('PHONE', 'Phone')
    contact_phone_private = _ContactInfoCode('PRIVPHONE',
                                             "Person's private phone number")
    contact_fax = _ContactInfoCode('FAX', 'Fax')
    contact_email = _ContactInfoCode('EMAIL', 'Email')
    contact_url = _ContactInfoCode('URL', 'URL')

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
    name_personal_title = _PersonNameCode('PERSONALTITLE', 'Persons personal title')
    name_work_title = _PersonNameCode('WORKTITLE', 'Persons work title')

    system_manual = _AuthoritativeSystemCode('Manual', 'Manual registration')

    # bootstrap_account is of this type:
    account_program = _AccountCode('programvare', 'Programvarekonto')
    home_status_not_created = _AccountHomeStatusCode('not_created', 'Not created')
    home_status_create_failed = _AccountHomeStatusCode(
        'create_failed', 'Creation failed')
    home_status_on_disk = _AccountHomeStatusCode(
        'on_disk', 'Currently on disk')
    home_status_archived = _AccountHomeStatusCode(
        'archived', 'Has been archived')

class Constants(CoreConstants, CommonConstants):
    pass


class ExampleConstants(Constants):
    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    externalid_fodselsnr = _PersonExternalIdCode('NO_BIRTHNO',
                                                 'Norwegian birth number')

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
