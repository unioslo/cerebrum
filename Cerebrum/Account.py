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

"""The Account module stores information about an account of
arbitrary type.  Extentions like PosixUser are used for additional
parameters that may be required by the requested backend.

Usernames are stored in the table entity_name.  The domain that the
default username is stored in is yet to be determined.
"""

import os
import crypt,random,string
import time
import re

from Cerebrum import Utils
from Cerebrum.Entity import \
     Entity, EntityName, EntityQuarantine
from Cerebrum.modules import PasswordChecker
from Cerebrum.Database import Errors
import cereconf

class AccountType(object):
    """The AccountType class does not use populate logic as the only
    data stored represent a PK in the database"""

    def get_account_types(self, all_persons_types=False, owner_id=None):
        """Return dbrows of account_types for the given account"""
        if all_persons_types or owner_id is not None:
            col = 'person_id'
            if owner_id is not None:
                val = owner_id
            else:
                val = self.owner_id
        else:
            col = 'account_id'
            val = self.entity_id
        return self.query("""
        SELECT person_id, ou_id, affiliation, account_id, priority
        FROM [:table schema=cerebrum name=account_type]
        WHERE %(col)s=:%(col)s
        ORDER BY priority""" % {'col': col},
                          {col: val})

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Insert of update the new account type, with the given
        priority increasing priority for conflicting elements.  If
        priority is None, insert priority=max+5"""
        all_pris = {}
        orig_pri = None
        max_pri = 0
        for row in self.get_account_types(all_persons_types=True):
            all_pris[int(row['priority'])] = row
            if(ou_id == row['ou_id'] and affiliation == row['affiliation'] and
               self.entity_id == row['account_id']):
                orig_pri = row['priority']
            if row['priority'] > max_pri:
                max_pri = row['priority']
        if priority is None:
            priority = max_pri + 5
        if orig_pri is None:
            if all_pris.has_key(priority):
                self._set_account_type_priority(all_pris, priority, priority+1)
            cols = {'person_id': int(self.owner_id),
                    'ou_id': int(ou_id),
                    'affiliation': int(affiliation),
                    'account_id': int(self.entity_id),
                    'priority': priority}
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_type] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join(cols.keys()),
                                     'binds': ", ".join([":%s" % t for t in cols.keys()])},
                         cols)
            self._db.log_change(self.entity_id, self.const.account_type_add,
                                None, change_params={'ou_id': int(ou_id),
                                                     'affiliation': int(affiliation),
                                                     'priority': priority})
        else:
            if orig_pri <> priority:
                self._set_account_type_priority(all_pris, orig_pri, priority)

    def _set_account_type_priority(self, all_pris, orig_pri, new_pri):
        """Recursively insert the new priority, increasing parent
        priority with one if there is a conflict"""
        if all_pris.has_key(new_pri):
            self._set_account_type_priority(all_pris, new_pri, new_pri + 1)
        orig_pri = int(orig_pri)
        cols = {'person_id': all_pris[orig_pri]['person_id'],
                'ou_id': all_pris[orig_pri]['ou_id'],
                'affiliation': all_pris[orig_pri]['affiliation'],
                'account_id': all_pris[orig_pri]['account_id'],
                'priority': new_pri}
        self.execute("""
        UPDATE [:table schema=cerebrum name=account_type]
        SET priority=:priority
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x)
                                   for x in cols.keys() if x != "priority"]), cols)
        self._db.log_change(self.entity_id, self.const.account_type_mod,
                            None, change_params={'new_pri': new_pri,
                                                 'old_pri': orig_pri})
        
    def del_account_type(self, ou_id, affiliation):
        cols = {'person_id': self.owner_id,
                'ou_id': ou_id,
                'affiliation': int(affiliation),
                'account_id': self.entity_id}
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_type]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x)
                                   for x in cols.keys()]), cols)
        self._db.log_change(self.entity_id, self.const.account_type_del,
                            None, change_params={'ou_id': int(ou_id),
                                                 'affiliation': int(affiliation)})

    def list_accounts_by_type(self, ou_id=None, affiliation=None,
                              status=None):
        """Return ``account_id``s of the matching accounts."""
        extra=""
        if affiliation is not None:
            extra += " AND at.affiliation=:affiliation"
            # To use 'affiliation' as a bind param, it might need
            # casting to 'int'.  Do this here, where we know that
            # 'affiliation' isn't None.
            affiliation = int(affiliation)
        if status is not None:
            extra += " AND pas.status=:status"
        if ou_id is not None:
            extra += " AND at.ou_id=:ou_id"
        return self.query("""
        SELECT DISTINCT at.person_id, at.ou_id, at.affiliation, at.account_id
        FROM [:table schema=cerebrum name=account_type] at,
             [:table schema=cerebrum name=person_affiliation_source] pas
        WHERE at.person_id=pas.person_id AND
              at.ou_id=pas.ou_id AND
              at.affiliation=pas.affiliation
              %s""" % extra,
                          {'ou_id': ou_id,
                           'affiliation': affiliation,
                           'status': status})

class Account(AccountType, EntityName, EntityQuarantine, Entity):

    __read_attr__ = ('__in_db', '__plaintext_password'
                     # TODO: Get rid of these.
                     )
    __write_attr__ = ('account_name', 'owner_type', 'owner_id', 'home', 'disk_id',
                      'np_type', 'creator_id', 'expire_date', 'create_date',
                      '_auth_info', '_acc_affect_auth_types')

    def clear(self):
        super(Account, self).clear()
        self.clear_class(Account)
        self.__updated = []

        # TODO: The following attributes are currently not in
        #       Account.__slots__, which means they will stop working
        #       once all Entity classes have been ported to use the
        #       mark_update metaclass.
        self._auth_info = {}
        self._acc_affect_auth_types = []

    def __eq__(self, other):
        assert isinstance(other, Account)

        if (self.account_name != other.account_name or
            int(self.owner_type) != int(other.owner_type) or
            self.owner_id != other.owner_id or
            self.np_type != other.np_type or
            self.creator_id != other.creator_id or
            self.home != other.home or
            self.disk_id != other.disk_id or
            self.expire_date != other.expire_date):
            return False
        return True

    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, home=None, disk_id=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_account)
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
        if home is not None and disk_id is not None:
            raise ValueError, "Cannot set both disk_id and home."
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.np_type = np_type
        self.creator_id = creator_id
        self.expire_date = expire_date
        self.account_name = name
        self.home = home
        self.disk_id = disk_id

    def affect_auth_types(self, *authtypes):
        self._acc_affect_auth_types = list(authtypes)

    def populate_authentication_type(self, type, value):
        self._auth_info[int(type)] = value
        self.__updated.append('password')

    def set_password(self, plaintext):
        """Updates all account_authentication entries with an encrypted
        version of the plaintext password.  The methods to be used
        are determined by AUTH_CRYPT_METHODS.

        Note: affect_auth_types is automatically extended to contain
        these methods."""
        for method in cereconf.AUTH_CRYPT_METHODS:
            method_const = getattr(self.const, method)
            if not method_const in self._acc_affect_auth_types:
                self._acc_affect_auth_types.append(method_const)
            enc = getattr(self, "enc_%s" % method)
            enc = enc(plaintext)
            self.populate_authentication_type(getattr(self.const, method), enc)
        self.__plaintext_password = plaintext

    def enc_auth_type_md5_crypt(self, plaintext, salt=None):
        if salt is None:
            saltchars = string.uppercase + string.lowercase + string.digits + "./"
            s = []
            for i in range(8):
                s.append(random.choice(saltchars))
            salt = "$1$" + "".join(s)
        return crypt.crypt(plaintext, salt)

    def enc_auth_type_crypt3_des(self, plaintext, salt=None):
        if salt is None:
            saltchars = string.uppercase + string.lowercase + string.digits + "./"
            salt = Utils.random_string(2, saltchars)
        return crypt.crypt(plaintext, salt)

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('account_id', ':acc_id'),
                    ('owner_type', ':o_type'),
                    ('owner_id', ':o_id'),
                    ('np_type', ':np_type'),
                    ('home', ':home'),
                    ('disk_id', ':disk_id'),
                    ('creator_id', ':c_id')]
            # Columns that have default values through DDL.
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_info] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         {'e_type' : int(self.const.entity_account),
                          'acc_id' : self.entity_id,
                          'o_type' : int(self.owner_type),
                          'c_id' : self.creator_id,
                          'o_id' : self.owner_id,
                          'np_type' : self.np_type,
                          'exp_date' : self.expire_date,
                          'home' : self.home,
                          'disk_id' : self.disk_id,
                          'create_date': self.create_date})
            self._db.log_change(self.entity_id, self.const.account_create, None)
            self.add_entity_name(self.const.account_namespace, self.account_name)
        else:
            cols = [('owner_type',':o_type'),
                    ('owner_id',':o_id'),
                    ('np_type',':np_type'),
                    ('home', ':home'),
                    ('disk_id', ':disk_id'),
                    ('creator_id',':c_id')]
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))

            self.execute("""
            UPDATE [:table schema=cerebrum name=account_info]
            SET %(defs)s
            WHERE account_id=:acc_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols])},
                         {'o_type' : int(self.owner_type),
                          'c_id' : self.creator_id,
                          'o_id' : self.owner_id,
                          'np_type' : self.np_type,
                          'exp_date' : self.expire_date,
                          'home' : self.home,
                          'disk_id' : self.disk_id,
                          'acc_id' : self.entity_id})
            self._db.log_change(self.entity_id, self.const.account_mod, None)
            if 'account_name' in self.__updated:
                self.update_entity_name(self.const.account_namespace, self.account_name)

        # We store the plaintext password in the changelog so that
        # other systems that need it may get it.  The changelog
        # handler should remove the plaintext password using some
        # criteria.
        try:
            plain = self.__plaintext_password
        except AttributeError:
            # TODO: this is meant to catch that self.__plaintext_password is unset
            pass
        else:
            # self.__plaintext_password is set.  Put the value in the
            # changelog.
            self._db.log_change(self.entity_id, self.const.account_password,
                                None, change_params={'password': plain})

        # Store the authentication data.
        for k in self._acc_affect_auth_types:
            k = int(k)
            what = 'insert'
            if self.__in_db:
                try:
                    dta = self.get_account_authentication(k)
                    if dta != self._auth_info.get(k, None):
                        what = 'update'
                    else:
                        what = 'nothing'
                except Errors.NotFoundError:
                     # insert
                     pass
            if self._auth_info.get(k, None) is not None:
                if what == 'insert':
                    self.execute("""
                    INSERT INTO
                      [:table schema=cerebrum name=account_authentication]
                      (account_id, method, auth_data)
                    VALUES (:acc_id, :method, :auth_data)""",
                                 {'acc_id' : self.entity_id, 'method' : k,
                                  'auth_data' : self._auth_info[k]})
                elif what == 'update':
                    self.execute("""
                    UPDATE [:table schema=cerebrum name=account_authentication]
                    SET auth_data=:auth_data
                    WHERE account_id=:acc_id AND method=:method""",
                                 {'acc_id' : self.entity_id, 'method' : k,
                                  'auth_data' : self._auth_info[k]})
            elif self.__in_db and what == 'update':
                    self.execute("""
                    DELETE FROM [:table schema=cerebrum name=account_authentication]
                    WHERE account_id=:acc_id AND method=:method""",
                                 {'acc_id' : self.entity_id, 'method' : k})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def new(self, name, owner_type, owner_id, np_type, creator_id,
            expire_date, home=None, disk_id=None):
        self.populate(name, owner_type, owner_id, np_type, creator_id,
                      expire_date, home=home, disk_id=disk_id)
        self.write_db()
        self.find(self.entity_id)

    def find(self, account_id):
        self.__super.find(account_id)

        (self.owner_type, self.owner_id,
         self.np_type, self.create_date, self.creator_id,
         self.expire_date, self.home, self.disk_id) = self.query_1("""
        SELECT owner_type, owner_id, np_type, create_date,
               creator_id, expire_date, home, disk_id
        FROM [:table schema=cerebrum name=account_info]
        WHERE account_id=:a_id""", {'a_id' : account_id})
        self.account_name = self.get_name(self.const.account_namespace)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name, domain=None):
        if domain is None:
            domain = int(self.const.account_namespace)
        EntityName.find_by_name(self, name, domain)

    def get_account_authentication(self, method):
        """Return the name with the given variant"""

        return self.query_1("""
        SELECT auth_data
        FROM [:table schema=cerebrum name=account_authentication]
        WHERE account_id=:a_id AND method=:method""",
                            {'a_id': self.entity_id,
                             'method': int(method)})

    def get_account_expired(self):
        """Return expire_date if account expire date is overdue, else False"""
        try:
            return self.query_1("""
            SELECT expire_date
            FROM [:table schema=cerebrum name=account_info]
            WHERE expire_date < [:now] AND account_id=:a_id""",
                                {'a_id': self.entity_id})
        except Errors.NotFoundError:
            return False

    # TODO: is_reserved and list_reserved_users belong in an extended
    # version of Account
    def is_reserved(self):
        """We define a reserved account as an account with no
        expire_date and no spreads"""
        if (self.expire_date is not None) or self.get_spread():
            return False
        return True

    def is_deleted(self):
        """We define a reserved account as an account with 
        expire_date < now() and no spreads"""
        if (self.expire_date is not None and
            self.expire_date < time.time and (not self.get_spread())):
            return True
        return False

    def list(self):
        """Returns all accounts"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info]""")

    def list_account_name_home(self):
        """Returns a list of account_id, name, home and path."""
        return self.query("""
        SELECT a.account_id, e.entity_name, a.home, d.path
        FROM [:table schema=cerebrum name=entity_name] e,
             [:table schema=cerebrum name=account_info] a
             LEFT JOIN [:table schema=cerebrum name=disk_info] d
               ON d.disk_id = a.disk_id
        WHERE a.account_id=e.entity_id""")

    def list_reserved_users(self):
        """Return all reserved users"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai
        WHERE ai.expire_date IS NULL AND NOT EXISTS (
          SELECT 'foo' FROM [:table schema=cerebrum name=entity_spread] es
          WHERE es.entity_id=ai.account_id)""")

    def list_accounts_by_owner_id(self, owner_id):
        """Return a list of account-ids, or None if none found"""
        try:
            return self.query("""
            SELECT account_id
            FROM [:table schema=cerebrum name=account_info]
            WHERE owner_id=:o_id""",{'o_id': owner_id})
        except Errors.NotFoundError:
            return None

    def get_account_name(self):
        return self.account_name

    def make_passwd(self, uname):
        """Generate a random password with 8 characters"""
        pot = ('-+?=*()/&%#\'_!,;.:'
               'abcdefghijklmnopqrstuvwxyABCDEFGHIJKLMNOPQRSTUVWXY0123456789')
        pc = PasswordChecker.PasswordChecker(self._db)
        while True:
            r = ''
            while len(r) < 8:
                r += pot[random.randint(0, len(pot)-1)]
            try:
                pc.goodenough(None, r, uname=uname)
                return r
            except PasswordChecker.PasswordGoodEnoughException:
                pass  # Wasn't good enough
