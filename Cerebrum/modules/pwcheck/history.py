#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2003-2015 University of Oslo, Norway
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
""" This module contains a password history check.

The PasswordHistory class is used to keep track of previous passwords for an
Entity. This allows one to prevent Entities from setting their password to an
old password.

NOTE
----
This module requires the design/mod_password_history.sql database module

HISTORY
-------
This module was moved from Cerebrum.modules.PasswordHistory. For the old
structure of PasswordHistory, please see:

> commit 9a01d8b6ac93513a57ac8d6393de842939582f51
> Mon Jul 20 14:12:55 2015 +0200

"""

import cereconf
import hashlib
import base64
from Cerebrum.DatabaseAccessor import DatabaseAccessor

from .common import PasswordNotGoodEnough

__version__ = "1.0"


class ClearPasswordHistoryMixin(DatabaseAccessor):

    """ A mixin that will delete password history. """

    def delete(self):
        if getattr(self, '__in_db', False):
            PasswordHistory(self._db).del_history(self.entity_id)
        super(ClearPasswordHistoryMixin, self).delete()


class PasswordHistoryMixin(ClearPasswordHistoryMixin):

    """ A mixin for use with accounts, etc. """
    # TODO: Should this inherit from Cerebrum.Account or Cerebrum.Entity?

    def password_good_enough(self, password):
        """ Match the password against PasswordHistory. """
        super(PasswordHistoryMixin, self).password_good_enough(password)
        self._check_password_history(password)
        self._check_password_history(password[0:8])

    def write_db(self):
        ret = super(PasswordHistoryMixin, self).write_db()
        plain = getattr(self, '__plaintext_password', None)
        if plain is not None:
            ph = PasswordHistory(self._db)
            ph.add_history(self, plain)
        return ret

    # If, for some reason Cerebrum.Account.set_password stops storing the
    # plaintext, we would need to do that here.
    #   def set_password(self, plaintext):
    #       self.__plaintext_password = plaintext
    #       super(PasswordHistoryMixin, self).set_password(plaintext)

    def _check_password_history(self, password):
        """ Check if entity had this passwordearlier.

        :param str password: The plaintext password.

        :return: Returns on success

        :raise PasswordNotGoodEnough:
            Raises an exception if the password, or a similar password has been
            used before.

        """
        ph = PasswordHistory(self._db)
        uname = getattr(self, 'account_name', None)
        eid = getattr(self, 'entity_id', None)

        if not uname or eid:
            return

        def what_range(ch):
            """Return a range of characters from character `ch'.

            This allows us to detect that the user changes password from
            '1secret' to '2secret'. """
            if not ch.isalpha():
                return range(ord(ch)-5, ord(ch)+6)
            if ch.isupper():
                return range(max(ord('A'), ord(ch)-5),
                             min(ord('Z')+1, ord(ch)+6))
            return range(max(ord('a'), ord(ch)-5),
                         min(ord('z')+1, ord(ch)+6))

        variants = []
        for m in (-1, 0):
            for r in what_range(password[m]):
                if m < 0:
                    tmp = password[:m]+chr(r)
                else:
                    tmp = chr(r)+password[m+1:]
                tmp = ph.encode_for_history(uname, tmp)
                variants.append(tmp)
        for r in ph.get_history(eid):
            if r['md5base64'] in variants:
                raise PasswordNotGoodEnough(
                    "Password too similar to an old password.")


class PasswordHistory(DatabaseAccessor):

    """PasswordHistory contains an API for accessing password history. """

    def encode_for_history(self, name, password):
        m = hashlib.md5("%s%s" % (name, password))
        return base64.encodestring(m.digest())[:22]

    def add_history(self, account, password, _csum=None, _when=None):
        """Add an entry to the password history."""
        if _csum is not None:
            csum = _csum
        else:
            csum = self.encode_for_history(account.account_name, password)
        if _when is not None:
            col_when = ", set_at"
            val_when = ", :when"
        else:
            col_when = val_when = ""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=password_history]
          (entity_id, md5base64 %s) VALUES (:e_id, :md5 %s)""" % (
            col_when, val_when), {'e_id': account.entity_id,
                                  'md5': csum,
                                  'when': _when})

    def del_history(self, entity_id):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=password_history]
        WHERE entity_id=:e_id""", {'e_id': entity_id})

    def get_history(self, entity_id):
        return self.query("""
        SELECT md5base64, set_at
        FROM [:table schema=cerebrum name=password_history]
        WHERE entity_id=:e_id""", {'e_id': entity_id})

    def find_old_password_accounts(self, date):
        """Returns account_id for all accounts that has not changed
        password since before date"""

        # TODO: hva med systemkonti o.l. uten passord?  har alle karantene?

        # Fetch all account_id that:
        # - has spread
        # - has expire_date in the future/not set
        # - newest entry in password_history is older than <date>
        return self.query(
            """SELECT account_id
            FROM [:table schema=cerebrum name=account_info] ai,
                 [:table schema=cerebrum name=password_history] ph
            WHERE (ai.expire_date IS NULL OR
                   ai.expire_date > [:now]) AND
                   ai.account_id=ph.entity_id
                   AND EXISTS (
                     SELECT 'foo'
                     FROM [:table schema=cerebrum name=entity_spread] es
                     WHERE ai.account_id=es.entity_id)
            GROUP BY ai.account_id
            HAVING MAX(set_at) < :date""", {'date': date})

    def find_no_history_accounts(self):
        """Returns account_id for all accounts that are not in
        password_history at all"""
        return self.query(
            """SELECT account_id
            FROM [:table schema=cerebrum name=account_info] ai
            WHERE (ai.expire_date IS NULL OR
                   ai.expire_date > [:now])
                   AND EXISTS (
                     SELECT 'foo'
                     FROM entity_spread es
                     WHERE ai.account_id=es.entity_id)
                   AND NOT EXISTS (
                     SELECT 'foo'
                     FROM entity_quarantine eq
                     WHERE ai.account_id=eq.entity_id)
                   AND NOT EXISTS (
                     SELECT 'foo'
                     FROM password_history ph
                     WHERE ai.account_id=ph.entity_id)""")
