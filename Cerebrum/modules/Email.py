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

"""."""

from Cerebrum import Utils
from Cerebrum import Constants
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import Entity
from Cerebrum.Disk import Host
from Cerebrum import Person
from Cerebrum import Account

import cereconf

class _EmailTargetCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_target_code]'


class _EmailDomainCategoryCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_domain_cat_code]'


class _EmailServerTypeCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_server_type_code]'


class EmailConstants(Constants.Constants):

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
        "Target is the local delivery defined for the Account whose"
        " account_id == email_target.entity_id.")

    email_target_deleted = _EmailTargetCode(
        'deleted',
        "Target type for addresses that are no longer working, but"
        " for which it is useful to include of a short custom text in"
        " the error message returned to the sender.  The text"
        " is taken from email_target.alias_value")

    email_target_forward = _EmailTargetCode(
        'forward',
        "Target is a pure forwarding mechanism; local deliveries will"
        " only occur as indirect deliveries to the addresses forwarded"
        " to.  Both email_target.entity_id and email_target.alias_value"
        " should be NULL, as they are ignored.  The email address(es)"
        " to forward to is taken from table email_forward.")

    email_target_file = _EmailTargetCode(
        'file',
        "Target is a file.  The absolute path of the file is gathered"
        " from email_target.alias_value.  Iff email_target.entity_id"
        " is set and belongs to an Account, deliveries to this target"
        " will be run as that account.")

    email_target_pipe = _EmailTargetCode(
        'pipe',
        "Target is a shell pipe.  The command (and args) to pipe mail"
        " into is gathered from email_target.alias_value.  Iff"
        " email_target.entity_id is set and belongs to an Account,"
        " deliveries to this target will be run as that account.")

    email_target_Mailman = _EmailTargetCode(
        'Mailman',
        "Target is a Mailman mailing list.  The command (and args) to"
        " pipe mail into is gathered from email_target.alias_value."
        "  Iff email_target.entity_id is set and belongs to an"
        " Account, deliveries to this target will be run as that"
        " account.")

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
                                  'cat': category})

    def remove_category(self, category):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_domain_category]
        WHERE domain_id=:d_id""", {'d_id': self.email_domain_id})

    def list_email_domains_with_category(self, category):
        return self.query("""
        SELECT ed.domain_id, ed.domain
        FROM [:table schema=cerebrum name=email_domain] ed,
        JOIN [:table schema=cerebrum name=email_domain_category] edc
          ON edc.domain_id = ed.domain_id
        WHERE edc.category = :cat""", {'cat': int(category)})

    def list_email_domains(self):
        return self.query("""
        SELECT domain_id, domain
        FROM [:table schema=cerebrum name=email_domain]""")


class EmailTarget(EmailEntity):
    __read_attr__ = ('__in_db', 'email_target_id')
    __write_attr__ = ('email_target_type', 'email_target_entity_id',
                      'email_target_entity_type', 'email_target_alias')

    def clear(self):
        self.clear_class(EmailTarget)
        self.__updated = []

    def populate(self, type, entity_id=None, entity_type=None, alias=None):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_target_type = type
        self.email_target_alias = alias
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
              (target_id, target_type, entity_id, entity_type, alias_value)
            VALUES (:t_id, :t_type, :e_id, :e_type, :alias)""",
                         {'t_id': self.email_target_id,
                          't_type': int(self.email_target_type),
                          'e_id': self.email_target_entity_id,
                          'e_type': entity_type,
                          'alias': self.email_target_alias})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_target]
            SET target_type=:t_type, entity_id=:e_id, entity_type=:e_type,
                alias_value=:alias
            WHERE target_id=:t_id""",
                         {'t_id': self.email_target_id,
                          't_type': self.email_target_type,
                          'e_id': self.email_target_entity_id,
                          'e_type': entity_type,
                          'alias': self.email_target_alias})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        (self.email_target_id, self.email_target_type,
         self.email_target_entity_id, self.email_target_entity_type,
         self.email_target_alias) = self.query_1("""
        SELECT target_id, target_type, entity_id, entity_type, alias_value
        FROM [:table schema=cerebrum name=email_target]
        WHERE target_id=:t_id""", {'t_id': target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_entity(self, entity_id, entity_type):
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE entity_id=:e_id AND entity_type=:e_type""",
                                 {'e_id': entity_id,
                                  'e_type': int(entity_type)})
        self.find(target_id)

    def find_by_alias(self, alias):
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE alias_value=:alias""", {'alias': alias})
        self.find(target_id)

    def find_by_entity_and_alias(self, entity_id, alias):
        # Due to the UNIQUE constraint in table email_target, this
        # should never find more than one row.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE entity_id=:e_id AND alias_value=:alias""",
                                 {'e_id': entity_id,
                                  'alias': alias})
        self.find(target_id)

    def list_email_targets(self):
        """Return target_id of all EmailTarget in database"""
        return self.query("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]""", fetchall=False)

    def list_email_targets_ext(self):
        """Returns target_id, target_type, entity_type, entity_id and
        alias_value"""
        return self.query("""
        SELECT target_id, target_type, entity_type, entity_id, alias_value
        FROM [:table schema=cerebrum name=email_target]
        """, fetchall=False)
        
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
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_entity_domain]
              (entity_id, affiliation, domain_id)
            VALUES (:e_id, :aff, :dom_id)""",
                         {'e_id': self.entity_id,
                          'aff': int(self.entity_email_affiliation),
                          'dom_id': self.entity_email_domain_id})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_entity_domain]
            SET affiliation=:aff, domain_id=:dom_id
            WHERE entity_id=:e_id""", {'e_id': self.entity_id,
                                       'aff': self.entity_email_affiliation,
                                       'dom_id': self.entity_email_domain_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, entity_id, affiliation=None):
        self.__super.find(entity_id)
        try:
            (self.entity_email_domain_id,
             self.entity_email_affiliation) = self.query_1("""
            SELECT domain_id, affiliation
            FROM [:table schema=cerebrum name=email_entity_domain]
            WHERE entity_id=:e_id AND
                  affiliation=:aff""", {'e_id': entity_id,
                                        'aff': affiliation})
            in_db = True
        except Errors.NotFoundError:
            in_db = False
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = in_db
        self.__updated = []

    def delete(self, affiliation=None):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_entity_domain]
        WHERE entity_id=:e_id AND
              affiliation=:aff""", {'e_id': self.entity_id,
                                    'aff': affiliation})


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

    def get_quota_soft(self):
        return self.email_quota_soft

    def get_quota_hard(self):
        return self.email_quota_hard

    def list_email_quota_ext(self):
        """Return all defined quotas; target_id, quota_soft and quota_hard."""
        return self.query("""
        SELECT target_id, quota_soft, quota_hard
        FROM [:table schema=cerebrum name=email_quota]""")

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

class _EmailVirusFoundCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_virus_found_code]'


class _EmailVirusRemovedCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_virus_removed_code]'


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
        WHERE target_id=:t_id""", {'t_id': self.email_target_id,
                                   'enable': enable})

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
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_vacation]
          (target_id, start_date, vacation_text, end_date, enable)
        VALUES (:t_id, :start, :text, :end, :enable)""",
                            {'t_id': self.email_target_id,
                             'start': start,
                             'text': text,
                             'end': end,
                             'enable': enable})

    def _set_vacation_enable(self, start, enable):
        return self.execute("""
        UPDATE [:table schema=cerebrum name=email_vacation]
        SET enable=:enable
        WHERE target_id=:t_id AND start_date=:start""",
                            {'t_id': self.email_target_id,
                             'start': start,
                             'enable': enable})

    def enable_vacation(self, start):
        return self._set_vacation_enable(start, True)

    def disable_vacation(self, start):
        return self._set_vacation_enable(start, False)

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
                raise RunTimeError, \
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
                raise RunTimeError, \
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
        ret = super(AccountEmailMixin, self).write_db()
        # Verify that Account has the email addresses it should,
        # creating those not present.
        self.update_email_addresses()
        return ret

    def update_email_addresses(self):
        ed = EmailDomain(self._db)
        ed.find(self.get_primary_domain())
        local_parts = [self.account_name]
        ea = EmailAddress(self._db)
        if self.const.email_domain_category_cnaddr in ed.get_categories():
            local_parts.insert(0, self.get_email_cn_local_part())


    def get_email_cn_local_part(self):
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
            return self.account_name
        p = Factory.get("Person")(self._db)
        p.find(self.owner_id)
##        full = p.get_name(self.const.source

    def get_primary_maildomain(self):
        """Return correct `domain_id' for account's primary address."""
        class UseDefaultDomainException(StandardError):
            pass
        try:
            # Find OU and affiliation for this user's best-priority
            # account_type entry.
            typs = self.get_account_types()
            if not typs:
                # If no appropriate account_type entries were found,
                # return the default maildomain.
                raise UseDefaultDomainException
            row = typs[0]
            ou, aff = row['ou_id'], row['affiliation']
            # If a maildomain is associated with this (ou, aff)
            # combination, then that is the user's default maildomain.
            entdom = EntityEmailDomain(self._db)
            try:
                entdom.find(ou, affiliation=aff)
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
            # Otherwise, try falling back to tha maildomain associated
            # with (ou, None).
            entdom.clear()
            try:
                entdom.find(ou)
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
            # Still no proper maildomain association has been found;
            # fall back to default maildomain.
            raise UseDefaultDomainException
        except UseDefaultDomainException:
            pass
        dom = EmailDomain(self._db)
        dom.find_by_domain(cereconf.EMAIL_DEFAULT_DOMAIN)
        return dom.email_domain_id

    def get_primary_mailaddress(self):
        """Return account's current primary address, or None."""
        target_type = int(self.const.email_target_account)
        return self.query("""
        SELECT ea.local_part || '@' || ed.domain AS email_primary_address
        FROM [:table schema=cerebrum name=account_type] at
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_type = :targ_type AND
             et.entity_id = at.account_id
        JOIN [:table schema=cerebrum name=email_primary_address] epa
          ON epa.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.address_id = epa.address_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE at.account_id = :e_id""",
                              {'e_id': int(self.entity_id),
                               'targ_type': target_type})

    def _calc_new_primary_mailaddress(self):
        dom_id = self.get_primary_maildomain()
        dom = EmailDomain(self._db)
        dom.find(dom_id)
        ctgs = dom.get_categories()
        if self.const.email_domain_category_cnaddr in ctgs:
            local_part = "" # TODO: Calculate this based on full name
        elif self.const.email_domain_category_uidaddr in ctgs:
            local_part = self.account_name
        else:
            # Neither username- nor fullname-based addresses should be
            # defined in the user's (apparent) default maildomain; use
            # username@EMAIL_DEFAULT_DOMAIN instead.
            local_part = self.account_name
            dom.clear()
            dom.find(cereconf.EMAIL_DEFAULT_DOMAIN)
        # Check that this address doesn't belong to something else.
        addr = EmailAddress(self._db)
        try:
            addr.find_by_local_part_and_domain(local_part,
                                               dom.get_domain_name())
            targ = EmailTarget(self._db)
            targ.find(addr.email_addr_target_id)
            if targ.email_target_type <> self.const.email_target_account or \
                   targ.email_target_entity_id <> self.entity_id:
                # Address exists, but this Account is not the owner.
                pass
        except Errors.NotFoundError:
            pass

        # Validate that value of local_part is proper for use as an
        # email address local part.


class PersonEmailMixin(Person.Person):

    """Email-module mixin for core class ``Person''."""

    def getdict_external_id2mailaddr(self, id_type):
        ret = {}
        # TODO: How should multiple external_id entries, only
        # differing in person_external_id.source_system, be treated?
        target_type = int(self.const.email_target_account)
        for row in self.query("""
        SELECT pei.external_id,
               ea.local_part || '@' || ed.domain AS email_primary_address
        FROM [:table schema=cerebrum name=person_external_id] pei
        JOIN [:table schema=cerebrum name=account_type] at
          ON at.person_id = pei.person_id AND
             at.priority = (SELECT min(at2.priority)
                            FROM [:table schema=cerebrum name=account_type] at2
                            WHERE at2.person_id = pei.person_id)
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_type = :targ_type AND
             et.entity_id = at.account_id
        JOIN [:table schema=cerebrum name=email_primary_address] epa
          ON epa.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.address_id = epa.address_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE pei.id_type = :id_type""",
                              {'id_type': int(id_type),
                               'targ_type': target_type}):
            ret[row['external_id']] = row['email_primary_address']
        return ret
