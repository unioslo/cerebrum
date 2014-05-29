#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2013-2014 University of Oslo, Norway
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

This is a subclass of PowershellClient.

This module can be used by exports or an event daemon for creating,
deleting and updating mailboxes and distribution groups in Exchange 2013."""


import cerebrum_path
from Cerebrum.Utils import read_password
from Cerebrum.modules.ad2.winrm import PowershellClient
from Cerebrum.modules.ad2.winrm import WinRMServerException
from Cerebrum.modules.exchange.Exceptions import *
from Cerebrum.modules.exchange.v2013.ExchangeClient import ExchangeClient
import re


class UiAExchangeClient(ExchangeClient):
    def __init__(self, auth_user, domain_admin, ex_domain_admin,
                    management_server, session_key=None, *args, **kwargs):
        """Set up the WinRM client to be used with running Exchange commands.
        
        @type auth_user: string
        @param auth_user: The username of the account we use to connect to the
            server.

        @type domain_admin: string
        @param domain_admin: The username of the account we use to connect to
            the AD domain we are going to synchronize with.

        """

        super(UiAExchangeClient, self).__init__(auth_user, domain_admin, 
               ex_domain_admin, management_server, session_key, *args, **kwargs)

    _pre_execution_code_commented = u"""
        # Create credentials for the new-PSSession
        $pass = ConvertTo-SecureString -Force -AsPlainText %(ex_pasw)s;
        $cred = New-Object System.Management.Automation.PSCredential( `
        %(ex_domain_user)s, $pass);

        # We collect any existing sessions, and connect to the first one.
        # TODO: Filter them based on availability and state
        $sessions = Get-PSSession -ComputerName %(management_server)s `
        -Credential $cred -Name %(session_key)s 2> $null;

        if ( $sessions ) {
            $ses = $sessions[0];
            Connect-PSSession -Session $ses 2> $null > $null;
        }

        # If Get-PSSession or Connect-PSSession fails, make a new one!
        if (($? -and ! $ses) -or ! $?) {
            $ses = New-PSSession -ComputerName %(management_server)s `
            -Credential $cred -Name %(session_key)s -ConfigurationName Cerebrum;
            
            # We need to access Active-directory in order to find out if a
            # user is in AD:
            Import-Module ActiveDirectory 2> $null > $null;
            
            # Import Exchange stuff or everything else:
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

            # Redefine get-credential so it returns the appropriate credential
            # that is defined earlier. This allows us to avoid patching
            # Connect-ExchangeServer for each damn update.
            Invoke-Command { function get-credential () { return $cred;} } `
            -Session $ses;

            Invoke-Command { Connect-ExchangeServer `
            -ServerFqdn %(management_server)s -UserName %(ex_user)s } `
            -Session $ses;
        }
        # We want to have something to search for when removing all the crap
        # we can't redirect.
        write-output EOB;"""

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
            -Credential $cred -Name %(session_key)s -ConfigurationName Cerebrum;
            
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
            -ServerFqdn %(management_server)s -UserName %(ex_user)s } `
            -Session $ses;
        }
        write-output EOB;"""

    # After a command has run, we run the post execution code. We must
    # disconnect from the PSSession, in order to be able to resume it later
    _post_execution_code = u"""; Disconnect-PSSession $ses 2> $null > $null;"""

    # As with the post execution code, we want to clean up after us, when
    # the client terminates, hence the termination code
    _termination_code = u"""; Remove-PSSession -Session $ses 2> $null > $null;"""

    def execute(self, *args, **kwargs):
        """Override the execute command with all the startup and teardown
        commands for Exchange.

        @type kill_session: bool
        @param kill_session: If True, run Remove-PSSession instead of
            Disconnect-PSSession.

        @rtype: tuple
        @return: A two element tuple: (ShellId, CommandId). Could later be used
            to get the result of the command.
        """
        setup = self._pre_execution_code % {
                    'session_key': self.session_key,
                    'ad_domain_user': self.escape_to_string('%s\\%s' % 
                                        (self.ad_domain, self.ad_user)),
                    'ad_user': self.escape_to_string(self.ad_user),
                    'ad_pasw': self.escape_to_string(self.ad_user_password),
                    'ex_domain_user': self.escape_to_string('%s\\%s' % 
                                        (self.ex_domain, self.ex_user)),
                    'ex_user': self.escape_to_string(self.ex_user),
                    'ex_pasw': self.escape_to_string(self.ex_user_password),
                    'management_server': self.escape_to_string(
                                                self.management_server)}
        # TODO: Fix this on a lower level
        if kwargs.has_key('kill_session') and kwargs['kill_session']:
            args = (args[0] + self._termination_code, )
        else:
            args = (args[0] + self._post_execution_code, )

        try:
            return super(UiAExchangeClient, self).execute(setup, *args, **kwargs)
        except WinRMServerException, e:
            raise ExchangeException(e)
        except URLError, e:
            # We can expect that the servers go up-and-down a bit.
            # We need to tell the caller about this. For example, events
            # should be queued for later attempts.
            raise ServerUnavailableException(e)


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
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True


