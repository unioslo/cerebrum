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



class _EmailTargetCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_target_code]'


class _EmailDomainCategoryCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_domain_cat_code]'


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

    email_target_account = _EmailTargetCode(
        'account',
        "Target is the local delivery defined for the Account whose"
        " account_id == email_target.entity_id.")

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
    __write_attr__ = ('email_domain_name', 'email_domain_category',
                      'email_domain_description')

    def clear(self):
        self.clear_class(EmailDomain)
        self.__updated = False

    def populate(self, domain, category, description):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.email_domain_name = domain
        self.email_domain_category = category
        self.email_domain_description = description

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.email_domain_id = int(self.nextval("email_id_seq"))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_domain]
              (domain_id, domain, category, description)
            VALUES (:d_id, :name, :category, :descr)""",
                         {'d_id': self.email_domain_id,
                          'name': self.email_domain_name,
                          'category': self.email_domain_category,
                          'descr': self.email_domain_description})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_domain]
            SET domain=:name, category=:category, description=:descr
            WHERE domain_id=:d_id""",
                         {'d_id': self.email_domain_id,
                          'name': self.email_domain_name,
                          'category': self.email_domain_category,
                          'descr': self.email_domain_description})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def find(self, domain_id):
        (self.email_domain_id, self.email_domain_name,
         self.email_domain_category,
         self.email_domain_description) = self.query_1("""
         SELECT domain_id, domain, category, description
         FROM [:table schema=cerebrum name=email_domain]
         WHERE domain_id=:d_id""", {'d_id': domain_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

    def find_by_domain(self, domain):
        domain_id = self.query_1("""
        SELECT domain_id
        FROM [:table schema=cerebrum name=email_domain]
        WHERE domain=:name""", {'name': domain})
        self.find(domain_id)

    def get_domain_name(self):
        return self.email_domain_name


class EmailTarget(EmailEntity):
    __read_attr__ = ('__in_db', 'email_target_id')
    __write_attr__ = ('email_target_type', 'email_target_entity_id',
                      'email_target_entity_type', 'email_target_alias')

    def clear(self):
        self.clear_class(EmailTarget)
        self.__updated = False

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
        if is_new:
            self.email_target_id = int(self.nextval("email_id_seq"))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_target]
              (target_id, target_type, entity_id, entity_type, alias_value)
            VALUES (:t_id, :t_type, :e_id, :e_type, :alias)""",
                         {'t_id': self.email_target_id,
                          't_type': self.email_target_type,
                          'e_id': self.email_target_entity_id,
                          'e_type': self.email_target_entity_type,
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
                          'e_type': self.email_target_entity_type,
                          'alias': self.email_target_alias})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
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
        self.__updated = False

    def find_by_entity(self, entity_id, entity_type):
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE entity_id=:e_id AND entity_type=:e_type""",
                                 {'e_id': entity_id,
                                  'e_type': entity_type})
        self.find(target_id)

    def find_by_alias(self, alias):
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE alias_value=:alias""", {'alias': alias})
        self.find(target_id)

    def get_all_email_targets(self):
        """Return target_id of all EmailTarget in database"""
        return self.query("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]""")


class EmailAddress(EmailEntity):
    __read_attr__ = ('__in_db', 'email_addr_id')
    __write_attr__ = ('email_addr_local_part', 'email_addr_domain_id',
                      'email_addr_target_id', 'email_addr_expire_date')
    def clear(self):
        self.clear_class(EmailAddress)
        self.__updated = False

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
        self.__updated = False
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
        self.__updated = False

    def find_by_address(self, address):
        lp, dp = address.split('@')
        domain = EmailDomain(self._db).find_by_domain(dp)
        address_id = self._db.query_1("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_address]
        WHERE local_part=:lp AND domain_id=:d_id""",
                                      {'lp': lp,
                                       'd_id': domain.email_domain_id})
        self.find(address_id)
    
    def get_all_email_addresses(self):
        """Return address_id of all EmailAddress in database"""
        return self.query("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_address]""")

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
    __write_attr__ = ('entity_email_domain_id',)

    def clear(self):
        self.__super.clear()
        self.clear_class(EntityEmailDomain)
        self.__updated = False

    def populate_email_domain(self, domain_id):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.entity_email_domain_id = domain_id

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_entity_domain]
              (entity_id, entity_type, domain_id)
            VALUES (:e_id, :e_type, :dom_id)""",
                         {'e_id': self.entity_id,
                          'e_type': int(self.entity_type),
                          'dom_id': self.entity_email_domain_id})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_entity_domain]
            SET domain_id=:dom_id
            WHERE entity_id=:e_id""", {'e_id': self.entity_id,
                                       'dom_id': self.entity_email_domain_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def find(self, entity_id):
        self.__super.find(entity_id)
        try:
            self.entity_email_domain_id = self.query_1("""
            SELECT domain_id
            FROM [:table schema=cerebrum name=email_entity_domain]
            WHERE entity_id=:e_id""", {'e_id': entity_id})
            in_db = True
        except Errors.NotFoundError:
            in_db = False
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = in_db
        self.__updated = False


class EmailQuota(EmailTarget):
    """Mixin class allowing quotas to be set on specific `EmailTarget`s."""
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_quota_soft', 'email_quota_hard')

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailQuota)
        self.__updated = False

    def populate_quota(self, soft, hard):
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
        self.__updated = False
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
        self.__updated = False

    def get_quota_soft(self):
        return self.email_quota_soft

    def get_quota_hard(self):
        return self.email_quota_hard


class _EmailSpamLevelCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_spam_level_code]'


class _EmailSpamActionCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_spam_action_code]'


class EmailSpamFilter(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_spam_level', 'email_spam_action')

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailSpamFilter)
        self.__updated = False

    def populate_spam_filter(self, level, action):
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
                          'level': self.email_spam_level,
                          'action': self.email_spam_action})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_spam_filter]
            SET level=:level,
                action=:action
            WHERE target_id=:t_id""", {'t_id': self.email_target_id,
                                       'level': self.email_spam_level,
                                       'action': self.email_spam_action})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
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
        self.__updated = False

    def get_spam_level(self):
        return self.email_spam_level

    def get_spam_action(self):
        return self.email_spam_action



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
        self.__updated = False

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
        self.__updated = False
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
        self.__updated = False

    def is_enabled(self):
        if self.email_virus_enable == "T":
            return True
        return False

    def get_virus_found_act(self):
        return self.email_virus_found_act

    def get_virus_removed_act(self):
        return self.email_virus_removed_act


class EmailForward(EmailTarget):
    def find(self, account_id): pass
    def populate_forward(self, address, enable): pass
    def write_db(self): pass
    def list_forward(self): pass


class EmailVacation(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_vacation_start', 'email_vacation_text',
                      'email_vacation_end', 'email_vacation_enable')

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailVacation)
        self.__updated = False

    def populate_vacation(self, start_date, message, end_date, enable): pass
    def find(self, target_id): pass
    def write_db(self): pass
    def list_vacation(self): pass


class EmailPrimaryAddress(EmailTarget):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_primaddr_id',)

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailPrimaryAddress)
        self.__updated = False

    def populate(self, address_id):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
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
        self.__updated = False
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
        self.__updated = False
