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

"""HiA needs a file with Cyrus IMAP-users. This"""

import string

# from Cerebrum.Utils import Factory
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.EmailLDAP import EmailLDAP

class EmailLDAPHiAMixin(EmailLDAP):
    """Methods specific for HiA."""

    def __init__(self, db):
        self.__super.__init__(db)
        self.account_file_name = "/cerebrum/dumps/LDAP/cyrus-users.txt"
        self.account_file = None

        
    def read_misc_target(self):
        self.account_file = Utils.SimilarSizeWriter(self.account_file_name, "w")


    def get_misc(self, entity_id, target_id, email_target_type):
        if email_target_type == self.const.email_target_account:
            if self.acc2name.has_key(entity_id):
                self.account_file.write("%s\n" % self.acc2name[entity_id][0])
            else:
                print "ERROR!!! EntityID found, but no username found: %s" % entity_id
        return None


    def close_misc_target(self):
        self.account_file.close()
