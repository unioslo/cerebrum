#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2016 University of Oslo, Norway
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

"""Module used for provisioning in Exchange 2013 via powershell.

This module can be used by exports or an event daemon for creating,
deleting and updating mailboxes and distribution groups in Exchange 2013."""

from __future__ import unicode_literals

from Cerebrum.modules.exchange.Exceptions import ExchangeException
from Cerebrum.modules.no.uio.exchange.ExchangeClient import ExchangeClient
from Cerebrum.modules.exchange.Exceptions import AlreadyPerformedException


class UiAExchangeClient(ExchangeClient):
    def __init__(self,
                 auth_user,
                 domain_admin,
                 ex_domain_admin,
                 management_server,
                 exchange_server,
                 session_key=None,
                 *args,
                 **kwargs):
        """Set up the WinRM client to be used with running Exchange commands.

        :type auth_user: string
        :param auth_user: The username of the account we use to connect to the
            server.

        :type domain_admin: string
        :param domain_admin: The username of the account we use to connect to
            the AD domain we are going to synchronize with.

        """
        self.exchange_server = exchange_server
        super(UiAExchangeClient, self).__init__(auth_user,
                                                domain_admin,
                                                ex_domain_admin,
                                                management_server,
                                                None,
                                                session_key=session_key,
                                                *args,
                                                **kwargs)
        self.logger.debug("UiAExchangeClient super returned")

    def _get_pre_execution_code(self):
        """Return Powershell commands that should be run before a command.

        This is a override, as UiA has a bit different setup than UiO. Mostly,
        it does the same as its superclass, except from 1) making use of a
        session configuration on the AD side, and 2) specifying an Exchange
        server to talk with instead of using a custom Powershell module,
        written for Cerebrum to talk with Exchange.

        """
        return """
            $pass = ConvertTo-SecureString -Force -AsPlainText %(ex_pasw)s;
            $cred = New-Object System.Management.Automation.PSCredential( `
            %(ex_domain_user)s, $pass);

            $sessions = Get-PSSession -ComputerName %(management_server)s `
            -Credential $cred -Name %(session_key)s 2> $null;

            if ( $sessions ) {
                $ses = $sessions[0];
                Connect-PSSession -Session $ses 2> $null > $null;
            }

            if (($? -and ! $ses) -or ! $?) {
                $ses = New-PSSession -ComputerName %(management_server)s `
                -Credential $cred -Name %(session_key)s
                -ConfigurationName Cerebrum;

                Import-Module ActiveDirectory 2> $null > $null;

                Invoke-Command { . RemoteExchange.ps1 } -Session $ses;

                Invoke-Command { $pass = ConvertTo-SecureString -Force `
                -AsPlainText %(ex_pasw)s } -Session $ses;

                Invoke-Command { $cred = New-Object `
                System.Management.Automation.PSCredential(%(ex_user)s, $pass)`
                } -Session $ses;

                Invoke-Command { $ad_pass = ConvertTo-SecureString -Force `
                -AsPlainText %(ad_pasw)s } -Session $ses;

                Invoke-Command { $ad_cred = New-Object `
                System.Management.Automation.PSCredential(`
                %(ad_domain_user)s, $ad_pass) } -Session $ses;

                Invoke-Command { Import-Module ActiveDirectory } -Session $ses;

                Invoke-Command { function get-credential () { return $cred;} }`
                -Session $ses;

                Invoke-Command { Connect-ExchangeServer `
                -ServerFqdn %(exchange_server)s -UserName %(ex_user)s } `
                -Session $ses;
            }
            write-output EOB;""" % {
            'session_key': self.session_key,
            'ad_domain_user': self.escape_to_string(
                '%s\\%s' % (self.ad_domain, self.ad_user)),
            'ad_user': self.escape_to_string(self.ad_user),
            'ad_pasw': self.escape_to_string(self.ad_user_password),
            'ex_domain_user': self.escape_to_string(
                '%s\\%s' % (self.ex_domain, self.ex_user)),
            'ex_user': self.escape_to_string(self.ex_user),
            'ex_pasw': self.escape_to_string(self.ex_user_password),
            'management_server': self.escape_to_string(
                self.management_server),
            'exchange_server': self.escape_to_string(
                self.exchange_server)}

    ######
    # Mailbox-specific operations
    ######

    def new_mailbox(self, uname):
        """Create a new mailbox in Exchange.

        @type uname: string
        @param uname: The users username

        @rtype: bool
        @return: Return True if success

        @raise ExchangeException: If the command failed to run for some reason
        """

        cmd = self._generate_exchange_command('Enable-Mailbox',
                                              {'Identity': uname})

        # We set the mailbox as hidden, in the same call. We won't
        # risk exposing in the really far-fetched case that the integration
        # crashes in between new-mailbox and set-mailbox.

        cmd += '; ' + self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'HiddenFromAddressListsEnabled': True})

        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_address_policy(self, uname, enabled=False):
        """Set the EmailAddressPolicEnabled for a mailbox.

        @type uname: string
        @param uname: The username to look up associated malbox by

        @type enabled: bool
        @param enabled: Enable or disable the AddressPolicy

        @raise ExchangeException: If the command failed to run for some reason
        """
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'EmailAddressPolicyEnabled': enabled})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_names(self, uname, first_name, last_name, full_name):
        """Set a users name

        @type uname: string
        @param uname: The uname to select account by

        @type first_name: string
        @param first_name: The persons first name

        @type last_name: string
        @param last_name: The persons last name

        @type full_name: string
        @param full_name: The persons full name, to use as display name

        @raises ExchangeException: Raised upon errors
        """
        cmd = self._generate_exchange_command(
            'Set-User',
            {'Identity': uname,
             'FirstName': first_name,
             'LastName': last_name,
             'DisplayName': full_name})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_mailbox(self, uname):
        """Remove a mailbox and it's linked account from Exchange.

        :type uname: string
        :param uname: The users username.

        :raises ExchangeException: If the command fails to run.
        """
        cmd = self._generate_exchange_command(
            'Remove-Mailbox',
            {'Identity': uname},
            ('Confirm:$false',))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    ######
    # General group operations
    ######

    def set_distgroup_description(self, gname, description):
        """Set a distributiongroups description.

        @type gname: string
        @param gname: The groups name

        @type description: string
        @param description: The groups description

        @raises ExchangeException: If the command fails to run
        """
        cmd = self._generate_exchange_command(
            'Set-Group',
            {'Identity': gname,
             'Notes': description.strip()})
        # TODO: On the line above, we strip of the leading and trailing
        # whitespaces. We need to do this, as leading and trailing whitespaces
        # triggers an error when we set the "description" when creating the
        # mailboxes. But, we don't need to do this if we change the description
        # after the mailbox has been created! Very strange behaviour. Think
        # about this and fix it (whatever that means).
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_distgroup_member(self, gname, member):
        """Add member to a distgroup.

        :type gname: string
        :param gname: The groups name.

        :type member: string
        :param member: The members name.

        :rtype: bool
        :return: Returns True if the operation resulted in an update, False if
            it does not.

        :raise ExchangeException: If it fails to run."""
        cmd = self._generate_exchange_command(
            'Add-DistributionGroupMember',
            {'Identity': gname,
             'Member': member},
            ('BypassSecurityGroupManagerCheck',))
        out = self.run(cmd)
        if 'stderr' in out:
            # If this matches, we have performed a duplicate operation. Notify
            # the caller of this trough raise.
            if 'MemberAlreadyExistsException' in out['stderr']:
                raise AlreadyPerformedException
            else:
                raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_distgroup_member(self, gname, member):
        """Remove a member from a distributiongroup.

        :type gname: string
        :param gname: The groups name.

        :type member: string
        :param member: The members username.

        :raises ExchangeException: If it fails."""
        # TODO: Add DomainController arg.
        cmd = self._generate_exchange_command(
            'Remove-DistributionGroupMember',
            {'Identity': gname,
             'Member': member},
            ('BypassSecurityGroupManagerCheck',
             'Confirm:$false'))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True
