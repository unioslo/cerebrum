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

"""The PasswordHistory module is used to keep track of previous
passwords for an Entity.  This allows one to prevent Entities from
setting their password to an old password.
"""

import cereconf
import md5
import base64
from Cerebrum.DatabaseAccessor import DatabaseAccessor

class PasswordHistory(DatabaseAccessor):
    """PasswordHistory does not enfoce that Entity is an Account as
    other things also may have passwords"""

    def encode_for_history(self, account, password):
        m = md5.md5("%s%s" % (account.account_name, password))
        return base64.encodestring(m.digest())[:22]

    def add_history(self, account, password, _csum=None, _when=None):
        """Add an entry to the password history."""
        if _csum is not None:
            csum = _csum
        else:
            csum = self.encode_for_history(account, password)
        if _when is not None:
            col_when = ", set_at"
            val_when = ", :when"
        else:
            col_when = val_when = ""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=password_history]
          (entity_id, md5base64 %s) VALUES (:e_id, :md5 %s)""" % (
            col_when, val_when),
                     {'e_id': account.entity_id, 'md5': csum, 'when': _when})

    def del_history(self, entity_id):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=password_history]
        WHERE entity_id=:e_id""", {'e_id': entity_id})

    def get_history(self, entity_id):
        return self.query("""
        SELECT md5base64, set_at
        FROM [:table schema=cerebrum name=password_history] WHERE entity_id=:e_id""",
                          {'e_id': entity_id})   

