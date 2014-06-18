#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2011-2012 University of Oslo, Norway
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
"""Module for communication and interaction with Active Directory.

The module is working as a layer between the AD service and the AD
synchronisations in Cerebrum. The main class, L{ADclient}, is an abstraction
level between direct WinRM communication and the AD sync itself, trying to
handle the powershell specific behaviour, and giving the sync an easier API to
work with.

TODO: The API should have been cleaned up a bit. Maybe it should be called
ADPowershellClient, and the method names should have had the same name system.

For now, we are using the WinRM service from Microsoft, which makes us able to
send commands to be executed at a given Windows host. We send various
powershell commands from the ActiveDirectory powershell module, which are
talking with the domain controllers through Active Directory Web Service:

  Cerebrum -> Windows Member server (WinRM) -> AD domain controller (ADWS)
                 (powershell commands)

"""

import time
import re
import base64

import cerebrum_path
import cereconf
from Cerebrum.Utils import read_password
from Cerebrum.Utils import Factory

try:
    import json
except ImportError:
    # Until python 2.6, we have our local, partly tweaked json module for python
    # 2.5. At python 2.6, you _should_ use the proper json module.
    from Cerebrum.extlib import json

from Cerebrum.modules.ad2.winrm import PowershellClient, iter2stream
from Cerebrum.modules.ad2.winrm import PowershellException, ExitCodeException

class ObjectAlreadyExistsException(PowershellException):
    """Exception for telling that an object already exists in AD."""
    pass

class NoAccessException(PowershellException):
    """Exception for telling that Cerebrum were not allowed to execute an
    operation due to limited access rights in Active Directory.

    """
    pass

class SizeLimitException(PowershellException):
    """Exception for when too many rows are tried to be returned from AD.

    This is triggered by AD when you try to get lists of more than 1500? 2000?
    objects, for example all objects in an OU or all members of a large group.
    The limit is a standard value in AD, but it could be set to other values.

    """
    pass

class OUUnknownException(PowershellException):
    """Exception for when an OU was not found.

    This could happen in various scenarios, e.g. when trying to create an object
    in a given, nonexisting OU, or trying to get all objects from a given OU.

    """
    pass

class SetAttributeException(PowershellException):
    """Exception for when updating attributes failed.

    Failing to add an attribute for an object could come of many reasons.

    One example could be that the given attribute element is required to refer
    to another AD object, which doesn't exist in the given location. This is for
    instance a common error for the Member attribute.

    """
    pass

class CommandTooLongException(Exception):
    """If the given command is too long to be run through WinRM.

    The commands could be limited either by Powershell's command line, cmd's
    command line, or even WinRM. The maximum length for cmd.exe is 8191 for
    modern Windows versions (http://support.microsoft.com/kb/830473).

    This is not always enforced in our code, as we are not always sure when it
    happens, and what situations in the Windows environment that could cause it.
    It is, for now, only enforced in the more common situations where we could
    handle it. In the future, we might want to move this into `winrm.py` as one
    of the regular ExitCodeExceptions.

    """
    pass

class ADclient(PowershellClient):
    """Client that sends commands to AD for the AD-sync.

    Contains various methods for getting and setting data from/to AD for the
    ADsync. This class should take care of how the powershell commands should
    look like and how the server output is formatted.

    Note that the commands here should do exactly what they're told and nothing
    more. The ADSync should take care of any weird behaviour. This is to let the
    ADSync's subclass change its behaviour without having to subclass this class
    as well.

    """

    # Unfortunately, there are some attributes that are readable as one name,
    # and writable by another. This is the mapping of the names, so that the
    # names are automatically swapped out when needed. The keys are the readable
    # names, while the values are the strings that should be used when updating
    # the attribute in AD:
    attribute_write_map = {'Surname': 'Sn',}

    # The main objectClass that we are targeting in AD. This is used if nothing
    # else is specified when running a command:
    object_class = 'user'

    def __init__(self, auth_user, domain_admin, dryrun, domain, *args,
                 **kwargs):
        """Set up the WinRM client to be used with running AD commands.

        @type auth_user: string
        @param auth_user: The username of the account we use to connect to the
            server.

        @type domain_admin: string
        @param domain_admin:
            The username of the account we use to connect to the AD domain we
            are going to synchronize with. Could also contain the domain that
            the user belongs to, in the format of 'user@domain' or
            'domain/user'.

        @type domain: string
        @param domain: 
            The AD domain that we should work against. It is in this client only
            used to set the domain for the domain admin, if not set in the
            'domain_admin' parameter.

        @type dryrun: bool
        @param dryrun: If True, commands that make changes to AD will not get
            executed.

        """
        super(ADclient, self).__init__(*args, **kwargs)
        self.add_credentials(username=auth_user,
                password=unicode(read_password(auth_user, self.host), 'utf-8'))

        # Note that we save the user's password by domain and not the host. It
        # _could_ be the wrong way to do it. TBD: Maybe both host and domain?
        if domain_admin:
            ad_user, user_domain = self._split_domain_username(domain_admin)
            if not user_domain:
                user_domain = domain or ''
            self.ad_account_username = '%s@%s' % (ad_user, user_domain)
            self.logger.debug2("Using domain account: %s",
                               self.ad_account_username)
            self.ad_account_password = unicode(read_password(ad_user, user_domain),
                                               'utf-8')
        else:
            self.logger.debug2("Not using a domain account")
        self.dryrun = dryrun
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.connect()

    def _split_domain_username(self, name):
        """Separate the domain and username from a full domain username.

        Usernames could be in various formats:
         - username@domain
         - domain\username
         - domain/username

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
        return name, None

    def _generate_ad_command(self, command, kwargs={}, novalueargs=()):
        """Generate a command for AD queries out of the given input.

        Most of the AD commands have the same format, and contains some of the
        same standard parameters. This is to make it more convenient to generate
        commands with the same, default parameters.

        Note that some parameters gets added, like Server, which gets filled
        with the same DC for all AD commands.

        @type command: string
        @param command: The name of the AD-command that should be executed.
            Example: Get-ADUser. Case is not important for powershell, but you
            should format it correctly, to make it easier for this method to
            behave differently for different commands later.

        @type kwargs: dict
        @param kwargs:
            The parameters to feed the command with. Note that the values gets
            sent through L{escape_to_string}, so you shouldn't do this yourself,
            but just sending them in raw format.
            
            Example:

                {'Filter': '*',
                 'SearchBase': 'OU=Users,DC=kaos', 
                 'Properties': ('Name', 'DN', 'SAMAccountName')}

            which becomes:

                -Filter '*' \
                -SearchBase 'OU=Users,DC=kaos' \
                -Properties 'Name','DN','SAMAccountName'

        @type novalueargs: string or list thereof
        @param novalueargs:
            Parameters which does not require any value. E.g. -Reset for
            Set-ADAccountPassword. No escape is performed on these, so could
            also be used for special parameters, like:

                -Confirm $false

            Just remember that the initial dash gets added, so don't add the
            first dash yourself. Example:

                ['Reset', 'Confirm $false']

            becomes the string:

                -Reset -Confirm $false

        @rtype: string
        @return:
            A correctly formatted command as a string. Example:

                Get-ADUser -Credential $cred -Filter '*'

        """
        dc = self.get_chosen_domaincontroller()
        if dc:
            kwargs['Server'] = dc
        if isinstance(novalueargs, basestring):
            novalueargs = (novalueargs,)
        # The parameter "-Credential $cred" is special, as "$cred" should not be
        # wrapped inside a string. Everything else should, though.
        return '%s -Credential $cred %s %s' % (command,
                          ' '.join('-%s %s' % (k, self.escape_to_string(v))
                                   for k, v in kwargs.iteritems()),
                          ' '.join('-%s' % v for v in novalueargs))

    def get_data(self, commandid, signal=True, timeout_retries=50):
        """Get the output for a given command.

        The method is overridden to parse raised exceptions and raise a more
        proper exception for AD commands, e.g. for access limit and
        object-not-found errors. When a command fails, the superclass raises an
        ExitCodeException, where powershell normally gives you an explanation on
        the error in 'stderr'. Example:

            Add-ADGroupMember : Cannot find an object with identity: 'testuser' under: 'DC=
            kaos,DC=local'.
            At line:5 char:19
            +  Add-ADGroupMember <<<<  -Credential $cred -Identity 'CN=testgroup,OU=gro
            ups,OU=cerebrum,DC=kaos,DC=local' -Confirm:$false -Member @('testuser','mrtest
            ','test2')
                + CategoryInfo          : ObjectNotFound: (testuser:ADPrincipal) [Add-ADGr 
               oupMember], ADIdentityNotFoundException
                + FullyQualifiedErrorId : SetADGroupMember.ValidateMembersParameter,Micros 
               oft.ActiveDirectory.Management.Commands.AddADGroupMember

        The first line in the error gives the information that this method
        checks, to find out what kind of exception to raise.

        Note that this command is executed even when in dryrun, since you would
        like to retrieve data from AD, just not write back changes. Each method
        that does something with AD must therefore not send data when in dryrun.

        """
        try:
            return super(ADclient, self).get_data(commandid, signal,
                                                  timeout_retries)
        except ExitCodeException, e:
            code, stderr, output = e.exitcode, e.stderr, e.output
            self.logger.debug3("ExitCodeException: %s: %s (%s)" % (code, stderr,
                                                                   output))
            if not stderr:
                # TBD: raise powershell-exception or exitcodeexception? Is it
                # possible to separate those exceptions from each other?
                raise
            if 'Insufficient access rights to perform the operation' in stderr:
                raise NoAccessException(code, stderr, output)
            if 'Access is denied' in stderr:
                raise NoAccessException(code, stderr, output)
            if ': The size limit for this request was exceeded' in stderr:
                raise SizeLimitException(code, stderr, output)
            if ': Directory object not found' in stderr:
                # TODO: This might not always mean that the OU is missing, it
                # could also sometimes mean that the object itself is missing.
                # Need to find a way to differentiate this?
                raise OUUnknownException(code, stderr, output)
            if 'ADIdentityAlreadyExistsException' in stderr:
                raise ObjectAlreadyExistsException(code, stderr, output)
            if ('An attempt was made to add an object to the directory with\n '
                    'a name\n that is already in use' in e.stderr):
                raise ObjectAlreadyExistsException(code, stderr, output)
            if re.search(': The specified \w+ already exists', stderr):
                raise ObjectAlreadyExistsException(code, stderr, output)
            if 'Set-ADObject : The specified account does not exist' in stderr:
                raise SetAttributeException(code, stderr, output)
            if 'The command line is too long' in stderr:
                raise CommandTooLongException(code, stderr, output)
            if re.search("Move-ADObject : .+object's paren.+is either "
                         "uninstantiated or deleted",
                         stderr, re.DOTALL):
                raise OUUnknownException(code, stderr, output)
            raise PowershellException(code, stderr, output)

    # Commands to execute before every given powershell command. This is to set
    # up the environment properly, for our use. Note that it requires some input
    # arguments to be valid powershell code.
    _pre_execution_code = u"""
        $pass = ConvertTo-SecureString -Force -AsPlainText %(ad_pasw)s;
        $cred = New-Object System.Management.Automation.PSCredential(%(ad_user)s, $pass);
        Import-Module ActiveDirectory;
        """

    def execute(self, *args, **kwargs):
        """Override the execute command with all the startup commands for AD.

        """
        setup = self._pre_execution_code % {
                        'ad_user': self.escape_to_string(self.ad_account_username),
                        'ad_pasw': self.escape_to_string(self.ad_account_password)}
        #for a in args:
        #    print a
        return super(ADclient, self).execute(setup, *args, **kwargs)

    # Standard lines in powershell that we can't get rid of by powershell code.
    # Piping doesn't seem to work, at least in powershell 2.0.
    ignore_stdout = ("WARNING: Error initializing default drive: 'Unable to "
                     "contact the server. This \nmay be because this server "
                     "does not exist, it is currently down, or it does not\n "
                     "have the Active Directory Web Services running.'.\n")

    def get_output(self, commandid=None, signal=True, timeout_retries=50):
        """Override the output getter to remove unwanted output.

        In powershell 2.0, you cannot avoid getting a warning from when
        importing the ActiveDirectory module, as our authentication user does
        not have AD privileges, only our domain account, which is initiated
        after importing the module. The error message is:

            WARNING: Error initializing default drive: 'Unable to contact the
            server. This may be because this server does not exist, it is
            currently down, or it does not have the Active Directory Web
            Services running.'.

        Such a warning gets removed before the remaining output is returned.

        """
        first_round = True
        for code, out in super(PowershellClient, self).get_output(commandid,
                                                       signal, timeout_retries):
            if first_round:
                out['stdout'] = out.get('stdout', 
                                        '').replace(self.ignore_stdout, '')
                first_round = False
            yield code, out

    def start_list_objects(self, ou, attributes, object_class):
        """Start to search for objects in AD, but do not retrieve the data yet.

        The server is asked to generate a list of the objects, and returns an ID
        which we could later use to retrieve the generated list from. It is
        designed like this because the list could take some time to produce.

        @type ou: string
        @param ou: The OU in AD to search in. All objects from given OU and its
            child OUs are returned.

        @type attributes: dict, list or tuple
        @param attributes:
            A list of all attributes that should be returned for all the objects
            that were found. If a dict is given, its keys are used as the
            attribute list.

        @type object_class: string
        @param object_class:
            Specifies what objectClass in AD the returned object must be.

        @rtype: string
        @return: A string which should be used as a reference to later retrieve
            the result from AD. This is since AD could be using some time to
            go through all the objects, and you could then be able to do
            something more useful while waiting.

        """
        self.logger.debug("Start fetching %s objects from AD, OU: %s",
                          object_class, ou)
        # TBD: Should we check if the given attributes are valid?
        if isinstance(attributes, dict):
            attributes = attributes.keys()
        params = {'SearchBase': ou,
                  'Properties': [self.attribute_write_map.get(a, a)
                                 for a in attributes],
                  }
        cmd = 'Get-ADObject'
        filter = "Filter {objectClass -eq '%s'}" % object_class
        # User objects requires special care, as Get-ADObject will not return
        # the attribute Enabled, and also, the filtering by objectclass='user'
        # also includes computer objects for some reason. See
        # http://technet.microsoft.com/en-us/library/ee198834.aspx for some
        # information about this.
        #
        # Note that this could also affect other ObjectClasses...
        if object_class == 'user':
            cmd = 'Get-ADUser'
        # TODO: It looks like we should use ForEach-Object instead, to avoid too
        # much memory usage, which creates problems for WinRM.
        command = ("if ($str = %s | ConvertTo-Json) { $str -replace '$',';' }"
                   % self._generate_ad_command(cmd, params, filter))
        # TODO: Should return a callable instead of having another method for
        # getting the data. Could be using a decorator instead.
        return self.execute(command)

    def get_list_objects(self, commandid, other=None):
        """Get list of AD objects, as requested by L{start_list_objects}.

        The returned data is parsed into native python elements, as much as is
        possible with the returned data format. Uses ConvertTo-Json for this.

        The server should have been generating the list of objects in the
        background, and this method sends a request to get the output.

        Note that some key names are translated, as they are are different
        between reading and writing. This is done here, so those who use this
        client should not need to know of this, but only use the standard key.
        See L{self.attribute_write_map} for the mapping.

        @type commandid: string
        @param commandid: A CommandId from a previous call to
            L{start_list_objects}, which is the server reference to the output.

        @type other: dict
        @param other: A dict to put output from the server that is not a part of
            the object list. E.g. for different warnings. If not set, all other
            output will be logged as warnings.

        @rtype: iterator
        @return: An iterator over each object that is returned from AD. Each
            object is a dict with the different attributes.

            TODO: How about AccountControl?

        """
        attr_map_reverse = dict((value, key) for key, value in
                                self.attribute_write_map.iteritems())
        other_set = True
        if other is None:
            other = dict()
            other_set = False
        try:
            for obj in self.get_output_json(commandid, other):
                # Some attribute keys are unfortunately not the same when
                # reading and writing, so we need to translate those here
                yield dict((attr_map_reverse.get(key, key), value)
                           for key, value in obj.iteritems())
        finally:
            # Check for other ouput:
            if not other_set:
                for type in other:
                    for o in other[type]:
                        if o:
                            self.logger.warn("Unknown output %s: %s" % (type, o))

    def disable_object(self, dn):
        """Set an object as not enabled.

        Note that this only affects accounts, it doesn't look like you can
        disable other object types.

        """
        self.logger.info('Disabling object: %s', (dn,))
        if self.dryrun:
            return True
        out = self.run(self._generate_ad_command('Disable-ADAccount',
                                                 {'Identity': dn}))
        return not out.get('stderr')

    def delete_object(self, dn):
        """Delete an object from AD.

        This removes the data about an object from AD. It is possible to restore
        the object if AD is in level 2008 R2 level.

        TODO: the command prompts for confirmation, which we can't give. How to
        setup the sync to not ask us about this?

        """
        self.logger.info('Deleting object: %s', (dn,))
        if self.dryrun:
            return True
        out = self.run(self._generate_ad_command('Remove-ADObject',
                                                 {'Identity': dn},
                                                 'Confirm:$false'))
        return not out.get('stderr')

    def get_object(self, ad_id, object_class=None, attributes=None):
        """Send a command for receiving information about an object from AD.

        Dryrun does not affect this command, since it works readonly.

        @type ad_id: string
        @param ad_id: The identification of the object. Could be Distinguished Name
            (DN), Fully Qualified Domain Name (FQDN), username, UID, GID, SID or
            anything that AD accepts as identification.

        @type object_class: str
        @param object_class:
            Specify what objectClass the returned object should be of, e.g.
            'user', 'group', or something else. This affects what default
            attributes are returned and how the given L{ad_id} is used as
            identifier in AD - for users and security groups you could for
            instance use SAMAccountName, but OUs and distribution groups would
            either require the full DN or its GUID.

        @type attributes: dict
        @param attributes: What attributes that should be returned for the
            object. Note that standard attributes for the object type is always
            returned.

        @rtype: dict
        @return: The object's attributes.

        @raise PowershellException: If the powershell command failed somehow,
            e.g. if the object was not found or if the script didn't have read
            access for the object.

        """
        out = self.run('''if ($str = %s | ConvertTo-Json) {
            $str -replace '$', ';'
            }''' % self._generate_ad_command('Get-ADObject',
                                             {'Identity': ad_id}))
        ret = self.get_output_json(out, dict())
        if not ret:
            raise Exception("Bad output - was object '%s' not found?" % ad_id)
        return ret

    def find_object(self, object_class=None, name=None, ou=None,
                    attributes=None, ad_object_class=None):
        """Search for a given object by the given input criterias.

        @type object_class: str
        @param object_class:
            What objectClass in AD the object must be of to be returned.

        @type name: str
        @param name:
            If specified, the object is searched for by the given Name
            attribute.

        @type ou: str
        @param ou:
            If specified, the search is limited to the given AD OU.

        @type attributes: dict
        @param attributes:
            If specified, the given attributes are added as criterias. Could for
            instance be used to find the object by its given SAMAccountName.

        @type ad_object_class: str
        @param ad_object_class:
            If specified, only objects of the given objectClass are returned.

        @rtype: list of dicts
        @return:
            The objects from AD that matched the criterias are returned,
            together with some of their AD attributes.

        """
        parameters = {}
        if ou:
            parameters['SearchBase'] = ou
        filters = {}
        if attributes:
            filters.update(attributes)
        if name:
            filters['Name'] = name
        if ad_object_class:
            filters['ObjectClass'] = ad_object_class
        extra = {}
        if filters:
            extra = 'Filter {%s}' % ' -and '.join("%s -eq '%s'" % (k, v)
                                                  for k, v in
                                                  filters.iteritems())
        cmd = ("if ($str = %s | ConvertTo-Json) { $str -replace '$', ';' }" %
               self._generate_ad_command('Get-ADObject', parameters, extra))
        out = self.run(cmd)
        res_list = []
        json_output = self.get_output_json(out,dict())
        if json_output:
            if isinstance(json_output, dict):
                # In case there is found only one object, get_output_json will
                # return a single dictionary. This method however needs to 
                # return a list, so we have to make a list of one element.
                res_list.append(json_output)
            else:
                # With several objects found, get_output_json returns a list of
                # dicts. No additional transformation needed.
                res_list = json_output
        return res_list

    def create_object(self, name, path, object_class, attributes=None,
                      parameters=None):
        """Send a command for creating a new object in AD.

        Note that accounts are set as disabled by default, and cannot be enabled
        unless a valid password is set for them (or PasswordNotRequired is set).

        TODO: more info

        @type name: string
        @param name: The name of the object to create.

        @type path: string
        @param path: The OU to create the object in.

        @type object_class: string
        @param object_class:
            Sets the class of the object in AD, e.g. user or group. The class
            must exist in the AD schema.

        @type attributes: dict
        @param attributes: All attributes that should be set for the object at
            once.

        @type parameters: dict
        @param parameters: Other options to the creation process. The keys are
            the name of the parameter in the powershell command. For instance
            will an element named 'GroupScope' with the value 'Global' become::

                -GroupScope 'Global'

        @rtype: dict
        @return: Basic information about the newly created AD-object, in the
            same form as the objects from L{get_list_objects}.

        @raise ObjectAlreadyExistsException: If the object already exists in the
            domain, this exception is raised.

        @raise PowershellException: If the powershell command failed somehow,
            e.g. if the object already existed, or if the script didn't have
            access to create the object. The output is put in the exception, you
            will for example get the information about the object if the object
            already exists.

        """
        self.logger.info("Creating %s in AD: %s (%s)", object_class, name, path)
        if not parameters:
            parameters = dict()

        # Add some extra parameters for the various types of objects:
        # TODO: this might be moved into subclasses of ADclient, one per object
        # type? Would probably make easier code... Or we could just depend on
        # the configuration for this behaviour, at least for the attributes.
        if (str(object_class).lower() == 'account' or 
            str(object_class).lower() == 'group'):
            # SAMAccountName is mandatory for some object types:
            # TODO: check if this is not necessary any more...
            if 'SamAccountName' not in attributes:
                attributes['SamAccountName'] = name

        # Add the attributes, but mapped to correctly name used in AD:
        if attributes:
            attributes = dict((self.attribute_write_map.get(name, name), value)
                              for name, value in attributes.iteritems()
                              if value is not None)
            parameters['OtherAttributes'] = attributes

        parameters['Name'] = name
        parameters['Path'] = path
        parameters['Type'] = object_class
        cmd = self._generate_ad_command('New-ADObject', parameters, 'PassThru')
        cmd = '''if ($str = %s | ConvertTo-Json) {
            $str -replace '$',';'
            }''' % cmd
        if self.dryrun:
            # Some of the variables are mandatory to be returned, so we have to
            # just put something in them, for the sake of testing:
            ret = attributes.copy()
            ret['Name'] = ret['SamAccountName'] = name
            ret['DistinguishedName'] = 'CN=%s,%s' % (name, path)
            ret['SID'] = None
            return ret
        ret = self.get_output_json(self.run(cmd), dict())
        if not ret:
            e_msg = "Creating object %s not confirmed by AD" % name
            self.logger.warn(e_msg)
            raise Exception(e_msg)
        self.logger.debug("New AD-object: %s" % ret)
        return ret

    def move_object(self, ad_id, ou):
        """Send a command for moving an object to the given OU.

        Both the object and the OU must exists on beforehand.

        @type ad_id: string
        @param ad_id: Any Id that identifies the object in AD. Could be
            SamAccountName, DN, SID, UID or anything that is accepted by AD.

        @type ou: string
        @param ou: The OU that the object should be moved into. Must be on the
            DistinguishedName form for AD to understand it.

        @raise PowershellException: If the powershell command failed somehow,
            e.g. if the OU does not exists or the system account were not
            allowed to move the object.

        """
        self.logger.info("Moving %s to OU: %s", ad_id, ou)
        cmd = self._generate_ad_command('Move-ADObject', {'Identity': ad_id,
                                                          'TargetPath': ou})
        if self.dryrun:
            return True
        out = self.run(cmd)
        return not out.get('stderr')

    def _setadobject_command_wrapper(self, ad_id, action, attributes):
        """Run Set-ADObject on a given object and update its attributes.

        If the list of attributes to update makes the query too long, it is
        split up and run in several commands.

        This method makes sure that if some of the attributes or attributes'
        elements are not accepted by AD, all of the elements are tried to be set
        again. This is making this method even more complicated, and could slow
        the sync down when this situation occurs, but at least we make sure that
        one single, bogus element will not be able to block the update of the
        whole AD object.

        :type ad_id: str
        :param ad_id: The ID of the object whose attributes will be updated.
        
        :type action: str
        :param action:
            What to perform with the object' attributes. Could for instance be
            `Clear`, `Add` or `Remove`.

        :type attributes: list
        :param attributes:
            List of attributes to update. The keys are the name of the
            attribute, while the value

        :rtype: bool
        :return:
            True if the *all* the given attribute elements  were updated
            properly.

        """
        if action.lower() not in ('add', 'clear', 'remove', 'replace'):
            raise Exception("Invalid action for updating %s: %s" % (ad_id,
                            action))
        def run_setadobject(attrs):
            """Helper method for running the Set-ADObject command"""
            cmd = self._generate_ad_command('Set-ADObject',
                                            {'Identity': ad_id,
                                             action: attrs})
            # PowerShell commands are executed through Windows command line. The
            # maximum length of the command there is 8191 for modern Windows
            # versions (http://support.microsoft.com/kb/830473). Due to
            # additional parameters that other methods add to the command, the
            # part of it which is generated here has to be even shorter. The
            # limit at 8000 bytes seems to be working.
            # TODO: This should be checked for in winrm.py.
            if len(cmd) > 8000:
                raise CommandTooLongException('Too long')
            self.logger.debug3("Command: %s", cmd)
            if self.dryrun:
                return True
            self.run(cmd)

        def wrap_setadobject(attrs):
            """Run Set-ADObject aggresively, retrying if it fails.

            The retry is attempted by running separate commands per element per
            attribute. This could be a slow process if many attributes have
            failed, but at least we make sure that the valid attribute elements
            really gets set.

            :raise CommandTooLongException:
                If the given attributes makes the command too long for WinRM to
                execute.

            :rtype: bool
            :return: If *all* the attributes were updated in AD.

            """
            try:
                return run_setadobject(attrs)
            except SetAttributeException:
                # Not giving up yet! We retry by adding each attribute's
                # elements separately.
                self.logger.debug2("Failed updating all attributes, splitting")
                success = True
                for atrname, values in attrs.iteritems():
                    for element in values:
                        try:
                            run_setadobject({atrname: element})
                        except SetAttributeException, e:
                            success = False
                            self.logger.warn(
                                "Failed updating %s for %s with element: '%s'"
                                " error: %s", atrname, ad_id, element, e)
                return success

        try:
            return wrap_setadobject(attributes)
        except CommandTooLongException:
            # Strictly speaking, here we have to check if we have to perform
            # 'Clear' operation, before we go into the loop below to update 
            # attributes. However, the only realistic case here is that
            # the length is exceeded because we have to update too many
            # elements in the attributes, not to clear them.
            self.logger.debug3("Command too long, splitting")
            success = True
            for k, v in attributes.iteritems():
                # Elements of the list are approximately the same length
                # 5000 is empirically chosen to have some length reserve
                # TODO: 5000 is not always enough, we need to be more generic
                splits = sum(len(elem) for elem in v) / 5000 + 1
                elems_in_split = len(v) / splits + 1 
                newattrs = {}
                for i in range(0, splits):
                    newattrs[k] = v[i * elems_in_split:(i+1) * elems_in_split]
                    if not wrap_setadobject(newattrs):
                        success = False
                    self.logger.debug3("Attribute %s partially updated.", k)
                self.logger.debug3("Attribute %s fully updated", k)
            return success

    def update_attributes(self, ad_id, attributes, old_attributes=None):
        """Update an AD object with the given attributes.

        It takes time to update each attribute, so you should not update
        attributes that is already set correctly.

        There are different ways we could update an object's attributes. The
        Set-ADObject have the options:

          -Clear    Remove the whole attribute.
          -Replace  Replace a specific value - you need to specify the old
                    value.
          -Add      Add an extra value to the attribute.
          -Remove   Remove a given value from the attribute.

        Are there any easier way in AD to modify objects, I wonder?

        :type ad_id: str
        :param ad_id:
            The Id of the object to update. Normally the DistinguishedName. A
            SamAccountName is often not enough to find it.

        :type attributes: dict
        :param attributes:
            The attributes that should be updated in AD. The keys are the name
            of the attribute, while the value is a dict with different elements
            for what should be done with elements of the specific attribute,
            e.g. add, remove or fullupdate.

            If an attribute's value is None, it will instead be removed.

        :type old_attributes: dict
        :param old_attributes:
            The existing attribute set for the object in AD. This is needed to
            know how the attributes should be modified in AD, e.g. replaced or
            added.

        :rtype: bool
        :return:
            True if the object got *fully* updated in AD. False means that the
            object didn't get updated at all, or that only some of the
            attributes got updated.

        """
        self.logger.info(u'Updating attributes for %s: %s', ad_id,
                         ', '.join(attributes.keys()))
        success = True
        removes = dict()
        adds = dict()
        fullupdates = dict()
        # Sort the attributes in what to add, remove or fully update. Some
        # attributes are named differently when reading and writing in AD, so we
        # need to map them properly.
        for k, v in attributes.iteritems():
            if 'remove' in v:
                removes[self.attribute_write_map.get(k, k)] = v['remove']
            elif 'add' in v:
                adds[self.attribute_write_map.get(k, k)] = v['add']
            else:
                fullupdates[k] = v['fullupdate']

        if removes:
            if not self._setadobject_command_wrapper(ad_id, 'Remove', removes):
                return False
        if adds:
            if not self._setadobject_command_wrapper(ad_id, 'Add', adds):
                success = False
        if fullupdates:
            clears = set()
            updates = dict()
            for k, v in fullupdates.iteritems():
                # What attributes need to be cleared before adding the correct 
                # ones. No need to clear already empty attributes.
                if old_attributes.get(k):
                    clears.add(self.attribute_write_map.get(k, k))
                # Do not update attributes if they are "None" in Cerebrum.
                # It may lead to strange values in AD in the future.
                # Just leave them cleared.
                if v:
                    updates[self.attribute_write_map.get(k, k)] = v 
            # We could save runtime on combining Clear and Add in the same
            # commands, but at the cost of more complexity. This should normally
            # not happen, maybe except for the initial sync for an instance.
            if clears:
                self._setadobject_command_wrapper(ad_id, 'Clear', clears)
            if updates and not self._setadobject_command_wrapper(ad_id, 
                                                                'Add', updates):
                success = False
        return success

    def get_ad_attribute(self, adid, attributename):
        """Start generating a list of a given object's given AD attribute.

        The AD server is asked to generate a list of the attribute, which could
        be received and parsed by L{get_list_attribute}. The purpose of this
        separation is that the output could take some time to produce, so you
        could do something else while waiting.

        @type adid: str
        @param adid:
            The idenficator of the object in AD to get the attribute from.

        @type attributename: str
        @param attributename:
            The name of the attribute that we should get a list from. Must be a
            valid attribute name in AD, and should be multivalued to be of any
            use.

        @rtype: callable
        @return:
            A callable that should be called to retrieve the data from the
            attribute. When called, an iterator of each element in the attribute
            is returned.

        """
        self.logger.debug2("Get attribute %s from AD for %s" % (attributename,
                                                                adid))
        # No dryrun here, since it's read-only
        cmdid = self.execute('(%s).%s' % (
                    self._generate_ad_command('Get-ADObject',
                                              {'Identity': adid,
                                               'Properties': attributename}),
                    attributename))
        def getout(cmd):
            # TODO: By printing the attribute, it is split out on each line.
            # Note, however, that cmd breaks the lines at 80 or more characters,
            # so elements longer than that will be split in different elements,
            # which needs to be fixed!
            out = self.get_data(cmd).get('stdout')
            self.logger.debug3("Got output of length: %d" % len(out))
            for line in out.split('\n'):
                line = line.strip()
                if line:
                    yield line
        # TODO: Make this a decorator instead?
        return lambda: getout(cmdid)


    # TODO: All the old group-member functionality should be removed, as it is
    # now handled through the regular update of attributes!

    # The name of the attribute for where the members of the object are located.
    # For a regular Group, 'member' is default, while for e.g. NisNetGroups is
    # this 'memberNisNetGroup'.
    # TODO: This must be removed in the future, as this should rather be
    # configurable, as all other attributes! We must be able to sync members
    # independently of the attribute!
    attributename_members = 'member'

    def start_list_members(self, groupid):
        """Make AD start generating a list of a group's members.

        The server is asked to generate a list of the members, and returns an ID
        which we could later use to retrieve the generated list. It is designed
        like this because the list could take some time to produce, especially
        for larger groups.

        @type groupid: string
        @param groupid: The Id for the group in AD.

        @rtype: string
        @return: A string which should be used as a reference to later retrieve
            the results. This is since AD could be using some time to go through
            all the objects, and you could then be able to do something more
            useful while waiting.

        """
        # No dryrun here, since it's read-only
        return self.execute('''if ($str = %s | ConvertTo-Json) {
                $str -replace '$', ';'
            }''' % self._generate_ad_command('Get-ADGroupMember',
                                             {'Identity': groupid}))

    def get_list_members(self, commandid):
        """Get the list of group members, as requested by L{start_list_members}.

        The server should have been generating the list of objects in the
        background, and this method sends a request to get the output.

        @type commandid: string
        @param commandid: A CommandId from a previous call to
            L{start_list_members}, which is the server reference to the output.

        @rtype: iterator
        @return: An iterator over each member that is returned from AD. Each
            object is a dict with its basic attributes.

        @raise SizeLimitException: If the given group is too large (TODO: how
            many members are max? 2000?), this exception would be raised. AD
            does not allow listing out such large groups, and it is not
            recommended to change this limit either.

        """
        return self.get_output_json(commandid, dict())
        # TODO: check other output?

    def empty_group(self, groupid):
        """Remove all the members of a given group in AD.

        This could be used when the group has too many members to be able to
        retrieve them from AD. The group could be then be refilled.

        @type groupid: string
        @param groupid: The Id of the group in AD.

        """
        self.logger.debug("Removing all members of group: %s" % groupid)
        cmd = self._generate_ad_command('Set-ADObject',
                                        {'Identity': groupid,
                                         'Clear': self.attributename_members})
        if self.dryrun:
            return True
        output = self.run(cmd)
        return not output.get('stderr')

    def add_members(self, groupid, members, attribute_name=None):
        """Send command for adding given members to a given group in AD.

        Note that if one of the members already exists in the group, powershell
        will raise an exception and none of the members will be added.

        There is a limit in CMD, in which a command can only be up to a certain
        number of characters. This method solves this by splitting the member
        list over several commands, if the member list is large enough (more
        than 1000 members).

        @type groupid: string
        @param groupid:
            The Id for the group, e.g. DistinguishedName or SamAccountName.

        @type members: set of strings
        @param members:
            The set of members to add to the group, identified by their
            DistinguishedName. The members must not exist in the group, as that
            would make the powershell command fail. SAMAccountName or Name are
            not accepted by AD without workarounds.

        @type attribute_name: str
        @param attribute_name:
            The name of the member attribute to update in AD. Uses the default
            L{self.attributename_members} if not specified.

        @rtype: bool
        @return:
            Telling if the member add worked or failed.

        # TODO: add support for not having to check the member lists first?

        """
        if not attribute_name:
            attribute_name = self.attributename_members
        self.logger.debug("Adding %d members for object: %s" % (len(members),
                                                                groupid))
        # TODO: Testing new method: adding each member, one by one, to avoid
        # problems with single, bad behaving members preventing everyone else
        # from becoming members. Must be tested to see if it takes too much time
        # to do it this way.
        failed_members = []
        for member in members:
            self.logger.debug("Adding member: %s", member)
            cmd = self._generate_ad_command(
                    'Set-ADObject',
                    {'Identity': groupid,
                     'Add': {attribute_name: member}})
            if not self.dryrun:
                try:
                    self.run(cmd)
                except PowershellException, e:
                    self.logger.warn("Failed adding '%s' to group %s: %s",
                                     groupid, member, e)
                    failed_members.append(member)
        return not failed_members

    def remove_members(self, groupid, members, attribute_name=None):
        """Send command for removing given members from a given group in AD.

        Note that if one of the members does not exist in the group, the command
        will raise an exception.

        @type groupid: string
        @param groupid: The Id for the group, e.g. DistinguishedName or
            SamAccountName.

        @type members: set, list or tuple
        @param members: The list of members to remove from the group. All the
            given members must be members of the group, and they must be
            identified by their DistinguishedName.

        @type attribute_name: str
        @param attribute_name:
            The name of the member attribute to update in AD. Uses the default
            L{self.attributename_members} if not specified.
        
        # TODO: Add support for not getting exceptions if the members doesn't
        # exist.

        """
        if not attribute_name:
            attribute_name = self.attributename_members
        self.logger.debug("Removing %d members for group: %s" % (len(members),
                                                                 groupid))
        # Printing out the first 500 members, for debugging reasons:
        self.logger.debug2("Removing members for %s: %s...", groupid,
                           ', '.join(tuple(members)[:500]))
        # TODO: Should do the removal in the same way as self.add_member
        cmd = self._generate_ad_command(
                        'Set-ADObject',
                        {'Identity': groupid,
                         'Remove': {attribute_name: members}})
        if self.dryrun:
            return True
        output = self.run(cmd)
        return not output.get('stderr')

    def enable_object(self, ad_id):
        """Enable a given object in AD. The object must exist.

        This only works for Accounts, as that's the only available command for
        enabling objects in AD.

        @type ad_id: string
        @param ad_id: The Id for the object. Normally the DistinguishedName.

        """
        self.logger.info('Enabling object: %s', ad_id)
        cmd = self._generate_ad_command('Enable-ADAccount', {'Identity': ad_id})
        if self.dryrun:
            return True
        out = self.run(cmd)
        return not out.get('stderr')

    def set_password(self, ad_id, password):
        """Send a new password for a given object.

        This only works for Accounts.

        @param ad_id: The Id for the object. Could be the SamAccountName,
            DistinguishedName, SID, UUID and probably some other identifiers.
 
        @type password: string
        @param password: The new passord for the object. Must be in plaintext,
            as that is how AD requires it to be, for now.

        """
        self.logger.info('Setting password for: %s', ad_id)
        # Would like to be able to give AD a hash/crypt in some format that is
        # not readable for others. We convert it to base64 only to avoid any
        # trouble with string escape characters - this is not for security
        # reasons.
        password = base64.b64encode(password)
        cmd = '''$b = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String(%(pwd)s));
            $pwd = ConvertTo-SecureString -AsPlainText -Force $b;
            %(cmd)s -NewPassword $pwd;
        ''' % {'pwd': self.escape_to_string(password),
               'cmd': self._generate_ad_command('Set-ADAccountPassword',
                                                {'Identity': ad_id}, 
                                                ['Reset'])}
        #Set-ADAccountPassword -Identity %(_ad_id)s -Credential $cred -Reset -NewPassword $pwd
        if self.dryrun:
            return True
        out = self.run(cmd)
        return not out.get('stderr')

    def get_chosen_domaincontroller(self, reset=False):
        """Fetch and cache a preferred Domain Controller (DC).

        The list of DCs is fetched from AD the first time. The answer is then
        cached, so the next time asked, we reuse the same DC.

        We cache a preferred DC to sync with to avoid that we have to wait
        inbetween the updates for the DCs to have synced. We could still go
        without this, but then we could get race conditions. Domain Controllers
        are normally reached semi-randomly, to avoid that one DC gets overused.

        @type reset: bool
        @param reset: 
            If True, we should ignore the already chosen DC and pick one again.
            If False, the already chosen DC is returned.

        @rtype: str
        @return:
            The Name attribute for the chosen DC is returned, as this could be
            used directly in the powershell commands.

        """
        if reset or not getattr(self, '_chosen_dc', False):
            # Can't make use of _generate_ad_command here, as it calls this
            # method.
            cmd = "Get-ADDomainController -Credential $cred | ConvertTo-Json"
            ret = self.get_output_json(self.run(cmd), dict())
            self._chosen_dc = ret['Name']
            self.logger.debug("Preferred DC: %s", self._chosen_dc)
        return self._chosen_dc

    def update_recipient(self, ad_dn):
        """Run the cmdlet Update-Recipient for a given object.

        @type ad_dn: str
        @param ad_dn:
            The Id for the object. Most likely DistinguishedName, but sometimes
            could also be the SamAccountName, SID, UUID 
            and probably some other identifiers.

        @rtype: bool
        @return:
            True if there was no error during the command execution (stderr
            from the command is missing). False otherwise.

        """
        self.logger.info("Run Update-Recipient for: %s", ad_dn)

        # TODO: Could we use the standard parameters?
        cmd = self._generate_ad_command('Update-Recipient', 
                                        {'Identity': ad_dn})
        if self.dryrun:
            return True
        out = self.run(cmd)
        return not out.get('stderr')

    def execute_script(self, script, **kwargs):
        """Execute a script remotely on the Windows side.

        The given script file gets executed by powershell on the server side.
        Note that the ExecutionPolicy defines if the script has to be signed or
        not before you could execute it. This is up to the administrators of the
        AD domain, as they then have to sign the script.

        TODO: Check if this works! 
        
        TBD: Should we call it in parallell, thus not getting any feedback from
        it? Or should we get the output and send it by mail to the AD
        administrators?

        @type script: string
        @param script: The absolute path to the script that should get executed.

        @type **kwargs: mixed
        @param **kwargs: All arguments are made into parameters for the command,
            on the form: -KEY VALUE

        @rtype: NoneType
        @return: Nothing is returned, as we could run the command in parallell.

        @raise PowershellException: If the script couldn't get executed, if the
            script contained a syntax error, or any other error that could occur
            at once.

        """
        self.logger.info("Executing script %s, args: %s", script, kwargs)
        params = ' '.join('-%s %s' % (x[0], x[1]) for x in kwargs.iteritems())
        cmd = '& %(cmd)s %(params)s' % {'cmd': self.escape_to_string(script),
                                        'params': params}
        if self.dryrun:
            return True
        # TODO: How about just executing it, and not getting the feedback from
        # it? Could it be done without WinRM complaining after some attempts?
        t = time.time()
        self.run(cmd)
        self.logger.debug("Script %s got executed in %.2f seconds", script,
                          time.time() - t)

# TODO: The rest should be modified or removed, as we should not communicate
# with the old ADServer any more:
class ADUtils(object):
    """Utility methods for communicating both with AD and Cerebrum.

    This should be the base class for classes that should work and synchronise
    with AD, both fullsync and quicksyncs. Contains basic functionality.

    """

    def __init__(self, db, logger, host, port, ad_domain_admin, winrm_user,
                 encrypted=True):
        """Set up sync and connect to the given Windows service.

        @type db: Cerebrum.CLDatabase.CLDatabase
        @param db: The Cerebrum database connection that should be used.

        @type logger: Cerebrum.modules.cerelog.CerebrumLogger
        @param logger: The Cerebrum logger to use.

        @type host: str
        @param host: Hostname of the Windows server to communicate with.

        @type port: int
        @param port: Port number at the Windows server. If not given, the
            default port is used.

        @type encrypted: bool
        @param encrypted: If the communication should go encrypted. Do not set
            this to False when in production or working with authentic data!

        @type ad_domain_admin: str
        @param ad_domain_admin: The username of our domain account in AD that
            has the privileges to administrate our OUs.
            TODO: Should this go to the configuration instead?

        """
        pass

    # TODO: This should go into a subclass, as not all uses exchange:
    def update_Exchange(self, ad_obj):
        """
        Telling the AD-service to start the Windows Power Shell command
        Update-Recipient on object in order to prep them for Exchange.
        
        @param ad_objs : object to run command on
        @type  ad_objs: str
        """
        msg = "Running Update-Recipient for object '%s' against Exchange" % ad_obj
        if self.dryrun:
            self.logger.debug("Not %s", msg)
            return
        self.logger.info(msg)

        # Use self.ad_dc if it exists, otherwise try cereconf.AD_DC
        try:
            ad_dc = self.ad_dc
        except AttributeError:
            ad_dc = getattr(cereconf, "AD_DC", None)

        if ad_dc:
            self.run_cmd('run_UpdateRecipient', ad_obj, ad_dc)
        else:
            self.run_cmd('run_UpdateRecipient', ad_obj)

    def attr_cmp(self, cb_attr, ad_attr):
        """
        Compare new (attribute calculated from Cerebrum data) and old
        ad attribute. 

        @param cb_attr: attribute calculated from Cerebrum data
        @type cb_attr: unicode, list or tuple
        @param ad_attr: Attribute fetched from AD
        @type ad_attr: list || unicode || str
        
        @rtype: cb_attr or None
        @return: cb_attr if attributes differ. None if no difference or
        comparison cannot be made.
        """
        # Sometimes attrs from ad are put in a list
        if isinstance(ad_attr, (list, tuple)) and len(ad_attr) == 1:
            ad_attr = ad_attr[0]
        
        # Handle list, tuples and (unicode) strings
        if isinstance(cb_attr, (list, tuple)):
            cb_attr = list(cb_attr)
            # if cb_attr is a list, make sure ad_attr is a list 
            if not isinstance(ad_attr, (list, tuple)):
                ad_attr = [ad_attr]
            cb_attr.sort()
            ad_attr.sort()

        # Now we can compare the attrs
        if isinstance(ad_attr, (str, unicode)) and isinstance(cb_attr, (str, unicode)):
            # Don't care about case
            if cb_attr.lower() != ad_attr.lower():
                return cb_attr
        else:
            if cb_attr != ad_attr:
                return cb_attr

class ADUserUtils(ADUtils):
    """
    User specific methods
    """

    def move_user(self, dn, ou):
        self.move_object(dn, ou, obj_type="user")

    def deactivate_user(self, ad_user):
        """
        Delete or deactivate user in Cerebrum-controlled OU.

        @param ad_user: AD attributes
        @type dn: dict
        """
        dn = ad_user["distinguishedName"]
        # Delete or disable?
        if self.delete_users:
            self.delete_user(dn)
        else:
            # Check if user is already disabled
            if not ad_user['ACCOUNTDISABLE']:
                self.disable_user(dn)
            # Disabled users lives in AD_LOST_AND_FOUND OU
            if self.get_ou(dn) != self.get_deleted_ou():
                self.move_user(dn, self.get_deleted_ou())


    def delete_user(self, dn):
        """
        Delete user object in AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not deleting user %s" % dn)
            return
        
        if self.run_cmd('bindObject', dn):
            self.logger.info("Deleting user %s" % dn)
            self.run_cmd('deleteObject')


    def disable_user(self, dn):
        """
        Disable user in AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not disabling user %s" % dn)
            return
        self.logger.info("Disabling user %s" % dn)
        self.commit_changes(dn, ACCOUNTDISABLE=True)
         

    def create_ad_account(self, attrs, ou, create_homedir=False):
        """
        Create AD account, set password and default properties. 

        @param attrs: AD attrs to be set for the account
        @type attrs: dict        
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        uname = attrs.pop("sAMAccountName")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating user %s" % uname)
            return
        
        sid = self.run_cmd("createObject", "User", ou, uname)
        if not sid:
            # Don't continue if createObject fails
            return
        self.logger.info("created user %s with sid %s", uname, sid)

        # Set password
        pw = unicode(self.ac.make_passwd(uname), cereconf.ENCODING)
        self.run_cmd("setPassword", pw)

        # Set properties. First remove any properties that cannot be set like this
        for a in ("distinguishedName", "cn"):
            if attrs.has_key(a):
                del attrs[a]
        # Don't send attrs with value == None
        for k, v in attrs.items():
            if v is None:
                del attrs[k]
        if self.run_cmd("putProperties", attrs) and self.run_cmd("setObject"):
            # TBD: A bool here to decide if createDir should be performed or not?
            # Create accountDir for new account if attributes where set.
            # Give AD time to take a breath before creating homeDir
            if create_homedir:
                time.sleep(5)
                self.run_cmd("createDir")
        return sid

class ADGroupUtils(ADUtils):
    """
    Group specific methods
    """
    def __init__(self, db, logger, host, port, ad_domain_admin):
        ADUtils.__init__(self, db, logger, host, port, ad_domain_admin)
        self.group = Factory.get("Group")(self.db)
    

    def commit_changes(self, dn, **changes):
        """
        Set attributes for account

        @param dn: AD attribute distinguishedName 
        @type dn: str
        @param changes: attributes that should be changed in AD
        @type changes: dict (keyword args)
        """
        if not self.dryrun and self.run_cmd('bindObject', dn):
            self.logger.info("Setting attributes for %s: %s" % (dn, changes))
            # Set attributes in AD
            self.run_cmd('putGroupProperties', changes)
            self.run_cmd('setObject')


    def create_ad_group(self, attrs, ou):
        """
        Create AD group.

        @param attrs: AD attrs to be set for the account
        @type attrs: dict        
        @param ou: LDAP path to base ou for the entity type
        @type ou: str        
        """
        gname = attrs.pop("name")
        if self.dryrun:
            self.logger.debug("DRYRUN: Not creating group %s" % gname)
            return

        # Create group object
        sid = self.run_cmd("createObject", "Group", ou, gname)
        if not sid:
            # Don't continue if createObject fails
            return
        self.logger.info("created group %s with sid %s", gname, sid)
        # # Set other properties
        if attrs.has_key("distinguishedName"):
            del attrs["distinguishedName"]
        self.run_cmd("putGroupProperties", attrs)
        self.run_cmd("setObject")
        # createObject succeded, return sid
        return sid


    def delete_group(self, dn):
        """
        Delete group object in AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not deleting %s" % dn)
            return

        if self.run_cmd('bindObject', dn):
            self.logger.info("Deleting group %s" % dn)
            self.run_cmd('deleteObject')


    def sync_members(self, dn, members):
        """
        Sync members for a group to AD.

        @param dn: AD attribute distinguishedName 
        @type dn: str
        @param members: List of account and group names
        @type members: list
        
        """
        if self.dryrun:
            self.logger.debug("DRYRUN: Not syncing members for %s" % dn)
            return
        # We must bind to object before calling syncMembers
        if dn and self.run_cmd('bindObject', dn):
            if self.run_cmd("syncMembers", members, False, False):
                self.logger.info("Synced members for group %s" % dn)
