# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

""" Directory-based backend - in this case LDAP """

import re
import string
import sys
import time
try:
    set()
except:
    from sets import Set as set

import unicodedata

import ldap
import urllib
from ldap import modlist

from ceresync import config
from ceresync.syncws import Affiliation
log = config.logger

import unittest
from ceresync.errors import ServerError

class LdapConnectionError(ServerError):
    pass

class OUNotFoundException(Exception):
    pass

class LdapBack(object):
    """
    All default values such as basedn for each type of object shall be fetch
    from a configuration file. If config is misconfigured, this module should
    log this in somewhat human readable form.

    PosixUser,PosixGroup etc will inherit this class.
    """
    l = None

    def __init__(self):
        self.l = None # Holds the authenticated ldapConnection object
        self.ignore_attr_types = [] # To be overridden by subclasses
        self.populated = False

    def begin(self, incr=False, bulk_add=True, bulk_update=True,
                    bulk_delete=True, uri=None, binddn=None, bindpw=None):
        """
        If incr is true, updates will be incremental, ie the 
        original content will be preserved, and can be updated by
        update() and delete()

        begin() opens a connection to the server running LDAP and 
        tries to authenticate
        """
        self.incr = incr
        self.do_add= incr or bulk_add
        self.do_update= incr or bulk_update
        self.do_delete= incr or bulk_delete
        self.uri= uri or config.get("ldap", "uri")
        self.binddn= binddn or config.get("ldap", "binddn")
        self.bindpw= bindpw or config.get("ldap", "bindpw")

        try:
            log.debug("Connecting to %s", self.uri)
            self.l = ldap.initialize(self.uri)
            self.l.simple_bind_s(self.binddn,self.bindpw)
            self.insync = []
        except ldap.LDAPError,e:
            log.error("Error connecting to server: %s" % (e))
            raise LdapConnectionError

        # Check that the base exists. If not, produce a warning and create it.
        try:
            self.l.search_s(self.base, ldap.SCOPE_BASE)
        except ldap.NO_SUCH_OBJECT, e:
            log.warning("Creating non-existing base '%s'.",self.base)
            entry= { 'objectClass': ['top','organizationalUnit'],
                     'ou': self.base.split(',',1)[0].split('=',1)[1], }
            self.l.add_s(self.base, modlist.addModlist(entry))

        if not self.incr:
            self.populate()

    def close(self):
        """
        Syncronize current base if incr=False, then
        close ongoing operations and disconnect from server
        """
        if not self.incr :
            self.syncronize()
        try:
            self.l.unbind_s()
        except ldap.LDAPError,e:
            log.error("Error occured while closing LDAPConnection: %s" % (e))

    def _cmp(self,x,y):
        """Comparator for sorting hierarchical DNs for ldapsearch-result"""
        x = x.count(",")
        y = y.count(",")
        if x < y : return 1
        elif x == y : return 0
        else: return -1

    def syncronize(self):
        """ Deletes objects not to be found in given base.
        Only for use when incr is set to False.
        """
        if self.incr:
            return

        log.debug("Syncronizing LDAP database")
        self.indirectory = []
        res = self.search(filterstr=self.filter,attrslist=["dn"]) # Only interested in attribute dn to be received
        for (dn,attrs) in res:
            self.indirectory.append(dn)
        for entry in self.insync:
            try:
                self.indirectory.remove(entry)
            except:
                log.info("Info: Didn't find entry: %s." % entry)
        # Sorts the list so children are deleted before parents.
        self.indirectory.sort(self._cmp)
        for entry in self.indirectory:
            # FIXME - Fetch list of DNs not to be touched
            if entry.lower() == 'ou=organization,dc=ntnu,dc=no':
                continue
            else:
                log.info("Found %s in database.. should not be here.. removing" % entry)
                self.delete(dn=entry)
        log.debug("Done syncronizing")

    def abort(self):
        """
        Close ongoing operations and disconnect from server
        """
        try:
            self.l.unbind_s()
        except ldap.LDAPError,e:
            log.error("Error occured while closing LDAPConnection: %s" % (e))

    def add(self, obj, update_if_exists=True):
        """
        Add object into LDAP. If the object exist, we update all attributes given.
        """
        dn=self.get_dn(obj)
        if not self.incr and dn in self.indirectory:
            self.update(obj)
            return
        if not self.do_add:
            self.insync.append(dn)
            return

        attrs=self.get_attributes(obj)
        try:
            mod_attrs = modlist.addModlist(attrs,self.ignore_attr_types)
        except AttributeError,ae:
            log.exception("AttributeError caught from modlist.addModlist: %s" % ae.__str__)
            log.exception("attrs: %s, ignore_attr_types: %s" % (attrs, self.ignore_attr_types))
            sys.exit(1)
        try:
            self.l.add_s(dn,mod_attrs)
            log.info("Added '%s'", dn)
            self.insync.append(dn)
        except ldap.ALREADY_EXISTS,e:
            self.update(obj)
        except ldap.LDAPError,e:
            log.exception("An error occured while adding %s: %s. mod_attrs: %s" % (dn,e.args, mod_attrs))
            sys.exit()
        except TypeError,te:
            log.exception("Expected a string in the list in function add.")
            log.debug("Attr_dict: %s" % attrs)
            log.debug("Modifylist: %s" % mod_attrs)
            sys.exit()

    def update(self,obj,old=None, ignore_oldexistent=True):
        """
        Update object in LDAP. If the object does not exist, we add the object. 
        """
        dn=self.get_dn(obj)
        if not self.do_update:
            self.insync.append(dn)
            return
        attrs=self.get_attributes(obj)
        old_attrs = None
        ignore_attr_types = [] + self.ignore_attr_types

        # Fetch old values from LDAP
        res = self.search(base=dn) # using dn as base, and fetch first record
        if not res:
            self.add(obj)
            return
        old_attrs = res[0][1]

        # Make shure we don't remove existing objectclasses, as long
        # as we get to add the ones we need to have
        missing_objectclasses = set(attrs['objectClass']) - set(old_attrs['objectClass'])
        # If we have 0 missing values, ignore attr objectclass
        # If we have N misssing, fetch the old ones and add missing ones
        # into the  updated list of values for attr objectclass
        if len(missing_objectclasses) == 0:
            ignore_attr_types.append('objectClass')
        else:
            attrs['objectClass'] = old_attrs['objectClass'] + list(missing_objectclasses)

        mod_attrs = modlist.modifyModlist(old_attrs,attrs,ignore_attr_types,ignore_oldexistent)
        try:
            # Only update if there are changes. python_ldap seems to complain when given empty modlists
            if (mod_attrs != []): 
                self.l.modify_s(dn,mod_attrs)
                log.info("Updated '%s'", dn)
            self.insync.append(dn)
        except ldap.LDAPError,e:
            log.exception("An error occured while modifying %s" % (dn))

    def delete(self,obj=None,dn=None):
        """
        Delete object from LDAP. 
        """
        if not self.do_delete:
            return
        if obj:
            dn=self.get_dn(obj)
        try:
            self.l.delete_s(dn)
            log.info("Deleted '%s'", dn)
        except ldap.NO_SUCH_OBJECT,e:
            log.error("%s not found when trying to remove from database" % (dn))
        except ldap.LDAPError,e:
            log.error("Error occured while trying to remove %s from database: %s" % (dn,e))

    def search(self,base=None,scope=ldap.SCOPE_SUBTREE,filterstr='(objectClass=*)',attrslist=None,attrsonly=0):
        if base == None:
            base = self.base
        try:
            result = self.l.search_s(base,scope,filterstr,attrslist,attrsonly)
        except ldap.LDAPError,e:
            # FIXME: Returns error when on no entries found... (bug or feature?)
            log.error("Error occured while searching with filter: %s" % (filterstr))
            return [] # Consider raise exception later
        return result

    def has_object(self, obj):
        if not obj:
            return False

        if not self.populated:
            self.populate()

        return self.indirectory.has_key(self.get_dn(obj))

    def get_object(self, obj):
        if not self.has_object(obj):
            return None

        return self.indirectory[self.get_dn(obj)]

    def populate(self, repopulate=False):
        """ Fetch all users stored in ldap under the given tree
        """
        if self.populated and not repopulate:
            return

        self.indirectory = {}
        res = self.search(filterstr=self.filter) # Only interested in attribute dn to be received
        for (dn,attrs) in res:
            self.indirectory[dn] = attrs

        self.populated = True

    def get_dn(self, obj):
        return "uid=%s,%s" % (self.get_uid(obj), self.base)

class AccountLdapBack(LdapBack):
    def get_uid(self, obj):
        return obj.name

    def get_cn(self, obj):
        return obj.gecos

    def get_sn(self, obj):
        return obj.gecos.split(" ").pop()

    def get_given_name(self, obj):
        full_name = self.get_cn(obj)
        return " ".join(full_name.split(" ")[:-1])
        
    def get_gecos(self, obj):
        return self.toAscii(obj.gecos)

    def get_password(self, obj):
        return "{%s}%s" % (config.get('ldap','hash').upper(), obj.passwd)

    def toAscii(self, utf8string):
        return unicodedata.normalize('NFKD', utf8string.decode('utf-8')).encode('ASCII', 'ignore')

class PersonLdapBack(LdapBack):
    def get_uid(self, obj):
        return obj.primary_account_name

    def get_cn(self, obj):
        return obj.full_name

    def get_sn(self, obj):
        return obj.last_name

    def get_given_name(self, obj):
        return obj.first_name
        
    def get_password(self, obj):
        return "{%s}%s" % (config.get('ldap','hash').upper(), obj.primary_account_password)

    def get_email(self, obj):
        return obj.email

class GroupLdapBack(LdapBack):
    def get_cn(self, obj):
        return obj.name

    def get_uid(self, obj):
        return obj.name

    def get_gid(self, obj):
        return obj.posix_gid

    def get_members(self, obj):
        return [str(m) for m in obj.members]

class PosixUser(AccountLdapBack):
    """Stub object for representation of an account."""
    def __init__(self,conn=None,base=None,filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter

        # Need 'person' for structural-objectclass
        self.obj_class = ['top','person','posixAccount','shadowAccount'] 
        self.ignore_attr_types = []

    def add(self, obj):
        if obj.posix_uid == "" or obj.full_name == "":
            log.debug("Ignoring %s with uid=%s and full_name='%s'", obj.name,
                      obj.posix_uid, obj.full_name)
            return
        super(PosixUser, self).add(obj)

    def get_attributes(self,obj):
        return {
            'objectClass': self.obj_class,
            'cn': self.get_cn(obj),
            'sn': self.get_sn(obj),
            'uid': self.get_uid(obj),
            'gecos': self.get_gecos(obj),
            'uidNumber': str(obj.posix_uid),
            'gidNumber': str(obj.posix_gid),
            'loginShell': str(obj.shell),
            'userPassword': self.get_password(obj),
            'homeDirectory': str(obj.homedir),
        }

class PosixGroup(GroupLdapBack):
    '''Abstraction of a group of accounts'''
    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter
        self.obj_class = ['top','posixGroup']
        self.ignore_attr_types = []

    def get_attributes(self,obj):
        return {
            'objectClass': self.obj_class,
            'cn': self.get_cn(obj),
            'gidNumber': self.get_gid(obj),
            'memberUid': self.get_members(obj),
        }

class Person(PersonLdapBack):
    def __init__(self, base="ou=people,dc=ntnu,dc=no", filter='(objectClass=*)', ouregister=None):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter
        self.obj_class = ['top','person','organizationalPerson','inetOrgPerson','eduPerson','norEduPerson','ntnuPerson']
        self.ignore_attr_types = []
        self.ouregister = ouregister

    def begin(self, **kwargs):
        LdapBack.begin(self, **kwargs)

    def add(self, obj):
        if not obj.primary_account:
            log.debug("Ignoring %s with primary_account=%s", obj.full_name, 
                      obj.primary_account)
            return
        super(Person, self).add(obj)

    def get_attributes(self,obj):
        s = {}
        s['objectClass']            = self.obj_class
        s['cn']                     = self.get_cn(obj)
        s['sn']                     = self.get_sn(obj)
        s['givenName']              = self.get_given_name(obj)
        s['uid']                    = self.get_uid(obj),
        s['userPassword']           = self.get_password(obj)
        s['eduPersonOrgDN']         = "dc=ntnu,dc=no"
        s['eduPersonAffiliation']   = self.get_affiliations(obj)
        s['norEduPersonBirthDate']  = self.get_birthdate(obj)
        s['norEduPersonNIN']        = self.get_social_security_number(obj)
        s['eduPersonPrincipalName'] = self.get_principal(obj)
        s['title']                  = self.get_title(obj)
        s['mail']                   = self.get_email(obj)
        s['norEduOrgAcronym']       = self.get_acronym_list(obj),
        return s

    def get_affiliations(self, obj):
        affiliations = set()
        for holder in obj.affiliations:
            aff = Affiliation(holder)
            if aff.affiliation == 'STUDENT':
                affiliations.add('student')
                affiliations.add('member')
            elif aff.affiliation == 'ANSATT':
                affiliations.add('employee')
                affiliations.add('member')
            elif aff.affiliation == 'TILKNYTTET':
                affiliations.add('affiliate')
            elif aff.affiliation == 'ALUMNI':
                affiliations.add('alum')
            else:
                log.warn("Unknown affiliation: %s" % aff.affiliation)
        return list(affiliations)

    def get_birthdate(self, obj):
        # Expecting birth_date from spine on the form "%Y-%m-%d 00:00:00.00"
        # Ldap wants the form "%Y%m%d".
        # FIXME: Should probably use datetime or mx.DateTime
        birth_date= obj.birth_date.split()[0].replace('-','')
        return ["%s"     %  birth_date]

    def get_title(self, obj):
        affiliations = self.get_affiliations(obj)
        if 'employee' in affiliations:
            return ['fast ansatt']

        if 'student' in affiliations:
            return ['student']

        if 'affiliate' in affiliations:
            return ['tilknyttet']

        if 'alum' in affiliations:
            return ['alumnus']

        return ["Ikke title enno"] 

    def get_principal(self, obj):
        return "%s@%s" % (obj.primary_account_name, config.get('ldap','eduperson_realm'))

    def get_social_security_number(self, obj):
        return obj.nin

    def get_acronym_list(self, obj):
        return self.ouregister.get_acronym_list(obj.primary_ou)

class OracleCalendar(AccountLdapBack):
    """
    Module for handling ldap entries for Oracle Calendar.  The Calendar
    periodically runs a diff against this ldap tree and adds new entries to the
    calendar in addition to disabling accounts that it no longer finds in the
    tree.
    """
    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)

        if base == None:
            self.base = config.get("ldap","calendar_base")
        else:
            self.base = base

        self.filter = filter
        self.obj_class = ('top','inetOrgPerson', 'shadowAccount')

    def get_attributes(self,obj):
        return {
            'uid': self.get_uid(obj),
            'objectClass': self.obj_class,
            'sn': self.get_sn(obj),
            'cn': self.get_cn(obj),
            'givenName': self.get_given_name(obj),
            'userPassword': self.get_password(obj),
            'mail': self.get_email(obj),
            'ou': self.get_ou(obj),
            'o': "NTNU",
        }

    def get_email(self, obj):
        return "%s@%s" % (self.get_uid(obj), 'ntnu.no')

    def get_ou(self, obj):
        return "OI-ITAVD:OI:RE:NTNU"

class AccessCardHolder(PersonLdapBack):
    """
    Module for populating an ntnuAccessCardHolder branch.  Used for the
    equictrac print system at NTNU.
    """
    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)

        self.base = base
        self.filter = filter
        self.obj_class = ('top', 'person', 'inetOrgPerson', 'ntnuAccessCardHolder')

    def get_attributes(self, obj):
        return {
            'objectClass': self.obj_class,
            'cn': obj.full_name,
            'description': "Adgangskort ved NTNU for Uniflow-utskriftsystem.",
            'sn': obj.last_name,
            'uid': self.get_uid(obj),
            'mail': obj.email,
            'ntnuAccessCardId': self.get_access_card_ids(obj),
        }

    def get_access_card_ids(self, obj):
        access_cards = set([obj.keycardid0, obj.keycardid1])
        return [card for card in access_cards if card]

###
### UnitTesting is good for you
###
class _testObject:
    def __init__(self):
        pass

class testLdapBack(unittest.TestCase):
    
    def setUp(self):
        self.lback = LdapBack()
        self.lback.begin()

    def tearDown(self):
        self.lback.close()

    def testSetup(self):
        pass

    def testBeginFails(self):
        self.assertRaises(LdapConnectionError, self.lback.begin, hostname='doesnotexist.bizz')

    def testClose(self):
        self.lback.close()

    def testAdd(self):
        user = _testObject()
        self.add(user)
        self.lback.close()

    def testUpdate(self):
        user = _testObject()
        self.update(user)
        self.lback.close()

    def testDelete(self):
        user = _testObject()
        self.delete(user)
        self.lback.close()


    # Test-cases to be added:
    # Search (find root-node from config-file)
    # Add,Update,Delete
    # sync a test-tree
    # strange characters in gecos-attribute.. 

if __name__ == "__main__":
    unittest.main()

# arch-tag: ec6c9186-9e3a-4c18-b467-a72d0d8861fc
