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
import crypt
import random
import string
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
                                                     'priority': int(priority)})
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
                            None, change_params={'new_pri': int(new_pri),
                                                 'old_pri': int(orig_pri)})
        
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
                              status=None, filter_expired=False,
                              account_id=None, person_id=None, fetchall=True):
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
        if person_id is not None:
            extra += " AND at.person_id=:person_id"
        if filter_expired:
            extra += " AND (ai.expire_date IS NULL OR ai.expire_date > [:now])"
        if account_id:
            extra += " AND ai.account_id=:account_id"
        return self.query("""
        SELECT DISTINCT at.person_id, at.ou_id, at.affiliation, at.account_id,
                        at.priority
        FROM [:table schema=cerebrum name=account_type] at,
             [:table schema=cerebrum name=person_affiliation_source] pas,
             [:table schema=cerebrum name=account_info] ai
        WHERE at.person_id=pas.person_id AND
              at.ou_id=pas.ou_id AND
              at.affiliation=pas.affiliation AND
              ai.account_id=at.account_id
              %s
        ORDER BY at.person_id, at.priority""" % extra,
                          {'ou_id': ou_id,
                           'affiliation': affiliation,
                           'status': status,
                           'account_id' : account_id,
                           'person_id': person_id}, fetchall = fetchall)
    # end list_accounts_by_type


class AccountHome(object):
    """AccountHome keeps track of where the users home dir is.  There
    may a different home dir for each spread.  A home is identified
    either by a disk_id, or by the string represented by home"""

    def clear_home(self, spread):
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=account_home]
            WHERE account_id=:account_id AND spread=:spread""", {
                'account_id': self.entity_id,
                'spread': int(spread)})
            self._db.log_change(
                self.entity_id, self.const.account_home_removed, None,
                change_params={'spread': int(spread)})

    def set_home(self, spread, disk_id=None, home=None, status=None):
        binds = {'account_id': self.entity_id,
                 'spread': int(spread),
                 'disk_id': disk_id,
                 'home': home,
                 'status': status
            }
        if status:
            binds['status'] = int(status)
        if home and disk_id:
            raise ValueError, "Cannot set both disk_id and home."
        try:
            old = self.get_home(spread)
            self.execute("""
            UPDATE [:table schema=cerebrum name=account_home]
            SET home=:home, disk_id=:disk_id, status=:status
            WHERE account_id=:account_id AND spread=:spread""", binds)
            self._db.log_change(
                self.entity_id, self.const.account_home_updated, None,
                change_params={'spread': int(spread),
                               'old_disk_id': Utils.format_as_int(old['disk_id']),
                               'old_home': old['home']})
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_home]
              (account_id, spread, home, disk_id, status)
            VALUES
              (:account_id, :spread, :home, :disk_id, :status)""", binds)
            self._db.log_change(
                self.entity_id, self.const.account_home_added, None,
                change_params={'spread': int(spread)})

    def get_home(self, spread):
        return self.query_1("""
        SELECT disk_id, home, status
        FROM [:table schema=cerebrum name=account_home]
        WHERE account_id=:account_id AND spread=:spread""",
                            {'account_id': self.entity_id,
                             'spread': int(spread)})

class Account(AccountType, AccountHome, EntityName, EntityQuarantine, Entity):

    __read_attr__ = ('__in_db', '__plaintext_password'
                     # TODO: Get rid of these.
                     )
    __write_attr__ = ('account_name', 'owner_type', 'owner_id',
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
            self.expire_date != other.expire_date):
            return False
        return True

    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, parent=None):
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
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.np_type = np_type
        self.creator_id = creator_id
        self.expire_date = expire_date
        self.account_name = name

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
            saltchars = string.ascii_letters + string.digits + "./"
            s = []
            for i in range(8):
                s.append(random.choice(saltchars))
            salt = "$1$" + "".join(s)
        return crypt.crypt(plaintext, salt)

    def enc_auth_type_crypt3_des(self, plaintext, salt=None):
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = Utils.random_string(2, saltchars)
        return crypt.crypt(plaintext, salt)

    def illegal_name(self, name):
        """Return a string with error message if username is illegal"""
        return False

    def write_db(self):
        tmp = self.illegal_name(self.account_name)
        if tmp:
            raise self._db.IntegrityError, "Illegal username: %s" % tmp

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
                          'create_date': self.create_date})
            self._db.log_change(self.entity_id, self.const.account_create, None)
            self.add_entity_name(self.const.account_namespace, self.account_name)
        else:
            cols = [('owner_type',':o_type'),
                    ('owner_id',':o_id'),
                    ('np_type',':np_type'),
                    ('creator_id',':c_id'),
                    ('expire_date', ':exp_date')]

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
            expire_date):
        self.populate(name, owner_type, owner_id, np_type, creator_id,
                      expire_date)
        self.write_db()
        self.find(self.entity_id)

    def find(self, account_id):
        self.__super.find(account_id)

        (self.owner_type, self.owner_id,
         self.np_type, self.create_date, self.creator_id,
         self.expire_date) = self.query_1("""
        SELECT owner_type, owner_id, np_type, create_date,
               creator_id, expire_date
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
        if (not self.is_expired()) and (not self.get_spread()):
            return True
        return False

    def is_deleted(self):
        """We define a reserved account as an account with 
        expire_date < now() and no spreads"""
        if self.is_expired() and not self.get_spread():
            return True
        return False

    def is_expired(self):
        now = self._db.DateFromTicks(time.time())
        if self.expire_date is None or self.expire_date >= now:
            return False
        return True

    def list(self, filter_expired=False, fetchall=True):
        """Returns all accounts"""
        where = []
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")
        if where:
            where = "WHERE %s" % " AND ".join(where)
        else:
            where = ""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai %s""" % where,
                          fetchall = fetchall)

    def list_account_name_home(self, spread, filter_home=False):
        """Returns a list of account_id, name, home and path.
           filter_home=False means that spread is a filter on
           accounts. filter_home=True means that the spread is
           a filter on home."""

        if filter_home:
            return self.query("""
            SELECT ai.account_id, en.entity_name, ah.home, d.path
            FROM [:table schema=cerebrum name=entity_name] en,
                 [:table schema=cerebrum name=account_info] ai
                 LEFT JOIN [:table schema=cerebrum name=account_home] ah
                   ON ah.account_id=ai.account_id AND ah.spread=:spread
                 LEFT JOIN [:table schema=cerebrum name=disk_info] d
                   ON d.disk_id = ah.disk_id
            WHERE ai.account_id=en.entity_id""", {'spread': int(spread)})

        return self.query("""
            SELECT ai.account_id, en.entity_name, ah.home, d.path
            FROM [:table schema=cerebrum name=entity_name] en,
                 [:table schema=cerebrum name=account_info] ai,
                 [:table schema=cerebrum name=entity_spread] es
                 LEFT JOIN [:table schema=cerebrum name=account_home] ah
                   ON ah.account_id=es.entity_id AND es.spread = ah.spread
                 LEFT JOIN [:table schema=cerebrum name=disk_info] d
                   ON d.disk_id = ah.disk_id
            WHERE ai.account_id=en.entity_id AND en.entity_id=es.entity_id
                  AND es.spread=:spread""", {'spread': int(spread)})

    
    def list_reserved_users(self, fetchall=True):
        """Return all reserved users"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai
        WHERE ai.expire_date IS NULL AND NOT EXISTS (
          SELECT 'foo' FROM [:table schema=cerebrum name=entity_spread] es
          WHERE es.entity_id=ai.account_id)""",
                          fetchall = fetchall)

    def list_deleted_users(self):
        """Return all deleted users"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_info] ai
        WHERE ai.expire_date < [:now] AND NOT EXISTS (
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

    def list_account_authentication(self, auth_type=None):
        type_str = ""
        if auth_type == None:
            type_str = "= %d" % int(self.const.auth_type_md5_crypt)
        elif isinstance(auth_type, list):
            type_str = "IN (%d" % int(auth_type[0])
            for at in auth_type[1:]:
                type_str += ", %d" % int(at)
            type_str += ")"
        else:
            type_str = "= %d" % int(auth_type)
        return self.query("""
        SELECT ai.account_id, en.entity_name, aa.method, aa.auth_data
        FROM [:table schema=cerebrum name=entity_name] en,
             [:table schema=cerebrum name=account_info] ai
             LEFT JOIN [:table schema=cerebrum name=account_authentication] aa
               ON ai.account_id=aa.account_id AND aa.method %s
        WHERE ai.account_id=en.entity_id""" % type_str)

    def get_account_name(self):
        return self.account_name

    def make_passwd(self, uname):
        """Generate a random password with 8 characters"""
        pot = string.ascii_letters + string.digits + '-+?=*()/&%#"_!,;.:'
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

    def suggest_unames(self, domain, fname, lname, maxlen=8, suffix=""):
        """Returns a tuple with 15 (unused) username suggestions based
        on the person's first and last name.

        domain: value domain code
        fname:  first name (and any middle names)
        lname:  last name
        maxlen: maximum length of a username (incl. the suffix)
        suffix: string to append to every generated username
        """
        goal = 15	# We may return more than this
        maxlen -= len(suffix)
        potuname = ()
        if fname.strip() == "" or lname.strip() == "":
            raise ValueError,\
                  "Currently only fullname supported, got '%s', '%s'" % \
                  (fname, lname)
        # We ignore hyphens in the last name, but extract the
        # initials from the first name(s).
        fname = self.simplify_name(fname, alt=1)
        lname = self.simplify_name(lname.replace('-', ''), alt=1)

        initials = [n[0] for n in re.split(r'[ -]', fname)]
        firstinit = "".join(initials[:-1])
        if len(initials) > 1:
            initial = initials[-1]
        else:
            initial = None

        # Now remove all hyphens and keep just the first name.  People
        # called "Geir-Ove Johnsen Hansen" generally prefer "geirove"
        # to just "geir".

        fname = fname.replace('-', '').split(" ")[0][0:maxlen]

        # For people with many (more than three) names, we prefer to
        # use all initials.
        # Example:  Geir-Ove Johnsen Hansen
        #           ffff fff i       llllll
        # Here, firstinit is "GO" and initial is "J".
        #
        # gohansen gojhanse gohanse gojhanse ... goh gojh
        # ssllllll ssilllll sslllll ssilllll     ssl ssil
        #
        # ("ss" means firstinit, "i" means initial, "l" means last name)

        if len(firstinit) > 1:
            llen = len(lname)
            if llen + len(firstinit) > maxlen:
                llen = maxlen - len(firstinit)
            for j in range(llen, 0, -1):
                un = firstinit + lname[0:j] + suffix
                if self.validate_new_uname(domain, un):
                    potuname += (un, )

                if initial and len(firstinit) + 1 + j <= maxlen:
                    un = firstinit + initial + lname[0:j] + suffix
                    if self.validate_new_uname(domain, un):
                        potuname += (un, )

                if len(potuname) >= goal:
                    break

        # Now try different substrings from first and last name.
        #
        # geiroveh,
        # fffffffl
        # geirovjh geirovh geirovha,
        # ffffffil ffffffl ffffffll
        # geirojh geiroh geirojha geiroha geirohan,
        # fffffil fffffl fffffill fffffll ffffflll
        # geirjh geirh geirjha geirha geirjhan geirhan geirhans
        # ffffil ffffl ffffill ffffll ffffilll fffflll ffffllll
        # ...
        # gjh gh gjha gha gjhan ghan ... gjhansen ghansen
        # fil fl fill fll filll flll     fillllll fllllll

        flen = len(fname)
        if flen > maxlen - 1:
            flen = maxlen - 1

        for i in range(flen, 0, -1):
            llim = len(lname)
            if llim > maxlen - i:
                llim = maxlen - i
            for j in range(1, llim + 1):
                if initial:
                    # Is there room for an initial?
                    if j < llim:
                        un = fname[0:i] + initial + lname[0:j] + suffix
                        if self.validate_new_uname(domain, un):
                            potuname += (un, )
                un = fname[0:i] + lname[0:j] + suffix
                if self.validate_new_uname(domain, un):
                    potuname += (un, )
            if len(potuname) >= goal:
                break

        # Absolutely last ditch effort:  geirov1, geirov2 etc.
        i = 1
        prefix = (fname + lname)[:maxlen - 2]

        while len(potuname) < goal and i < 100:
            un = prefix + str(i) + suffix
            i += 1
            if self.validate_new_uname(domain, un):
                potuname += (un, )

        return potuname

    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        try:
            # We instanciate EntityName directly because find_by_name
            # calls self.find() whose result may depend on the class
            # of self
            en = EntityName(self._db)
            en.find_by_name(uname, domain)
            return 0
        except Errors.NotFoundError:
            return 1

    def simplify_name(self, s, alt=0, as_gecos=0):
        """Convert string so that it only contains characters that are
        legal in a posix username.  If as_gecos=1, it may also be
        used for the gecos field"""

        xlate = {'Æ' : 'ae', 'æ' : 'ae', 'Å' : 'aa', 'å' : 'aa'}
        if alt:
            s = string.join(map(lambda x:xlate.get(x, x), s), '')

        tr = string.maketrans(
           'ÆØÅæø¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäçèéêëìíîïñòóôõöùúûüý{[}]|¦\\',
           'AOAaooaAAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuuyaAaAooO')
        s = string.translate(s, tr)

        xlate = {}
        for y in range(0200, 0377): xlate[chr(y)] = 'x'
        xlate['Ð'] = 'Dh'
        xlate['ð'] = 'dh'
        xlate['Þ'] = 'Th'
        xlate['þ'] = 'th'
        xlate['ß'] = 'ss'
        s = string.join(map(lambda x:xlate.get(x, x), s), '')
        s = re.sub(r'[^a-zA-Z0-9 -]', '', s)
        if not as_gecos:
            s = s.lower()
        return s

    def search(self, spread=None, name=None, owner_id=None, owner_type=None,
               exclude_expired=False):
        """Retrieves a list of Accounts filtered by the given criterias.
        
        Returns a list of tuples with the info (account_id, name).
        If no criteria is given, all accounts are returned. ``name`` should
        be string if given. ``spead`` can either be string or int. ``owner_id``
        and ``owner_type`` should be int. Wildcards * and ? are expanded for
        "any chars" and "one char"."""

        def prepare_string(value):
            value = value.replace("*", "%")
            value = value.replace("?", "_")
            value = value.lower()
            return value

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=account_info] ai")
        tables.append("[:table schema=cerebrum name=entity_name] en")
        where.append("en.entity_id=ai.account_id")
        where.append("en.value_domain=:vdomain")

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("ai.account_id=es.entity_id")
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
            where.append("LOWER(en.entity_name) LIKE :name")

        if owner_id is not None:
            where.append("ai.owner_id=:owner_id")

        if owner_type is not None:
            where.append("ai.owner_type=:owner_type")

        if exclude_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT ai.account_id AS account_id, en.entity_name AS name
        FROM %s %s""" % (','.join(tables), where_str),
            {'spread': spread, 'entity_type': int(self.const.entity_account),
             'name': name, 'owner_id': owner_id, 'owner_type': owner_type,
             'vdomain': int(self.const.account_namespace)})

