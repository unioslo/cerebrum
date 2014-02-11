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

from Cerebrum.Utils import Factory
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules import EntityTrait
from Cerebrum.modules.no.uio.DiskQuota import DiskQuota
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules import dns
from Cerebrum.Utils import pgp_encrypt, Factory

class AccountTSDMixin(Account.Account):
    """Account mixin class for TSD specific behaviour.

    Accounts should only be part of a single project (OU), and should for
    instance have defined a One Time Password (OTP) key for two-factor
    authentication.

    """

    # TODO: create and deactive - do they need to be subclassed?

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Subclass setting of the account_type.

        Since OUs are treated as separate projects in TSD, we need to add some
        protection to them. An account should only be allowed to be part of a
        single OU, no others, to avoid mixing different projects' data.

        Also, when a user is added to a project, we should also give the account
        extra functionality related to the project.

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

        # If the given project is set up so that every project member should
        # have their own virtual linux machine, we need to create this host for
        # the account:
        if affiliation == self.const.affiliation_project:
            et = EntityTrait.EntityTrait(self._db)
            et.find(ou_id)
            vmtrait = et.get_trait(self.const.trait_project_vm_type)
            if vmtrait and vmtrait['strval'] in ('linux_vm',
                                                 'win_and_linux_vm'):
                ou = Factory.get('OU')(self._db)
                ou.find(ou_id)
                hostname = '%s-l.tsd.usit.no.' % self.account_name
                dnsowner = ou._populate_dnsowner(hostname)
                host = dns.HostInfo.HostInfo(self._db)
                host.populate(dnsowner.entity_id, 'IBM-PC\tWINDOWS')
                host.write_db()
        return self.__super.set_account_type(ou_id, affiliation, priority)

    def _generate_otpkey(self, length=192):
        """Return a randomly generated OTP key.

        @type length: int
        @param length: The number of bits that should be generated.

        @rtype: str
        @return: The OTP key, formed as a string of the hexadecimal values.

        """
        l = int(length / 8) # to support if a float sneaks in
        f = open('/dev/random', 'rb')
        return ''.join('%x' % ord(o) for o in f.read(l))

    def regenerate_otpkey(self):
        """Create a new OTP key and store it for the account.

        TODO: Note that we do not store the OTP key in Cerebrum, for now. We
        should only pass it on to the Gateway, so it's only stored in one place.
        Other requirements could change this in the future.

        @rtype: string
        @return:
            The full URI of otpauth, as defined in cereconf.OTP_URI_FORMAT,
            filled with the proper data. The format should follow
            https://code.google.com/p/google-authenticator/wiki/KeyUriFormat

        """
        key = self._generate_otpkey(getattr(cereconf, 'OTP_KEY_LENGTH', 160))
        secret = base64.b32encode(key)
        # Get the token type from trait, e.g. totp or hotp.
        tokentype = 'totp'
        typetrait = self.get_trait(self.const.trait_otp_device)
        if typetrait:
            tokentype = typetrait['strval']
        return cereconf.OTP_URI_FORMAT % {
                'secret': secret,
                'user': '%s@%s' % (self.account_name,
                                   cereconf.INSTITUTION_DOMAIN_NAME),
                'type': tokentype,
                }
