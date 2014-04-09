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
import math
#from mx import DateTime
import re

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
        self.setup_for_project()
        return self.__super.set_account_type(ou_id, affiliation, priority)

    def setup_for_project(self):
        """Set up different config and attributes for a project account. 

        When a user is added to a project, we should also give the account extra
        functionality related to the project, like a linux machine if the
        project is set to use that.

        """
        ou = Factory.get('OU')(self._db)

        # The account and OU must be approved before we should set anything
        is_approved = False
        for row in self.get_account_types():
            if row['affiliation'] != self.const.affiliation_project:
                continue
            ou.clear()
            ou.find(row['ou_id'])
            if not tuple(ou.get_entity_quarantine()):
                is_approved = True
        if not is_approved:
            return

        # If the given project is set up so that every project member should
        # have their own virtual linux machine, we need to create this host for
        # the account:
        vmtrait = ou.get_trait(self.const.trait_project_vm_type)
        if vmtrait and vmtrait['strval'] in ('linux_vm', 'win_and_linux_vm'):
            hostname = '%s-l.tsd.usit.no.' % self.account_name
            dnsowner = ou._populate_dnsowner(hostname)
            host = dns.HostInfo.HostInfo(self._db)
            host.populate(dnsowner.entity_id, 'IBM-PC\tWINDOWS')
            host.write_db()

    def get_username_without_project(self, username=None):
        """Helper method for fetching the username without the project prefix.

        This was originally not needed, but due to changes in the requirements
        we unfortunately need to a downstripped username from time to time.

        If the format of the project prefix changes in the future, we need to
        expand this method later.

        @type username: str
        @param username:
            A username with a project prefix. If not given, we expect that
            L{self.account_name} is available.

        @rtype: str
        @return:
            The username without the project prefix.

        @raise Exception:
            If the username does not have the format of project accounts.

        """
        if username is None:
            username = self.account_name
        # Users that not fullfill the project format
        if '-' not in username:
            raise Exception("User is not a project account: %s" % username)
        return username[4:]

    def delete_entity_quarantine(self, *args, **kwargs):
        """Override to also setup the project account."""
        self.__super.delete_entity_quarantine(*args, **kwargs)
        self.setup_for_project()

    def _generate_otpkey(self, length=192):
        """Return a randomly generated OTP key of the given length.

        @type length: int
        @param length:
            The number of bits that should be generated. Note that the number is
            rounded upwards to be contained in a full byte (8 bits).

        @rtype: str
        @return:
            The OTP key, formed as a string of the hexadecimal values. Each
            hexadecimal value represent 8 bits.

        """
        bytes = int(math.ceil(float(length) / 8))
        ret = ''
        f = open('/dev/random', 'rb')
        # f.read might return less than what is needed, so might need to fetch
        # more random bits before we're done:
        while len(ret) < bytes:
            ret += ''.join('%x' % ord(o) for o in f.read(bytes/2 + 1))
        f.close()
        return ret[:bytes]

    def regenerate_otpkey(self, tokentype=None):
        """Create a new OTP key for the account.

        Note that we do not store the OTP key in Cerebrum. We only pass it on to
        the Gateway, so it's only stored one place. Other requirements could
        change this in the future.

        The OTP type, e.g. hotp or totp, is retrieved from the person's trait.

        @type tokentype: str
        @param tokentype:
            What token type the OTP should become, e.g. 'totp' or 'hotp'. Note
            that it could also be translated by L{cereconf.OTP_MAPPING_TYPES} if
            it matches a value there.

            If this parameter is None, the person's default OTP type will be
            used, or 'totp' by default if no value is set for the person.

        @rtype: string
        @return:
            The full URI of otpauth, as defined in cereconf.OTP_URI_FORMAT,
            filled with the proper data. The format should follow
            https://code.google.com/p/google-authenticator/wiki/KeyUriFormat

        """
        # Generate a new key:
        key = self._generate_otpkey(getattr(cereconf, 'OTP_KEY_LENGTH', 160))
        secret = base64.b32encode(key)
        # Get the tokentype
        if tokentype is None:
            tokentype = 'totp'
            if self.owner_type == self.const.entity_person:
                pe = Factory.get('Person')(self._db)
                pe.find(self.owner_id)
                typetrait = pe.get_trait(self.const.trait_otp_device)
                if typetrait:
                    tokentype = typetrait['strval']
        # A mapping from e.g. Nettskjema's smartphone_yes -> topt:
        mapping = getattr(cereconf, 'OTP_MAPPING_TYPES', {})
        tokentype = mapping.get(tokentype, tokentype)
        return cereconf.OTP_URI_FORMAT % {
                'secret': secret,
                'user': '%s@%s' % (self.account_name,
                                   cereconf.INSTITUTION_DOMAIN_NAME),
                'type': tokentype,
                }

    def illegal_name(self, name):
        """TSD's checks on what is a legal username.

        This checks both project accounts and system accounts, so the project
        prefix is not checked.

        """
        tmp = super(AccountTSDMixin, self).illegal_name(name)
        if tmp:
            return tmp
        if len(name) > getattr(cereconf, 'USERNAME_MAX_LENGTH', 12):
            return "too long (%s)" % name
        if re.search("^[^A-Za-z]", name):
            return "must start with a character (%s)" % name
        if re.search("[^A-Za-z0-9\-_]", name):
            return "contains illegal characters (%s)" % name
        return False
