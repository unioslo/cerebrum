# -*- coding: iso-8859-1 -*-
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

"""Module for making Cerebrum into a local email address database.

This module contains various classes that enables Cerebrum to act as a
source of email address/email delivery data, as is needed by any email
system.

The interface in this module is not designed for any particular email
system implementation or configuration; depending on the format one
exports the Cerebrum email data to, the data should be usable by quite
a few different MTAs.

Some Cerebrum installations might want to use only a subset of the
classes in this module; the minimal subset consists of EmailDomain,
EmailAddress and EmailTarget.

The relation between the components in the minimal subset is as
follows:

 * EmailAddress N-to-1 EmailDomain
   There are typically many EmailAddresses with the same EmailDomain.

 * EmailAddress N-to-1 EmailTarget
   All EmailAddresses must point to exactly one EmailTarget.  Multiple
   EmailAddresses may point at the same EmailTarget.

   [ If there is a need to have a single email address point to
     multiple delivery targets, one can use either the 'multi'
     EmailTarget type (if all the targets are local users, make a
     Cerebrum group whose members are these users, and associate an
     EmailTarget with that group), or use the EmailForward interface
     (associate one or more (possibly non-local) email addresses with
     an EmailTarget. ]

See contrib/generate_mail_ldif.py for an example of a script exporting
the email data.  Note, though, that this example assumes that your
Cerebrum instance uses more than the minimal subset of email-related
classes."""

import re
import string
import time

from Cerebrum import Utils
from Cerebrum import Constants
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import Entity
from Cerebrum.Disk import Host
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Errors

import cereconf

class _EmailTargetCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_target_code]'


class _EmailDomainCategoryCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_domain_cat_code]'


class _EmailServerTypeCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_server_type_code]'


class _EmailSpamLevelCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_spam_level_code]'

    def __init__(self, code, level=None, description=None):
        super(_EmailSpamLevelCode, self).__init__(code, description)
        self.level = level

    def insert(self):
        self._pre_insert_check()
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, %(str_col)s, level, %(desc_col)s)
        VALUES
          (%(code_seq)s, :str, :level, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
                         {'str': self.str,
                          'level': self.level,
                          'desc': self._desc})

    def get_level(self):
        if self.level is None:
            self.level = int(self.sql.query_1("""
            SELECT level
            FROM %(code_table)s
            WHERE code=:code""" % {'code_table': self._lookup_table},
                                              {'code': int(self)}))
        return self.level


class _EmailSpamActionCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_spam_action_code]'


class _EmailVirusFoundCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_virus_found_code]'


class _EmailVirusRemovedCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_virus_removed_code]'


class EmailConstants(Constants.Constants):

    EmailTarget = _EmailTargetCode
    EmailDomainCategory = _EmailDomainCategoryCode
    EmailServerType = _EmailServerTypeCode
    EmailSpamLevel = _EmailSpamLevelCode
    EmailSpamAction = _EmailSpamActionCode
    EmailVirusFound = _EmailVirusFoundCode
    EmailVirusRemoved = _EmailVirusRemovedCode

    email_domain_category_noexport = _EmailDomainCategoryCode(
        'noexport',
        'Addresses in these domains can be defined, but are not'
        ' exported to the mail system.  This is useful for'
        ' pre-defining addresses prior to taking over a new'
        ' maildomain.')

    email_domain_category_cnaddr = _EmailDomainCategoryCode(
        'cnaddr',
        "Primary user addresses in these domains will be based on the"
        " owner's full common name, and not just e.g. the username.")

    email_domain_category_uidaddr = _EmailDomainCategoryCode(
        'uidaddr',
        'Primary user addresses in these domains will be on the'
        ' format username@domain.')

    email_domain_category_include_all_uids = _EmailDomainCategoryCode(
        'all_uids',
        'All account email targets should get a valid address in this domain,'
        ' on the form <accountname@domain>.')

    email_target_account = _EmailTargetCode(
        'account',
        "Target is the local delivery defined for the PosixUser whose"
        " account_id == email_target.using_uid.")

    email_target_deleted = _EmailTargetCode(
        'deleted',
        "Target type for addresses that are no longer working, but"
        " for which it is useful to include a short custom text in"
        " the error message returned to the sender.  The text"
        " is taken from email_target.alias_value")

    email_target_forward = _EmailTargetCode(
        'forward',
        "Target is a pure forwarding mechanism; local deliveries will"
        " only occur as indirect deliveries to the addresses forwarded"
        " to.  Both email_target.entity_id, email_target.using_uid and"
        " email_target.alias_value should be NULL, as they are ignored."
        "  The email address(es) to forward to is taken from table"
        " email_forward.")

    email_target_file = _EmailTargetCode(
        'file',
        "Target is a file.  The absolute path of the file is gathered"
        " from email_target.alias_value.  Iff email_target.using_uid"
        " is set, deliveries to this target will be run as that"
        " PosixUser.")

    email_target_pipe = _EmailTargetCode(
        'pipe',
        "Target is a shell pipe.  The command (and args) to pipe mail"
        " into is gathered from email_target.alias_value.  Iff"
        " email_target.using_uid is set, deliveries to this target"
        " will be run as that PosixUser.")

    email_target_Mailman = _EmailTargetCode(
        'Mailman',
        "Target is a Mailman mailing list.  The command (and args) to"
        " pipe mail into is gathered from email_target.alias_value."
        "  Iff email_target.using_uid is set, deliveries to this target"
        " will be run as that PosixUser.")

    email_target_multi = _EmailTargetCode(
        'multi',
        "Target is the set of `account`-type targets corresponding to"
        " the Accounts that are first-level members of the Group that"
        " has group_id == email_target.entity_id.")

    email_server_type_nfsmbox = _EmailServerTypeCode(
        'nfsmbox',
        "Server delivers mail as mbox-style mailboxes over NFS.")

    email_server_type_cyrus = _EmailServerTypeCode(
        'cyrus_IMAP',
        "Server is a Cyrus IMAP server, which keeps mailboxes in a"
        " Cyrus-specific format.")


class EmailEntity(DatabaseAccessor):
    """Abstract superclass for email 'entities'.

    Email 'entities' (EmailDomain, EmailTarget and EmailAddress)
    aren't regular Cerebrum entities, as many of the bells and
    whistles one can attach to regular entities don't make sense for
    email data.

    This class simulates (convenient parts of) the regular Cerebrum
    entity interface for email 'entities'."""

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)


    __metaclass__ = Utils.mark_update
    pass


class EmailDomain(EmailEntity):
    """Interface to the email domains your MTA should consider as 'local'.

    Before any email address can be registered in Cerebrum, the domain
    part of the address must be registered.  A registered email domain
    can have any number of 'categories' associated with it."""

    __read_attr__ = ('__in_db',
                     # Won't be necessary here if we're a subclass of Entity.
                     'email_domain_id')
    __write_attr__ = ('email_domain_name', 'email_domain_description')

    def clear(self):
        self.clear_class(EmailDomain)
        self.__updated = []

    def populate(self, domain, description):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_domain_name = domain
        self.email_domain_description = description

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.email_domain_id = int(self.nextval("email_id_seq"))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_domain]
              (domain_id, domain, description)
            VALUES (:d_id, :name, :descr)""",
                         {'d_id': self.email_domain_id,
                          'name': self.email_domain_name,
                          'descr': self.email_domain_description})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_domain]
            SET domain=:name, description=:descr
            WHERE domain_id=:d_id""",
                         {'d_id': self.email_domain_id,
                          'name': self.email_domain_name,
                          'descr': self.email_domain_description})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, domain_id):
        (self.email_domain_id, self.email_domain_name,
         self.email_domain_description) = self.query_1("""
         SELECT domain_id, domain, description
         FROM [:table schema=cerebrum name=email_domain]
         WHERE domain_id=:d_id""", {'d_id': domain_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_domain(self, domain):
        domain_id = self.query_1("""
        SELECT domain_id
        FROM [:table schema=cerebrum name=email_domain]
        WHERE domain=:name""", {'name': domain})
        self.find(domain_id)

    def get_domain_name(self):
        return self.email_domain_name

    # TODO:
    # - Rename the cereconf.LDAP['rewrite_email_domain'] configuration option.
    # - Remove support for LDAP_REWRITE_EMAIL_DOMAIN after a while.

    # Support both Cerebrum/default_config.py version 1.81 and older versions.
    _rewrite_domain = getattr(cereconf, 'LDAP', {}).get('rewrite_email_domain')
    if not _rewrite_domain:
        _rewrite_domain = getattr(cereconf, 'LDAP_REWRITE_EMAIL_DOMAIN',
                                  _rewrite_domain)

    def rewrite_special_domains(self, domain):
        return self._rewrite_domain.get(domain, domain)

    def get_categories(self):
        return self.query("""
        SELECT category
        FROM [:table schema=cerebrum name=email_domain_category]
        WHERE domain_id=:d_id""", {'d_id': self.email_domain_id})

    def add_category(self, category):
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_domain_category]
          (domain_id, category)
        VALUES (:d_id, :cat)""", {'d_id': self.email_domain_id,
                                  'cat': int(category)})

    def remove_category(self, category):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_domain_category]
        WHERE domain_id=:d_id""", {'d_id': self.email_domain_id})

    def list_email_domains_with_category(self, category):
        return self.query("""
        SELECT ed.domain_id, ed.domain
        FROM [:table schema=cerebrum name=email_domain] ed
        JOIN [:table schema=cerebrum name=email_domain_category] edc
          ON edc.domain_id = ed.domain_id
        WHERE edc.category = :cat""", {'cat': int(category)})

    def list_email_domains(self):
        return self.query("""
        SELECT domain_id, domain
        FROM [:table schema=cerebrum name=email_domain]""")


class EmailTarget(EmailEntity):
    """Interface for registering valid email delivery targets.

    Targets can either be associated with a Cerebrum entity, implying
    delivery to that entity (typically an account or, for the
    special-case 'multi'-type target, a group of local accounts), or
    with a free-form text (for e.g. file og pipe deliveries).

    There is also a field where one can specify which POSIX user
    deliveries to this target should be run under.

    The EmailAddress class is used to register which email addresses
    that should be connected to a target; each EmailAddress must be
    connected to a single EmailTarget."""

    __read_attr__ = ('__in_db', 'email_target_id')
    __write_attr__ = ('email_target_type', 'email_target_entity_id',
                      'email_target_entity_type', 'email_target_alias',
                      'email_target_using_uid')

    def clear(self):
        self.clear_class(EmailTarget)
        self.__updated = []

    def populate(self, type, entity_id=None, entity_type=None, alias=None,
                 using_uid=None):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_target_type = type
        self.email_target_alias = alias
        self.email_target_using_uid = using_uid
        if entity_id is None and entity_type is None:
            self.email_target_entity_id = self.email_target_entity_type = None
        elif entity_id is not None and entity_type is not None:
            self.email_target_entity_id = entity_id
            self.email_target_entity_type = entity_type
        else:
            raise ValueError, \
                  "Must set both or none of (entity_id, entity_type)."

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        entity_type = self.email_target_entity_type
        if entity_type is not None:
            entity_type = int(entity_type)
        if is_new:
            self.email_target_id = int(self.nextval("email_id_seq"))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_target]
              (target_id, target_type, entity_id, entity_type, alias_value,
               using_uid)
            VALUES (:t_id, :t_type, :e_id, :e_type, :alias, :uid)""",
                         {'t_id': self.email_target_id,
                          't_type': int(self.email_target_type),
                          'e_id': self.email_target_entity_id,
                          'e_type': entity_type,
                          'alias': self.email_target_alias,
                          'uid': self.email_target_using_uid})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_target]
            SET target_type=:t_type, entity_id=:e_id, entity_type=:e_type,
                alias_value=:alias, using_uid=:uid
            WHERE target_id=:t_id""",
                         {'t_id': self.email_target_id,
                          't_type': int(self.email_target_type),
                          'e_id': self.email_target_entity_id,
                          'e_type': entity_type,
                          'alias': self.email_target_alias,
                          'uid': self.email_target_using_uid})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        (self.email_target_id, self.email_target_type,
         self.email_target_entity_id, self.email_target_entity_type,
         self.email_target_alias,
         self.email_target_using_uid) = self.query_1("""
        SELECT target_id, target_type, entity_id, entity_type, alias_value,
               using_uid
        FROM [:table schema=cerebrum name=email_target]
        WHERE target_id=:t_id""", {'t_id': target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def delete(self):
        # We do not delete the corresponding rows in email_address
        # (and by extension, in email_primary_address) to reduce the
        # chance of catastrophic mistakes.
        for table in ('email_forward', 'email_vacation', 'email_quota',
                      'email_spam_filter', 'email_virus_scan',
                      'email_target_server'):
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=%s]
            WHERE target_id=:e_id""" % table, {'e_id': self.email_target_id})

        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_target]
        WHERE target_id=:e_id""", {'e_id': self.email_target_id})

    def find_by_email_target_attrs(self, **kwargs):
        if not kwargs:
            raise ProgrammingError, \
                  "Need at least one column argument to find target"
        where = []
        binds = {}
        for column in ('target_type', 'entity_id', 'alias_value',
                       'using_uid'):
            if column in kwargs:
                where.append("%s = :%s" % (column, column))
                binds[column] = kwargs[column]
                if column == 'target_type':
                    # Avoid errors caused by the database driver
                    # converting bind args to str's.
                    binds[column] = int(binds[column])
                del kwargs[column]
        if kwargs:
            raise ProgrammingError, \
                  "Unrecognized argument(s): %r" % kwargs
        where = " AND ".join(where)
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE %s""" % where, binds)
        self.find(target_id)

    def find_by_entity(self, entity_id):
        # This might find no rows.  In those cases, query_1() will
        # raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE entity_id=:e_id""", {'e_id': entity_id})
        self.find(target_id)

    def find_by_alias(self, alias):
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE alias_value=:alias""", {'alias': alias})
        self.find(target_id)

    def find_by_alias_and_account(self, alias, using_uid):
        # Due to the UNIQUE constraint in table email_target, this can
        # only find more than one row if both entity_id and alias are
        # None.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE (alias_value=:alias OR :alias IS NULL)
          AND (using_uid=:uid OR :uid IS NULL)""",
                                 {'uid': using_uid,
                                  'alias': alias})
        self.find(target_id)

    def get_addresses(self, special=True):
        """Return all email_addresses associated with this
        email_target as row objects.  If special is False, rewrite the
        magic domain names into working domain names."""
        ret = self.query("""
        SELECT ea.local_part, ed.domain, ea.address_id
        FROM [:table schema=cerebrum name=email_address] ea
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE ea.target_id = :t_id""", {'t_id': int(self.email_target_id)})
        if not special:
            ed = EmailDomain(self._db)
            for r in ret:
                r['domain'] = ed.rewrite_special_domains(r['domain'])
        return ret

    def list_email_targets(self):
        """Return target_id of all EmailTarget in database"""
        return self.query("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]""", fetchall=False)

    def list_email_targets_ext(self):
        """Return an iterator over all email_target rows.

        For each row, the following columns are included:
          target_id, target_type, entity_type, entity_id, alias_value
          and using_uid.

        """
        return self.query("""
        SELECT target_id, target_type, entity_type, entity_id, alias_value,
               using_uid
        FROM [:table schema=cerebrum name=email_target]
        """, fetchall=False)
    
    def list_email_target_primary_addresses(self, target_type=None):
        """Return an iterator over primary email-addresses belonging
        to email_target.
        Returns target_id, entity_id, local_part and domain.

        target_type decides which email_target to filter on.
        """

        where = ""
        if target_type:
            where = "WHERE et.target_type = %d" % int(target_type)
 
        return self.query("""
        SELECT et.target_id, et.entity_id, ea.local_part, ed.domain
        FROM [:table schema=cerebrum name=email_target] et
          JOIN [:table schema=cerebrum name=email_primary_address] epa
            ON et.target_id=epa.target_id
          JOIN [:table schema=cerebrum name=email_address] ea
            ON epa.address_id=ea.address_id
          JOIN [:table schema=cerebrum name=email_domain] ed
            ON ea.domain_id=ed.domain_id
        %s""" % where)
        
    def get_target_type(self):
        return self.email_target_type

    def get_target_type_name(self):
        name = self._db.pythonify_data(self.email_target_type)
        name = _EmailTargetCode(name)
        return name

    def get_alias(self):
        return self.email_target_alias

    def get_entity_id(self):
        return self.email_target_entity_id

    def get_entity_type(self):
        return self.email_target_entity_type


class EmailAddress(EmailEntity):
    """Interface for registering known local email addresses.

    EmailAddresses must have a valid localpart, which must be unique
    within the EmailDomain of the address.  Each EmailAddress must be
    connected to a EmailTarget."""

    __read_attr__ = ('__in_db', 'email_addr_id')
    __write_attr__ = ('email_addr_local_part', 'email_addr_domain_id',
                      'email_addr_target_id', 'email_addr_expire_date')
    def clear(self):
        self.clear_class(EmailAddress)
        self.__updated = []

    def populate(self, local_part, domain_id, target_id, expire=None):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_addr_local_part = local_part
        self.email_addr_domain_id = domain_id
        self.email_addr_target_id = target_id
        self.email_addr_expire_date = expire

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.email_addr_id = int(self.nextval("email_id_seq"))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_address]
              (address_id, local_part, domain_id, target_id,
               create_date, change_date, expire_date)
            VALUES (:a_id, :lp, :d_id, :t_id, [:now], [:now], :expire)""",
                         {'a_id': self.email_addr_id,
                          'lp': self.email_addr_local_part,
                          'd_id': self.email_addr_domain_id,
                          't_id': self.email_addr_target_id,
                          'expire': self.email_addr_expire_date})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_address]
            SET local_part=:lp, domain_id=:d_id, target_id=:t_id,
                expire_date=:expire, change_date=[:now]
            WHERE address_id=:a_id""",
                         {'a_id': self.email_addr_id,
                          'lp': self.email_addr_local_part,
                          'd_id': self.email_addr_domain_id,
                          't_id': self.email_addr_target_id,
                          'expire': self.email_addr_expire_date})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, address_id):
        (self.email_addr_id, self.email_addr_local_part,
         self.email_addr_domain_id, self.email_addr_target_id,
         self.email_addr_expire_date) = self.query_1("""
        SELECT address_id, local_part, domain_id, target_id, expire_date
        FROM [:table schema=cerebrum name=email_address]
        WHERE address_id=:a_id""", {'a_id': address_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []
        
    def delete(self):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_address]
        WHERE address_id=:e_id""", {'e_id': self.email_addr_id})

    def find_by_local_part_and_domain(self, local_part, domain_id):
        address_id = self._db.query_1("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_address]
        WHERE local_part=:lp AND domain_id=:d_id""",
                                      {'lp': local_part,
                                       'd_id': domain_id})
        self.find(address_id)

    def find_by_address(self, address):
        lp, dp = address.split('@')
        domain = EmailDomain(self._db)
        domain.find_by_domain(dp)
        self.find_by_local_part_and_domain(lp, domain.email_domain_id)

    def list_email_addresses(self):
        """Return address_id of all EmailAddress in database"""
        return self.query("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_address]""", fetchall=False)

    def list_email_addresses_ext(self, domain=None):
        """Return address_id, target_id, local_part and domainof all
        EmailAddress in database"""
        with_domain = ""
        if domain is not None:
            with_domain = " AND d.domain = :domain"
        return self.query("""
        SELECT a.address_id, a.target_id, a.local_part, d.domain
        FROM [:table schema=cerebrum name=email_address] a,
             [:table schema=cerebrum name=email_domain] d
        WHERE a.domain_id = d.domain_id""" + with_domain,
                          {'domain': domain},
                          fetchall=False)

    def list_target_addresses(self, target_id):
        """Return address_id, local_part and domain_id for target_id"""
        return self.query("""
        SELECT address_id, local_part, domain_id
        FROM [:table schema=cerebrum name=email_address]
        WHERE target_id = :t_id""",
                          {'t_id': target_id},
                          fetchall=False)

    def get_target_id(self):
        """Return target_id of this EmailAddress in database"""
        return self.email_addr_target_id

    def get_domain_id(self):
        """Return domain_id of this EmailAddress in database"""
        return self.email_addr_domain_id

    def get_localpart(self):
        """Return domain_id of this EmailAddress in database"""
        return self.email_addr_local_part

########################################################################
########################################################################
########################################################################


class EntityEmailDomain(Entity):
    """Mixin class for Entities that can be associated with an email domain."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('entity_email_domain_id', 'entity_email_affiliation')

    def clear(self):
        self.__super.clear()
        self.clear_class(EntityEmailDomain)
        self.__updated = []

    def populate_email_domain(self, domain_id, affiliation=None):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.entity_email_domain_id = domain_id
        self.entity_email_affiliation = affiliation

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        affiliation = self.entity_email_affiliation
        if affiliation is not None:
            affiliation = int(affiliation)
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_entity_domain]
              (entity_id, affiliation, domain_id)
            VALUES (:e_id, :aff, :dom_id)""",
                         {'e_id': self.entity_id,
                          'aff': affiliation,
                          'dom_id': self.entity_email_domain_id})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_entity_domain]
            SET affiliation = :aff, domain_id = :dom_id
            WHERE entity_id = :e_id AND
              ((:aff IS NULL AND affiliation IS NULL) OR
               affiliation = :aff)""", {'e_id': self.entity_id,
                                       'aff': affiliation,
                                       'dom_id': self.entity_email_domain_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, entity_id, affiliation=None):
        self.__super.find(entity_id)
        (self.entity_email_domain_id,
         self.entity_email_affiliation) = self.query_1("""
        SELECT domain_id, affiliation
        FROM [:table schema=cerebrum name=email_entity_domain]
        WHERE entity_id=:e_id AND
          ((:aff IS NULL AND affiliation IS NULL) OR
           affiliation=:aff)""", {'e_id': entity_id,
                                  'aff': affiliation})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def list_affiliations(self, domain_id=None):
        """Return all rows (entitity_id, affiliation, domain_id)
        associated with the e-mail domain domain_id, OR this entity
        and any affilation."""
        sql = """
        SELECT entity_id, affiliation, domain_id
        FROM [:table schema=cerebrum name=email_entity_domain]"""
        if domain_id:
            return self.query(sql + "WHERE domain_id=:d_id",
                              {'d_id': domain_id})
        return self.query(sql + "WHERE entity_id=:e_id",
                          {'e_id': self.entity_id})

    def delete(self):
        if self.entity_email_affiliation:
            aff_cond = "affiliation=:aff"
        else:
            aff_cond = "affiliation IS NULL"
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_entity_domain]
        WHERE entity_id=:e_id AND """ + aff_cond,
                            {'e_id': self.entity_id,
                             'aff': self.entity_email_affiliation})


class EmailQuota(EmailTarget):
    """Mixin class allowing quotas to be set on specific `EmailTarget`s."""
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_quota_soft', 'email_quota_hard')

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailQuota)
        self.__updated = []

    def populate(self, soft, hard, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_quota_soft = soft
        self.email_quota_hard = hard

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_quota]
              (target_id, quota_soft, quota_hard)
            VALUES (:t_id, :soft, :hard)""",
                         {'t_id': self.email_target_id,
                          'soft': self.email_quota_soft,
                          'hard': self.email_quota_hard})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_quota]
            SET quota_soft=:soft,
                quota_hard=:hard
            WHERE target_id=:t_id""", {'t_id': self.email_target_id,
                                       'soft': self.email_quota_soft,
                                       'hard': self.email_quota_hard})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        self.__super.find(target_id)
        self.email_quota_soft, self.email_quota_hard = self.query_1("""
        SELECT quota_soft, quota_hard
        FROM [:table schema=cerebrum name=email_quota]
        WHERE target_id=:t_id""", {'t_id': target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def delete(self):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_quota]
        WHERE target_id=:e_id""", {'e_id': self.email_target_id})

    def get_quota_soft(self):
        return self.email_quota_soft

    def get_quota_hard(self):
        return self.email_quota_hard

    def list_email_quota_ext(self):
        """Return all defined quotas; target_id, quota_soft and quota_hard."""
        return self.query("""
        SELECT target_id, quota_soft, quota_hard
        FROM [:table schema=cerebrum name=email_quota]""")


class EmailSpamFilter(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_spam_level', 'email_spam_action')

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailSpamFilter)
        self.__updated = []

    def populate(self, level, action, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_spam_level = level
        self.email_spam_action = action

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_spam_filter]
              (target_id, level, action)
            VALUES (:t_id, :level, :action)""",
                         {'t_id': self.email_target_id,
                          'level': int(self.email_spam_level),
                          'action': int(self.email_spam_action)})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_spam_filter]
            SET level=:level,
                action=:action
            WHERE target_id=:t_id""", {'t_id': self.email_target_id,
                                       'level': int(self.email_spam_level),
                                       'action': int(self.email_spam_action)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        self.__super.find(target_id)
        self.email_spam_level, self.email_spam_action = self.query_1("""
        SELECT level, action
        FROM [:table schema=cerebrum name=email_spam_filter]
        WHERE target_id=:t_id""",{'t_id': self.email_target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def get_spam_level(self):
        level = self._db.pythonify_data(self.email_spam_level)
        if isinstance(level, int):
            level = _EmailSpamLevelCode(level)
        elif isinstance(level, _EmailSpamLevelCode):
            pass
        else:
            raise TypeError
        return level.get_level()

    def get_spam_action(self):
        action = self._db.pythonify_data(self.email_spam_action)
        action = _EmailSpamActionCode(action)
        return action

    def list_email_spam_filters_ext(self):
        """Join between spam_filter, email_spam_level_code and
        email_spam_action_code. Returns target_id, level and code_str."""
        return self.query("""
        SELECT f.target_id, l.level, a.code_str
        FROM [:table schema=cerebrum name=email_spam_filter] f,
             [:table schema=cerebrum name=email_spam_level_code] l,
             [:table schema=cerebrum name=email_spam_action_code] a
        WHERE f.level = l.code AND f.action = a.code""")

class EmailVirusScan(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_virus_found_act', 'email_virus_removed_act',
                      'email_virus_enable')

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailVirusScan)
        self.__updated = []

    def populate_virus_scan(self, found_action, removed_action, enable):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_virus_found_act = found_action
        self.email_virus_removed_act = removed_action
        self.email_virus_enable = enable

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_virus_scan]
              (target_id, found_action, rem_action, enable)
            VALUES (:t_id, :found, :removed, :enable)""",
                         {'t_id': self.email_target_id,
                          'found': self.email_virus_found_act,
                          'removed': self.email_virus_removed_act,
                          'enable': self.email_virus_enable})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_virus_scan]
            SET found_action=:found, rem_action=:remove, enable=:enable
            WHERE target_id=:t_id""",
                         {'t_id': self.email_target_id,
                          'found': self.email_virus_found_act,
                          'removed': self.email_virus_removed_act,
                          'enable': self.email_virus_enable})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        self.__super.find(target_id)
        (self.email_virus_found_act, self.email_virus_removed_act,
         self.email_virus_enable) = self.query_1("""
        SELECT found_action, rem_action, enable
        FROM [:table schema=cerebrum name=email_virus_scan]
        WHERE target_id=:t_id""",{'t_id': self.email_target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def get_enable(self):
        if self.email_virus_enable == "T":
            return True
        return False

    def get_virus_found_act(self):
        found = self._db.pythonify_data(self.email_virus_found_act)
        found = _EmailVirusFoundCode(found)
        return found

    def get_virus_removed_act(self):
        removed = self._db.pythonify_data(self.email_virus_removed_act)
        removed = _EmailVirusRemovedCode(removed)
        return removed

    def list_email_virus_ext(self):
        """Join between email_virus_scan, email_virus_found_code and
        email_virus_removed_code. Returns target_id, found_str(code from
        email_virus_found_code), removed_str(code from email_virus_removed_code)
        and enable."""
        return self.query("""
        SELECT s.target_id, f.code_str AS found_str, r.code_str AS removed_str, s.enable
        FROM [:table schema=cerebrum name=email_virus_scan] s,
             [:table schema=cerebrum name=email_virus_found_code] f,
             [:table schema=cerebrum name=email_virus_removed_code] r
        WHERE s.found_action = f.code AND s.rem_action = r.code""")

class EmailForward(EmailTarget):

    def add_forward(self, forward, enable=True):
        enable = 'F'
        if enable:
            enable = 'T'
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_forward]
          (target_id, forward_to, enable)
        VALUES (:t_id, :forward, :enable)""", {'t_id': self.email_target_id,
                                               'forward': forward,
                                               'enable': enable})

    def _set_forward_enable(self, forward, enable):
        return self.execute("""
        UPDATE [:table schema=cerebrum name=email_forward]
        SET enable=:enable
        WHERE target_id = :t_id AND
              forward_to = :fwd""", {'enable': enable,
                                     'fwd': forward,
                                     't_id': self.email_target_id})

    def enable_forward(self, forward):
        return self._set_forward_enable(forward, 'T')

    def disable_forward(self, forward):
        return self._set_forward_enable(forward, 'F')

    def get_forward(self):
        return self.query("""
        SELECT forward_to, enable
        FROM [:table schema=cerebrum name=email_forward]
        WHERE target_id=:t_id""", {'t_id': self.email_target_id})

    def delete_forward(self, forward):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_forward]
        WHERE target_id=:t_id AND forward_to=:forward""",
                            {'t_id': self.email_target_id,
                             'forward': forward})

    def list_email_forwards(self):
        return self.query("""
        SELECT target_id, forward_to, enable
        FROM [:table schema=cerebrum name=email_forward]
        """, fetchall=False)

class EmailVacation(EmailTarget):

    def add_vacation(self, start, text, end=None, enable=False):
        # TODO: Should use DDL-imposed default values if not
        # instructed otherwise.
        if enable:
            enable = 'T'
        else:
            enable = 'F'
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_vacation]
          (target_id, start_date, vacation_text, end_date, enable)
        VALUES (:t_id, :start, :text, :end, :enable)""",
                            {'t_id': self.email_target_id,
                             'start': start,
                             'text': text,
                             'end': end,
                             'enable': enable})

    def enable_vacation(self, start, enable=True):
        if enable:
            enable = 'T'
        else:
            enable = 'F'
        return self.execute("""
        UPDATE [:table schema=cerebrum name=email_vacation]
        SET enable=:enable
        WHERE target_id=:t_id AND start_date=:start""",
                            {'t_id': self.email_target_id,
                             'start': start,
                             'enable': enable})

    def disable_vacation(self, start):
        return self.enable_vacation(start, False)

    def get_vacation(self):
        return self.query("""
        SELECT vacation_text, start_date, end_date, enable
        FROM [:table schema=cerebrum name=email_vacation]
        WHERE target_id=:t_id
        ORDER BY start_date""", {'t_id': self.email_target_id})

    def delete_vacation(self, start):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_vacation]
        WHERE target_id=:t_id AND start_date=:start""",
                            {'t_id': self.email_target_id,
                             'start': start})

    def list_email_vacations(self):
        return self.query("""
        SELECT target_id, vacation_text, start_date, end_date, enable
        FROM [:table schema=cerebrum name=email_vacation]
        """, fetchall=False)

class EmailPrimaryAddressTarget(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_primaddr_id',)

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailPrimaryAddressTarget)
        self.__updated = []

    def populate(self, address_id, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            if parent is None:
                raise RuntimeError, \
                      "Can't populate EmailPrimaryAddressTarget w/o parent."
            self.__in_db = False
        self.email_primaddr_id = address_id

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_primary_address]
              (target_id, address_id)
            VALUES (:t_id, :addr_id)""",
                         {'t_id': self.email_target_id,
                          'addr_id': self.email_primaddr_id})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_primary_address]
            SET address_id=:addr_id
            WHERE target_id=:t_id""", {'t_id': self.email_target_id,
                                       'addr_id': self.email_primaddr_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Delete primary address.  Note that this will _not_ call
        delete() in parent.  If you want to delete the EmailTarget as
        well, you need to do so explicitly."""
        ret = self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_primary_address]
        WHERE target_id=:e_id""", {'e_id': self.email_target_id})

    def find(self, target_id):
        self.__super.find(target_id)
        self.email_primaddr_id = self.query_1("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_primary_address]
        WHERE target_id=:t_id""", {'t_id': self.email_target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def list_email_primary_address_targets(self):
        return self.query("""
        SELECT target_id, address_id
        FROM [:table schema=cerebrum name=email_primary_address]""",
                          fetchall=False)

    def get_address_id(self):
        return self.email_primaddr_id


class EmailServer(Host):
    __read_attr__ = ('__in_db', )
    __write_attr__ = ('email_server_type', )

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailServer)
        self.__updated = []

    def populate(self, server_type, name=None, description=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Host.populate(self, name, description)
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_server_type = server_type

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_server]
              (server_id, server_type)
            VALUES (:s_id, :type)""",
                         {'s_id': self.entity_id,
                          'type': int(self.email_server_type)})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_server]
            SET server_type=:type
            WHERE server_id=:s_id""", {'s_id': self.entity_id,
                                       'type': int(self.email_server_type)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, server_id):
        self.__super.find(server_id)
        self.email_server_type = self.query_1("""
        SELECT server_type
        FROM [:table schema=cerebrum name=email_server]
        WHERE server_id=:s_id""", {'s_id': self.entity_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def list_email_server_ext(self):
        return self.query("""
        SELECT s.server_id, s.server_type, h.name
        FROM [:table schema=cerebrum name=email_server] s,
             [:table schema=cerebrum name=host_info] h
        WHERE s.server_id = h.host_id
        """, fetchall=False)

class EmailServerTarget(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_server_id',)

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailServerTarget)
        self.__updated = []

    def populate(self, server_id, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            if parent is None:
                raise RuntimeError, \
                      "Can't populate EmailServerTarget w/o parent."
            self.__in_db = False
        self.email_server_id = server_id

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_target_server]
              (target_id, server_id)
            VALUES (:t_id, :srv_id)""",
                         {'t_id': self.email_target_id,
                          'srv_id': self.email_server_id})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_target_server]
            SET server_id=:srv_id
            WHERE target_id=:t_id""", {'t_id': self.email_target_id,
                                       'srv_id': self.email_server_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        self.__super.find(target_id)
        self.email_server_id = self.query_1("""
        SELECT server_id
        FROM [:table schema=cerebrum name=email_target_server]
        WHERE target_id=:t_id""", {'t_id': self.email_target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def get_server_id(self):
        return self.email_server_id

    def list_email_server_targets(self):
        return self.query("""
        SELECT target_id, server_id
        FROM [:table schema=cerebrum name=email_target_server]
        """, fetchall=False)

class AccountEmailMixin(Account.Account):
    """Email-module mixin for core class ``Account''."""

    def write_db(self):
        # Make sure Account is present in database.
        ret = self.__super.write_db()
        if ret is not None:
            # Account.write_db() seems to have made changes.  Verify
            # that this Account has the email addresses it should,
            # creating those not present.
            self.update_email_addresses()
        return ret

    def update_email_addresses(self):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_expired() or self.is_reserved():
            target_type = self.const.email_target_deleted
        try:
            et.find_by_email_target_attrs(entity_id = self.entity_id)
            et.email_target_type = target_type
        except Errors.NotFoundError:
            # We don't want to create e-mail targets for reserved or
            # deleted accounts, but we do convert the type of existing
            # e-mail targets above.
            if target_type == self.const.email_target_deleted:
                return
            et.populate(target_type, self.entity_id, self.const.entity_account)
        et.write_db()
        # For deleted/reserved users, set expire_date for all of the
        # user's addresses, and don't allocate any new addresses.
        ea = EmailAddress(self._db)
        if target_type == self.const.email_target_deleted:
            expire_date = self._db.DateFromTicks(time.time() +
                                                 60 * 60 * 24 * 180)
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                if ea.email_addr_expire_date is None:
                    ea.email_addr_expire_date = expire_date
                ea.write_db()
            return
        # Until a user's email target is associated with an email
        # server, the mail system won't know where to deliver mail for
        # that user.  Hence, we return early (thereby avoiding
        # creation of email addresses) for such users.
        est = EmailServerTarget(self._db)
        try:
            est.find(et.email_target_id)
        except Errors.NotFoundError:
            return
        # Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
        ed = EmailDomain(self._db)
        ed.find(self.get_primary_maildomain())
        domains = [ed.email_domain_name]
        if cereconf.EMAIL_DEFAULT_DOMAIN not in domains:
            domains.append(cereconf.EMAIL_DEFAULT_DOMAIN)
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
        primary_set = False
        epat = EmailPrimaryAddressTarget(self._db)
        for domain in domains:
            if ed.email_domain_name <> domain:
                ed.clear()
                ed.find_by_domain(domain)
            # Check for 'cnaddr' category before 'uidaddr', to prefer
            # 'cnaddr'-style primary addresses for users in
            # maildomains that have both categories.
            ctgs = [int(r['category']) for r in ed.get_categories()]
            local_parts = []
            if int(self.const.email_domain_category_cnaddr) in ctgs:
                local_parts.append(self.get_email_cn_local_part())
                local_parts.append(self.account_name)
            elif int(self.const.email_domain_category_uidaddr) in ctgs:
                local_parts.append(self.account_name)
            for lp in local_parts:
                lp = self.wash_email_local_part(lp)
                # Is the address taken?
                ea.clear()
                try:
                    ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
                    if ea.email_addr_target_id <> et.email_target_id:
                        # Address already exists, and points to a
                        # target not owned by this Account.
                        continue
                    # Address belongs to this account; make sure
                    # there's no expire_date set on it.
                    ea.email_addr_expire_date = None
                except Errors.NotFoundError:
                    # Address doesn't exist; create it.
                    ea.populate(lp, ed.email_domain_id, et.email_target_id,
                                expire=None)
                ea.write_db()
                if not primary_set:
                    epat.clear()
                    try:
                        epat.find(ea.email_addr_target_id)
                        epat.populate(ea.email_addr_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.email_addr_id, parent = et)
                    epat.write_db()
                    primary_set = True

    def get_email_cn_local_part(self, given_names=-1, max_initials=None):
        """
        Construct a "pretty" local part.

        If given_names=-1, keep the given name if the person has only
        one, but reduce them to initials only when the person has more
        than one.
           "John"                  -> "john"
           "John Doe"              -> "john.doe"
           "John Ronald Doe"       -> "j.r.doe"
           "John Ronald Reuel Doe" -> "j.r.r.doe"

        If given_names=0, only initials are included
           "John Ronald Doe"       -> "j.r.doe"

        If given_names=1, the first given name will always be included
           "John Ronald Doe"       -> "john.r.doe"

        If max_initials is set, no more than this number of initials
        will be included.  With max_initials=1 and given_names=-1
           "John Doe"              -> "john.doe"
           "John Ronald Reuel Doe" -> "j.doe"

        With max_initials=1 and given_names=1
           "John Ronald Reuel Doe" -> "john.r.doe"
        """

        assert(given_names >= -1)
        assert(max_initials is None or max_initials >= 0)

        try:
            full = self.get_fullname()
        except Errors.NotFoundError:
            full = self.account_name
        names = [x.lower() for x in re.split(r'\s+', full)]
        last = names.pop(-1)
        names = [x for x in '-'.join(names).split('-') if x]

        if given_names == -1:
            if len(names) == 1:
                # Person has only one name, use it in full
                given_names = 1
            else:
                # Person has more than one name, only use initials
                given_names = 0

        if len(names) > given_names:
            initials = [x[0] for x in names[given_names:]]
            if max_initials is not None:
                initials = initials[:max_initials]
            names = names[:given_names] + initials
        names.append(last)
        return self.wash_email_local_part(".".join(names))

    def get_fullname(self):
        if self.owner_type <> self.const.entity_person:
            # In the Cerebrum core, there is only one place the "full
            # name" of an account can be registered: As the full name
            # of the person owner.  Hence, for non-personal accounts,
            # we just use the account name.
            #
            # Note that the situation may change for specialisations
            # of the core Account class; e.g. the PosixUser class
            # allows full name to be registered directly on the
            # account, in the `gecos' attribute.  To take such
            # specialisations into account (for *all* your users),
            # override this method in an appropriate subclass, and set
            # cereconf.CLASS_ACCOUNT accordingly.
            raise Errors.NotFoundError, \
                  "No full name for non-personal account."
        p = Utils.Factory.get("Person")(self._db)
        p.find(self.owner_id)
        full = p.get_name(self.const.system_cached, self.const.name_full)
        return full

    def get_primary_maildomain(self):
        """Return correct `domain_id' for account's primary address."""
        dom = EmailDomain(self._db)
        dom.find_by_domain(cereconf.EMAIL_DEFAULT_DOMAIN)
        entdom = EntityEmailDomain(self._db)
        # Find OU and affiliation for this user's best-priority
        # account_type entry.
        for row in self.get_account_types():
            ou, aff = row['ou_id'], row['affiliation']
            # If a maildomain is associated with this (ou, aff)
            # combination, then that is the user's default maildomain.
            entdom.clear()
            try:
                entdom.find(ou, affiliation=aff)
                # If the default domain is specified, ignore this
                # affiliation.
                if entdom.entity_email_domain_id == dom.email_domain_id:
                    continue
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
            # Otherwise, try falling back to tha maildomain associated
            # with (ou, None).
            entdom.clear()
            try:
                entdom.find(ou)
                if entdom.entity_email_domain_id == dom.email_domain_id:
                    continue
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
        # Still no proper maildomain association has been found; fall
        # back to default maildomain.
        return dom.email_domain_id

    def get_primary_mailaddress(self):
        """Return account's current primary address."""
        r = self.query_1("""
        SELECT ea.local_part, ed.domain
        FROM [:table schema=cerebrum name=account_info] ai
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_primary_address] epa
          ON epa.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.address_id = epa.address_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE ai.account_id = :e_id""",
                              {'e_id': int(self.entity_id)})
        ed = EmailDomain(self._db)
        return (r['local_part'] + '@' +
                ed.rewrite_special_domains(r['domain']))

    def getdict_uname2mailaddr(self, filter_expired=True):
        ret = {}
        target_type = int(self.const.email_target_account)
        namespace = int(self.const.account_namespace)
        ed = EmailDomain(self._db)
        where = "en.value_domain = :namespace"
        if filter_expired:
            where += " AND (ai.expire_date IS NULL OR ai.expire_date > [:now])"
        for row in self.query("""
        SELECT en.entity_name, ea.local_part, ed.domain
        FROM [:table schema=cerebrum name=account_info] ai
        JOIN [:table schema=cerebrum name=entity_name] en
          ON en.entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_type = :targ_type AND
             et.entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_primary_address] epa
          ON epa.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.address_id = epa.address_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE """ + where,
                              {'targ_type': target_type,
                               'namespace': namespace}):
            ret[row['entity_name']] = '@'.join((
                row['local_part'],
                ed.rewrite_special_domains(row['domain'])))
        return ret

    def wash_email_local_part(self, local_part):
        lp = Utils.latin1_to_iso646_60(local_part)
        # Translate ISO 646-60 representation of Norwegian characters
        # to the closest single-ascii-letter.
        xlate = {'[': 'A', '{': 'a',
                 '\\': 'O', '|': 'o',
                 ']': 'A', '}': 'a'}
        lp = ''.join([xlate.get(c, c) for c in lp])
        # Don't use caseful local-parts; lowercase them before they're
        # written to the database.
        lp = lp.lower()
        # Retain only characters that are likely to be intentionally
        # used in local-parts.
        allow_chars = string.ascii_lowercase + string.digits + '-_.'
        lp = "".join([c for c in lp if c in allow_chars])
        # The '.' character isn't allowed at the start or end of a
        # local-part.
        while lp.startswith('.'):
            lp = lp[1:]
        while lp.endswith('.'):
            lp = lp[:-1]
        if not lp:
            raise ValueError, "Local-part can't be empty (%r -> %r)" % (
                local_part, lp)
        return lp

    def set_account_type(self, *param, **kw):
        ret = self.__super.set_account_type(*param, **kw)
        self.update_email_addresses()
        return ret

    def del_account_type(self, *param, **kw):
        ret = self.__super.del_account_type(*param, **kw)
        self.update_email_addresses()
        return ret

    def add_spread(self, *param, **kw):
        ret = self.__super.add_spread(*param, **kw)
        self.update_email_addresses()
        return ret

    def delete_spread(self, *param, **kw):
        ret = self.__super.delete_spread(*param, **kw)
        self.update_email_addresses()
        return ret


class AccountEmailQuotaMixin(Account.Account):
    """Email-quota module for core class 'Account'."""

    def update_email_quota(self, force=False):
        """Set e-mail quota according to values in cereconf.EMAIL_HARD_QUOTA.
         EMAIL_HARD_QUOTA is in MiB andbased on affiliations.
         If cereconf.EMAIL_ADD_QUOTA_REQUEST = True, any change is made and
         user's e-mail is on a Cyrus server, add a request in Cerebrum to have
         Cyrus updated accordingly.  If force is true, such a request is always
         made for Cyrus users (i.e. quota < new_quota).
         Soft quota is in percent, fetched from EMAIL_SOFT_QUOTA."""
        change = force
        quota = self._calculate_account_emailquota()
        eq = EmailQuota(self._db)
        try:
            eq.find_by_entity(self.entity_id)
        except Errors.NotFoundError:
            if quota is not None:
                change = True
                eq.populate(cereconf.EMAIL_SOFT_QUOTA, quota)
                eq.write_db()
        else:
            # We never decrease the quota, to allow for manual overrides
            if quota is None:
                eq.delete()
            elif quota > eq.email_quota_hard:
                change = True
                eq.email_quota_hard = quota
                eq.write_db()
        if not change:
            return
        if cereconf.EMAIL_ADD_QUOTA_REQUEST:
            from Cerebrum.modules.bofhd.utils import BofhdRequests
            br = BofhdRequests(self._db, self.const)
            est = EmailServerTarget(self._db)
            try:
                est.find_by_entity(self.entity_id)
            except:
                return
            es = EmailServer(self._db)
            es.find(est.email_server_id)
            if es.email_server_type == self.const.email_server_type_cyrus:
                br = BofhdRequests(self._db, self.const)
                # The call graph is too complex when creating new users or
                # migrating old users.  So to avoid problems with this
                # function being called more than once, we just remove any
                # conflicting requests, so that the last request added
                # wins.
                br.delete_request(entity_id=self.entity_id,
                                  operation=self.const.bofh_email_hquota)
                # If the ChangeLog module knows who the user requesting
                # this change is, use that knowledge.  Otherwise, set
                # requestor to None; it's the best we can do.
                requestor = getattr(self._db, 'change_by', None)
                br.add_request(requestor, br.now, self.const.bofh_email_hquota,
                               self.entity_id, None)

    # Calculate quota for this account 
    def _calculate_account_emailquota(self):
        quota_settings = cereconf.EMAIL_HARD_QUOTA
        if quota_settings is None:
            return None
        # '*' is default quota size in EMAIL_HARD_QUOTA dict
        max_quota = quota_settings['*']
        for r in self.get_account_types():
            affiliation = str(self.const.PersonAffiliation(r['affiliation']))
            if quota_settings.has_key(affiliation):
                # always choose the largest quota
                if quota_settings[affiliation] is None:
                    return None
                if quota_settings[affiliation] > max_quota:
                    max_quota = quota_settings[affiliation]
        return max_quota


class PersonEmailMixin(Person.Person):

    """Email-module mixin for core class ``Person''."""

    def list_primary_email_address(self, entity_type):
        """Returns a list of (entity_id, address) pairs for entities
        of type 'entity_type'"""
        return self._id2mailaddr(entity_type=entity_type).items()

    def _update_cached_names(self):
        self.__super._update_cached_names()
        acc = Utils.Factory.get('Account')(self._db)
        for row in self.get_accounts():
            acc.clear()
            acc.find(row['account_id'])
            acc.update_email_addresses()

    def getdict_external_id2mailaddr(self, id_type):
        """Return dict mapping person_external_id to email for
        person_external_id type 'id_type'"""
        return self._id2mailaddr(id_type=id_type)

    def _id2mailaddr(self, id_type=None, entity_type=None, filter_expired=True):
        ret = {}
        # TODO: How should multiple external_id entries, only
        # differing in person_external_id.source_system, be treated?
        target_type = int(self.const.email_target_account)
        if id_type is not None:
            id_type = int(id_type)
            select_col = "eei.external_id"
            main_table = "[:table schema=cerebrum name=entity_external_id] eei"
            primary_col = "eei.entity_id"
            where = "eei.id_type = :id_type"
            key_col = 'external_id'
        else:
            entity_type = int(entity_type)
            select_col = "ei.entity_id"
            main_table = "[:table schema=cerebrum name=entity_info] ei"
            primary_col = "ei.entity_id"
            where = "ei.entity_type=:entity_type"
            key_col = 'entity_id'

        if filter_expired:
            expired_table = ", [:table schema=cerebrum name=account_info] ai"
            expired_where = (" AND ai.account_id = at2.account_id " +
                              " AND (ai.expire_date IS NULL OR " +
                              "      ai.expire_date > [:now])")
        else:
            expired_where = expired_table = ""

        ed = EmailDomain(self._db)
        for row in self.query("""
        SELECT %s, ea.local_part, ed.domain
        FROM %s
        JOIN [:table schema=cerebrum name=account_type] at
          ON at.person_id = %s AND
             at.priority = (SELECT min(at2.priority)
                            FROM [:table schema=cerebrum name=account_type] at2
                                 %s
                            WHERE at2.person_id = %s %s)
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_type = :targ_type AND
             et.entity_id = at.account_id
        JOIN [:table schema=cerebrum name=email_primary_address] epa
          ON epa.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.address_id = epa.address_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE %s""" % (select_col, main_table, primary_col, expired_table,
                       primary_col, expired_where, where),
                              {'id_type': id_type,
                               'targ_type': target_type,
                               'entity_type': entity_type}):
            ret[row[key_col]] = '@'.join((
                row['local_part'],
                ed.rewrite_special_domains(row['domain'])))
        return ret

# arch-tag: f323adc6-a14f-441c-ab1d-ab203065cae8
