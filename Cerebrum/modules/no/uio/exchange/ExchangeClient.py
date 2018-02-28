#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2017 University of Oslo, Norway
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

from __future__ import unicode_literals

import re
import string

from six import string_types, text_type

from urllib2 import URLError

from Cerebrum.Utils import read_password
from Cerebrum.modules.ad2.winrm import PowershellClient
from Cerebrum.modules.ad2.winrm import (WinRMServerException,
                                        PowershellException)
from Cerebrum.modules.exchange.Exceptions import (ServerUnavailableException,
                                                  ObjectNotFoundException,
                                                  ExchangeException,
                                                  ADError,
                                                  AlreadyPerformedException)


# Reeeaally  simple and stupid mock of the client…
class ClientMock(object):
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, a):
        def mocktrue(*args, **kw):
            return True
        return mocktrue


class ExchangeClient(PowershellClient):
    """A PowerShell client implementing function calls against Exchange."""
    def __init__(self,
                 auth_user,
                 domain_admin,
                 ex_domain_admin,
                 management_server,
                 exchange_commands,
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
        super(ExchangeClient, self).__init__(*args, **kwargs)
        self.logger.debug("ExchangeClient super returned")
        self.add_credentials(
            username=auth_user,
            password=read_password(auth_user, self.host, encoding='utf-8'))

        self.ignore_stdout_pattern = re.compile('.*EOB\n', flags=re.DOTALL)
        # Patterns used to filter out passwords.
        self.wash_output_patterns = [
            re.compile('ConvertTo-SecureString.*\\w*...', flags=re.DOTALL)]
        self.management_server = management_server
        self.exchange_commands = exchange_commands
        self.session_key = session_key if session_key else 'cereauth'

        # TODO: Make the following line pretty
        self.auth_user_password = read_password(auth_user, kwargs['host'],
                                                encoding='utf-8')
        # Note that we save the user's password by domain and not the host. It
        # _could_ be the wrong way to do it. TBD: Maybe both host and domain?
        self.ad_user, self.ad_domain = self._split_domain_username(
            domain_admin)
        self.ad_user_password = read_password(self.ad_user, self.ad_domain,
                                              encoding='utf-8')
        self.ex_user, self.ex_domain = self._split_domain_username(
            ex_domain_admin)
        self.ex_user_password = read_password(self.ex_user, self.ex_domain,
                                              encoding='utf-8')
        # Set up the winrm / PowerShell connection
        self.logger.debug("ExchangeClient: Preparing to connect")
        self.connect()
        self.logger.debug("ExchangeClient: Connected")

        # Collect AD-controllers
        controllers = self._get_domain_controllers(self.ad_domain,
                                                   self.ex_domain)
        self.ad_server = controllers['domain']
        self.resource_ad_server = controllers['resource_domain']
        # TODO: For all commands. Use the two variables above, and specify
        # which DC we use
        self.logger.debug("ExchangeClient: Init done")

    def _split_domain_username(self, name):
        """Separate the domain and username from a full domain username.

        Usernames could be in various formats:
         - username@domain
         - domain\\username
         - domain/username

        :type name: string
        :param name: domain\\username

        :rtype: tuple
        :return: Two elements: the username and the domain. If the username is
            only a username without a domain, the last element is an empty
            string."""
        if '@' in name:
            return name.split('@', 1)
        for char in ('\\', '/'):
            if char in name:
                domain, user = name.split(char, 1)
                return user, domain
        # Guess the domain is not set then:
        return name, ''

    _pre_execution_code_commented = """
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
            -Credential $cred -Name %(session_key)s;

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

    def _get_pre_execution_code(self):
        """Return Powershell commands that should be run before a command.

        This is what it does, in a nutshell:

        1. Define a credential for the communication between the springboard and
           the management server.
        2. Collect & connect to a previous PSSession, if this client has created
           one.
        3. If there is not an existing PSSession, create a new one
        3.1. Import the Active-Directory module
        3.2. Define credentials on the management server
        3.3. Initialize the Exchange module that gives us
             management-opportunities

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
                -Credential $cred -Name %(session_key)s;

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

                Invoke-Command { Import-Module C:\Modules\CerebrumExchange }
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
                }

    # After a command has run, we run the post execution code. We must
    # disconnect from the PSSession, in order to be able to resume it later
    _post_execution_code = """; Disconnect-PSSession $ses 2> $null > $null;"""

    # As with the post execution code, we want to clean up after us, when
    # the client terminates, hence the termination code
    _termination_code = ("""; Remove-PSSession -Session $ses """
                         """2> $null > $null;""")

    def execute(self, *args, **kwargs):
        """Override the execute command with all the startup and teardown
        commands for Exchange.

        :type kill_session: bool
        :param kill_session: If True, run Remove-PSSession instead of
            Disconnect-PSSession.

        :rtype: tuple
        :return: A two element tuple: (ShellId, CommandId). Could later be used
            to get the result of the command."""
        setup = self._get_pre_execution_code()

        # TODO: Fix this on a lower level
        if 'kill_session' in kwargs and kwargs['kill_session']:
            args = (args[0] + self._termination_code, )
        else:
            args = (args[0] + self._post_execution_code, )

        try:
            return super(ExchangeClient, self).execute(setup, *args, **kwargs)
        except WinRMServerException, e:
            raise ExchangeException(e)
        except URLError, e:
            # We can expect that the servers go up-and-down a bit.
            # We need to tell the caller about this. For example, events
            # should be queued for later attempts.
            raise ServerUnavailableException(e)

    def escape_to_string(self, data):
        """
        Override PowershellClient and return appropriate empty strings.

        :type data: mixed (dict, list, tuple, string or int)
        :param data: The data that must be escaped to be usable in powershell.

        :rtype: string
        :return: A string that could be used in powershell commands directly.
        """
        if isinstance(data, string_types) and not data:
            return "''"
        else:
            return super(ExchangeClient, self).escape_to_string(data)

    def get_output(self, commandid=None, signal=True, timeout_retries=50):
        """Override the output getter to remove unwanted output.

        Someone decided to implement write-host. We need to remove the stuff
        from write-host."""
        hit_eob = False
        for code, out in super(PowershellClient, self).get_output(
                commandid, signal, timeout_retries):
            out['stdout'] = out.get('stdout', '')
            if 'EOB\n' in out['stdout']:
                hit_eob = True
                out['stdout'] = re.sub(self.ignore_stdout_pattern, '',
                                       out['stdout'])
            elif not hit_eob:
                out['stdout'] = ''
            # Recover if the command hangs/crashes on the Windows-side:
            if ('stderr' in out
                    and 'The session availability is Busy' in out['stderr']):
                self.kill_session()
            if 'stderr' in out:
                for pat in self.wash_output_patterns:
                    out['stderr'] = re.sub(pat, 'PATTERN EXCLUDED',
                                           out['stderr'])
            yield code, out

    def _generate_exchange_command(self, command, kwargs={}, novalueargs=()):
        """Utility function for generating Exchange commands. Will stuff the
        command inside a Invoke-Command call.

        :type command: string
        :param command: The command to run.

        :type kwargs: dict
        :param kwargs: Keyword arguments to command.

        :type novalueargs: tuple
        :param novalueargs: Arguments that won't be escaped.

        :rtype: string
        :return: The command that will be invoked on the management server."""
        # TODO: Should we make escape_to_string handle credentials in a special
        #  way? Now we just add 'em as novalueargs in the functions.
        # We could define a Credential-class which subclasses str...
        return 'Invoke-Command { %s %s %s } -Session $ses;' % (
            command,
            ' '.join('-%s %s' % (k, self.escape_to_string(v))
                     for k, v in kwargs.iteritems()),
            ' '.join('-%s' % v for v in novalueargs))

    def kill_session(self):
        """Kill the current PSSession."""

        # TODO: Program this better. Do we really care about the return status?
        out = self.run(';', kill_session=True)
        return False if 'stderr' in out and out['stderr'] else True

    def in_ad(self, username):
        """Check if a user exists in AD.

        :type username: string
        :param username: The users username.

        :rtype: bool
        :return: Return True if the user exists.

        :raises ObjectNotFoundException: Raised if the account does not exist
            in AD.
        :raises ADError: Raised if the credentials are wrong, the server is
            down, and probarbly a whole lot of other reasons."""

        out = self.run(self._generate_exchange_command(
            'Get-ADUser',
            {'Identity': username, 'Server': self.ad_server},
            ('Credential $cred',)))

        if 'stderr' in out:
            if 'ADIdentityNotFoundException' in out['stderr']:
                # When this gets raised, the account does not exist in the
                # master domain.
                raise ObjectNotFoundException(
                    '%s not found on %s' % (username, self.ad_server))
            else:
                # We'll end up here if the server is down, or the credentials
                # are wrong. TODO: Should we raise this exception?
                raise ADError(out['stderr'])
        return True

    def in_exchange(self, name):
        """Check if an object exists in Exchange.

        :type name: string
        :param name: The objects distinguished name.

        :rtype: bool
        :return: Return True if the object exists.

        :raises ObjectNotFoundException: Raised if the object does not exist
            in Exchange.
        :raises ADError: Raised if the credentials are wrong, the server is
            down, and probarbly a whole lot of other reasons."""

        out = self.run(self._generate_exchange_command(
            'Get-ADObject',
            {'Identity': name, 'Server': self.ad_server},
            ('Credential $cred',)))

        if 'stderr' in out:
            if 'ADIdentityNotFoundException' in out['stderr']:
                # When this gets raised, the object does not exist in Exchange
                raise ObjectNotFoundException(
                    '%s not found in Exchange' % name)
            else:
                # We'll end up here if the server is down, or the credentials
                # are wrong. TODO: Should we raise this exception?
                raise ADError(out['stderr'])
        return True

    def _get_domain_controllers(self, domain, resource_domain=''):
        """Collect DomainControllers.

        :type domain: string
        :param domain: domain-name of the master domain-

        :rtype: dict
        :return: {'resource_domain': 'b.exutv.uio.no', 'domain': 'a.uio.no'}.

        :raises ADError: Raised upon errors."""
        cmd = self._generate_exchange_command(
            'Get-ADDomainController -DomainName ' +
            '\'%s\' -Discover | Select -Expand HostName' % domain)
        cmd += self._generate_exchange_command(
            'Get-ADDomainController -DomainName ' +
            '\'%s\' -Discover | Select -Expand HostName' % resource_domain)
        out = self.run(cmd)
        if 'stderr' in out:
            raise ADError(out['stderr'])
        else:
            tmp = out['stdout'].split()
            return {'resource_domain': tmp[1], 'domain': tmp[0]}

    ######
    # Mailbox-specific operations
    ######

    def new_mailbox(self, uname, display_name, first_name, last_name,
                    primary_address, db=None, ou=None):
        """Create a new mailbox in Exchange.

        :type uname: string
        :param uname: The users username.

        :type display_name: string
        :param display_name: The users full name.

        :type first_name: string
        :param first_name: The users given name.

        :type last_name: string
        :param last_name: The users family name.

        :type primary_address: string
        :param primary_address: The users primary email address.

        :type db: string
        :param db: The DB the user should reside on.

        :type ou: string
        :param ou: The container that the mailbox should be organized in.

        :rtype: bool
        :return: Return True if success.

        :raise ExchangeException: If the command failed to run for some reason
        """
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_new_mailbox' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_new_mailbox'])
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(
                uname=self.escape_to_string(uname),
                primary_address=self.escape_to_string(primary_address),
                display_name=self.escape_to_string(display_name),
                first_name=self.escape_to_string(first_name),
                last_name=self.escape_to_string(last_name)))
        try:
            out = self.run(cmd)
        except PowershellException:
            raise ExchangeException('Could not create mailbox for %s' % uname)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def create_shared_mailbox(self, name):
        """Create a new shared mailbox in Exchange.

        :type name: string
        :param name: The mailbox name.

        :rtype: bool
        :return: Return True if success.

        :raise ExchangeException: If the command failed to run for some reason
        """
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_create_shared_mailbox' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_create_shared_mailbox'])
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(
                name=self.escape_to_string(name)))
        try:
            out = self.run(cmd)
        except PowershellException:
            raise ExchangeException(
                'Could not create shared mailbox for {name}'.format(name=name))
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def delete_shared_mailbox(self, name):
        """Remove a shared mailbox.

        :type name: string
        :param name: The mailbox name

        :raises ExchangeException: If the command fails to run.
        """
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_delete_shared_mailbox' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_delete_shared_mailbox'])
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(name=self.escape_to_string(name)))
        try:
            out = self.run(cmd)
        except PowershellException:
            raise ExchangeException(
                'Could not remove shared mailbox for {name}'.format(name=name))
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_primary_mailbox_address(self, uname, address):
        """Set primary email addresses from a mailbox.

        :type uname: string
        :param uname: The user name to look up associated mailbox by.

        :type address: string
        :param address: The email address to set as primary.

        :raise ExchangeException: If the command failed to run
            for some reason."""
        # TODO: Do we want to set EmailAddressPolicyEnabled at the same time?
        # TODO: Verify how this acts with address policy on
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'PrimarySmtpAddress': address})

        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_mailbox_addresses(self, uname, addresses):
        """Add email addresses from a mailbox.

        :type uname: string
        :param uname: The user name to look up associated mailbox by.

        :type addresses: list
        :param addresses: A list of addresses to add.

        :raise ExchangeException: If the command failed to run
            for some reason."""
        addrs = {'add': addresses}
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'EmailAddresses': addrs})
        out = self.run(cmd)

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_mailbox_addresses(self, uname, addresses):
        """Remove email addresses from a mailbox.

        :type uname: string
        :param uname: The user name to look up associated mailbox by.

        :type addresses: list
        :param addresses: A list of addresses to remove.

        :raise ExchangeException: If the command failed to run
            for some reason."""
        addrs = {'remove': addresses}
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'EmailAddresses': addrs})
        out = self.run(cmd)

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_visibility(self, uname, visible=False):
        """Set the visibility of a mailbox in the address books.

        :type uname: string
        :param uname: The username associated with the mailbox.

        :type enabled: bool
        :param enabled: To show or hide the mailbox. Default hide.

        :raises ExchangeException: If the command fails to run."""
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'HiddenFromAddressListsEnabled': not visible})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_quota(self, uname, soft, hard):
        """Set the quota for a particular mailbox.

        :type uname: string
        :param uname: The username to look up associated mailbox by.

        :type soft: int
        :param soft: The soft-quota limit in MB.

        :type hard: int
        :param hard: The hard-quota limit in MB.

        :raise ExchangeException: If the command failed to run
            for some reason."""
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'IssueWarningQuota': '"%d MB"' % int(soft),
             'ProhibitSendReceiveQuota': '"%d MB"' % int(hard),
             'ProhibitSendQuota': '"%d MB"' % int(hard)},
            ('UseDatabaseQuotaDefaults:$false',))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_names(self, uname, first_name, last_name, full_name):
        """Set a users name.

        :type uname: string
        :param uname: The uname to select account by.

        :type first_name: string
        :param first_name: The persons first name.

        :type last_name: string
        :param last_name: The persons last name.

        :type full_name: string
        :param full_name: The persons full name, to use as display name.

        :raises ExchangeException: Raised upon errors."""
        # TODO: When empty strings as args to the keyword args are handled
        # appropriatly, change this back.
        args = ["FirstName %s" % self.escape_to_string(first_name),
                "LastName %s" % self.escape_to_string(last_name),
                "DisplayName %s" % self.escape_to_string(full_name)]

        cmd = self._generate_exchange_command(
            'Set-User',
            {'Identity': uname},
            (' -'.join(args),))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def export_mailbox(self, uname):
        raise NotImplementedError

    def remove_mailbox(self, uname):
        """Remove a mailbox and it's linked account from Exchange.

        :type uname: string
        :param uname: The users username.

        :raises ExchangeException: If the command fails to run.
        """
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_remove_mailbox' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_remove_mailbox'])
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(uname=self.escape_to_string(uname)))
        try:
            out = self.run(cmd)
        except PowershellException:
            raise ExchangeException('Could not remove mailbox for %s' % uname)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_forward(self, uname, address):
        """Set forwarding address for a mailbox.

        :type uname: string
        :param uname: The users username.

        :type address: String or None
        :param address: The forwarding address to set.

        :raises ExchangeException: If the command fails to run."""
        if not address:
            cmd = self._generate_exchange_command(
                'Set-Mailbox',
                {'Identity': uname},
                ('ForwardingSmtpAddress $null',))
        else:
            cmd = self._generate_exchange_command(
                'Set-Mailbox',
                {'Identity': uname,
                 'ForwardingSmtpAddress': address})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_local_delivery(self, uname, local_delv):
        """Set local delivery for a mailbox.

        :type uname: string
        :param uname: The users username.

        :type local_delivery: bool
        :param local_delivery: Enable or disable local delivery.

        :raises ExchangeException: If the command fails to run."""
        cmd = self._generate_exchange_command(
            'Set-Mailbox',
            {'Identity': uname,
             'DeliverToMailboxAndForward': local_delv})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_spam_settings(self, uname, level, action):
        """Set spam settings for a user.

        :type uname: string
        :param uname: The username.

        :type level: int
        :param level: The spam level to set.

        :type action: string
        :param action: The spam action to set.

        :raises ExchangeException: If the command fails to run."""
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_set_spam_settings' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_set_spam_settings'])
        args = {'uname': self.escape_to_string(uname),
                'level': self.escape_to_string(level),
                'action': self.escape_to_string(action)}
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(args))
        try:
            out = self.run(cmd)
        except PowershellException, e:
            raise ExchangeException(text_type(e))
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    ######
    # General group operations
    ######

    def new_group(self, gname, ou=None):
        """Create a new mail enabled security group.

        :type gname: string
        :param gname: The groups name.

        :type ou: string
        :param ou: The container the group should be organized in.

        :raises ExchangeException: Raised if the command fails to run.
        """
        param = {'Name':  gname,
                 'GroupCategory': 'Security',
                 'GroupScope': 'Universal',
                 'Server': self.resource_ad_server}
        if ou:
            param['Path'] = ou
        cmd = self._generate_exchange_command(
            'New-ADGroup',
            param,
            ('Credential $cred',))

        param = {'Identity': '"CN=%s,%s"' % (gname, ou),
                 'DomainController': self.resource_ad_server}
        nva = ('Confirm:$false',)
        cmd += self._generate_exchange_command(
            'Enable-Distributiongroup',
            param,
            nva)

        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def new_roomlist(self, gname, ou=None):
        """Create a new Room List.

        :type gname: string
        :param gname: The roomlists name.

        :type ou: string
        :param ou: Which container to put the object into.

        :raise ExchangeException: If the command cannot be run, raise."""
        # Yeah, we need to specify the Confirm-option as a NVA,
        # due to the silly syntax.
        param = {'Name': gname,
                 'Type': 'Distribution'}
        if ou:
            param['OrganizationalUnit'] = ou
        cmd = self._generate_exchange_command(
            'New-DistributionGroup',
            param,
            ('RoomList', 'Confirm:$false',))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_roomlist(self, gname):
        """Remove a roomlist.

        :type gname: string
        :param gname: The roomlists name.

        :raise ExchangeException: If the command cannot be run, raise."""
        cmd = self._generate_exchange_command(
            'Remove-DistributionGroup',
            {'Identity': gname},
            ('Confirm:$false',))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_group(self, gname):
        """Remove a mail enabled securitygroup.

        :type gname: string
        :param gname: The groups name.

        :raises ExchangeException: Raised if the command fails to run."""
        cmd = self._generate_exchange_command(
            'Remove-ADGroup',
            {'Identity':  gname},
            ('Confirm:$false', 'Credential $cred'))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_group_display_name(self, gname, dn):
        """Set a groups display name.

        :type gname: string
        :param gname: The groups name.

        :type dn: str
        :param dn: display name.

        :raises ExchangeException: If the command fails to run."""
        cmd = self._generate_exchange_command(
            'Set-ADGroup',
            {'Identity': gname,
             'DisplayName': dn},
            ('Credential $cred',))
        # TODO: Verify how this is to be done
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_description(self, gname, description):
        """Set a distributiongroups description.

        :type gname: string
        :param gname: The groups name.

        :type description: str
        :param description: The groups description.

        :raises ExchangeException: If the command fails to run."""
        cmd = self._generate_exchange_command(
            'Set-Group',
            {'Identity': gname},
            ('Notes %s' % self.escape_to_string(description.strip()),))

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

    ######
    # Distribution Group-specific operations
    ######

    def set_distgroup_address_policy(self, gname, enabled=False):
        """Enable or disable the AddressPolicy for the Distribution Group.

        :type gname: string
        :param gname: The groups name.

        :type enabled: bool
        :param enabled: Enable or disable address policy.

        :raise ExchangeException: If the command cannot be run, raise."""
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup',
            {'Identity': gname,
             'EmailAddressPolicyEnabled': enabled})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

#    def set_roomlist(self, gname):
#        """Define a distribution group as a roomlist.
#
#        :type gname: string
#        :param gname: The groups name
#
#        :raise ExchangeException: Raised if the command cannot be run.
#        """
#        cmd = self._generate_exchange_command(
#                'Set-DistributionGroup',
#               {'Identity': gname},
#               ('RoomList',))
#        out = self.run(cmd)
#        if out.has_key('stderr'):
#            raise ExchangeException(out['stderr'])
#        else:
#            return True

    def set_distgroup_primary_address(self, gname, address):
        """Set the primary-address of a Distribution Group.

        :type gname: string
        :param gname: The groups name.

        :type address: string
        :param address: The primary address.

        :raise ExchangeException: If the command cannot be run, raise."""
        #   TODO: We want to diable address policy while doing htis?
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup',
            {'Identity': gname,
             'PrimarySmtpAddress': address})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_visibility(self, gname, visible=True):
        """Set the visibility of a DistributionGroup in the address books.

        :type gname: string
        :param gname: The group name

        :type visible: bool
        :param visible: Should the group be visible? Defaults to true

        :raises ExchangeException: If the command fails to run."""
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup',
            {'Identity': gname,
             'HiddenFromAddressListsEnabled': visible})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_distgroup_addresses(self, gname, addresses):
        """
        Add email addresses from a distribution group

        :type gname: string
        :param gname: The group name to look up associated distgroup by.

        :type addresses: list
        :param addresses: A list of addresses to add.

        :raise ExchangeException: If the command failed to run for some reason.
        """
        # TODO: Make me handle single addresses too!
        addrs = {'add': addresses}
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup',
            {'Identity': gname,
             'EmailAddresses': addrs})
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
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_add_distgroup_member' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_add_distgroup_member'])
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(
                member=member,
                gname=gname))
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
        assert(isinstance(self.exchange_commands, dict) and
               'execute_on_remove_distgroup_member' in self.exchange_commands)
        cmd_template = string.Template(
            self.exchange_commands['execute_on_remove_distgroup_member'])
        cmd = self._generate_exchange_command(
            cmd_template.safe_substitute(
                member=member,
                gname=gname))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_distgroup_addresses(self, gname, addresses):
        """
        Remove email addresses from a distgroup.

        :type gname: string
        :param gname: The group name to look up associated distgroup by.

        :type addresses: list
        :param addresses: A list of addresses to remove.

        :raise ExchangeException: If the command failed to run for some reason.
        """
        # TODO: Make me handle single addresses too!
        addrs = {'remove': addresses}
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup',
            {'Identity': gname,
             'EmailAddresses': addrs})
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_member_restrictions(self, gname, join='Closed',
                                          part='Closed'):
        """Set the member restrictions on a Distribution Group.
        Default is 'Closed'-state.

        :type gname: string
        :param gname: The groups name.

        :type join: str
        :param join: Set MemberJoinRestriction to 'Open', 'Closed' or
            'ApprovalRequired'.

        :type part: str
        :param part: Set MemberPartApprovalRequiredion to 'Open', 'Closed' or
            'ApprovalRequired'.

        :raise ExchangeException: If the command cannot be run, raise."""
        # TBD: Enforce constraints on join- and part-restrictions?
        params = {'Identity': gname}
        if join:
            params['MemberJoinRestriction'] = join
        if part:
            params['MemberDepartRestriction'] = part
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup', params)

        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_manager(self, gname, addr):
        """Set the manager of a distribution group.

        :type gname: string
        :param gname: The groups name.

        :type addr: str
        :param uname: The e-mail address which manages this group.

        :raise ExchangeException: If the command cannot be run, raise."""
        cmd = self._generate_exchange_command(
            'Set-DistributionGroup',
            {'Identity':  gname,
             'ManagedBy': addr},
            ('BypassSecurityGroupManagerCheck',))
        out = self.run(cmd)
        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        else:
            return True

    ######
    # Get-operations used for checking state in Exchange
    ######

    # TODO: Refactor these two or something
    def get_mailbox_info(self, attributes):
        """Get information about the mailboxes in Exchange.

        :type attributes: list(string)
        :param attributes: Which attributes we want to return.

        :raises ExchangeException: Raised if the command fails to run."""
        # TODO: Filter by '-Filter {IsLinked -eq "True"}' on get-mailbox.
        cmd = self._generate_exchange_command(
            '''Get-Mailbox -ResultSize Unlimited | Select %s''' %
            ', '.join(attributes))
        # TODO: Do we really need to add that ;? We can't have it here...
        json_wrapped = '''if ($str = %s | ConvertTo-Json) {
            $str -replace '$', ';'
            }''' % cmd[:-1]
        out = self.run(json_wrapped)
        try:
            ret = self.get_output_json(out, dict())
        except ValueError as e:
            raise ExchangeException('No mailboxes exists?: {!s}\n{!s}'
                                    .format(e, out))

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        elif not ret:
            raise ExchangeException(
                'Bad output while fetching mailboxes: %s' % out)
        else:
            return ret

    def get_user_info(self, attributes):
        """Get information about a user in Exchange.

        :type attributes: list(string)
        :param attributes: Which attributes we want to return.

        :raises ExchangeException: Raised if the command fails to run."""
        # TODO: I hereby leave the tidying up this call generation as an
        #       exercise to my followers.
        cmd = self._generate_exchange_command(
            '''Get-User -Filter * -ResultSize Unlimited | Select %s''' %
            ', '.join(attributes))

        # TODO: Do we really need to add that ;? We can't have it here...
        json_wrapped = '''if ($str = %s | ConvertTo-Json) {
            $str -replace '$', ';'
            }''' % cmd[:-1]
        out = self.run(json_wrapped)
        try:
            ret = self.get_output_json(out, dict())
        except ValueError, e:
            raise ExchangeException('No users exist?: %s' % e)

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        elif not ret:
            raise ExchangeException(
                'Bad output while fetching users: %s' % out)
        else:
            return ret

    ######
    # Get-operations used for checking group state in Exchange
    ######

    def get_group_info(self, attributes, ou=None):
        """Get information about the distribution group in Exchange.

        :type attributes: list(string)
        :param attributes: Which attributes we want to return.

        :type ou: string
        :param ou: The organizational unit to look in.

        :raises ExchangeException: Raised if the command fails to run."""
        if ou:
            f_org = '-OrganizationalUnit \'%s\'' % ou
        else:
            f_org = ''

        cmd = self._generate_exchange_command(
            '''Get-DistributionGroup %s -ResultSize Unlimited | Select %s''' %
            (f_org, ', '.join(attributes)))
        # TODO: Do we really need to add that ;? We can't have it here...
        json_wrapped = '''if ($str = %s | ConvertTo-Json) {
            $str -replace '$', ';'
            }''' % cmd[:-1]
        out = self.run(json_wrapped)
        try:
            ret = self.get_output_json(out, dict())
        except ValueError, e:
            raise ExchangeException('No groups exists?: %s' % e)

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        elif not ret:
            raise ExchangeException(
                'Bad output while fetching groups: %s' % out)
        else:
            return ret

    def get_group_description(self, ou=None):
        """Get the description from groups in Exchange.

        :type ou: string
        :param ou: The organizational unit to look in.

        :raises ExchangeException: Raised if the command fails to run."""
        if ou:
            f_org = '-OrganizationalUnit \'%s\'' % ou
        else:
            f_org = ''

        cmd = self._generate_exchange_command(
            '''Get-Group %s -ResultSize Unlimited | Select Name, Notes''' %
            f_org)
        # TODO: Do we really need to add that ;? We can't have it here...
        json_wrapped = '''if ($str = %s | ConvertTo-Json) {
            $str -replace '$', ';'
            }''' % cmd[:-1]
        out = self.run(json_wrapped)
        try:
            ret = self.get_output_json(out, dict())
        except ValueError, e:
            raise ExchangeException('No groups exists?: %s' % e)

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        elif not ret:
            raise ExchangeException(
                'Bad output while fetching NOTES: %s' % out)
        else:
            return ret

    def get_group_members(self, gname):
        """Return the members of a group.

        :type gname: string
        :param gname: The groups name.

        :raises ExchangeException: Raised if the command fails to run."""
        # Jeg er mesteren!!!!!11
        cmd = self._generate_exchange_command(
            '$m = @(); $m += Get-ADGroupMember %s -Credential $cred | ' %
            gname + 'Select -ExpandProperty Name; ConvertTo-Json $m')
        out = self.run(cmd)
        try:
            ret = self.get_output_json(out, dict())
        except ValueError, e:
            raise ExchangeException('No group members in %s?: %s' % (gname, e))

        if 'stderr' in out:
            raise ExchangeException(out['stderr'])
        # TODO: Be more specific in this check?
        elif ret is None:
            raise ExchangeException(
                'Bad output while fetching members from %s: %s' %
                (gname, out))
        else:
            return ret
