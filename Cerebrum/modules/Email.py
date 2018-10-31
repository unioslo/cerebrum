# -*- coding: utf-8 -*-
# Copyright 2003-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import re
import string
import time

import six

from Cerebrum import Utils
from Cerebrum.Utils import prepare_string, argument_to_sql
from Cerebrum.utils import transliterate
from Cerebrum.Entity import Entity
from Cerebrum.Disk import Host
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Errors
from EmailConstants import (_EmailTargetCode, _EmailSpamActionCode,
                            _EmailSpamLevelCode, _EmailVirusFoundCode,
                            _EmailVirusRemovedCode)
import cereconf

__version__ = "1.5"


Entity_class = Utils.Factory.get("Entity")


@six.python_2_unicode_compatible
class EmailDomain(Entity_class):
    """Interface to the email domains your MTA should consider as 'local'.

    Before any email address can be registered in Cerebrum, the domain
    part of the address must be registered.  A registered email domain
    can have any number of 'categories' associated with it."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_domain_name', 'email_domain_description')

    # TBD: missing __eq__

    def clear(self):
        # conv
        super(EmailDomain, self).clear()
        self.clear_class(EmailDomain)
        self.__updated = []

    def _validate_domain_name(self, domainname):
        """Utility method for checking that the given e-mail
        domainname adheres to current standards.

        @param domainname: Domainname that is to be checked.
        @type domainname: String

        @raise AttributeError: If domainname fails any of the checks.
        """
        uber_hyphen = re.compile(r'--+')
        valid_chars = re.compile(r'^[a-zA-Z\-0-9]+$')

        for element in domainname.split("."):
            if element.startswith("-") or element.endswith("-"):
                raise AttributeError("Illegal name: '%s';" % domainname +
                                     " Element cannot start or end with '-'")
            if uber_hyphen.search(element):
                raise AttributeError("Illegal name: '%s';" % domainname +
                                     " More than one '-' in a row")
            if not valid_chars.search(element):
                raise AttributeError("Illegal name: '%s';" % domainname +
                                     " Invalid character(s)")

    def populate(self, domain, description, parent=None):
        # conv
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_email_domain)
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self._validate_domain_name(domain)
        self.email_domain_name = domain
        self.email_domain_description = description

    def delete(self):
        # Need to clean up categories first
        for category_row in self.get_categories():
            self.remove_category(category_row['category'])
        # exchange-relatert-jazz
        # requires cl-use!
        self._db.log_change(self.entity_id, self.clconst.email_dom_rem, None,
                            change_params={
                                'del_domain': self.email_domain_name})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_domain]
        WHERE domain_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_domain]
              (domain_id, domain, description)
            VALUES (:d_id, :name, :descr)""",
                         {'d_id': self.entity_id,
                          'name': self.email_domain_name,
                          'descr': self.email_domain_description})
            # exchange-relatert-jazz
            self._db.log_change(self.entity_id, self.clconst.email_dom_add,
                                None,
                                change_params={
                                    'new_domain_name': self.email_domain_name,
                                    'new_domain_desc':
                                        self.email_domain_description})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_domain]
            SET domain=:name, description=:descr
            WHERE domain_id=:d_id""",
                         {'d_id': self.entity_id,
                          'name': self.email_domain_name,
                          'descr': self.email_domain_description})
            # exchange-relatert-jazz
            self._db.log_change(self.entity_id, self.clconst.email_dom_mod,
                                None,
                                change_params={
                                    'mod_domain_name': self.email_domain_name,
                                    'mod_domain_desc':
                                        self.email_domain_description})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, domain_id):
        # conv
        self.__super.find(domain_id)

        (self.email_domain_name, self.email_domain_description) = self.query_1("""
         SELECT domain, description
         FROM [:table schema=cerebrum name=email_domain]
         WHERE domain_id=:d_id""", {'d_id': domain_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_domain(self, domain):
        # NA
        domain_id = self.query_1("""
        SELECT domain_id
        FROM [:table schema=cerebrum name=email_domain]
        WHERE domain=:name""", {'name': domain})
        self.find(domain_id)

    def get_domain_name(self):
        return self.email_domain_name

    # FIXME: wrong name space. LDAP shouldn't affect this module
    _rewrite_domain = cereconf.LDAP['rewrite_email_domain']

    def rewrite_special_domains(self, domain):
        # NA
        """There may exist domains with special meaning which aren't a
        valid part of an e-mail address.  This function makes all
        addresses valid.
        """
        return self._rewrite_domain.get(domain, domain)

    def get_categories(self):
        # conv
        return self.query("""
        SELECT category
        FROM [:table schema=cerebrum name=email_domain_category]
        WHERE domain_id=:d_id""", {'d_id': self.entity_id})

    def add_category(self, category):
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id, self.clconst.email_dom_addcat,
                            None,
                            change_params={'category': int(category)})
        # conv
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_domain_category]
          (domain_id, category)
        VALUES (:d_id, :cat)""", {'d_id': self.entity_id,
                                  'cat': int(category)})

    def remove_category(self, category):
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id, self.clconst.email_dom_remcat,
                            None,
                            change_params={'category': int(category)})
        # conv
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_domain_category]
        WHERE domain_id=:d_id AND category=:cat""",
                            {'d_id': self.entity_id,
                             'cat': int(category)})

    def list_email_domains_with_category(self, category):
        # NA
        return self.query("""
        SELECT ed.domain_id, ed.domain
        FROM [:table schema=cerebrum name=email_domain] ed
        JOIN [:table schema=cerebrum name=email_domain_category] edc
          ON edc.domain_id = ed.domain_id
        WHERE edc.category = :cat""", {'cat': int(category)})

    def list_email_domains(self):
        # NA
        return self.query("""
        SELECT domain_id, domain
        FROM [:table schema=cerebrum name=email_domain]""")

    def search(self, name=None, description=None, category=None):
        """
        Retrieves a list of EmailDomains filtered by the given criterias.

        If no criteria is given, all domains are returned. ``name`` and
        ``description`` should be strings if given.
        ``category`` must be an int, a constant or a string that can be
        int()-ed, or it can be a list of such values.

        Wildcards * and ? are expanded for "any chars" and "one char".
        """

        where = []
        binds = {}
        joins = []

        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(ed.domain) LIKE :name")
            binds['name'] = name

        if description is not None:
            description = prepare_string(description)
            where.append("LOWER(ed.description) LIKE :desc")
            binds['desc'] = description

        if category is not None:
            where.append(argument_to_sql(category, "edc.category", binds, int))
            joins.append("""
                JOIN [:table schema=cerebrum name=email_domain_category] edc
                  ON edc.domain_id = ed.domain_id
            """)

        where_str = ""
        if where:
            where_with_precedence = ["(%s)" % x for x in where]
            where_str = " WHERE %s" % " AND ".join(where_with_precedence)

        join_str = ""
        if joins:
            join_str = " ".join(joins)

        return self.query("""
        SELECT ed.domain_id, ed.domain, ed.description
        FROM [:table schema=cerebrum name=email_domain] ed %s %s
        """ % (join_str, where_str), binds)

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.email_domain_name
        return '<unbound domain>'


@six.python_2_unicode_compatible
class EmailTarget(Entity_class):
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

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_target_type', 'email_target_entity_id',
                      'email_target_entity_type', 'email_target_alias',
                      'email_target_using_uid', 'email_server_id')

    def clear(self):
        # conv
        super(EmailTarget, self).clear()
        self.clear_class(EmailTarget)
        self.__updated = []

    def populate(self, type, target_entity_id=None,
                 target_entity_type=None, alias=None, using_uid=None,
                 server_id=None, parent=None):
        # conv
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_email_target)
        try:
            if not self.__in_db:
                raise RuntimeError('populate() called multiple times.')
        except AttributeError:
            self.__in_db = False
        self.email_target_type = type
        self.email_target_alias = alias
        self.email_target_using_uid = using_uid
        self.email_server_id = server_id
        if target_entity_id is None and target_entity_type is None:
            self.email_target_entity_id = self.email_target_entity_type = None
        elif target_entity_id is not None and target_entity_type is not None:
            self.email_target_entity_id = target_entity_id
            self.email_target_entity_type = target_entity_type
        else:
            raise ValueError('Must set both or none of (target_entity_id, '
                             'target_entity_type).')

    def write_db(self):
        # conv
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        target_entity_type = self.email_target_entity_type
        if target_entity_type is not None:
            target_entity_type = int(target_entity_type)
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_target]
              (target_id, target_type, target_entity_id, target_entity_type,
               alias_value, using_uid, server_id)
            VALUES (:t_id, :t_type, :e_id, :e_type, :alias, :uid, :server_id)
                         """,
                         {'t_id': self.entity_id,
                          't_type': int(self.email_target_type),
                          'e_id': self.email_target_entity_id,
                          'e_type': target_entity_type,
                          'alias': self.email_target_alias,
                          'uid': self.email_target_using_uid,
                          'server_id': self.email_server_id})
            # exchange-relatert-jazz
            self._db.log_change(self.entity_id,
                                self.clconst.email_target_add,
                                self.email_target_entity_id,
                                change_params={
                                    'target_type': int(self.email_target_type)
                                })
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_target]
            SET target_type=:t_type, target_entity_id=:e_id,
                target_entity_type=:e_type, alias_value=:alias,
                using_uid=:uid, server_id=:server_id
            WHERE target_id=:t_id""",
                         {'t_id': self.entity_id,
                          't_type': int(self.email_target_type),
                          'e_id': self.email_target_entity_id,
                          'e_type': target_entity_type,
                          'alias': self.email_target_alias,
                          'uid': self.email_target_using_uid,
                          'server_id': self.email_server_id})
            # exchange-relatert-jazz
            # we are mostly interested in changes to target_type
            # and server, ignoring other changes (although it
            # would probably be better to re-write API so that
            # every changes is done separately, but there is no
            # time for that. Jazz (2013-11)
            self._db.log_change(self.entity_id,
                                self.clconst.email_target_mod,
                                self.email_target_entity_id,
                                change_params={
                                    'target_type': int(self.email_target_type),
                                    'server_id': self.email_server_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id):
        # conv
        self.__super.find(target_id)

        (self.email_target_type, self.email_target_entity_id,
         self.email_target_entity_type, self.email_target_alias,
         self.email_target_using_uid,
         self.email_server_id) = self.query_1("""
        SELECT target_type, target_entity_id, target_entity_type,
               alias_value, using_uid, server_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE target_id=:t_id""", {'t_id': target_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def delete(self):
        # conv

        # We do not delete the corresponding rows in email_address
        # (and by extension, in email_primary_address) to reduce the
        # chance of catastrophic mistakes.
        #
        # TBD: is this really a good idea? medling in other classes.
        #      makes ChangeLogging harder.
        # exchange-relatert-jazz
        # TODO: this is definitely not a very good idea. delete should be
        # done in each class. (Jazz, 2013-11)
        for table in ('email_forward', 'email_vacation', 'email_quota',
                      'email_spam_filter', 'email_virus_scan',
                      'email_target_filter'):
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=%s]
            WHERE target_id=:e_id""" % table, {'e_id': self.entity_id})

        self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_target]
        WHERE target_id=:e_id""", {'e_id': self.entity_id})
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_target_rem,
                            self.email_target_entity_id,
                            change_params={
                                'target_type': int(self.email_target_type)})
        self.__super.delete()

    def find_by_email_target_attrs(self, **kwargs):
        # NA
        if not kwargs:
            raise Errors.ProgrammingError(
                'Need at least one column argument to find target')
        where = []
        binds = {}
        for column in ('target_type', 'target_entity_id', 'alias_value',
                       'using_uid', 'server_id'):
            if column in kwargs:
                where.append("%s = :%s" % (column, column))
                binds[column] = kwargs[column]
                if column == 'target_type':
                    # Avoid errors caused by the database driver
                    # converting bind args to str's.
                    binds[column] = int(binds[column])
                del kwargs[column]
        if kwargs:
            raise Errors.ProgrammingError('Unrecognized argument(s): %r'
                                          % kwargs)
        where = " AND ".join(where)
        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE %s""" % where, binds)
        self.find(target_id)

    def find_by_target_entity(self, target_entity_id):
        # NA

        # This might find no rows.  In those cases, query_1() will
        # raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE target_entity_id=:e_id""", {'e_id': target_entity_id})
        self.find(target_id)

    def find_by_alias(self, alias):
        # NA

        # This might find no rows, and it might find more than one
        # row.  In those cases, query_1() will raise an exception.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE alias_value=:alias""", {'alias': alias})
        self.find(target_id)

    def find_by_alias_and_account(self, alias, using_uid):
        # NA

        # Due to the UNIQUE constraint in table email_target, this can
        # only find more than one row if both target_entity_id and alias
        # are None.
        target_id = self.query_1("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE (alias_value=:alias OR :alias IS NULL)
          AND (using_uid=:uid OR :uid IS NULL)""",
                                 {'uid': using_uid,
                                  'alias': alias})
        self.find(target_id)

    def get_addresses(self, special=True):
        # conv
        """
        Return all email_addresses associated with this email_target as row
        objects.
        If special is False, rewrite the magic domain names into
        working domain names."""
        ret = self.query("""
        SELECT ea.local_part, ed.domain, ea.address_id
        FROM [:table schema=cerebrum name=email_address] ea
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE ea.target_id = :t_id""", {'t_id': int(self.entity_id)})
        if not special:
            ed = EmailDomain(self._db)
            for r in ret:
                r['domain'] = ed.rewrite_special_domains(r['domain'])
        return ret

    def list_email_targets(self):
        # NA
        """Return target_id of all EmailTarget in database"""
        return self.query("""
        SELECT target_id
        FROM [:table schema=cerebrum name=email_target]""", fetchall=False)

    def list_email_server_targets(self):
        # NA
        return self.query("""
        SELECT target_id, server_id
        FROM [:table schema=cerebrum name=email_target]
        WHERE server_id IS NOT NULL
        """, fetchall=False)

    # exchange-relatert-jazz
    # production og mail-ldif is very slow, trying to make it possible
    # to optimize targets listing a little bit
    def list_email_targets_ext(self, target_entity_id=None, target_type=None):
        """
        Return an iterator over all email_target rows.
        If target_entity_id is specified,
        only return email_targets with the given target_entity. If target_type
        is specified, return all email_target_rows with the conforming
        target_type.

        For each row, the following columns are included:
        target_id, target_type, target_entity_type, target_entity_id,
        alias_value, using_uid and server_id.
        """

        binds = {}
        where_str = ""
        if target_entity_id and target_type:
            raise Errors.ProgrammingError, \
                "Cannot use both entity_id and target_type!"
        if target_entity_id is not None:
            where_str = " WHERE %s" % argument_to_sql(
                target_entity_id, "target_entity_id", binds, int)
        if target_type is not None:
            where_str = " WHERE %s" % argument_to_sql(
                target_type, "target_type", binds, int)
        return self.query("""
        SELECT target_id, target_type, target_entity_type,
               target_entity_id, alias_value, using_uid,
               server_id
        FROM [:table schema=cerebrum name=email_target]%s
        """ % where_str, binds, fetchall=False)

    def list_email_target_primary_addresses(self, target_type=None,
                                            target_entity_id=None):
        # conv
        """Return an iterator over primary email-addresses belonging to email_target.
        Returns target_id, target_entity_id, local_part and domain.

        target_type decides which email_target to filter on.
        """

        where = list()
        binds = dict()
        if target_type:
            where.append("et.target_type = %d" % int(target_type))

        if target_entity_id is not None:
            where.append(argument_to_sql(target_entity_id,
                                         "et.target_entity_id",
                                         binds,
                                         int))

        if where:
            where = "WHERE " + " AND ".join(where)
        else:
            where = ''

        return self.query("""
        SELECT et.target_id, et.target_entity_id, ea.local_part, ed.domain,
        et.server_id
        FROM [:table schema=cerebrum name=email_target] et
          JOIN [:table schema=cerebrum name=email_primary_address] epa
            ON et.target_id=epa.target_id
          JOIN [:table schema=cerebrum name=email_address] ea
            ON epa.address_id=ea.address_id
          JOIN [:table schema=cerebrum name=email_domain] ed
            ON ea.domain_id=ed.domain_id
        %s""" % where, binds)

    def get_target_type(self):
        # NA
        return self.email_target_type

    def get_target_type_name(self):
        # NA
        name = self._db.pythonify_data(self.email_target_type)
        name = _EmailTargetCode(name)
        return name

    def get_alias(self):
        # NA
        return self.email_target_alias

    def get_target_entity_id(self):
        # NA
        return self.email_target_entity_id

    def get_target_entity_type(self):
        # NA
        return self.email_target_entity_type

    def get_server_id(self):
        # NA
        return self.email_server_id

    def __str__(self):
        if hasattr(self, 'entity_id'):
            tp = self.const.EntityType(self.email_target_type)
            target = Utils.Factory.get(
                Utils.Factory.type_component_map.get(str(tp), 'Entity'))(
                    self.db)
            return '{}:{}'.format(
                six.text_type(self.email_target_type),
                six.text_type(target))


@six.python_2_unicode_compatible
class EmailAddress(Entity_class):
    """Interface for registering known local email addresses.

    EmailAddresses must have a valid localpart, which must be unique
    within the EmailDomain of the address.  Each EmailAddress must be
    connected to a EmailTarget."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_addr_local_part', 'email_addr_domain_id',
                      'email_addr_target_id', 'email_addr_expire_date')

    def clear(self):
        # conv
        self.__super.clear()
        self.clear_class(EmailAddress)
        self.__updated = []

    def populate(self, local_part, domain_id, target_id, expire=None,
                 parent=None):
        # conv
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_email_address)
        try:
            if not self.__in_db:
                raise RuntimeError('populate() called multiple times.')
        except AttributeError:
            self.__in_db = False
        self.email_addr_local_part = local_part
        self.email_addr_domain_id = domain_id
        self.email_addr_target_id = target_id
        self.email_addr_expire_date = expire

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_address]
              (address_id, local_part, domain_id, target_id,
               change_date, expire_date)
            VALUES (:a_id, :lp, :d_id, :t_id, [:now], :expire)""",
                         {'a_id': self.entity_id,
                          'lp': self.email_addr_local_part,
                          'd_id': self.email_addr_domain_id,
                          't_id': self.email_addr_target_id,
                          'expire': self.email_addr_expire_date})
            # exchange-relevant-jazz
            # we would like to be able to search for all
            # changes related to a target. as this includes
            # address-manipulation subject_entity in change_log
            # will be the target_id and not the address_id
            self._db.log_change(
                self.email_addr_target_id,
                self.clconst.email_address_add,
                self.entity_id,
                change_params={'lp': self.email_addr_local_part,
                               'dom_id': self.email_addr_domain_id})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_address]
            SET local_part=:lp, domain_id=:d_id, target_id=:t_id,
                expire_date=:expire, change_date=[:now]
            WHERE address_id=:a_id""",
                         {'a_id': self.entity_id,
                          'lp': self.email_addr_local_part,
                          'd_id': self.email_addr_domain_id,
                          't_id': self.email_addr_target_id,
                          'expire': self.email_addr_expire_date})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, address_id):
        # conv
        self.__super.find(address_id)

        (self.email_addr_local_part, self.email_addr_domain_id,
         self.email_addr_target_id,
         self.email_addr_expire_date) = self.query_1("""
        SELECT local_part, domain_id, target_id, expire_date
        FROM [:table schema=cerebrum name=email_address]
        WHERE address_id=:a_id""", {'a_id': address_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def delete(self):
        # conv
        # We must store these params, in order to remove this address from
        # target system
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_address]
        WHERE address_id=:e_id""", {'e_id': self.entity_id})
        # exchange-relevant-jazz
        # in order to collect all target-related changes
        # address-manipulation is change_logged with target_id
        # as subject_entity
        self._db.log_change(self.email_addr_target_id,
                            self.clconst.email_address_rem,
                            self.entity_id,
                            change_params={
                                'lp': self.email_addr_local_part,
                                'dom_id': self.email_addr_domain_id})
        self.__super.delete()

    def find_by_local_part_and_domain(self, local_part, domain_id):
        # NA
        address_id = self._db.query_1("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_address]
        WHERE local_part=:lp AND domain_id=:d_id""",
                                      {'lp': local_part,
                                       'd_id': domain_id})
        self.find(address_id)

    def find_by_address(self, address):
        # NA
        lp, dp = address.split('@')
        domain = EmailDomain(self._db)
        domain.find_by_domain(dp)
        self.find_by_local_part_and_domain(lp, domain.entity_id)

    def validate_localpart(self, localpart):
        # NA
        """Check that localpart is syntactically correct.  This is a
        subset (simplification) of RFC 2821 syntax, so e.g. quotes
        (neither quotation marks nor backslash) or comments (in
        parentheses) are not allowed.

        """
        # TBD: Should populate() etc. call this function?  If so, it
        # would need to throw an exception.  Which one?

        # 64 characters should be enough for everybody.
        # (RFC 2821 4.5.3.1)
        if len(localpart) > 64:
            return False
        # Only allow US-ASCII, and no SPC or DEL either.
        if re.search(r'[^!-~]', localpart):
            return False
        # No empty atoms
        if localpart.count(".."):
            return False
        # No "specials" (RFC 2822 3.2.1)
        if re.search(r'[()<>[]:;@\\,]', localpart):
            return False
        return True

    # FIXME: Can anyone explain what this can be used for?
    def list_email_addresses(self):
        # NA
        """Return address_id of all EmailAddress in database"""
        return self.query("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_address]""", fetchall=False)

    # FIXME: Should probably be replaced by search().
    def list_email_addresses_ext(self, domain=None):
        # NA
        """Return address_id, target_id, local_part and domain of all
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

    def search(self, local_part=None, local_part_pattern=None,
               target_id=None, domain_id=None, filter_expired=True,
               fetchall=False):
        """Search for EmailAddresse by given criterias.

        @type local_part: str
        @param local_part:
            Filter the result by a given local part. Must match exactly.

        @type local_part_pattern: str
        @param local_part_pattern:
            Filter the result by a given local part pattern. The pattern is run
            through an SQL like query and is case insensitive.

        @type target_id: int or sequence thereof
        @param target_id:
            Filter the result by the addresses belonging to the given targets.

        @type domain_id: int
        @param domain_id:
            Filter the result by a given domain.

        @type filter_expired: bool
        @param filter_expired:
            Filter the result by only returning addresses where the expire_date
            is either not set or has not passed, i.e. is expired.

        @type fetchall: bool
        @param fetchall:
            If True, all db-rows are fetched from the db immediately. If False,
            an iterator is returned, returning each row on demand, which could
            in some cases lead to lower memory usage, but it could also lead to
            a performance penalty.

        @rtype: iterable (yielding db-rows with address information)
        @return:
            An iterable (sequence or generator) with the db-rows that matches
            the given search criterias for EmailAddress. Each db-row contains
            the elements address_id, target_id, local_part, domain_id, and
            domain (name of the domain).

        """
        conditions = []
        binds = locals()
        if local_part is not None:
            conditions.append('ea.local_part = :local_part')
        if local_part_pattern is not None:
            local_part_pattern = local_part_pattern.lower()
            conditions.append('LOWER(ea.local_part) LIKE :local_part_pattern')
        if domain_id is not None:
            conditions.append('ea.domain_id = :domain_id')
        if target_id is not None:
            conditions.append(
                argument_to_sql(target_id, "ea.target_id", binds, int))
        if filter_expired:
            conditions.append('(ea.expire_date IS NULL OR'
                              ' ea.expire_date > [:now])')
        where = ""
        if conditions:
            where = " WHERE " + " AND ".join(conditions)
        return self.query(
            """ SELECT ea.address_id, ea.target_id, ea.local_part,
                       ed.domain_id, ed.domain
            FROM [:table schema=cerebrum name=email_address] ea
            JOIN [:table schema=cerebrum name=email_domain] ed
              ON ea.domain_id = ed.domain_id""" + where,
            binds, fetchall=fetchall)

    # FIXME: should be replaced by search()
    def list_target_addresses(self, target_id):
        # NA
        """Return address_id, local_part and domain_id for target_id"""
        return self.query("""
        SELECT address_id, local_part, domain_id
        FROM [:table schema=cerebrum name=email_address]
        WHERE target_id = :t_id""",
                          {'t_id': target_id},
                          fetchall=False)

    def get_target_id(self):
        # NA
        """Return target_id of this EmailAddress in database"""
        return self.email_addr_target_id

    def get_domain_id(self):
        # NA
        """Return domain_id of this EmailAddress in database"""
        return self.email_addr_domain_id

    def get_localpart(self):
        # NA
        """Return domain_id of this EmailAddress in database"""
        return self.email_addr_local_part

    def get_address(self):
        # NA
        """Return textual representation of address,
        i.e. 'local_part@domain'.

        """
        domain = EmailDomain(self._db)
        domain.find(self.email_addr_domain_id)
        return (self.email_addr_local_part + '@' +
                domain.rewrite_special_domains(domain.email_domain_name))

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.get_address()
        return '<unbound email address>'


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
                raise RuntimeError('populate() called multiple times.')
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
            # exchange-relevant-jazz
            self._db.log_change(self.entity_email_domain_id,
                                self.clconst.email_entity_dom_add,
                                self.entity_id,
                                change_params={'aff': affiliation})
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
            # exchange-relevant-jazz
            self._db.log_change(self.entity_email_domain_id,
                                self.clconst.email_entity_dom_mod,
                                self.entity_id,
                                change_params={'aff': affiliation})
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
        # exchange-relevant-jazz
        self._db.log_change(
            self.entity_email_domain_id,
            self.clconst.email_entity_dom_rem,
            self.entity_id,
            change_params={'aff': self.entity_email_affiliation})
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
                raise RuntimeError('populate() called multiple times.')
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
                         {'t_id': self.entity_id,
                          'soft': self.email_quota_soft,
                          'hard': self.email_quota_hard})
            # exchange-relevant-jazz
            self._db.log_change(self.entity_id,
                                self.clconst.email_quota_add,
                                None,
                                change_params={'soft': self.email_quota_soft,
                                               'hard': self.email_quota_hard})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_quota]
            SET quota_soft=:soft,
                quota_hard=:hard
            WHERE target_id=:t_id""", {'t_id': self.entity_id,
                                       'soft': self.email_quota_soft,
                                       'hard': self.email_quota_hard})
            # exchange-relevant-jazz
            self._db.log_change(self.entity_id,
                                self.clconst.email_quota_mod,
                                None,
                                change_params={'soft': self.email_quota_soft,
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
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_quota_rem,
                            None)
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_quota]
        WHERE target_id=:e_id""", {'e_id': self.entity_id})

    def get_quota_soft(self):
        return self.email_quota_soft

    def get_quota_hard(self):
        return self.email_quota_hard

    def list_email_quota_ext(self):
        """Return all defined quotas; target_id, quota_soft and quota_hard."""
        return self.query("""
        SELECT target_id, quota_soft, quota_hard
        FROM [:table schema=cerebrum name=email_quota]""")

    def get_quota_stats_by_server(self, server):
        """Return statistics about the quota handed out to account
        targets.  If there are no targets on a server, the values will
        be None."""
        return self.query_1(
            """ SELECT SUM(eq.quota_hard) AS total_quota,
                       MIN(eq.quota_hard) AS min_quota,
                       MAX(eq.quota_hard) AS max_quota,
                       COUNT(*) AS total_accounts
            FROM email_target et
            JOIN email_quota eq ON et.target_id = eq.target_id
            WHERE et.server_id = :server AND et.target_type = :t_type""",
            {'server': int(server),
             't_type': int(self.const.email_target_account)})


class EmailTargetFilter(EmailTarget):
    """Container class for various filters placed on EmailTarget.
    Primarily designed for filters such as gray-listing, but the class
    supports other types of filters."""
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('email_target_filter_filter',)

    def clear(self):
        self.__super.clear()
        self.clear_class(EmailTargetFilter)
        self.__updated = []

    def populate(self, filter, parent=None):
        """Registered settings for other filters than pre-set
        spam filters."""
        if parent is not None:
            self.__xerox__(parent)
        try:
            if not self.__in_db:
                raise RuntimeError('populate() called multiple times.')
        except AttributeError:
            self.__in_db = False
        self.email_target_filter_filter = filter

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=email_target_filter]
              (target_id, filter)
            VALUES (:t_id, :filter)""",
                         {'t_id': self.entity_id,
                          'filter': int(self.email_target_filter_filter)})
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_tfilter_add,
                None,
                change_params={'filter': int(self.email_target_filter_filter)})
        else:
            # Binary table. No need to update with the same info
            pass
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def find(self, target_id, filter):
        self.__super.find(target_id)
        self.email_target_filter_filter = self.query_1("""
        SELECT filter
        FROM [:table schema=cerebrum name=email_target_filter]
        WHERE target_id=:t_id AND filter=:filter""", {'t_id': self.entity_id,
                                                      'filter': filter})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def enable_email_target_filter(self, filter):
        """Helper method, used to enable a given filter. Needs
        write_db()"""
        self.email_target_filter_filter = filter

    def disable_email_target_filter(self, filter):
        """Helper method, used to enable a given filter."""
        # exchange-relatert-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_tfilter_rem,
                            None,
                            change_params={'filter': int(filter)})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_target_filter]
        WHERE target_id=:t_id AND filter=:filter""",
                            {'t_id': self.entity_id,
                             'filter': filter})

    def list_email_target_filter(self, target_id=None, filter=None):
        """List all registered email_target_filters, filtered on target_id
        and/or filter_type."""
        lst = []
        if target_id:
            lst.append("target_id=:t_id")
        if filter:
            lst.append("filter=:filter")
        where = ""
        if lst:
            where = "WHERE " + " AND ".join(lst)
        return self.query("""
        SELECT target_id, filter
        FROM [:table schema=cerebrum name=email_target_filter]
        %s""" % where, {'t_id': target_id,
                        'filter': filter})


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
                raise RuntimeError('populate() called multiple times.')
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
                         {'t_id': self.entity_id,
                          'level': int(self.email_spam_level),
                          'action': int(self.email_spam_action)})
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_sfilter_add,
                None,
                change_params={
                    'level': int(self.email_spam_level),
                    'action': int(self.email_spam_action)})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_spam_filter]
            SET level=:level,
                action=:action
            WHERE target_id=:t_id""", {'t_id': self.entity_id,
                                       'level': int(self.email_spam_level),
                                       'action': int(self.email_spam_action)})
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_sfilter_mod,
                None,
                change_params={
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
        WHERE target_id=:t_id""", {'t_id': self.entity_id})
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
                raise RuntimeError('populate() called multiple times.')
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
                         {'t_id': self.entity_id,
                          'found': self.email_virus_found_act,
                          'removed': self.email_virus_removed_act,
                          'enable': self.email_virus_enable})
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_scan_add,
                None,
                change_params={'found': int(self.email_virus_found_act),
                               'removed': int(self.email_virus_removed_act),
                               'enable': int(self.email_virus_enable)})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_virus_scan]
            SET found_action=:found, rem_action=:remove, enable=:enable
            WHERE target_id=:t_id""",
                         {'t_id': self.entity_id,
                          'found': self.email_virus_found_act,
                          'removed': self.email_virus_removed_act,
                          'enable': self.email_virus_enable})
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_scan_mod,
                None,
                change_params={'found': int(self.email_virus_found_act),
                               'removed': int(self.email_virus_removed_act),
                               'enable': int(self.email_virus_enable)})
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
        WHERE target_id=:t_id""", {'t_id': self.entity_id})
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
        """ TODO.

        Join between email_virus_scan, email_virus_found_code and
        email_virus_removed_code.

        Returns target_id, found_str(code from email_virus_found_code),
        removed_str(code from email_virus_removed_code) and enable.
        """
        return self.query(
            """ SELECT s.target_id, f.code_str AS found_str,
                       r.code_str AS removed_str, s.enable
            FROM [:table schema=cerebrum name=email_virus_scan] s,
                 [:table schema=cerebrum name=email_virus_found_code] f,
                 [:table schema=cerebrum name=email_virus_removed_code] r
            WHERE s.found_action = f.code AND s.rem_action = r.code""")


class EmailForward(EmailTarget):
    """Forwarding addresses attached to EmailTargets."""

    def find(self, target_id):
        """Find EmailForward, with associated attributes.

        :type target_id: int
        :param target_id: The EmailTargets entity id."""
        super(EmailForward, self).find(target_id)
        try:
            self.local_delivery = self._db.query_1(
                """SELECT local_delivery FROM
                    [:table schema=cerebrum name=email_local_delivery] WHERE
                    target_id = :t_id""",
                {'t_id': target_id})
        except Errors.NotFoundError:
            self.local_delivery = False

    def enable_local_delivery(self):
        """Enable local delivery for EmailTarget."""
        if not self.local_delivery:
            self.local_delivery = True
            self._db.log_change(self.entity_id,
                                self.clconst.email_local_delivery,
                                None,
                                change_params={'enabled': True})
            self.execute(
                """INSERT INTO [:table schema=cerebrum name=email_local_delivery]
                    (target_id, local_delivery) VALUES (:t_id, :ld)""",
                {'t_id': self.entity_id,
                 'ld': True})

    def disable_local_delivery(self):
        """Disable local delivery for EmailTarget."""
        if self.local_delivery:
            self.local_delivery = False
            self._db.log_change(self.entity_id,
                                self.clconst.email_local_delivery,
                                None,
                                change_params={'enabled': False})
            self.execute(
                """DELETE FROM [:table schema=cerebrum name=email_local_delivery]
                    WHERE target_id = :t_id""",
                {'t_id': self.entity_id})

    def add_forward(self, forward, enable=True):
        """Add a forwarding address to an EmailTarget.

        :param str forward: The address to forward to.
        :param bool enable: Enable or disable this forward.
        """
        enable = 'T' if enable else 'F'
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_forward_add,
                            None,
                            change_params={'forward': forward,
                                           'enable': enable})
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_forward]
          (target_id, forward_to, enable)
        VALUES (:t_id, :forward, :enable)""", {'t_id': self.entity_id,
                                               'forward': forward,
                                               'enable': enable})

    def _set_forward_enable(self, forward, enable):
        if enable == 'F':
            cat = self.clconst.email_forward_disable
        else:
            cat = self.clconst.email_forward_enable
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            cat,
                            None,
                            change_params={'forward': forward})

        return self.execute("""
        UPDATE [:table schema=cerebrum name=email_forward]
        SET enable=:enable
        WHERE target_id = :t_id AND
              forward_to = :fwd""", {'enable': enable,
                                     'fwd': forward,
                                     't_id': self.entity_id})

    def enable_forward(self, forward):
        """Enable forwarding to a specific (existing) address.

        :param str forward: The address to enable forward for.
        """
        return self._set_forward_enable(forward, 'T')

    def disable_forward(self, forward):
        """Disable forwarding to a specific (existing) address.

        :param str forward: The address to disable forwarding for.
        """
        return self._set_forward_enable(forward, 'F')

    def get_forward(self):
        """Fetch all forwards attached to the EmailTarget."""
        return self.query("""
        SELECT forward_to, enable
        FROM [:table schema=cerebrum name=email_forward]
        WHERE target_id=:t_id""", {'t_id': self.entity_id})

    def delete_forward(self, forward):
        """Delete the forwarding address associated with this EmailTarget.

        :param str forward: The forwarding address to delete.
        """
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_forward_rem,
                            None,
                            change_params={'forward': forward})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_forward]
        WHERE target_id=:t_id AND forward_to=:forward""",
                            {'t_id': self.entity_id,
                             'forward': forward})

    def list_email_forwards(self):
        """List all existing forwards."""
        return self.query("""
        SELECT target_id, forward_to, enable
        FROM [:table schema=cerebrum name=email_forward]
        """, fetchall=False)

    def list_local_delivery(self):
        """List all local deliveries.

        :rtype: list
        :return: [(target_id, local_delivery)]."""
        return self.query("""SELECT * FROM
        [:table schema=cerebrum name=email_local_delivery]""")

    def search(self, forward_to=None, enable=None, target_id=None,
               fetchall=False):
        """Search for email forwards.

        :type forward_to: str
        :param forward_to: The forward address to search for.
            May contain % for wildcard matching.
        :type enable: bool
        :param enable: Wheter forwards should be enabled or disabled
            (default: both).
        :type target_id: int
        :param target_id: Search for forwards realted to an EmailTarget.
        :type fetchall: bool
        :param fetchall: Return iterator or list (default: iterator).

        :rtype: list
        :return: A list of forwards found. Looks like
            [(forward_to, enable, target_id)].
        """
        conditions = []
        binds = {}

        if forward_to is not None:
            binds['forward_to'] = forward_to.lower()
            conditions.append('LOWER(ef.forward_to) LIKE :forward_to')
        if enable is not None:
            binds['enable'] = 'T' if enable is True else 'F'
            conditions.append('ef.enable = :enable')
        if target_id is not None:
            binds['target_id'] = target_id
            conditions.append('ef.target_id = :target_id')

        where = ""
        if conditions:
            where = " WHERE " + " AND ".join(conditions)
        return self.query(
            """SELECT *
            FROM [:table schema=cerebrum name=email_forward] ef""" + where,
            binds, fetchall=fetchall)


class EmailVacation(EmailTarget):

    def add_vacation(self, start, text, end=None, enable=False):
        # TODO: Should use DDL-imposed default values if not
        # instructed otherwise.
        if enable:
            enable = 'T'
        else:
            enable = 'F'
        ret = self.execute("""
        INSERT INTO [:table schema=cerebrum name=email_vacation]
          (target_id, start_date, vacation_text, end_date, enable)
        VALUES (:t_id, :start, :text, :end, :enable)""",
                           {'t_id': self.entity_id,
                            'start': start,
                            'text': text,
                            'end': end,
                            'enable': enable})
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_vacation_add, None,
                            change_params={'start': start,
                                           'end': end,
                                           'enable': enable})
        return ret

    def enable_vacation(self, start, enable=True):
        if enable:
            enable = 'T'
            cat = self.clconst.email_vacation_enable
        else:
            enable = 'F'
            cat = self.clconst.email_vacation_disable
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            cat, None,
                            change_params={'start': start})
        return self.execute("""
        UPDATE [:table schema=cerebrum name=email_vacation]
        SET enable=:enable
        WHERE target_id=:t_id AND start_date=:start""",
                            {'t_id': self.entity_id,
                             'start': start,
                             'enable': enable})

    def disable_vacation(self, start):
        return self.enable_vacation(start, False)

    def get_vacation(self):
        return self.query("""
        SELECT vacation_text, start_date, end_date, enable
        FROM [:table schema=cerebrum name=email_vacation]
        WHERE target_id=:t_id
        ORDER BY start_date""", {'t_id': self.entity_id})

    def delete_vacation(self, start):
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_vacation_rem,
                            None,
                            change_params={'start': start})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_vacation]
        WHERE target_id=:t_id AND start_date=:start""",
                            {'t_id': self.entity_id,
                             'start': start})

    def list_email_vacations(self):
        return self.query("""
        SELECT target_id, vacation_text, start_date, end_date, enable
        FROM [:table schema=cerebrum name=email_vacation]
        """, fetchall=False)

    def list_email_active_vacations(self):
        import mx
        return self.query("""
        SELECT target_id, vacation_text, start_date, end_date, enable
        FROM [:table schema=cerebrum name=email_vacation]
        WHERE enable = 'T' AND
              start_date<=:cur AND
              end_date>=:cur OR end_date IS NULL
        """, {'cur': mx.DateTime.today()}, fetchall=False)


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
                raise RuntimeError('populate() called multiple times.')
        except AttributeError:
            if parent is None:
                raise RuntimeError(
                    "Can't populate EmailPrimaryAddressTarget without parent.")
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
                         {'t_id': self.entity_id,
                          'addr_id': self.email_primaddr_id})
            # exchange-relevant-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_primary_address_add,
                None,
                change_params={'addr_id': self.email_primaddr_id})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_primary_address]
            SET address_id=:addr_id
            WHERE target_id=:t_id""", {'t_id': self.entity_id,
                                       'addr_id': self.email_primaddr_id})
            # exchange-relevant-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_primary_address_mod,
                None,
                change_params={'addr_id': self.email_primaddr_id})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Delete primary address.  Note that this will _not_ call
        delete() in parent.  If you want to delete the EmailTarget as
        well, you need to do so explicitly."""
        # exchange-relevant-jazz
        self._db.log_change(self.entity_id,
                            self.clconst.email_primary_address_rem,
                            None,
                            change_params={'addr_id': self.email_primaddr_id})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=email_primary_address]
        WHERE target_id=:e_id""", {'e_id': self.entity_id})

    def find(self, target_id):
        self.__super.find(target_id)
        self.email_primaddr_id = self.query_1("""
        SELECT address_id
        FROM [:table schema=cerebrum name=email_primary_address]
        WHERE target_id=:t_id""", {'t_id': self.entity_id})
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
                raise RuntimeError('populate() called multiple times.')
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
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_server_add,
                None,
                change_params={'server_type': int(self.email_server_type)})
        else:
            # TBD: What about DELETEs?
            self.execute("""
            UPDATE [:table schema=cerebrum name=email_server]
            SET server_type=:type
            WHERE server_id=:s_id""", {'s_id': self.entity_id,
                                       'type': int(self.email_server_type)})
            # exchange-relatert-jazz
            self._db.log_change(
                self.entity_id,
                self.clconst.email_server_mod,
                None,
                change_params={'server_type': int(self.email_server_type)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=email_server]
            WHERE server_id=:s_id""", {'s_id': self.entity_id,
                                       'type': int(self.email_server_type)})
        # exchange-relatert-jazz
        self._db.log_change(
            self.entity_id,
            self.clconst.email_server_rem,
            None,
            change_params={'server_type': int(self.email_server_type)})
        return self.__super.delete()
    # end delete

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

    def list_email_server_ext(self, server_type=None):
        """List all e-mail servers, optionally filtered by
        server_type."""
        where = ""
        if server_type is not None:
            where = "WHERE s.server_type = %d" % server_type
        return self.query("""
        SELECT s.server_id, s.server_type, en.entity_name AS name
        FROM [:table schema=cerebrum name=email_server] s
        JOIN [:table schema=cerebrum name=host_info] h
          ON s.server_id = h.host_id
        JOIN [:table schema=cerebrum name=entity_name] en
          ON h.host_id = en.entity_id AND
             en.value_domain = [:get_constant name=host_namespace]
        %s
        """ % where)

    def search(self, host_id=None, name=None, description=None):
        """Retrieves a list of EmailServers filtered by the given criterias.

        If no criteria is given, all hosts are returned. ``name`` and
        ``description`` should be strings if given. Wildcards * and ? are
        expanded for "any chars" and "one char".

        :return list:
            A list of tuples/db_rows with fields: (host_id, name, description,
            server_type).
        """
        where = list()
        binds = dict()

        query_fmt = """
        SELECT DISTINCT hi.host_id, en.entity_name AS name,
                        hi.description, s.server_type
        FROM [:table schema=cerebrum name=host_info] hi
        JOIN [:table schema=cerebrum name=email_server] s
          ON hi.host_id = s.server_id
        JOIN [:table schema=cerebrum name=entity_name] en
          ON hi.host_id = en.entity_id AND
             en.value_domain = [:get_constant name=host_namespace]
        {where!s}
        """

        if host_id is not None:
            where.append(argument_to_sql(host_id, 'hi.host_id', binds, int))

        if name is not None:
            where.append("LOWER(en.entity_name) LIKE :name")
            binds['name'] = prepare_string(name.lower())

        if description is not None:
            where.append("LOWER(hi.description) LIKE :desc")
            binds['desc'] = prepare_string(description.lower())

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query(query_fmt.format(where=where_str), binds)


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

    # exchange-relatert-jazz
    # I did not touch this method and cannot see any readily
    # implemented improvements relates to Exchange roll-out or
    # completed migration to Exchange at UiO. Someone should, however,
    # take at look at the metod after migration is completed as new
    # data may be discovered during migration. Jazz (2013-11)
    #
    def update_email_addresses(self):
        # Find, create or update a proper EmailTarget for this
        # account.
        et = EmailTarget(self._db)
        target_type = self.const.email_target_account
        if self.is_expired() or self.is_reserved():
            target_type = self.const.email_target_deleted
        changed = False
        try:
            et.find_by_email_target_attrs(target_entity_id=self.entity_id)
            if et.email_target_type != target_type:
                changed = True
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
        if changed and cereconf.EMAIL_EXPIRE_ADDRESSES is not False:
            if target_type == self.const.email_target_deleted:
                seconds = cereconf.EMAIL_EXPIRE_ADDRESSES * 86400
                expire_date = self._db.DateFromTicks(time.time() + seconds)
            else:
                expire_date = None
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                ea.email_addr_expire_date = expire_date
                ea.write_db()
        # Active accounts shouldn't have an alias value (it is used
        # for failure messages)
        if changed and target_type == self.const.email_target_account:
            if et.email_target_alias is not None:
                et.email_target_alias = None
                et.write_db()

        if target_type == self.const.email_target_deleted:
            return
        # Until a user's email target is associated with an email
        # server, the mail system won't know where to deliver mail for
        # that user.  Hence, we return early (thereby avoiding
        # creation of email addresses) for such users.
        if not et.email_server_id:
            return
        self._update_email_address_domains(et)

    def _update_email_address_domains(self, et):
        # Figure out which domain(s) the user should have addresses
        # in.  Primary domain should be at the front of the resulting
        # list.
        ed = EmailDomain(self._db)
        ea = EmailAddress(self._db)
        ed.find(self.get_primary_maildomain())
        domains = self.get_prospect_maildomains()
        # Iterate over the available domains, testing various
        # local_parts for availability.  Set user's primary address to
        # the first one found to be available.
        primary_set = False
        epat = EmailPrimaryAddressTarget(self._db)
        for domain in domains:
            if ed.entity_id != domain:
                ed.clear()
                ed.find(domain)
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
                    ea.find_by_local_part_and_domain(lp, ed.entity_id)
                    if ea.email_addr_target_id != et.entity_id:
                        # Address already exists, and points to a
                        # target not owned by this Account.
                        #
                        # TODO: An expired address gets removed by a
                        # database cleaning job, and when it's gone,
                        # the address will eventually be recreated
                        # connected to this target.
                        continue
                except Errors.NotFoundError:
                    # Address doesn't exist; create it.
                    ea.populate(lp, ed.entity_id, et.entity_id,
                                expire=None)
                ea.write_db()
                if not primary_set:
                    epat.clear()
                    try:
                        epat.find(ea.email_addr_target_id)
                        epat.populate(ea.entity_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.entity_id, parent=et)
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
        try:
            full = self.get_fullname()
        except Errors.NotFoundError:
            full = self.account_name
        if not isinstance(full, six.text_type):
            raise Errors.CerebrumError(
                'Corrupt input while converting full_name')
        return self.get_email_cn_given_local_part(
            full_name=full, given_names=given_names, max_initials=max_initials)

    def get_email_cn_given_local_part(
            self, full_name, given_names=-1, max_initials=None):
        """Return a "pretty" local part out of a given name. This can be used to
        see what cn a name change would give.

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

        # NOTE: This needs some more work. It will now fail for certain names,
        # See CRB-131  - fhl, 2013-09-26
        def compress_preposition_surname(n):
            v = ['de', 'van', 'von']
            i = None
            for x in v:
                try:
                    i = n.index(x)
                    continue
                except ValueError:
                    pass
            if i:
                t = n.pop(i)
                n[i] = t + n[i]
            return n

        assert(given_names >= -1)
        assert(max_initials is None or max_initials >= 0)

        names = [x.lower() for x in re.split(r'\s+', full_name)]
        # names = compress_preposition_surname(names) # CRB-131, see above
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
        """
        Returns the cached full name of the person owning the POSIX account.
        @return: The person owner's full name.
        """
        p = Utils.Factory.get("Person")(self._db)
        p.find(self.owner_id)
        full = p.get_name(self.const.system_cached, self.const.name_full)
        return full

    def get_prospect_maildomains(self, use_default_domain=True):
        """
        Return correct `domain_id's for the account's account_types regardless
        of what's populated in email_address.

        Domains will be sorted based on account_type priority and have
        cereconf.EMAIL_DEFAULT_DOMAIN last in the list.
        """
        dom = EmailDomain(self._db)
        if use_default_domain:
            dom.find_by_domain(cereconf.EMAIL_DEFAULT_DOMAIN)
        entdom = EntityEmailDomain(self._db)
        domains = []
        # Find OU and affiliation for this account.
        for row in self.get_account_types():
            ou, aff = row['ou_id'], row['affiliation']
            # If a maildomain is associated with this (ou, aff)
            # combination, then that is the user's default maildomain.
            entdom.clear()
            try:
                entdom.find(ou, affiliation=aff)
                # If the default domain is specified, ignore this
                # affiliation.
                if use_default_domain:
                    if entdom.entity_email_domain_id == dom.entity_id:
                        continue
                domains.append(entdom.entity_email_domain_id)
            except Errors.NotFoundError:
                # Otherwise, try falling back to tha maildomain associated
                # with (ou, None).
                entdom.clear()
                try:
                    entdom.find(ou)
                    if entdom.entity_email_domain_id == dom.entity_id:
                        continue
                    domains.append(entdom.entity_email_domain_id)
                except Errors.NotFoundError:
                    pass
        if use_default_domain:
            # Append cereconf.EMAIL_DEFAULT_DOMAIN last to return a vaild
            # domain always
            domains.append(dom.entity_id)
        return domains

    def get_primary_maildomain(self, use_default_domain=True):
        """Return correct `domain_id' for account's primary address."""
        dom = EmailDomain(self._db)
        if use_default_domain:
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
                if use_default_domain:
                    # If the default domai n is specified, ignore this
                    # affiliation.
                    if entdom.entity_email_domain_id == dom.entity_id:
                        continue
                return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
            # Otherwise, try falling back to tha maildomain associated
            # with (ou, None).
            entdom.clear()
            try:
                entdom.find(ou)
                if use_default_domain:
                    if entdom.entity_email_domain_id == dom.entity_id:
                        continue
                    return entdom.entity_email_domain_id
            except Errors.NotFoundError:
                pass
        if use_default_domain:
            # Still no proper maildomain association has been found; fall
            # back to default maildomain.
            return dom.entity_id

    def get_primary_mailaddress(self):
        """Return account's current primary address."""
        r = self.query_1("""
        SELECT ea.local_part, ed.domain
        FROM [:table schema=cerebrum name=account_info] ai
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_entity_id = ai.account_id
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

    def getdict_uname2mailaddr(
            self, filter_expired=True, primary_only=True, filter_deleted=True):
        """Collect uname -> e-mail address mappings.

        This method collects e-mail address information for all users in
        Cerebrum. primary_only controls whether the method fetches just the
        primary address or all of the addresses for each username.

        @type filter_expired: bool
        @param filter_expired:
          When True, do NOT collect information about expired accounts.

        @type primary_only: bool
        @param primary_only:
          When True, collect primary e-mail addresses only.

        @type filter_deleted: bool
        @param filter_deleted:
          When True, do NOT collect information about deleted email accounts.

        @rtype: dict (of basestring to basestring/sequence of basestring)
        @return:
          A dict mapping user names (all/non-expired) to e-mail
          information. When primary_only is True, 'information' is a
          basestring. When primary_only is False, 'information' is a sequence
          (even when there is just one e-mail address for a user names)
        """
        query_fmt = """
            SELECT en.entity_name, ea.local_part, ed.domain
            FROM [:table schema=cerebrum name=account_info] ai
            JOIN [:table schema=cerebrum name=entity_name] en
              ON en.entity_id = ai.account_id
            JOIN [:table schema=cerebrum name=email_target] et
              ON {target_join!s}
              AND et.target_entity_id = ai.account_id
            {extra_join!s}
            JOIN [:table schema=cerebrum name=email_domain] ed
              ON ed.domain_id = ea.domain_id
            WHERE {where!s}
            """

        where = ["en.value_domain = :namespace", ]
        binds = {'namespace': int(self.const.account_namespace)}

        target_type = [self.const.email_target_account, ]
        if not filter_deleted:
            target_type.append(self.const.email_target_deleted)
        target_join = argument_to_sql(
            target_type, 'et.target_type', binds, int)

        if primary_only:
            extra_join = """
                JOIN [:table schema=cerebrum name=email_primary_address] epa
                  ON epa.target_id = et.target_id
                JOIN [:table schema=cerebrum name=email_address] ea
                  ON ea.address_id = epa.address_id
            """
        else:
            extra_join = """
                 JOIN [:table schema=cerebrum name=email_address] ea
                   ON ea.target_id = et.target_id
            """

        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        ret = {}
        ed = EmailDomain(self._db)

        for row in self.query(
                query_fmt.format(
                    target_join=target_join,
                    extra_join=extra_join,
                    where=" AND ".join(where)),
                binds, fetchall=False):
            uname = row['entity_name']
            address = '@'.join((row['local_part'],
                                ed.rewrite_special_domains(row['domain'])))
            if primary_only:
                ret[uname] = address
            else:
                ret.setdefault(uname, set()).add(address)
        return ret

    def wash_email_local_part(self, local_part):
        """
        """
        lp = transliterate.for_email_local_part(local_part)
        # Retain only characters that are likely to be intentionally
        # used in local-parts.
        allow_chars = string.ascii_lowercase + string.digits + '-_.'
        lp = "".join([c for c in lp if c in allow_chars])
        # The '.' character isn't allowed at the start or end of a local-part.
        lp = lp.strip('.')
        # Two '.' characters can't be together
        while lp.find('..') != -1:
            lp = lp.replace('..', '.')
        if not lp:
            raise ValueError(
                "Local-part can't be empty (%r -> %r)" % (local_part, lp))
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

    def delete_posixuser(self):
        """Email target has a foreign key with posix user"""
        res = self.query("""
            SELECT * FROM [:table schema=cerebrum name=email_target]
            WHERE using_uid = :eid""", {'eid': self.entity_id})
        if len(res) > 0:
            raise Errors.TooManyRowsError('Account is used in email targets')

    def get_delete_blockers(self, ignore_email_targets=False, **kw):
        """Return list of conflicting email targets"""
        ret = super(AccountEmailMixin, self).get_delete_blockers(**kw)
        if ignore_email_targets:
            return ret
        res = self.query("""
            SELECT * FROM [:table schema=cerebrum name=email_target]
            WHERE using_uid = :eid AND (target_entity_id IS NULL OR
                         target_entity_id <> :eid)""",
                         {'eid': self.entity_id})
        ret.extend(['Email target {}'.format(x['alias_value']
                                             if x['alias_value']
                                             else x['target_id'])
                    for x in res])
        return ret

    def delete(self):
        """Delete the account's email addresses and email target, so that the
        entity could be fully deleted from the database.

        TODO: Note that the EmailTarget and EmailAddresses are automatically
        readded by update_email_addresses if you for instance remove an ac_type
        for the account. Not sure how to avoid this, other than either first
        disable the account, or (or what?)
        """
        et = EmailTarget(self._db)
        try:
            et.find_by_target_entity(self.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            ep = EmailPrimaryAddressTarget(self._db)
            try:
                ep.find(et.entity_id)
                ep.delete()
                ep.write_db()
            except Errors.NotFoundError:
                pass

            ea = EmailAddress(self._db)
            for row in et.get_addresses():
                ea.clear()
                ea.find(row['address_id'])
                ea.delete()
                ea.write_db()
            et.write_db()
            et.delete()
        self.__super.delete()


class AccountEmailQuotaMixin(Account.Account):
    """Email-quota module for core class 'Account'."""

    def update_email_quota(self):
        """Set e-mail quota according to values in cereconf.EMAIL_HARD_QUOTA.
         EMAIL_HARD_QUOTA is in MiB and based on affiliations.
         Soft quota is in percent, fetched from EMAIL_SOFT_QUOTA."""
        quota = self._calculate_account_emailquota()
        eq = EmailQuota(self._db)
        try:
            eq.find_by_target_entity(self.entity_id)
        except Errors.NotFoundError:
            if quota is not None:
                eq.populate(cereconf.EMAIL_SOFT_QUOTA, quota)
                eq.write_db()
        else:
            # We never decrease quota, because of manual overrides
            if quota is None:
                eq.delete()
            elif quota > eq.email_quota_hard:
                eq.email_quota_hard = quota
                eq.write_db()

    # Calculate quota for this account
    def _calculate_account_emailquota(self):
        quota_settings = cereconf.EMAIL_HARD_QUOTA
        if quota_settings is None:
            return None
        # '*' is default quota size in EMAIL_HARD_QUOTA dict
        max_quota = quota_settings['*']
        for r in self.get_account_types():
            affiliation = six.text_type(self.const.PersonAffiliation(
                r['affiliation']))
            if affiliation in quota_settings:
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
        return self._id2mailaddr(entity_type=entity_type).iteritems()

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

    def _id2mailaddr(
            self, id_type=None, entity_type=None, filter_expired=True):
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
             et.target_entity_id = at.account_id
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
