#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""Account mixin for the TSD project.

Accounts in TSD needs to be controlled. The most important issue is that one
account is only allowed to be a part of one single project, which is why we
should refuse account_types from different OUs for a single account.

"""

import base64
#from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules.no.uio.DiskQuota import DiskQuota
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Utils import pgp_encrypt, Factory

class AccountTSDMixin(Account.Account):
    """Account mixin class for TSD specific behaviour.

    Accounts should only be part of a single project (OU), and should for
    instance have defined a One Time Password (OTP) key for two-factor
    authentication.

    """

    # TODO: create and deactive - do they need to be subclassed?

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Subclass setting of the account_type to avoid more than one OU.

        This is to avoid letting an account get access to different projects.

        """
        if affiliation == self.const.affiliation_project:
            for row in self.list_accounts_by_type(account_id=self.entity_id,
                                affiliation=self.const.affiliation_project,
                                # We want the deleted ones too, as the account
                                # could have previously been part of a project:
                                filter_expired=False):
                if row['ou_id'] != ou_id:
                    raise Errors.CerebrumError('Account already part of other '
                                               'project OUs')
        return self.__super.set_account_type(ou_id, affiliation, priority)

    def _generate_otpkey(self, length=192):
        """Return a randomly generated OTP key.

        @type length: int
        @param length: The number of bits that should be generated.

        @rtype: str
        @return: The OTP key, formed as a string of the hexadecimal values.

        """
        l = int(length / 8) # to support if a float sneaks in
        f = open('/dev/urandom', 'rb')
        return ''.join('%x' % ord(o) for o in f.read(l))

    def regenerate_otpkey(self):
        """Create a new OTP key and store it for the account.
        
        @rtype: string
        @return: TODO: Only the key, or in a formatted URI, as defined in
            https://code.google.com/p/google-authenticator/wiki/KeyUriFormat?

        """
        key = self._generate_otpkey(getattr(cereconf, 'OTP_KEY_LENGTH', 160))
        secret = base64.b32encode(key)
        # TODO: token type, totp or hotp, found in a user's trait

        uri = cereconf.OTP_URI_FORMAT % {'secret': secret,
                'user': '%s@%s' % (self.account_name,
                    cereconf.INSTITUTION_DOMAIN_NAME),
                'type': 'totp'}
        return uri
