# Copyright 2002 University of Oslo, Norway
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

from Cerebrum import Utils
from Cerebrum.Entity import \
     Entity, EntityName, EntityQuarantine
from Cerebrum.Database import Errors
from Cerebrum import cereconf
import crypt,random,string

class Account(EntityName, EntityQuarantine, Entity):
    __metaclass__ = Utils.mark_update

    __read_attr = ('__in_db',)
    __write_attr__ = ('account_name', 'owner_type', 'owner_id',
                      'np_type', 'creator_id', 'expire_date', 'create_date')

    def clear(self):
        super(Account, self).clear()
        for attr in Account.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in Account.__write_attr__:
            setattr(self, attr, None)
            self.__updated = False
        self._name_info = {}
        self._auth_info = {}
        self._acc_affect_auth_types = ()

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
        self.__in_db = False
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.np_type = np_type
        self.creator_id = creator_id
        self.expire_date = expire_date
        self.account_name = name

    def affect_auth_types(self, *authtypes):
        self._acc_affect_auth_types = authtypes

    def populate_authentication_type(self, type, value):
        self._auth_info[int(type)] = value

    def set_password(self, plaintext):
        """Updates all account_authentication entries with an encrypted
        version of the plaintext password.  The methods to be used
        are determined by AUTH_CRYPT_METHODS.

        Note: affect_auth_types is automatically extended to contain
        these methods."""
        for method in cereconf.AUTH_CRYPT_METHODS:
            method_const = getattr(self.const, method)
            if not method_const in self._acc_affect_auth_types:
                self._acc_affect_auth_types = self._acc_affect_auth_types + (method_const,)
            enc = getattr(self, "enc_%s" % method)
            enc = enc(plaintext)
            self.populate_authentication_type(getattr(self.const, method), enc)

    def enc_auth_type_md5(self, plaintext):
        saltchars = string.uppercase + string.lowercase + string.digits + "./"
        s = []
        for i in range(8):
            s.append(random.choice(saltchars))
        salt = "$1$" + string.join(s, "")
        return crypt.crypt(plaintext, salt)

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        if not self.__in_db:
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
            # TBD: This is superfluous (and wrong) to do here if
            # there's a write_db() method in EntityName.
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=entity_name]
              (entity_id, value_domain, entity_name)
            VALUES (:g_id, :domain, :name)""",
                         {'g_id': self.entity_id,
                          'domain': int(self.const.account_namespace),
                          'name': self.account_name})
        else:
            cols = [('owner_type',':o_type'),
                    ('owner_id',':o_id'),
                    ('np_type',':np_type'),
                    ('creator_id',':c_id')]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
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
                          'e_date' : self.expire_date,
                          'acc_id' : self.entity_id})
            # TBD: Maybe this is better done in EntityName.write_db()?
            self.execute("""
            UPDATE [:table schema=cerebrum name=entity_name]
            SET entity_name=:name
            WHERE
              entity_id=:g_id AND
              value_domain=:domain""",
                         {'g_id': self.entity_id,
                          'domain': int(self.const.account_namespace),
                          'name': self.account_name})

        # Store the authentication data.
        for k in self._acc_affect_auth_types:
            k = int(k)
            what = 'insert'
            if self.__in_db:
                try:
                    dta = self.get_account_authentication(k)
                    if dta != self._auth_info.get(k, None):
                        what = 'update'
                except Errors.NotFoundError:
                     # insert
                     pass
            if self._auth_info.get(k, None) is not None:
                if what == 'insert':
                    self.execute("""
                    INSERT INTO [:table schema=cerebrum name=account_authentication]
                        (account_id, method, auth_data)
                    VALUES (:acc_id, :method, :auth_data)""",
                                 {'acc_id' : self.account_id, 'method' : k,
                                  'auth_data' : self._auth_info[k]})
                else:
                    self.execute("""
                    UPDATE [:table schema=cerebrum name=account_authentication]
                    SET auth_data=:auth_data
                    WHERE account_id=:acc_id AND method=:method""",
                                 {'acc_id' : self.account_id, 'method' : k,
                                  'auth_data' : self._auth_info[k]})
            elif self.__in_db and what == 'update':
                    self.execute("""
                    DELETE [:table schema=cerebrum name=account_authentication]
                    WHERE account_id=:acc_id AND method=:method""",
                                 {'acc_id' : self.account_id, 'method' : k})
        del self.__in_db
        self.__in_db = True
        self.__updated = False

    def find(self, account_id):
        super(Account, self).find(account_id)

        (self.account_id, self.owner_type, self.owner_id,
         self.np_type, self.create_date, self.creator_id,
         self.expire_date) = self.query_1(
            """SELECT account_id, owner_type, owner_id, np_type, create_date, creator_id, expire_date
               FROM [:table schema=cerebrum name=account_info]
               WHERE account_id=:a_id""", {'a_id' : account_id})
        self.account_name = self.get_name(self.const.account_namespace)[0][2]

    def find_account_by_name(self, domain, name):
        self.find_by_name(domain, name)
        self.find(self.entity_id)

    def get_account_authentication(self, method):
        """Return the name with the given variant"""

        return self.query_1("""SELECT auth_data FROM [:table schema=cerebrum name=account_authentication]
            WHERE account_id=:a_id AND method=:method""",
                            {'a_id' : self.account_id, 'method' : int(method)})
