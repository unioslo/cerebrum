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
import re

from Cerebrum import Utils
from Cerebrum.Entity import \
     Entity, EntityName, EntityQuarantine
from Cerebrum.Database import Errors
import cereconf

class PasswordGoodEnoughException(Exception):
    """Exception raised by Account.goodenough() for insufficiently strong passwds."""
    pass

class AccountType(object):
    """The AccountType class does not use populate logic as the only
    data stored represent a PK in the database"""

    def get_account_types(self):
        """Return dbrows of account_types for the given account"""
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=account_type]
        WHERE account_id=:account_id""",
                          {'account_id': self.entity_id})

    def add_account_type(self, person_id, ou_id, affiliation):
        cols = {'person_id': int(person_id),
                'ou_id': int(ou_id),
                'affiliation': int(affiliation),
                'account_id': int(self.entity_id)}
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=account_type] (%(tcols)s)
        VALUES (%(binds)s)""" % {'tcols': ", ".join(cols.keys()),
                                 'binds': ", ".join([":%s" % t for t in cols.keys()])},
                     cols)

    def del_account_type(self, person_id, ou_id, affiliation):
        cols = {'person_id': person_id,
                'ou_id': ou_id,
                'affiliation': int(affiliation),
                'account_id': self.entity_id}
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_type]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x)
                                   for x in cols.keys()]), cols)

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
        for attr in Account.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in Account.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

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
        self.__updated = True

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
                          'e_date' : self.expire_date,
                          'home' : self.home,
                          'disk_id' : self.disk_id,
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
            self._db.log_change(self.entity_id, self.const.a_password,
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
        self.__updated = False
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
        self.__updated = False

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
        while 1:
            r = ''
            while(len(r) < 8):
                r += pot[random.randint(0, len(pot)-1)]
            try:
                if self.goodenough(uname, r): break
            except PasswordGoodEnoughException:
                pass  # Wasn't good enough
        return r

    def look(self, FH, key, dict, fold):
        """Quick port of look.pl (distributed with perl)"""
        blksize = os.statvfs(FH.name)[0]
        if blksize < 1 or blksize > 65536: blksize = 8192
        if dict: key = re.sub(r'[^\w\s]', '', key)
        if fold: key = key.lower()
        max = int(os.path.getsize(FH.name) / blksize)
        min = 0
        while (max - min > 1):
            mid = int((max + min) / 2)
            FH.seek(mid * blksize, 0)
            if mid: line = FH.readline()  # probably a partial line
            line = FH.readline()
            line.strip()
            if dict: line = re.sub(r'[^\w\s]', '', line)
            if fold: line = line.lower()
            if line < key:
                min = mid
            else:
                max = mid
        min = min * blksize
        FH.seek(min, 0)
        if min: FH.readline()
        while 1:
            line = FH.readline()
            if not line: break
            line.strip()
            if dict: line = re.sub(r'[^\w\s]', '', line)
            if fold: line = line.lower()
            if line >= key: break
            min = FH.tell()
        FH.seek(min, 0)
        return min

    # TODO: These don't belong here
    msgs = {
        'not_null_char': ("Please don't use the null character in your"
                          " password."),
        'atleast8': "The password must be at least 8 characters long.",
        '8bit': ("Don't use 8-bit characters in your password (זרו),"
                 " it creates problems when using some keyboards."),
        'space': ("Don't use a space in the password.  It creates"
                  " problems for the POP3-protocol (Eudora and other"
                  " e-mail readers)."),
        'mix_needed8': ("A valid password must contain characters from at"
                        " least three of these four character groups:"
                        " Uppercase letters, lowercase letters, numbers and"
                        " special characters.  If the password only contains"
                        " one uppercase letter, this must not be at the start"
                        " of the password.  If the first 8 characters only"
                        " contains one number or special character, this must"
                        " not be in position 8."),
        'mix_needed': ("A valid password must contain characters from at"
                       " least three of these four character groups:"
                       " Uppercase letters, lowercase letters, numbers and"
                       " special characters."),

        'was_like_old': ("That was to close to an old password.  You must"
                         " select a new one."),
        'dict_hit': "Don't use words in a dictionary."
        }
    words = ("dummy",)
    dir = "/tmp"

    def check_password_history(self, uname, passwd):
        """Check wether uname had this passwd earlier.  Raises a
        TODOError if this is true"""
        if 0:
            raise PasswordGoodEnoughException(msgs['was_like_old'])
        return 1

    def goodenough(self, uname, passwd):
        """Perform a number of checks on a password to see if it is
        random enough.  This is done by checking the mix of
        upper/lowercase letters and special characers, as well as
        checking a database."""
        # TODO:  This needs more work.
        msgs = self.msgs
        passwd = passwd[0:8]

        if re.search(r'\0', passwd):
            raise PasswordGoodEnoughException(msgs['not_null_char'])

        if len(passwd) < 8:
            raise PasswordGoodEnoughException(msgs['atleast8'])


        if re.search(r'[\200-\376]', passwd):
            raise PasswordGoodEnoughException(msgs['8bit'])

        if re.search(r' ', passwd):
            raise PasswordGoodEnoughException(msgs['space'])

        # I'm not sure that the below is very smart.  If this rule
        # causes most users to include a digit in their password, one
        # has managed to reduce the password space by 26*2/10 provided
        # that a hacker performs a bruteforce attack

        good_try = variation = 0
        if re.search(r'[a-z]', passwd): variation += 1
        if re.search(r'[A-Z][^A-Z]{7}', passwd): good_try += 1
        if re.search(r'[A-Z]', passwd[1:8]): variation += 1
        if re.search(r'[^0-9]{7}[0-9]', passwd): good_try += 1

        if re.search(r'[0-9]', passwd[0:7]): variation += 1
        if re.search(r'[A-Za-z0-9]{7}[^A-Za-z0-9]', passwd): good_try += 1
        if re.search(r'[^A-Za-z0-9]', passwd[0:7]): variation += 1

        if variation < 3:
            if good_try:
                raise PasswordGoodEnoughException(msgs['mix_needed8'])
            else:
                raise PasswordGoodEnoughException(msgs['mix_needed'])

        # Too much like the old password?

        self.check_password_history(uname, passwd)   # Will raise on error

        # Is it in one of the dictionaries?

        if re.search(r'^[a-zA-Z]', passwd):
            chk = passwd.lower()
            # Truncate common suffixes before searching dict.

            even = ''
            chk = re.sub(r'\d+$', '', chk)
            chk = re.sub(r'\(', '', chk)

            chk = re.sub('s$', '', chk)
            chk = re.sub('ed$', '', chk)
            chk = re.sub('er$', '', chk)
            chk = re.sub('ly$', '', chk)
            chk = re.sub('ing$', '', chk)

            # We'll iterate over several dictionaries.

            for d in self.words:
                f = file("%s/%s" % (self.dir, d))
                self.look(f, chk, 1, 1)

                # Do the lookup (dictionary order, case folded)
                while (1):
                    line = f.readline()
                    print "r: %s" % line
                    if line is None: break
                    line = line.lower()
                    if line[0:len(chk)] != chk: break
                    raise PasswordGoodEnoughException(msgs['dict_hit'])
        return 1

