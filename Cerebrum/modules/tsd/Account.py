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

from Cerebrum.modules.tsd import TSDUtils

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
        if not self.is_approved():
            return

        # If the given project is set up so that every project member should
        # have their own virtual linux machine, we need to create this host for
        # the account:
        vmtrait = ou.get_trait(self.const.trait_project_vm_type)
        if vmtrait and vmtrait['strval'] in ('linux_vm', 'win_and_linux_vm'):
            hostname = '%s-l.tsd.usit.no.' % self.account_name
            dnsowner = ou._populate_dnsowner(hostname)
            host = dns.HostInfo.HostInfo(self._db)
            hinfo = 'IBM-PC\tLINUX'
            try:
                host.find_by_dns_owner_id(dnsowner.entity_id)
            except Errors.NotFoundError:
                host.populate(dnsowner.entity_id, hinfo)
            host.hinfo = hinfo
            host.write_db()
            for comp in getattr(cereconf, 'TSD_HOSTPOLICIES_LINUX', ()):
                TSDUtils.add_host_to_policy_component(self._db, host.entity_id,
                                                      comp)

    def get_tsd_project_id(self):
        """Helper method for getting the ou_id for the account's project.

        @rtype: int
        @return:
            The entity_id for the TSD project the account is affiliated with.

        @raise NotFoundError:
            If the account is not affiliated with any project.

        @raise Exception:
            If the account has more than one project affiliation, which is not
            allowed in TSD, or if the account is not affiliated with any
            project.

        """
        rows = self.list_accounts_by_type(
                    account_id=self.entity_id,
                    affiliation=self.const.affiliation_project)
        assert len(rows) < 2, "Account affiliated with more than one project"
        for row in rows:
            return row['ou_id']
        raise Errors.NotFoundError('Account not affiliated with any project')

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
        # Round upwards to nearest full byte by adding 7 to the number of bits.
        # This makes sure that it's always rounded upwards if not modulo 0 to 8.
        bytes = (length + 7) / 8
        ret = ''
        f = open('/dev/urandom', 'rb')
        # f.read _could_ return less than what is needed, so need to make sure
        # that we have enough data, in case the read should stop:
        while len(ret) < bytes:
            ret += f.read(bytes - len(ret))
        f.close()
        return ret

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
        secret = base64.b32encode(self._generate_otpkey(
                                    getattr(cereconf, 'OTP_KEY_LENGTH', 160)))
        # Get the tokentype
        if not tokentype:
            tokentype = 'totp'
            if self.owner_type == self.const.entity_person:
                pe = Factory.get('Person')(self._db)
                pe.find(self.owner_id)
                typetrait = pe.get_trait(self.const.trait_otp_device)
                if typetrait:
                    tokentype = typetrait['strval']

        # A mapping from e.g. Nettskjema's smartphone_yes -> topt:
        mapping = getattr(cereconf, 'OTP_MAPPING_TYPES', {})
        try:
            tokentype = mapping[tokentype]
        except KeyError:
            raise Errors.CerebrumError('Invalid tokentype: %s' % tokentype)
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

    def is_approved(self):
        """Return if the user is approved for a TSD project or not.

        The approval is in two levels: First, the TSD project (OU) must be
        approved, then the account must not be quarantined.

        :rtype: bool
        :return: True i

        """
        # Check user quarantine:
        if self.get_entity_quarantine(type=self.const.quarantine_not_approved,
                                      only_active=True):
            return False
        # Check if OU is approved:
        try:
            projectid = self.get_tsd_project_id()
        except Errors.NotFoundError:
            # Not affiliated with any project, therefore not approved
            return False
        ou = Factory.get('OU')(self._db)
        ou.clear()
        ou.find(projectid)
        return ou.is_approved()
