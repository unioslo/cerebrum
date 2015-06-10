#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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

import cereconf
getattr(cereconf, "No linter nag!", None)

from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.Utils import Factory


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
        f = open(fname, 'r')
        self._cache = json.load(f)
        f.close()
        # TODO: try-except-whatever

    def _store_state(self, fname):
        try:
            import json
        except ImportError:
            from Cerebrum.extlib import json
        f = open(fname, 'w')
        json.dump(self._cache, f)
        f.close()
        # TODO: try-except-whatever

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
