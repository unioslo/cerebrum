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

from Cerebrum.Entity import \
     Entity, EntityName, EntityQuarantine
from Cerebrum import cereconf
import crypt,random,string

# TODO: I'm not sure how PosixUser should be imported as a mix-in
# class.  The current implementation makes Account depending on Posix
# user, which is not correct.

from Cerebrum.modules.PosixUser import PosixUser

class Account(Entity, EntityName, EntityQuarantine, PosixUser):

    def clear(self):
        self.owner_type = None
        self.owner_id = None
        self.np_type = None
        self.creator_id = None
        self.expire_date = None
        self._name_info = {}
        self._acc_affect_domains = None
        self._auth_info = {}
        self._acc_affect_auth_types = None

    def __eq__(self, other):
        if self._pn_affect_source is None:
            return True
        assert isinstance(other, Account)
        if not PosixUser.__eq__(self, other): return False

        if (self.owner_type != other.owner_type or
            self.owner_id != other.owner_id or
            self.np_type != other.np_type or
            self.creator_id != other.creator_id or
            self.expire_date != other.expire_date):
            return False

        for type in self._acc_affect_domains:  # Compare unames in afffect_domaines
            other_name = other.get_name(type)
            my_name = self._name_info.get(type, None)
            if my_name != other_name:
                return False
        return True

    def affect_domains(self, *domains):
        self._acc_affect_domains = domains

    def populate_name(self, domain, name):
        """Username is stored in entity_name."""
        self._name_info[domain] = name

    def populate(self, owner_type, owner_id, np_type, creator_id, expire_date):
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.np_type = np_type
        self.creator_id = creator_id
        self.expire_date = expire_date

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
            if not method in self._acc_affect_auth_types:
                self._acc_affect_auth_types = self._acc_affect_auth_types + (method,)
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
    
    def write_db(self, as_object=None):
        type = self.np_type
        if type is not None: type = int(type)

        if as_object is None:
            new_id = super(Account, self).new(int(self.const.entity_account))

            self.execute("""
            INSERT INTO [:table schema=cerebrum name=account_info] (entity_type, account_id,
                owner_type, owner_id, np_type, create_date, creator_id, expire_date)
            VALUES (:e_type, :acc_id, :o_type, :o_id, :np_type, [:now], :c_id, :e_date)""",
                         {'e_type' : int(self.const.entity_account),
                          'acc_id' : new_id,
                          'o_type' : int(self.owner_type),
                          'c_id' : self.creator_id,
                          'o_id' : self.owner_id,
                          'np_type' : type,
                          'e_date' : self.expire_date})
            self.account_id = new_id
            for k in self._acc_affect_domains:
                if self._name_info.get(k, None) is not None:
                    self.add_name(k, self._name_info[k])
            PosixUser.write_db(self, as_object)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=account_info]
            SET owner_type=:o_type, owner_id=:o_id, np_type=:np_type,
               creator_id:c_id, expire_date:e_date)
            WHERE account_id=:acc_id""",
                         {'o_type' : int(self.owner_type),
                          'c_id' : self.creator_id,
                          'o_id' : self.owner_id,
                          'np_type' : type,
                          'e_date' : self.expire_date,
                          'acc_id' : as_object.account_id})
            self.account_id = as_object.account_id

        # Store the authentication data.

        for k in self._acc_affect_auth_types:
            k = int(k)
            what = 'insert'
            if as_object is not None:
                try:
                    dta = as_object.get_account_authentication(k)
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
            elif as_object is not None and what == 'update':
                    self.execute("""
                    DELETE [:table schema=cerebrum name=account_authentication]
                    WHERE account_id=:acc_id AND method=:method""",
                                 {'acc_id' : self.account_id, 'method' : k})
        return new_id

    def find(self, account_id):
        super(Account, self).find(account_id)

        (self.account_id, self.owner_type, self.owner_id,
         self.np_type, self.create_date, self.creator_id,
         self.expire_date) = self.query_1(
            """SELECT account_id, owner_type, owner_id, np_type, create_date, creator_id, expire_date
               FROM [:table schema=cerebrum name=account_info]
               WHERE account_id=:a_id""", {'a_id' : account_id})

    def find_account_by_name(self, domain, name):
        self.find_by_name(domain, name)
        self.find(self.entity_id)

    def get_account_authentication(self, method):
        """Return the name with the given variant"""

        return self.query_1("""SELECT auth_data FROM [:table schema=cerebrum name=account_authentication]
            WHERE account_id=:a_id AND method=:method""",
                            {'a_id' : self.account_id, 'method' : int(method)})
    
