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

""""""

import string

from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.EmailLDAP import EmailLDAP

class EmailLDAPDebianEduMixin(EmailLDAP):
    """Methods specific for Debian-Edu."""

    def __init__(self, db):
        self.__super.__init__(db)
        self.a_id2name = {}
        self.e_id2passwd = {}
  
    def get_target(self, entity_id, target_id):
        tmp_addr = self.aid2addr[self.targ2prim[target_id]]
        lp, dom = string.split(tmp_addr, '@')
        target = self.acc2name[entity_id][0]
        return "%s@%s" % (target, dom)


    def read_misc_target(self):
        p = Factory.get('Person')(self._db)
        p_id2name = {}
        for row in p.list_persons_name():
            p_id2name[int(row['person_id'])] = row['name']
        a = Factory.get('Account')(self._db)
        for row in a.list():
            a_id = row['account_id']
            o_id = row['owner_id']
            if p_id2name.has_key(o_id):
                self.a_id2name[a_id] = p_id2name[o_id]
        a = Factory.get('Account')(self._db)
        for row in a.list_account_authentication():
            self.e_id2passwd[row['account_id']] = (row['entity_name'],
                                                   row['auth_data'])
        for row in a.list_account_authentication(self.const.auth_type_crypt3_des):
            # *sigh* Special-cases do exist. If a user is created when the
            # above for-loop runs, this loop gets a row more. Before I ignored
            # this, and the whole thing went BOOM on me.
            if not self.e_id2passwd.has_key(row['account_id']):
                self.e_id2passwd[row['account_id']] = (row['entity_name'],
                                                       row['auth_data'])
            elif self.e_id2passwd[row['account_id']][1] == None:
                self.e_id2passwd[row['account_id']] = (row['entity_name'],
                                                       row['auth_data'])


    def get_misc(self, entity_id, target_id, email_target_type):
        txt = ""
        if self.a_id2name.has_key(entity_id):
            txt = "name: %s" % self.a_id2name[entity_id]
        if self.a_id2name.has_key(entity_id) and \
           email_target_type == self.const.email_target_account and \
           self.e_id2passwd.has_key(entity_id):
            txt += "\n"
        if email_target_type == self.const.email_target_account:
            if self.e_id2passwd.has_key(entity_id):
                uname, passwd = self.e_id2passwd[entity_id]
                if not passwd:
                    passwd = "*invalid"
                txt += "userPassword: {crypt}%s" % passwd
                return txt
            else:
                txt = "No auth-data for user: %s\n" % entity_id
                sys.stderr.write(txt)
        return txt
