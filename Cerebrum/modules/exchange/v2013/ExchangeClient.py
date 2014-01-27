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
import re


class ExchangeClient(PowershellClient):
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

        # TODO: THIS IS ONLY FOR TESTING DNC, REMOVE AFTER THAT
        self.deliberate_failure = 0


#TODO: Bad hack, cleanup and fix
        super(ExchangeClient, self).__init__(*args, **kwargs)
#super(ExchangeClient, self).__init__(kwargs['host'], ex_domain_admin,
#        identity_file='/usit/cere-utv01/u1/jsama/exchange/keys/exutv-multi01',
#        logger=kwargs['logger'], timeout=60)
        self.add_credentials(username=auth_user,
                password=unicode(read_password(auth_user, self.host), 'utf-8'))

        self.ignore_stdout_pattern = re.compile('.*EOB\n', flags=re.DOTALL)
        self.management_server = management_server
        self.session_key = session_key if session_key else 'cereauth'

#self.auth_user_password = unicode(read_password(auth_user, management_server),
#                                                    'utf-8')
        # TODO: Make the following line pretty
        self.auth_user_password = unicode(
                read_password(auth_user, kwargs['host']), 'utf-8')
        # Note that we save the user's password by domain and not the host. It
        # _could_ be the wrong way to do it. TBD: Maybe both host and domain?
        self.ad_user, self.ad_domain = self._split_domain_username(
                                                            domain_admin)
        self.ad_user_password = unicode(read_password(self.ad_user,
                                                            self.ad_domain),
                                                            'utf-8')
        self.ex_user, self.ex_domain = self._split_domain_username(
                                                            ex_domain_admin)
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


    def _split_domain_username(self, name):
        """Separate the domain and username from a full domain username.

        Usernames could be in various formats:
         - username@domain
         - domain\username
         - domain/username

        @type name: string
        @param name: domain\username

        @rtype: tuple
        @return: Two elements: the username and the domain. If the username is
            only a username without a domain, the last element is an empty
            string.

        """
        if '@' in name:
            return name.split('@', 1)
        for char in ('\\', '/'):
            if char in name:
                domain, user = name.split(char, 1)
                return user, domain
        # Guess the domain is not set then:
        return name, ''
    
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
            return super(ExchangeClient, self).execute(setup, *args, **kwargs)
        except WinRMServerException, e:
            raise ExchangeException(e)
# TODO: This has been moved to a lower level.. Remove eventually
#        try:
#            return super(ExchangeClient, self).execute(setup, *args, **kwargs)
#        except WinRMServerException, e:
#            # TODO: Should we check for more exceptions inside here or
#            # something?
#
#            # If we wind up here, the MaxConcurrentOperationsPerUser variable
#            # might have reached it's limit. We try to close the shell on the
#            # springboard, and open a new connection. If that fails still,
#            # we raise an ExchangeException, to requeue the event at a later
#            # time.
#            #
#            # We really should not do this, as this really should not happen.
#            # It does happen, since Windows is Silly. Read the following
#            # document about Signal, and the note in the appendix:
#            # http://msdn.microsoft.com/en-us/library/cc251679.aspx
#            # http://msdn.microsoft.com/en-us/library/f8ba005a-8271-45ec-92cd-
#            #                                               43524d39c80f#id119
#            try:
#                self.logger.debug('Cought WinRM failure: %s' % str(e))
#                self.logger.debug('Trying to start a new shell..')
#                # We need to do this try/except when attempting a close.
#                # If the shell times out, we can't close it, since it does
#                # not exist (and the close operation raises an exception).
#                # If the number operations performed has reached the
#                # MaxConcurrentOperations- PerUsers limit, we must close the
#                # shell.
#                # TODO: Implement saner exception-handling here, when mood
#                # allows.
#                try:
#                    self.close()
#                except:
#                    pass
#                self.connect()
#                return super(ExchangeClient, self).execute(
#                                                        setup, *args, **kwargs)
#            except WinRMServerException, e:
#                raise ExchangeException(e)
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


    def get_output(self, commandid=None, signal=True, timeout_retries=50):
        """Override the output getter to remove unwanted output.

        Someone decided to implement write-host. We need to remove the stuff
        from write-host.
        """
        hit_eob = False
        for code, out in super(PowershellClient, self).get_output(commandid,
                                                    signal, timeout_retries):
            out['stdout'] = out.get('stdout', '')
            if 'EOB\n' in out['stdout']:
                hit_eob = True
                out['stdout'] = re.sub(self.ignore_stdout_pattern, '',
                                       out['stdout'])
            elif not hit_eob:
                out['stdout'] = ''

            yield code, out

    def _generate_exchange_command(self, command, kwargs={}, novalueargs=()):
        """Utility function for generating Exchange commands. Will stuff the
        command instide a Invoke-Command call.

        @type command: string
        @param command: The command to run

        @type kwargs: dict
        @param kwargs: Keyword arguments to command

        @type novalueargs: tuple
        @param novalueargs: Arguments that won't be escaped

        @rtype: string
        @return: The command that will be invoked on the management server
        """
        # TODO: Should we make escape_to_string handle credentials in a special
        #  way? Now we just add 'em as novalueargs in the functions.
        # We could define a Credential-class which subclasses str...
        return 'Invoke-Command { %s %s %s } -Session $ses;' % (command,
                            ' '.join('-%s %s' % (k, self.escape_to_string(v))
                                for k, v in kwargs.iteritems()),
                            ' '.join('-%s' % v for v in novalueargs))

    def kill_session(self):
        """Kill the current PSSession."""

        # TODO: Program this better. Do we really care about the return status?
        out = self.run(';', kill_session=True)
        return False if out.has_key('stderr') and out['stderr'] else True

    def in_ad(self, username):
        """Check if a user exists in AD.

        @type username: string
        @param username: The users username

        @rtype: bool
        @return: Return True if the user exists
        
        @raises ObjectNotFoundException: Raised if the account does not exist
            in AD
        @raises ADError: Raised if the credentials are wrong, the server is
            down, and probarbly a whole lot of other reasons
        """
        
        out = self.run(self._generate_exchange_command(
                    'Get-ADUser',
                    {'Identity': username, 'Server': self.ad_server },
                    ('Credential $cred',)))

        if out.has_key('stderr'):
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

        @type name: string
        @param name: The objects distinguished name

        @rtype: bool
        @return: Return True if the object exists
        
        @raises ObjectNotFoundException: Raised if the object does not exist
            in Exchange
        @raises ADError: Raised if the credentials are wrong, the server is
            down, and probarbly a whole lot of other reasons
        """
        
        out = self.run(self._generate_exchange_command(
                    'Get-ADObject',
                    {'Identity': name, 'Server': self.ad_server },
                    ('Credential $cred',)))

        if out.has_key('stderr'):
            if 'ADIdentityNotFoundException' in out['stderr']:
                # When this gets raised, the object does not exist in Exchange
                raise ObjectNotFoundException(
                        '%s not found in Exchange' % username)
            else:
                # We'll end up here if the server is down, or the credentials
                # are wrong. TODO: Should we raise this exception?
                raise ADError(out['stderr'])
        return True

    def _get_domain_controllers(self, domain, resource_domain=''):
        """Collect DomainControllers.
        
        @type domain: string
        @param domain: domain-name of the master domain
        
        @rtype: dict
        @return: {'resource_domain': 'b.exutv.uio.no', 'domain': 'a.uio.no'}

        @raises ADError: Raised upon errors
        """
        cmd = self._generate_exchange_command(
                        'Get-ADDomainController -DomainName ' +
                        '\'%s\' -Discover | Select -Expand HostName'
                                % domain)
        cmd += self._generate_exchange_command(
                        'Get-ADDomainController -DomainName ' +
                        '\'%s\' -Discover | Select -Expand HostName'
                            % resource_domain)
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ADError(out['stderr'])
        else:
            tmp = out['stdout'].split()
            return {'resource_domain' : tmp[1], 'domain': tmp[0]}

    ######
    # Mailbox-specific operations
    ######

    def new_mailbox(self, uname, display_name, first_name, last_name, db=None, ou=None):
        """Create a new mailbox in Exchange.

        @type username: string
        @param username: The users username

        @type display_name: string
        @param display_name: The users full name
        
        @type first_name: string
        @param first_name: The users given name

        @type last_name: string
        @param last_name: The users family name

        @type db: string
        @param db: The DB the user should reside on
        
        @type ou: string
        @param ou: The container that the mailbox should be organized in

        @rtype: bool
        @return: Return True if success
        
        @raise ExchangeException: If the command failed to run for some reason
        """

        """New-Mailbox
        -LinkedDomainController $ad_contoller
        -LinkedMasterAccount uio\jsama
        -LinkedCredential $ad_cred
        -Name jsama
        -DisplayName "Jo Sama"
        -FirstName Jo
        -LastName Sama"""

        kwargs = {'LinkedDomainController': self.ad_server,
                 'LinkedMasterAccount': '%s\%s' % (self.ad_domain, uname),
                 'Alias': uname,
                 #'Alias': uname,
                 'Name': uname,
                 'DisplayName': display_name,
                 'FirstName': first_name,
                 'LastName': last_name
        }
        if db:
            kwargs['Database'] = db
        if ou:
            kwargs['OrganizationalUnit'] = ou

        nva = ('LinkedCredential $ad_cred',)
        cmd = self._generate_exchange_command('New-Mailbox', kwargs, nva)

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

    def set_primary_mailbox_address(self, uname, address):
        """Set primary email addresses from a mailbox

        @type uname: string
        @param uname: The user name to look up associated mailbox by

        @type address: string
        @param address: The email address to set as primary

        @raise ExchangeException: If the command failed to run for some reason
        """
        # TODO: Do we want to set EmailAddressPolicyEnabled at the same time?
        # TODO: Verify how this acts with address policy on
        cmd = self._generate_exchange_command(
                'Set-Mailbox',
               {'Identity': uname,
                'PrimarySmtpAddress': address})
        
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_mailbox_addresses(self, uname, addresses):
        """Add email addresses from a mailbox

        @type uname: string
        @param uname: The user name to look up associated mailbox by

        @type addresses: list
        @param addresses: A list of addresses to add

        @raise ExchangeException: If the command failed to run for some reason
        """
        addrs = {'add': addresses}
        cmd = self._generate_exchange_command(
                'Set-Mailbox',
               {'Identity': uname,
                'EmailAddresses': addrs})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_mailbox_addresses(self, uname, addresses):
        """Remove email addresses from a mailbox

        @type uname: string
        @param uname: The user name to look up associated mailbox by

        @type addresses: list
        @param addresses: A list of addresses to remove

        @raise ExchangeException: If the command failed to run for some reason
        """
        addrs = {'remove': addresses}
        cmd = self._generate_exchange_command(
                'Set-Mailbox',
               {'Identity': uname,
                'EmailAddresses': addrs})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_visibility(self, uname, visible=False):
        """Set the visibility of a mailbox in the address books.

        @type uname: string
        @param uname: The username associated with the mailbox

        @type enabled: bool
        @param enabled: To show or hide the mailbox. Default hide.

        @raises ExchangeException: If the command fails to run.
        """
        cmd = self._generate_exchange_command(
                'Set-Mailbox',
                {'Identity': uname,
                 'HiddenFromAddressListsEnabled': not visible})
        out = self.run(cmd)
        if out.has_key('stderr'):
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
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_mailbox_quota(self, uname, soft, hard):
        """Set the quota for a particular mailbox.
        
        @type uname: string
        @param uname: The username to look up associated mailbox by

        @type soft: int
        @param soft: The soft-quota limit in MB

        @type hard: int
        @param hard: The hard-quota limit in MB

        @raise ExchangeException: If the command failed to run for some reason
        """
        cmd = self._generate_exchange_command(
                'Set-Mailbox',
                   {'Identity': uname,
                    'IssueWarningQuota': '"%d MB"' % int(soft),
                    'ProhibitSendReceiveQuota': '"%d MB"' % int(hard),
                    'ProhibitSendQuota': '"%d MB"' % int(hard)},
                ('UseDatabaseQuotaDefaults:$false',))
        out = self.run(cmd)
        if out.has_key('stderr'):
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
        cmd = self._generate_exchange_command('Set-User',
                {'Identity': uname,
                 'FirstName': first_name,
                 'LastName': last_name,
                 'DisplayName': full_name})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True
    
    def export_mailbox(self, uname):
        raise NotImplementedError

    def remove_mailbox(self, uname):
        """Remove a mailbox and it's linked account from Exchange
        
        @type uname: string
        @param uname: The users username

        @raises ExchangeException: If the command fails to run
        """
        cmd = self._generate_exchange_command(
                'Remove-Mailbox',
               {'Identity': uname},
               ('Confirm:$false',))
        # TODO: Verify how this is to be done
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True
    ######
    # General group operations
    ######
    
    def set_group_display_name(self, gname, dn):
        """Set a groups display name.

        @type gname: string
        @param gname: The groups name

        @type dn: str
        @param dn: display name

        @raises ExchangeException: If the command fails to run
        """
        cmd = self._generate_exchange_command(
                'Set-ADGroup',
               {'Identity': gname,
                'DisplayName': dn},
                ('Credential $cred',))
        # TODO: Verify how this is to be done
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True
   
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
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_secgroup_description(self, gname, description):
        """Set a securitygroups description.

        @type gname: string
        @param gname: The groups name

        @type description: str
        @param description: The groups description

        @raises ExchangeException: If the command fails to run
        """
        cmd = self._generate_exchange_command(
                'Set-ADGroup',
               {'Identity': gname,
                'Description': description},
                ('Credential $cred',))
        
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    ######
    # Distribution Group-specific operations
    ######

    def new_distribution_group(self, gname, ou=None):
        """Create a new Distribution Group

        @type gname: string
        @param gname: The groups name

        @type ou: string
        @param ou: Which container to put the object into
        
        @raise ExchangeException: If the command cannot be run, raise.
        """
        # Yeah, we need to specify the Confirm-option as a NVA,
        # due to the silly syntax.
        param = {'Name': gname,
                'Type': 'Distribution'}
        if ou:
            param['OrganizationalUnit'] = ou

        cmd = self._generate_exchange_command(
                'New-DistributionGroup',
                param,
                ('Confirm:$false',))

        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_address_policy(self, gname, enabled=False):
        """Enable or disable the AddressPolicy for the Distribution Group.

        @type gname: string
        @param gname: The groups name

        @type enabled: bool
        @param enabled: Enable or disable address policy

        @raise ExchangeException: If the command cannot be run, raise.
        """
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity': gname,
                'EmailAddressPolicyEnabled': enabled})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_primary_address(self, gname, address):
        """Set the primary-address of a Distribution Group.

        @type gname: string
        @param gname: The groups name

        @type address: string
        @param address: The primary address

        @raise ExchangeException: If the command cannot be run, raise.
        """
        #   TODO: We want to diable address policy while doing htis?
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity': gname,
                'PrimarySmtpAddress': address})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True
    
    def set_distgroup_visibility(self, gname, visible=True):
        """Set the visibility of a DistributionGroup in the address books.

        @type gname: string
        @param gname: The gropname associated with the mailbox

        @type enabled: bool
        @param enabled: To show or hide the mailbox. Default show.

        @raises ExchangeException: If the command fails to run.
        """
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
                {'Identity': gname,
                 'HiddenFromAddressListsEnabled': not visible})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_distgroup_addresses(self, gname, addresses):
        """Add email addresses from a distribution group

        @type gname: string
        @param gname: The group name to look up associated distgroup by

        @type addresses: list
        @param addresses: A list of addresses to add

        @raise ExchangeException: If the command failed to run for some reason
        """
        # TODO: Make me handle single addresses too!
        addrs = {'add': addresses}
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity': gname,
                'EmailAddresses': addrs})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_distgroup_member(self, gname, member):
        """Add member(s) to a distgroup.

        @type gname: string
        @param gname: The groups name
        
        @type member: string or list
        @param member: The members name, or a list of meber names

        @raise ExchangeException: If it fails to run
        """
    ##TODO: Add DomainController arg.
    #    if isinstance(member, list):
    #        # TODO: Should 300 be configurable?
    #        # We need to split the member list into pieces, or else stuff
    #        # crashes.
    #        ntp = 300
    #        slots = range(0, len(member), ntp)
    #        slots.append((len(member) - slots[-1]) + slots[-1])
    #        del slots[0]
    #        for x in slots:
    #            start = (x - (x % ntp)) if x % 2 else x - ntp
    #            end = x
    #            s_member = r'@(\"%s\")' % r'\", \"'.join(member[start:end])
    #            cmd = self._generate_exchange_command(
    #                    '%s | ForEach-Object { Add-DistributionGroupMember -Member $_ -Identity %s -BypassSecurityGroupManagerCheck }' % (s_member, gname))
# TO#DO: Create a new event_log_event for users that fail this!
    #                    #'%s | Add-DistributionGroupMember' % s_member,
    #                    #{'Identity': gname},
    #                    #('BypassSecurityGroupManagerCheck',))
    #            self.logger.info(cmd )
    #        #s_member = '@("%s")' % '", "'.join(member)
    #        #cmd = self._generate_exchange_command(
    #        #        '%s | Add-DistributionGroupMember' % s_member,
    #        #        {'Identity': gname},
    #        #        ('BypassSecurityGroupManagerCheck',))
    #    else:
        cmd = self._generate_exchange_command(
                'Add-DistributionGroupMember',
                {'Identity': gname,
                 'Member': member},
                ('BypassSecurityGroupManagerCheck',))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_distgroup_member(self, gname, member):
        """Remove a member from a distributiongroup

        @type gname: string
        @param gname: The groups name

        @type member: string
        @param member: The members username

        @raises ExchangeException: If it fails
        """
        #TODO: Add DomainController arg.
        cmd = self._generate_exchange_command(
                'Remove-DistributionGroupMember',
                {'Identity': gname,
                 'Member': member},
                ('BypassSecurityGroupManagerCheck',
                 'Confirm:$false'))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_distgroup_addresses(self, gname, addresses):
        """Remove email addresses from a distgroup

        @type gname: string
        @param gname: The group name to look up associated distgroup by

        @type addresses: list
        @param addresses: A list of addresses to remove

        @raise ExchangeException: If the command failed to run for some reason
        """
        # TODO: Make me handle single addresses too!
        addrs = {'remove': addresses}
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity': gname,
                'EmailAddresses': addrs})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_member_restrictions(self, gname, join='Closed',
                                                       part='Closed'):
        # TODO: fix docstring
        """Set the member restrictions on a Distribution Group.
        Default is all-false. False results in 'Closed'-state, True results
        in 'Open'-state.

        @type gname: string
        @param gname: The groups name

        @type join: str
        @param join: Enable, disable or restrict MemberJoinRestriction
        
        @type part: str
        @param part: Enable, disable or restrict MemberPartRestriction

        @raise ExchangeException: If the command cannot be run, raise.
        """
        params = {'Identity': gname}
        if join:
            params['MemberJoinRestriction'] = join
        if part:
            params['MemberDepartRestriction'] = part
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup', params)
        
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_moderation(self, gname, enabled=True):
        """Enable/disable moderation of group

        @type gname: string
        @param gname: The groups name

        @type enabled: bool
        @param enabled: Enable or disable moderation

        @raise ExchangeException: If the command cannot be run, raise.
        """
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity':  gname,
                'ModerationEnabled': enabled})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def set_distgroup_manager(self, gname, addr):
        """Set the manager of a distribution group.

        @type gname: string
        @param gname: The groups name

        @type addr: str
        @param uname: The e-mail address which manages this group

        @raise ExchangeException: If the command cannot be run, raise.
        """
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity':  gname,
                'ManagedBy': addr})
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True
    
    def set_distgroup_moderator(self, gname, addr):
        """Set the moderators of a distribution group.

        @type gname: string
        @param gname: The groups name

        @type addr: list
        @param uname: The e-mail addresses which moderates this group

        @raise ExchangeException: If the command cannot be run, raise.
        """
        # TODO: Make ModeratedBy a kwarg that accepts a list
        addr_str = ', '.join(addr)
        cmd = self._generate_exchange_command(
                'Set-DistributionGroup',
               {'Identity':  gname},
                ('ModeratedBy ' + addr_str,))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

#    def set_distgroup_mailtip(self, gname, mailtip):
#        """Set the MailTip (description) on a Distribution Group
#
#        @type gname: string
#        @param gname: The groups name
#
#        @type mailtip: string
#        @param mailtip: The groups description
#
#        @raise ExchangeException: If the command cannot be run, raise.
#        """
#        cmd = self._generate_exchange_command(
#                'Set-DistributionGroup',
#                {'Identity': gname,
#                 'MailTip': mailtip})
#        out = self.run(cmd)
#        if out.has_key('stderr'):
#            raise ExchangeException(out['stderr'])
#        else:
#            return True

    def remove_distgroup(self, gname):
        """Remove a distribution group.

        @type gname: string
        @param gname: The groups name

        @raise ExchangeException: If the command cannot be run, raise.
        """
        cmd = self._generate_exchange_command(
                'Remove-DistributionGroup',
               {'Identity': gname},
               ('Confirm:$false',))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True


    ######
    # Security Group-specific operations
    ######

    def new_secgroup(self, gname, ou=None):
        """Create a new securitygroup.

        @type gname: string
        @param gname: The groups name
        
        @type ou: string
        @param ou: The container the securitygroup should be organized in

        @raises ExchangeException: Raised if the command fails to run
        """
        param = {'Name':  gname,
                 'GroupCategory': 'Security',
                 'GroupScope': 'DomainLocal'}
        if ou:
            param['Path'] = ou
        cmd = self._generate_exchange_command(
                'New-ADGroup',
                param,
                ('Credential $cred',))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_secgroup(self, gname):
        """Remove a securitygroup.

        @type gname: string
        @param gname: The groups name

        @raises ExchangeException: Raised if the command fails to run
        """
        cmd = self._generate_exchange_command(
                'Remove-ADGroup',
                {'Identity':  gname},
                ('Confirm:$false', 'Credential $cred'))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def add_secgroup_member(self, gname, member):
        """Add a member from the master domain to a securitygroup.

        @type gname: string
        @param gname: The groups name

        @type member: string or list
        @param meber: The username of the member to add, or a list of em'

        @raises ExchangeException: Raised if the command fails to run
        """
        #TODO: Add DomainController arg.
        if isinstance(member, list):
            s_member = '@("%s")' % '", "'.join(member)
            cmd = self._generate_exchange_command(
                        '$m = %s | Get-ADUser' % s_member,
                        {'Server': self.ad_domain},
                        ('Credential $ad_cred',))
        else:
            cmd = self._generate_exchange_command(
                    '$m = Get-ADUser',
                    {'Identity': member,
                     'Server': self.ad_domain},
                     ('Credential $ad_cred',))
        cmd += '; ' +  self._generate_exchange_command(
                'Add-ADGroupMember',
                {'Identity':  gname},
                 ('Members $m', 'Credential $cred'))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    def remove_secgroup_member(self, gname, member):
        """Remove a member from the master domain to a securitygroup.

        @type gname: string
        @param gname: The groups name

        @type member: string
        @param meber: The username of the member to remove

        @raises ExchangeException: Raised if the command fails to run
        """

        #TODO: Add DomainController arg.
        # TODO: Make this support multiple users at a time!
        cmd = self._generate_exchange_command(
                '$m = Get-ADUser',
                {'Identity': member,
                 'Server': self.ad_domain},
                ('Credential $ad_cred',))
        cmd += '; ' +  self._generate_exchange_command(
                'Remove-ADGroupMember',
                {'Identity': gname},
                ('Members $m', 'Confirm:$false', 'Credential $cred'))
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return True

    ######
    # Get-operations used for checking state in Exchange
    ######


    def get_mailbox_info(self):
        """Get information about the mailboxes in Exchange

        @raises ExchangeException: Raised if the command fails to run
        """
        # TODO: Filter by '-Filter {IsLinked -eq "True"}' on get-mailbox.
        cmd = self._generate_exchange_command(
                'Get-Mailbox bore | select Identity, EmailAddresses, DisplayName, HiddenFromAddressListsEnabled, ProhibitSendReceiveQuota, IssueWarningQuota, FirstName, LastName, EmailAddressPolicyEnabled, IsLinked')
        out = self.run(cmd)
        if out.has_key('stderr'):
            raise ExchangeException(out['stderr'])
        else:
            return out