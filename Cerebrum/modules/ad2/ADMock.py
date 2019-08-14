#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2017 University of Oslo, Norway
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

"""Module for mocking communication and interaction with Active Directory.

This mock builds on L{ADclient}, and should be used the same way.
"""

from __future__ import with_statement

import collections

from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.modules.ad2.winrm import CommandTooLongException
from Cerebrum.Utils import Factory

import cereconf
getattr(cereconf, "No linter nag!", None)


class ADclientMock(ADUtils.ADclient):
    def __init__(self, *args, **kwargs):
        self.logger = kwargs['logger']
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._cache = dict()

    def _load_state(self, fname):
        try:
            import json
        except ImportError:
            from Cerebrum.extlib import json
        with open(fname, 'r') as f:
            self._cache = json.load(f)

    def _store_state(self, fname):
        try:
            import json
        except ImportError:
            from Cerebrum.extlib import json
        with open(fname, 'w') as f:
            json.dump(self._cache, f)

    def start_list_objects(self, ou, attributes, object_class, names=[]):
        """Start to search for objects in AD, but do not retrieve the data yet.

        The server is asked to generate a list of the objects, and returns an
        ID which we could later use to retrieve the generated list from. It is
        designed like this because the list could take some time to produce.

        @type ou: string
        @param ou: The OU in AD to search in. All objects from given OU and its
            child OUs are returned.

        @type attributes: dict, list or tuple
        @param attributes:
            A list of all attributes that should be returned for all the
            objects that were found. If a dict is given, its keys are used as
            the attribute list.

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
        # Return fake command_id
        return "command_id"

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
        @param other: A dict to put output from the server that is not a part
            of the object list. E.g. for different warnings. If not set, all
            other output will be logged as warnings.

        @rtype: iterator
        @return: An iterator over each object that is returned from AD. Each
            object is a dict with the different attributes.

            TODO: How about AccountControl?

        """
        for key in self._cache:
            yield self._cache[key]

    def disable_object(self, dn):
        """Set an object as not enabled.

        Note that this only affects accounts, it doesn't look like you can
        disable other object types.

        """
        self.logger.info('Disabling object: %s', (dn,))
        # TODO: Save state in cache.
        return True

    def delete_object(self, dn):
        """Delete an object from AD.

        This removes the data about an object from AD. It is possible to
        restore the object if AD is in level 2008 R2 level.

        TODO: the command prompts for confirmation, which we can't give. How to
        setup the sync to not ask us about this?

        """
        self.logger.info('Deleting object: %s', (dn,))
        del self._cache[dn]
        return True

    def get_object(self, ad_id, object_class=None, attributes=None):
        """Send a command for receiving information about an object from AD.

        Dryrun does not affect this command, since it works readonly.

        @type ad_id: string
        @param ad_id: The identification of the object. Could be Distinguished
            Name (DN), Fully Qualified Domain Name (FQDN), username, UID, GID,
            SID or anything that AD accepts as identification.

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
        # TODO: Search for objects in the cache. ad_id might take different
        # forms.
        if ad_id in self._cache:
            return self._cache.get(ad_id)
        else:
            raise ADUtils.OUUnknownException('Object not found')

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
            If specified, the given attributes are added as criterias. Could
            for instance be used to find the object by its given
            SAMAccountName.

        @type ad_object_class: str
        @param ad_object_class:
            If specified, only objects of the given objectClass are returned.

        @rtype: list of dicts
        @return:
            The objects from AD that matched the criterias are returned,
            together with some of their AD attributes.

        """
        return []

    def create_object(self, name, path, object_class, attributes=None,
                      parameters=None):
        """Send a command for creating a new object in AD.

        Note that accounts are set as disabled by default, and cannot be
        enabled unless a valid password is set for them (or PasswordNotRequired
        is set).

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

        @raise ObjectAlreadyExistsException: If the object already exists in
            the domain, this exception is raised.

        @raise PowershellException: If the powershell command failed somehow,
            e.g. if the object already existed, or if the script didn't have
            access to create the object. The output is put in the exception,
            you will for example get the information about the object if the
            object already exists.

        """
        self.logger.info("Creating %s in AD: %s (%s)",
                         object_class,
                         name,
                         path)
        if not parameters:
            parameters = dict()

        # Add some extra parameters for the various types of objects:
        # TODO: this might be moved into subclasses of ADclient, one per object
        # type? Would probably make easier code... Or we could just depend on
        # the configuration for this behaviour, at least for the attributes.
        if str(object_class).lower() == 'user':
            # SAMAccountName is mandatory for some object types:
            # TODO: check if this is not necessary any more...
            # User and group objects on creation should not have
            # SamAccountName in attributes. They should have it in
            # parameters instead.
            if 'SamAccountName' in attributes:
                parameters['SamAccountName'] = attributes['SamAccountName']
                del attributes['SamAccountName']
            else:
                parameters['SamAccountName'] = name
            parameters['CannotChangePassword'] = True
            parameters['PasswordNeverExpires'] = True
        elif str(object_class).lower() == 'group':
            if 'SamAccountName' in attributes:
                parameters['SamAccountName'] = attributes['SamAccountName']
                del attributes['SamAccountName']
            else:
                parameters['SamAccountName'] = name

        # Add the attributes, but mapped to correctly name used in AD:
        if attributes:
            attributes = dict((self.attribute_write_map.get(name, name), value)
                              for name, value in attributes.iteritems()
                              if value or isinstance(value, (bool, int, long,
                                                             float)))
        if attributes:
            parameters['OtherAttributes'] = attributes

        parameters['Name'] = name
        parameters['Path'] = path
        if str(object_class).lower() == 'user':
            parameters['Type'] = object_class
            cmd = self._generate_ad_command('New-ADUser',
                                            parameters, 'PassThru')
        elif str(object_class).lower() == 'group':
            # For some reason, New-ADGroup does not accept -Type parameter
            cmd = self._generate_ad_command('New-ADGroup',
                                            parameters, 'PassThru')
        else:
            parameters['Type'] = object_class
            cmd = self._generate_ad_command('New-ADObject',
                                            parameters, 'PassThru')
        cmd = '''if ($str = %s | ConvertTo-Json) {
            $str -replace '$',';'
            }''' % cmd

        # Some of the variables are mandatory to be returned, so we have to
        # just put something in them, for the sake of testing:
        ret = attributes.copy()
        ret['Name'] = ret['SamAccountName'] = name
        ret['DistinguishedName'] = 'CN=%s,%s' % (name, path)
        ret['SID'] = None
        self.logger.info(
            "'%s' stored in mock. Would have ran '%s' to create AD-object" %
            (ret, cmd))

        # Store object in cache
        ad_id = 'CN=%s,%s' % (name, path)
        self._cache[ad_id] = ret
        return ret

    def _run_setadobject(self, dn, action, attrs):
        """Helper method for running the Set-ADObject command"""
        cmd = self._generate_ad_command('Set-ADObject',
                                        {'Identity': dn,
                                         action: attrs})
        # PowerShell commands are executed through Windows command line.
        # The maximum length of the command there is 8191 for modern
        # Windows versions (http://support.microsoft.com/kb/830473). Due to
        # additional parameters that other methods add to the command, the
        # part of it which is generated here has to be even shorter. The
        # limit at 8000 bytes seems to be working.
        # TODO: This should be checked for in winrm.py.
        if len(cmd) > 8000:
            raise CommandTooLongException('Too long')
        self.logger.info("_run_setadobject would have ran the command: '%s'",
                         cmd)
        return True

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
            attribute. When called, an iterator of each element in the
            attribute is returned.

        """
        var = self._cache.get(adid)
        try:
            # TODO: Are there more types that should be handeled?
            if isinstance(var, basestring):
                raise TypeError
            return lambda: (e for e in var)
        except TypeError:
            # TODO: Is it OK to force the var to multivalue? Should we rather
            # raise?
            self.logger.warn("Attribute '%s' of '%s' is not multivalued."
                             " Will be returned as multivalued."
                             % (attributename, adid))
            return lambda: [var]

    def empty_group(self, groupid):
        """Remove all the members of a given group in AD.

        This could be used when the group has too many members to be able to
        retrieve them from AD. The group could be then be refilled.

        @type groupid: string
        @param groupid: The Id of the group in AD.

        """
        self.logger.debug("Removing all members of group: %s" % groupid)
        return True

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
        self.logger.debug("Adding %d members for object: %s" % (len(members),
                                                                groupid))
        for member in members:
            # TODO: Insert members into cache.
            self.logger.debug("Adding member: %s", member)
        return True

    def remove_members(self, groupid, members, attribute_name=None):
        """Send command for removing given members from a given group in AD.

        Note that if one of the members does not exist in the group, the
        command will raise an exception.

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
        self.logger.debug("Removing %d members for group: %s" % (len(members),
                                                                 groupid))
        # Printing out the first 500 members, for debugging reasons:
        self.logger.debug2("Removing members for %s: %s...", groupid,
                           ', '.join(tuple(members)[:500]))
        # TODO: Remove members from cache.
        return True

    def add_group_members(self, group_id, member_ids):
        """ Add member to AD group. """
        if not isinstance(member_ids, collections.Sequence):
            member_ids = [member_ids, ]
        self.logger.debug("Adding %d members for group: %s",
                          len(member_ids), group_id)
        # TODO: Cache members
        return True

    def remove_group_members(self, group_id, member_ids):
        """ Remove member from AD group. """
        if not isinstance(member_ids, collections.Sequence):
            member_ids = [member_ids, ]
        self.logger.debug("Removing %d members for group: %s",
                          len(member_ids), group_id)
        # TODO: Update cache
        return True

    def enable_object(self, ad_id):
        """Enable a given object in AD. The object must exist.

        This only works for Accounts, as that's the only available command for
        enabling objects in AD.

        @type ad_id: string
        @param ad_id: The Id for the object. Normally the DistinguishedName.

        """
        self.logger.info('Enabling object: %s', ad_id)
        # TODO: Update state in cache.
        return True

    def set_password(self, ad_id, password, password_type='plaintext'):
        """Send a new password for a given object.

        This only works for Accounts.

        :param ad_id: The Id for the object. Could be the SamAccountName,
            DistinguishedName, SID, UUID and probably some other identifiers.

        :param password: The new passord for the object. Must be in plaintext,
            as that is how AD requires it to be, for now.
        :type password: str

        :param password_type: The password type (default: 'plaintext').
                              Currently supported types:
                              'password' - GPG encrypted plaintext-password
                              'password-base64' - GPG encrypted base64-encoded
                                                  password
                              'plaintext' - unencrypted plaintext password
        :type password_type: str
        """
        self.logger.info('Setting password for: %s', ad_id)
        return True

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
        return "my.lovely.dc.example.com"

    def execute_script(self, script, **kwargs):
        """Execute a script remotely on the Windows side.

        The given script file gets executed by powershell on the server side.
        Note that the ExecutionPolicy defines if the script has to be signed or
        not before you could execute it. This is up to the administrators of
        the AD domain, as they then have to sign the script.

        TODO: Check if this works!

        TBD: Should we call it in parallell, thus not getting any feedback from
        it? Or should we get the output and send it by mail to the AD
        administrators?

        @type script: string
        @param script: The absolute path to the script that should get
            executed.

        @type **kwargs: mixed
        @param **kwargs: All arguments are made into parameters for the
            command, on the form: -KEY VALUE

        @rtype: NoneType
        @return: Nothing is returned, as we could run the command in parallell.

        @raise PowershellException: If the script couldn't get executed, if the
            script contained a syntax error, or any other error that could
            occur at once.

        """
        self.logger.info("Executing script %s, args: %s", script, kwargs)
        params = ' '.join('-%s %s' % (x[0], x[1]) for x in kwargs.iteritems())
        cmd = '& %(cmd)s %(params)s' % {'cmd': self.escape_to_string(script),
                                        'params': params}
        self.logger.debug("Mock would have ran '%s'" % cmd)
