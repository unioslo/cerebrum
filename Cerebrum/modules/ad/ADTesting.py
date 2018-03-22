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
import uuid
from functools import wraps

import cereconf

DEFAULT_OU = getattr(cereconf, 'AD_LDAP', 'ad_ldap_root')


def _make_guid(dn):
    try:
        oid = bytes(dn)
    except:
        oid = dn.decode('ascii', 'replace')
    return str(uuid.uuid3(uuid.NAMESPACE_OID, oid)).upper()


def _make_sid(dn):
    return 'S-1-5-' + '-'.join(str(sum(ord(char) for char in comp))
                               for comp in dn.split(','))


def debug_call(fn):
    fn_name = getattr(fn, '__name__', repr(fn))

    @wraps(fn)
    def _wrapper(self, *args, **kwargs):
        log_args = [repr(a) for a in args]
        for k, v in kwargs.items():
            log_args.append("%s=%r" % (k, v))
        self.logger.debug("%s(%s)", fn_name, ', '.join(log_args))
        retval = fn(self, *args, **kwargs)
        self.logger.debug("%s() = %r", fn_name, retval)
        return retval
    return _wrapper


class _base(object):
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

    @debug_call
    def moveObject(self, OU, Name=None):
        self.distinguishedName
        retur = self.checkObject('moveObject')
        if not retur[0]:
            return retur

        retur = self.bindObject(OU)
        if not retur[0]:
            return retur

        return (True, 'moveObject %s' % self.distinguishedName)

    @debug_call
    def checkObject(self, func='check_object'):
        if self.Object is None:
            self.logger.warn("Object is None in %s", func)
            return (False, "Object is None in %s" % func)
        else:
            return (True, "checkObject")

    @debug_call
    def bindObject(self, LDAPAccount):
        # normally the win32com object for connecting to the AD's LDAP
        self.Object = object()
        self.distinguishedName = LDAPAccount  # Note that this is not correct
        return (True, "Object bound to %s" % self.distinguishedName)

    @debug_call
    def rebindObject(self):
        return self.bindObject(self.distinguishedName)

    @debug_call
    def clearObject(self):
        del self.Object
        del self.distinguishedName
        del self.type
        return (True, "Object cleared.")

    @debug_call
    def setObject(self):
        assert hasattr(self, 'Object')
        return (True, 'SetInfo %s done.' % self.distinguishedName)

    @debug_call
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

    @debug_call
    def createObject(self, objType, OU, Name):
        retur = self.bindObject(OU)
        if not retur[0]:
            return retur
        self.distinguishedName = 'CN=%s,%s' % (Name, OU)
        if objType in ('user', 'group'):
            sid = _make_sid(self.distinguishedName)
        else:
            sid = _make_guid(self.distinguishedName)
        return (True, 'createObject %s' % self.distinguishedName, sid)

    @debug_call
    def getObjectProperties(self, properties):
        retur = self.checkObject('getObjectProperties')
        if not retur[0]:
            return retur

        accprop = {}

        for attr in properties:
            accprop[attr] = 'test'
        return (True, accprop)

    @debug_call
    def setObjectProperties(self, accprop):
        retur = self.checkObject('putObjectProperties')
        if not retur[0]:
            return retur
        return (True, "putObjectProperty %s" % self.distinguishedName)


class User(_base):
    """ Mock of the server side ADObject.Account """

    @debug_call
    def setUserAttributes(self, Attributes=None, AccountControl=None):
        """Register a set of userFields that should be used when syncing.
        """
        self.userAttributes = Attributes
        self.userAccountControl = AccountControl
        return (True, "setUserAttributes")

    @debug_call
    def getProperties(self):
        """ Function that finds and returns values of the account object. """
        retur = self.checkObject('getProperties')
        if not retur[0]:
            return retur

        accprop = {'sAMAccountName': self.distinguishedName.split(',')[0]}

        for attr in self.userAttributes:
            accprop[attr] = False

        for attr in self.userAccountControl:
            accprop[attr] = True
        return accprop

    @debug_call
    def putProperties(self, accprop=None):
        accprop = accprop or {}
        return (True, 'putProperty %s' % self.distinguishedName)

    @debug_call
    def setPassword(self, password):
        return (True, 'setPassword')


class Group(_base):
    """ Mock of the server side ADObject.Group """

    @debug_call
    def setGroupAttributes(self, attributes=None):
        self.groupAttributes = attributes
        return (True, "setGroupAttributes")

    @debug_call
    def putGroupProperties(self, grpprop=None):
        grpprop = grpprop or {}

        retur = self.checkObject('putProperties')
        if not retur[0]:
            return retur
        return (True, "putProperty %s" % self.distinguishedName)

    @debug_call
    def addremoveMembers(self, memberList, LDAPPath, remove):
        return (True, '')

    @debug_call
    def addMembers(self, memberList, LDAPPath=True):
        err = self.addremoveMembers(memberList, LDAPPath, False)
        return (err[0], 'addMembers')

    @debug_call
    def removeMembers(self, memberList, LDAPPath=True):
        err = self.addremoveMembers(memberList, LDAPPath, True)
        return (err[0], 'removeMembers')

    @debug_call
    def syncMembers(self, memberlist, LDAPPath=True, reportmissing=True):
        if reportmissing:
            return (False, ''.join(list(memberlist)))
        else:
            return (True, 'syncMembers')

    @debug_call
    def replaceMembers(self, memberList, LDAPPath=True):
        return (False, ''.join(list(memberList)))
        # return (True, 'syncMembers')

    @debug_call
    def listMembers(self):
        return True


class Contact(_base):

    def setContactAttributes(self, Attributes=None):
        self.contactAttributes = Attributes
        return (True, "setContactAttributes")

    def putContactProperties(self, contactprop=None):
        contactprop = contactprop or {}
        retur = self.checkObject('putProperties')
        if not retur[0]:
            return retur
        return (True, "putProperty %s" % self.distinguishedName)


class Search(_base):

    @debug_call
    def listObjects(self, searchtype, prop=False, OU=DEFAULT_OU):

        fields = ['distinguishedName', ]

        if searchtype not in ('user', 'group', 'organizationalUnit',
                              'contact'):
            return False

        if prop:
            dictofobjects = {}
            if searchtype == 'user':
                fields.append('sAMAccountName')
                fields.extend(self.userAttributes or ())
                if self.userAccountControl:
                    fields.append('userAccountControl')
            elif searchtype == 'group':
                fields.append('sAMAccountName')
                fields.extend(self.groupAttributes or ())
            elif searchtype == 'contact':
                fields.append('name')
                fields.extend(self.contactAttributes or ())

        if prop and searchtype == 'user':
            # TODO: add some mock objects?
            for i in range(0):
                properties = {}
                properties['distinguishedName'] = 'dn'
                if self.userAttributes is not None:
                    for uAtt in self.userAttributes:
                        properties[uAtt] = 'value'
                if self.userAccountControl is not None:
                    for uAC in self.userAccountControl:
                        if uAC == "PASSWD_CANT_CHANGE":
                            # properties[uAC] = False
                            properties[uAC] = True
                        else:
                            if 'userAccountControl':
                                properties[uAC] = True
                            else:
                                properties[uAC] = False

                # dictofobjects[sAMAccountName] = properties
            return dictofobjects

        elif prop and searchtype == 'group':
            # TODO: add some mock objects?
            for i in range(0):
                properties = {}
                properties['distinguishedName'] = 'dn'
                for gAtt in self.groupAttributes or ():
                    properties[gAtt] = 'value'
                # dictofobjects[sAMAccountName] = properties
            return dictofobjects

        elif prop and searchtype == 'contact':
            # TODO: add some mock objects?
            for i in range(0):
                properties = {}
                properties['distinguishedName'] = 'dn'
                for cAtt in self.contactAttributes or ():
                    properties[cAtt] = 'value'
                # dictofobjects[name] = properties
            return dictofobjects

        else:
            listofobjects = []
            # TODO: add some mock objects?
            for i in range(0):
                # listofobjects.append(dn)
                pass
            return listofobjects

    @debug_call
    def findObject(self, account, OU=False):
        # Returning False for now, might want to simulate a DistinguishedName.
        return False

    @debug_call
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
            dn = 'cn=%s,%s' % (n, OU)
            data[n] = {'distinguishedName': dn, }
            if getSid:
                data[n]['Sid'] = _make_sid(dn)
            if getGUID:
                # per-user unique 128b value
                data[n]['objectGUID'] = _make_guid(dn)
            self.logger.debug("obj=%r", data[n])

        return data


class MockADServer(User, Group, Contact, Search):
    pass
