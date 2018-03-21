# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
"""This file contains functionality for being able to test the AD sync in
different ways.

"""
import md5

import cereconf

DEFAULT_OU = getattr(cereconf, 'AD_LDAP', 'ad_ldap_root')


def _make_guid(value):
    uid = md5.md5(value).hexdigest().upper()
    return '-'.join((uid[:8], uid[8:12], uid[12:16], uid[16:20], uid[20:]))


def _make_sid(value):
    uid = md5.md5(value).hexdigest().upper()
    return 'S-1-5-' + '-'.join(
        str(int(n, 16)) for n in (uid[:4], uid[4:12], uid[12:20], uid[20:]))


class MockADServer(object):
    """A mock AD server used for testing the sync when in dry run mode and we
    can't connect to the AD server. It tries to behave as the server in
    L{servers/ad/} and the methods should be called directly instead of using
    xmlrpclib.

    It could be sub classed to be able to run it with your own test data. For
    instances should listObject be updated with returning mock data that is
    assumed to come from the AD server.

    Assumes success on most of the calls, and will only check basic settings.

    """

    def __init__(self, logger):
        self.logger = logger

    def listObjects(self, searchtype, prop=False, OU=DEFAULT_OU):
        """Return a list of distinguishedName for all objects of a specific
        type, e.g. 'user', 'group' or 'organizationalUnit'.

        """
        if prop:
            return {}
        return ()

    def setUserAttributes(self, Attributes=None, AccountControl=None):
        """Register a set of userFields that should be used when syncing.
        """
        self.userAttributes = Attributes
        self.userAccountControl = AccountControl
        return (True, "setUserAttributes")

    def moveObject(self, OU, Name=None):
        self.distinguishedName
        retur = self.checkObject('moveObject')
        if not retur[0]:
            return retur

        retur = self.bindObject(OU)
        if not retur[0]:
            return retur

        return (True, 'moveObject %s' % self.distinguishedName)

    def checkObject(self, func='check_object'):
        if self.Object is None:
            self.logger.warn("Object is None in %s", func)
            return (False, "Object is None in %s" % func)
        else:
            return (True, "checkObject")

    def bindObject(self, LDAPAccount):
        # normally the win32com object for connecting to the AD's LDAP
        self.Object = object()
        self.distinguishedName = LDAPAccount  # Note that this is not correct
        return (True, "Object bound to %s" % self.distinguishedName)

    def rebindObject(self):
        return self.bindObject(self.distinguishedName)

    def clearObject(self):
        del self.Object
        del self.distinguishedName
        del self.type
        return (True, "Object cleared.")

    def setObject(self):
        assert hasattr(self, 'Object')
        return (True, 'SetInfo %s done.' % self.distinguishedName)

    def deleteObject(self):
        retur = self.checkObject('deleteObject')
        if not retur[0]:
            return retur

        OUparts = self.distinguishedName.split(',')
        OU = ",".join(OUparts[1:])
        name = OUparts[0]

        retur = self.bindObject(OU)
        if not retur[0]:
            return retur

        self.clearObject()
        return (True, 'deleteObject "type" %s, %s' % (name, OU))

    def createObject(self, objType, OU, Name):
        retur = self.bindObject(OU)
        if not retur[0]:
            return retur
        sid = '1234566778990'
        self.distinguishedName = Name  # not correct
        return (True, 'createObject %s%s,%s' % ('CN=', Name, OU), sid)

    def getObjectProperties(self, properties):
        retur = self.checkObject('getObjectProperties')
        if not retur[0]:
            return retur

        accprop = {}

        for attr in properties:
            accprop[attr] = 'test'
        return (True, accprop)

    def setObjectProperties(self, accprop):
        retur = self.checkObject('putObjectProperties')
        if not retur[0]:
            return retur
        return (True, "putObjectProperty %s" % self.distinguishedName)

    def setContactAttributes(self, attributes=None):
        self.contactAttributes = attributes
        return (True, "setContactAttributes")

    def setGroupAttributes(self, attributes=None):
        self.groupAttributes = attributes
        return (True, "setGroupAttributes")

    def findObject(self, account, OU=False):
        # Returning False for now, might want to simulate a DistinguishedName.
        return False

    def getSid(self, acObject):
        return '123124125412'

    def getGUID(self, acObject):
        return '12412512512512'

    def getObjectID(self, getSid=True, getGUID=False, OU=DEFAULT_OU,
                    searchtype='user'):
        """ Gets the SID and/or GUID for users or groups and return a dict """
        fields = 'distinguishedName, sAMAccountName'
        objecttype = ''

        if searchtype == 'user':
            objecttype = "objectclass='user' AND objectcategory='Person'"
        elif searchtype == 'group':
            objecttype = "objectclass='group' AND objectcategory='group'"
        else:
            self.logger.error('getObjectID unknown type %r', searchtype)
            return False

        if getSid:
            fields = '%s,%s' % (fields, 'objectSid')
        if getGUID:
            fields = '%s,%s' % (fields, 'objectGUID')
        self.logger.debug(
            "SELECT '%s' FROM 'LDAP://%s' where %s", fields, OU, objecttype)

        names = ['foo', 'bar', 'baz', ]
        data = {}
        for n in names:
            data[n] = {
                'distinguishedName': 'cn=%s,%s' % (n, OU),
            }
            if getSid:
                data[n]['Sid'] = _make_sid(n)
            if getGUID:
                # per-user unique 128b value
                data[n]['objectGUID'] = _make_guid(n)
            self.logger.debug("obj=%r", data[n])

        return data
