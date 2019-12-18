# -*- coding: utf-8 -*-
# Copyright 2006 University of Oslo, Norway
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
import re

from Cerebrum import Account


class AccountNMHMixin(Account.Account):
    """Account mixin class providing functionality specific to NMH.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies as stated by the Indigo-project.

    """
    def populate(self, name, owner_type, owner_id, np_type, creator_id,
                 expire_date, description=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        # Override Account.populate in order to register 'primary e-mail
        # address
        self.__super.populate(name, owner_type, owner_id, np_type, creator_id,
                              expire_date, description=description)
        # register "primary" e-mail address as entity_contact
        c_val = name + '@nmh.no'
        c_desc = "E-mail address exported to LDAP"
        self.populate_contact_info(self.const.system_cached,
                                   type=self.const.contact_email,
                                   value=c_val, description=c_desc)

    def suggest_unames(self, person, maxlen=10, suffix=""):
        # Override Account.suggest_unames as NMH allows up to 10 chars
        # in unames
        return super(AccountNMHMixin, self).suggest_unames(person,
                                                           maxlen=maxlen,
                                                           suffix=suffix)

    def illegal_name(self, name):
        """NMH can only allow max 10 characters in usernames, due to
        restrictions in e.g. TimeEdit.

        """
        if len(name) > 10:
            return "too long (%s); max 10 chars allowed" % name
        if re.search("[^a-z]", name):
            return "contains illegal characters (%s); only a-z allowed" % name
        return super(AccountNMHMixin, self).illegal_name(name)


class AccountNmhEmailMixin(Account.Account):
    def get_primary_mailaddress(self):
        primary = self.get_contact_info(type=self.const.contact_email)
        if primary:
            return primary[0]['contact_value']
        else:
            return "<ukjent>"
