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
        # TODO: Implement this
        if self._pn_affect_source == None:
            return True
        assert isinstance(other, Account)
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
        # Updates all account_authentication entries with an encrypted
        # version of the plaintext password.  The methods to be used
        # are determined by AUTH_CRYPT_METHODS
        for method in cereconf.AUTH_CRYPT_METHODS:
            # TODO: We should probably assert that the corresponding
            # self._acc_affect_auth_types is set
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
        # TODO: Update existing records
        
        new_id = super(Account, self).new(int(self.const.entity_account))
        type = self.np_type
        if type != None: type = int(type)

        self.execute("""
        INSERT INTO [:table schema=cerebrum name=account_info] (entity_type, account_id, owner_type,
                    owner_id, np_type, create_date, creator_id, expire_date)
        VALUES (:e_type, :acc_id, :o_type, :o_id, :np_type, [:now], :c_id, :e_date)""",
                     {'e_type' : int(self.const.entity_account),
                      'acc_id' : new_id, 'o_type' : int(self.owner_type),
                      'c_id' : self.creator_id,
                      'o_id' : self.owner_id, 'np_type' : type,
                      'e_date' : self.expire_date})
        self.account_id = new_id
        for k in self._acc_affect_domains:
            if self._name_info.get(k, None) != None:
                self.add_name(k, self._name_info[k])
        PosixUser.write_db(self, as_object)

        # Store the authentication data.
        #
        # We probably want to do this in another way, or atleast
        # provide an optional method "set_password" that takes a
        # plaintext password as input, and sets the apropriate
        # auth_data for the desired (=_acc_affect_auth_types?)
        # account_authentication methods.

        for k in self._acc_affect_auth_types:
            k = int(k)
            if self._auth_info.get(k, None) != None:
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=account_authentication] (account_id, method, auth_data)
                VALUES (:acc_id, :method, :auth_data)""",
                             {'acc_id' : self.account_id, 'method' : k,
                              'auth_data' : self._auth_info[k]})
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
    
