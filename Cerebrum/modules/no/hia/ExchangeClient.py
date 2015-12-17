#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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

import re

from urllib2 import URLError

import cerebrum_path
getattr(cerebrum_path, "linter", "must be supressed!")

from Cerebrum.Utils import read_password
from Cerebrum.modules.ad2.winrm import WinRMServerException
from Cerebrum.modules.exchange.Exceptions import (ServerUnavailableException,
                                                  ExchangeException)
from Cerebrum.modules.exchange.v2013.ExchangeClient import (ClientMock,
                                                            ExchangeClient)


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
            the AD domain we are going to synchronize with."""
        super(UiAExchangeClient, self).__init__(*args, **kwargs)
        self.logger.debug("UiAExchangeClient super returned")
        self.add_credentials(
            username=auth_user,
            password=unicode(read_password(auth_user, self.host), 'utf-8'))

        self.ignore_stdout_pattern = re.compile('.*EOB\n', flags=re.DOTALL)
        self.wash_output_patterns = [
            re.compile('ConvertTo-SecureString.*\\w*...', flags=re.DOTALL)]
        self.management_server = management_server
        self.exchange_server = exchange_server
        self.session_key = session_key if session_key else 'cereauth'

        # TODO: Make the following line pretty
        self.auth_user_password = unicode(read_password(auth_user,
                                                        kwargs['host']),
                                          'utf-8')
        # Note that we save the user's password by domain and not the host. It
        # _could_ be the wrong way to do it. TBD: Maybe both host and domain?
        (self.ad_user,
         self.ad_domain) = self._split_domain_username(domain_admin)
        self.ad_user_password = unicode(read_password(self.ad_user,
                                                      self.ad_domain),
                                        'utf-8')
        (self.ex_user,
         self.ex_domain) = self._split_domain_username(ex_domain_admin)
        self.ex_user_password = unicode(read_password(self.ex_user,
                                                      self.ex_domain),
                                        'utf-8')
        # Set up the winrm / PowerShell connection
        self.connect()

        # Collect AD-controllers
        controllers = self._get_domain_controllers(self.ad_domain,
                                                   self.ex_domain)
        self.ad_server = controllers['domain']
        self.resource_ad_server = controllers['resource_domain']
        # TODO: For all commands. Use the two variables above, and specify
        # which DC we use

    # The pre-execution code is run when a command is run. This is what it does
    # in a nutshell:
    # 1. Define a credential for the communication between the springboard and
    #    the management server.
    # 2. Collect & connect to a previous PSSession, if this client has created
    #    one.
    # 3. If there is not an existing PSSession, create a new one
    # 3.1. Import the Active-Directory module
    # 3.2. Define credentials on the management server
    # 3.3. Initialize the Exchange module that gives us
    #      management-opportunities
    _pre_execution_code = u"""
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
            System.Management.Automation.PSCredential(%(ex_user)s, $pass) } `
            -Session $ses;

            Invoke-Command { $ad_pass = ConvertTo-SecureString -Force `
            -AsPlainText %(ad_pasw)s } -Session $ses;

            Invoke-Command { $ad_cred = New-Object `
            System.Management.Automation.PSCredential(`
            %(ad_domain_user)s, $ad_pass) } -Session $ses;

            Invoke-Command { Import-Module ActiveDirectory } -Session $ses;

            Invoke-Command { function get-credential () { return $cred;} } `
            -Session $ses;

            Invoke-Command { Connect-ExchangeServer `
            -ServerFqdn %(exchange_server)s -UserName %(ex_user)s } `
            -Session $ses;
        }
        write-output EOB;"""

    # After a command has run, we run the post execution code. We must
    # disconnect from the PSSession, in order to be able to resume it later
    _post_execution_code = u"""; Disconnect-PSSession $ses 2> $null > $null;"""

    # As with the post execution code, we want to clean up after us, when
    # the client terminates, hence the termination code
    _termination_code = (
        u"""; Remove-PSSession -Session $ses 2> $null > $null;""")

    def execute(self, *args, **kwargs):
        """Override the execute command with all the startup and teardown
        commands for Exchange.

        :type kill_session: bool
        :param kill_session: If True, run Remove-PSSession instead of
            Disconnect-PSSession.

        :rtype: tuple
        :return: A two element tuple: (ShellId, CommandId). Could later be used
            to get the result of the command."""
        setup = self._pre_execution_code % {
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
        # TODO: Fix this on a lower level
        if kwargs.get('kill_session', False):
            args = (args[0] + self._termination_code, )
        else:
            args = (args[0] + self._post_execution_code, )

        try:
            return super(UiAExchangeClient, self).execute(
                setup, *args, **kwargs)
        except WinRMServerException, e:
            raise ExchangeException(e)
        except URLError, e:
            # We can expect that the servers go up-and-down a bit.
            # We need to tell the caller about this. For example, events
            # should be queued for later attempts.
            raise ServerUnavailableException(e)

#    # TODO THIS IS ONLY FOR TESTING THE DELAYED NOTIFICATION COLLECTOR
#    def run(self, *args, **kwargs):
#        # Fail one out of three times. Seems like a good number for test?
#        if self.deliberate_failure == 4:
#            self.deliberate_failure = 0
#            raise ExchangeException
#        else:
#            self.deliberate_failure += 1
#        return super(ExchangeClient, self).run(*args, **kwargs)

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
        # TODO: Verify how this is to be done
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

        @type description: str
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
