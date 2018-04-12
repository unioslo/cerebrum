# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import base64
import os
import re

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Account
from Cerebrum import Errors
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

    @property
    def has_autofreeze_quarantine(self):
        """
        has_autofreeze_quarantine-property - getter

        :rtype: bool
        :return: Return True if the account has autofreeze quarantine(s),
            otherwise - False
        """
        return bool(
            self.get_entity_quarantine(
                qtype=self.const.quarantine_auto_frozen))

    @property
    def autofreeze_quarantine_start(self):
        """
        autofreeze_quarantine_start-property - getter

        :rtype: mx.DateTime or None
        :return: Return the start_date of the autofreeze quarantine
            (Note: None will be returned in a case of no autofreeze-quarantines
            for the Account. Hence mx.DateTime return value is a proof that
            the Account has at least one autofreeze-quarantine, while return
            value None is not a proof of the opposite
        """
        auto_frozen_quarantines = self.get_entity_quarantine(
            qtype=self.const.quarantine_auto_frozen)
        if auto_frozen_quarantines:
            return auto_frozen_quarantines[0]['start_date']
        return None

    def remove_autofreeze_quarantine(self):
        """A wrapper method that removes autofreeze quarantine
        from the account. It is equivalent to:
        self.delete_entity_quarantine(const.quarantine_auto_frozen)
        """
        self.delete_entity_quarantine(self.const.quarantine_auto_frozen)

    def add_autofreeze_quarantine(self, *args, **kwargs):
        """A wrapper method that adds autofreeze quarantine
        to the account. It is equivalent to:
        self.add_entity_quarantine(const.quarantine_auto_frozen, *args, **kw)
        """
        self.add_entity_quarantine(self.const.quarantine_auto_frozen,
                                   *args,
                                   **kwargs)

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Subclass setting of the account_type.

        Since OUs are treated as separate projects in TSD, we need to add some
        protection to them. An account should only be allowed to be part of a
        single OU, no others, to avoid mixing different projects' data.
        """
        if affiliation == self.const.affiliation_project:
            for row in self.list_accounts_by_type(
                    account_id=self.entity_id,
                    affiliation=self.const.affiliation_project,
                    # We want the deleted ones too, as the account
                    # could have previously been part of a project:
                    filter_expired=False
            ):
                if row['ou_id'] != ou_id:
                    raise Errors.CerebrumError('Account already part of other '
                                               'project OUs')
        return self.__super.set_account_type(ou_id, affiliation, priority)

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

    def _generate_otpkey(self, length=192):
        """Return a randomly generated OTP key of the given length.

        @type length: int
        @param length:
            The number of bits that should be generated. Note that the number
            is rounded upwards to be contained in a full byte (8 bits).

        @rtype: str (bytes)
        @return:
            The OTP key, formed as a string of the hexadecimal values. Each
            hexadecimal value represent 8 bits.
        """
        # Round upwards to nearest full byte by adding 7 to the number of bits.
        # This makes sure that it's always rounded upwards if not modulo 0 to 8
        int_bytes = (length + 7) / 8
        ret = six.binary_type()
        while len(ret) < int_bytes:
            ret += os.urandom(int_bytes - len(ret))
        return ret

    def regenerate_otpkey(self, tokentype=None):
        """Create a new OTP key for the account.

        Note that we do not store the OTP key in Cerebrum. We only pass it on
        to the Gateway, so it's only stored one place. Other requirements could
        change this in the future.

        The OTP type, e.g. hotp or totp, is retrieved from the person's trait.

        @type tokentype: str
        @param tokentype:
            What token type the OTP should become, e.g. 'totp' or 'hotp'. Note
            that it could also be translated by L{cereconf.OTP_MAPPING_TYPES}
            if it matches a value there.

            If this parameter is None, the person's default OTP type will be
            used, or 'totp' by default if no value is set for the person.

        @rtype: string (unicode)
        @return:
            The full URI of otpauth, as defined in cereconf.OTP_URI_FORMAT,
            filled with the proper data. The format should follow
            https://code.google.com/p/google-authenticator/wiki/KeyUriFormat

        """
        # Generate a new key:
        secret = base64.b32encode(
            self._generate_otpkey(
                getattr(cereconf, 'OTP_KEY_LENGTH', 160))).decode()
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
        if self.get_entity_quarantine(qtype=self.const.quarantine_not_approved,
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

    def validate_new_uname(self, domain, uname, owner_id=None):
        """
        Check that the requested username is legal and *globally* free

        Return True if `uname` is available, False otherwise
        """
        if not super(AccountTSDMixin, self).validate_new_uname(domain, uname):
            return False
        try:
            uname_tokens = re.split(r'^p\d+-', uname)
            if len(uname_tokens) != 2:
                # Not a real TSD-username
                return False
            existing_accounts = self.search(
                name='p*-{uname}'.format(uname=uname_tokens[1]))
            if not existing_accounts:
                return True
            owner_id = owner_id or self.owner_id
            if owner_id is None:
                # No owner_id provided. Assume the worst
                return False
            for account in existing_accounts:
                if account['owner_id'] != owner_id:
                    # Same name, two different persons
                    return False
            return True
        except:
            return False
