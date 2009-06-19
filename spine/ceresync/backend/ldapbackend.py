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
import sets

import ldap,ldif,dsml
import urllib
from ldap import modlist
from ldif import LDIFParser,LDIFWriter
from dsml import DSMLParser,DSMLWriter 

from ceresync import config
log = config.logger

import unittest
from ceresync.errors import ServerError


def ldapDict(s):
    """Oracle Internet Directory suck bigtime. if we insert with lowercase, 
    we might get camelCase back. Helperfunction for easier comparison of 
    dicts with attributes and values. This function lowercases all keys
    in a dictionary and keeps the values untouched.
    """
    for key, val in s.items():
        del s[key]
        s[key.lower()] = val
    return s

class LdapConnectionError(ServerError):
    pass

class DsmlHandler(DSMLParser):
    """Class for a DSMLv1 parser. Overrides method handle from class dsml.DSMLParser"""

    def handle(self):
        """Do something meaningful """
        pass

class LdifHandler(LDIFParser):
    """Class for LDIF records"""

class DsmlBack( DSMLParser ):
    """XML-based files. xmlns:dsml=http://www.dsml.org/DSML """
    def __init_(self,output_file=None,input_file=None,base64_attrs=None,cols=76,line_sep='\n'):
        self.output_file = output_file
        self._input_file = input_file
        self.base64_attrs = base64_attrs
        self.cols = cols
        self.line_sep = line_sep

    def handler(self,*args,**kwargs):
        pass

    def readin(self,srcfile,type="dsml"):
        """Default, the dsml.DSMLParser only wants to parse LDIF-files
        to convert it into DSML before we save it as <filenam>.dsml.
        This function will do both
        """
        pass
    
    def writeout(self):
        dsml.DSMLWriter.writeHeader()
        for record in self.records:
            dsml.DSMLWriter.writeRecord(record.dn,record.entry)
        dsml.DSMLWriter.writeFooter()

class LdifBack( object ):
    """LDIF-based files. 
    """
    def __init__(self,output_file=None, base64_attrs=None,cols=76,line_sep='\n'):
        self.output_file = output_file # or rather from a config-file or something
        self.base64_attrs = base64_attrs
        self.cols = cols
        self.line_sep = line_sep

    def readin(self,srcfile):
        self.file = srcfile
        try:
            file = open(self.file)
            self.records = ldif.ParseLDIF(file) # ldif.ParseLDIF is deprecated... re-implement later
            file.close() 
        except IOError,e:
            log.exception("An error occured while importing file: %s" % srcfile)

    def writeout(self):
        self.outfile = open(self.output_file,"w")
        for entry in self.records:
            self.outfile.write(ldif.CreateLDIF(entry[0],entry[1],self.base64_attrs,self.cols))
        self.outfile.close()
        
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

    def iso2utf(self, str):
        """ Return utf8-encoded string """
        return unicode(str, "iso-8859-1").encode("utf-8")
        
    def utf2iso(self, str):
        "Return decoded utf8-string"
        return unicode(str,"utf-8").encode("iso-8859-1")

    def begin(self, encoding, incr=False, bulk_add=True, bulk_update=True,
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

###
###
###


class PosixUser(LdapBack):
    """Stub object for representation of an account."""
    def __init__(self,conn=None,base=None,filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter
        # Need 'person' for structural-objectclass
        self.obj_class = ['top','person','posixAccount','shadowAccount'] 
        self.ignore_attr_types = []

    def add(self, obj):
        if obj.posix_uid == -1 or obj.full_name == "":
            log.debug("Ignoring %s with uid=%d and full_name='%s'", obj.name,
                      obj.posix_uid, obj.full_name)
            return
        super(PosixUser, self).add(obj)


    def get_attributes(self,obj):
        """Convert Account-object to map ldap-attributes"""
        s = {}
        s['objectClass']   = self.obj_class
        s['cn']            = ["%s"     %  self.iso2utf(obj.gecos)]
        s['sn']            = ["%s"     %  self.iso2utf(obj.gecos).split(" ").pop()]
        s['uid']           = ["%s"     %  obj.name]
        s['gecos']         = ["%s"     %  self.gecos(obj.gecos)]
        s['uidNumber']     = ["%s"     %  obj.posix_uid]
        s['gidNumber']     = ["%s"     %  obj.posix_gid]
        s['loginShell']    = ["%s"     %  obj.shell]
        s['userPassword']  = ["{%s}%s" % (config.get('ldap','hash').upper(), obj.passwd)]
        s['homeDirectory'] = ["%s"     %  obj.homedir]
        return s

    def gecos(self,s,default=1):
        # Taken from cerebrum/contrib/generate_ldif.py and then modified.
        # Maybe use latin1_to_iso646_60 from Cerebrum.utils?
        """  Convert special chars to 7bit ascii for gecos-attribute. """
        if default == 1:
            #translate = {'Æ' : 'Ae', 'æ' : 'ae', 'Å' : 'Aa', 'å' : 'aa','Ø' : 'Oe','ø' : 'oe' }
            translate = dict(zip(
                'ÆØÅæø¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäçèéêëìíîïñòóôõöùúûüýÿ{[}]|¦\\¨­¯´',
                'AOAaooaAAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuuyyaAaAooO"--\''))
        elif default == 2:
            translate = {'Æ' : 'A', 'æ' : 'a', 'Å' : 'A', 'å' : 'a','Ø' : 'O','ø' : 'o' }
        elif default == 3:
            translate = {'Æ' : '[', 'æ' : '{', 'Å' : ']', 'å' : '}','Ø' : '\\','ø' : '|' }
        s = string.join(map(lambda x:translate.get(x, x), s), '')
        return s

    def get_dn(self,obj):
        # Maybe generalize this to LdapBack instead
        return "uid=" + obj.name + "," + self.base

class PosixGroup(LdapBack):
    '''Abstraction of a group of accounts'''
    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter
        self.obj_class = ['top','posixGroup']
        # posixGroup supports attribute memberUid, which is multivalued (i.e. can be a list, or string)
        self.ignore_attr_types = []

    def get_attributes(self,obj):
        s = {}
        s['objectClass']     = self.obj_class
        s['cn']              = ["%s" % obj.name]
        s['gidNumber']       = ["%s" % obj.posix_gid]
        if (len(obj.members) > 0):
            s['memberUid']   = obj.members
        #if (len(obj.description) > 0):
        #    s['description'] = obj.description
        return s

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + self.base

class NetGroup(LdapBack):
    ''' '''
    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter
        self.obj_class = ('top', 'nisNetGroup')
        self.ignore_attr_types = []

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + self.base

    def get_attributes(self,obj):
        s = {}
        s['objectClass']       = self.obj_class
        s['cn']                = [obj.name]
        s['nisNetGroupTriple'] = [] # Which attribute to fetch? FIXME
        s['memberNisNetgroup'] = [] # Which attribute to fetch? FIXME
        return s


class Person(LdapBack):
    def __init__(self, base="ou=People,dc=ntnu,dc=no", filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.base = base
        self.filter = filter
        self.obj_class = ['top','person','organizationalPerson','inetOrgPerson','eduPerson','norEduPerson','ntnuPerson']
        self.ignore_attr_types = []

    def add(self, obj):
        if obj.primary_account == -1:
            log.debug("Ignoring %s with primary_account=%d", obj.full_name, 
                      obj.primary_account)
            return
        super(Person, self).add(obj)

    def get_dn(self,obj):
        return "uid=" + obj.primary_account_name + "," + self.base

    def get_attributes(self,obj):
        s = {}
        s['objectClass']            = self.obj_class
        s['cn']                     = ["%s"     %  self.iso2utf(obj.full_name)]
        s['sn']                     = ["%s"     %  self.iso2utf(obj.last_name)]
        s['givenName']              = ["%s"     %  self.iso2utf(obj.first_name)]
        s['uid']                    = ["%s"     %  obj.primary_account_name]
        # FIXME: Must look up in primary account to get password
        s['userPassword']           = ["{%s}%s" % (config.get('ldap','hash').upper(), obj.primary_account_passwd)]
        #s['userPassword']           = ["Ikkepassord"] #["{%s}%s" % (config.get('ldap','hash').upper(), obj.passwd)]
        s['eduPersonOrgDn']         = ["dc=ntnu,dc=no"] #Should maybe be in config?

        #must remove duplicate values
        affiliations = []
        for aff in obj.affiliations:
            if aff == 'STUDENT':
                affiliations.extend(['student','member'])
            elif aff == 'ANSATT':
                affiliations.extend(['employee','member'])
            elif aff == 'TILKNYTTET':
                affiliations.extend(['affiliate'])
            elif aff == 'ALUMNI':
                affiliations.extend(['alum'])
            else:
                log.warn("Unknown affiliation: %s" % aff)
        s['eduPersonAffiliation']   = {}.fromkeys(affiliations).keys() 

        # Expecting birth_date from spine on the form "%Y-%m-%d 00:00:00.00"
        # Ldap wants the form "%Y%m%d".
        # FIXME: Should probably use datetime or mx.DateTime
        birth_date= obj.birth_date.split()[0].replace('-','')
        s['norEduPersonBirthDate']  = ["%s"     %  birth_date]
        s['norEduPersonNIN']        = ["%s"     %  obj.nin] # Norwegian "Birth number" / SSN 
        s['eduPersonPrincipalName'] = ["%s@%s"  %  (obj.primary_account_name, config.get('ldap','eduperson_realm'))]
        if 'ANSATT' in obj.affiliations:
            s['title'] = ['ansatt']
        elif 'STUDENT' in obj.affiliations:
            s['title'] = ['student']
        elif 'TILKNYTTET' in obj.affiliations:
            s['title'] = ['tilknyttet']
        elif 'ALUMNI' in obj.affiliations:
            s['title'] = ['alumnus']
        else:
            s['title'] = ["Ikke title enno"] 
        if obj.work_title != '':
            pass
            #print "%s"     %  obj.work_title
        #s['title']                  = ["Ikke title enno"] #["%s"     %  obj.work_title]
        s['mail']                   = ["%s"     %  obj.email]
        return s

class Alias:
    """ Mail aliases, for setups that store additional mailinglists and personal aliases in ldap.
    rfc822 mail address of group member(s)
    Depends on rfc822-MailMember.schema

    Decide which schema you want to follow, and change objectclass-chain and attribute-names.
    Some prefer to use attribute mailDrop, mailHost etc from ISPEnv2.schema
    """
    def __init__(self, base=None, filter='(objectClass=*)'):
        self.base = base
        self.filter = filter
        self.obj_class = ('top','nisMailAlias')

    def get_dn(self,obj):
        return "cn=" + obj.name + "," + self.base

    def get_attributes(self,obj):
        s = {}
        s['objectClass']      = self.obj_class
        s['cn']               = [obj.name]
        s['rfc822MailMember'] = obj.membernames()
        return s

class OU(LdapBack):
    """ OrganizationalUnit, where people work or students follow studyprograms.
    Needs name,id and parent as minimum.
    """

    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)
        self.ou_dict = {}
        self.base = base
        self.filter = filter
        self.obj_class = ['top','organizationalUnit', 'norEduOrgUnit']
        self.processed= []
        self.on_hold= []

    def add(self, obj):
        dn= self.get_dn(obj)
        if dn == self.base:
            return
        elif dn in self.processed:
            log.warning("Entry with the same name already processed: %s", dn)
            return
        elif dn == None:
            log.debug("Parent of '%s' doesn't exist yet. On hold.",
                      obj.short_name)
            return
        self.processed.append(dn)
        super(OU, self).add(obj)

    def get_dn(self,obj):
        base = self.base
        filter = "(norEduOrgUnitUniqueIdentifier=%s)" % obj.parent_stedkode 
        if self.ou_dict.has_key(obj.parent_stedkode):
            parentdn = self.ou_dict[obj.parent_stedkode]
        elif obj.parent_stedkode == '':           # root-node
            self.ou_dict[obj.stedkode]= self.base
            return self.base
        else:
            found= self.search(base=base,filterstr=filter)
            if found:
                parentdn= found[0][0]
            else:
                self.on_hold.append(obj)
                return None

        dn = "ou=%s,%s" % (self.iso2utf(obj.short_name),parentdn,)
        self.ou_dict[obj.stedkode] = dn # Local cache to speed things up.. 
        return dn

    def get_attributes(self,obj):
        #FIXME: add support for storing unit-id,parent-id and rootnode-id
        s = {}
        s['objectClass']               = self.obj_class
        s['ou']                        = [self.iso2utf(obj.short_name)]
        s['cn']                        = [self.iso2utf(obj.display_name)]
        s['norEduOrgUnitUniqueIdentifier']= [obj.stedkode]
        #s['norEduOrgAcronym'] = obj.acronyms
        return s

    def close(self):
        while self.on_hold:
            obj= self.on_hold.pop(0)
            self.add(obj)
        super(OU,self).close()


class OracleCalendar(LdapBack):
    """
    """
    def __init__(self, base=None, filter='(objectClass=*)'):
        LdapBack.__init__(self)
        if base == None:
            self.base = config.get("ldap","calendar_base")
        else:
            self.base = base
        self.filter = filter
        self.obj_class = ('top','inetOrgPerson', 'shadowAccount', 'ctCalUser')
        self.obj_class = ('top','inetOrgPerson', 'shadowAccount')

    def get_dn(self,obj):
        return "uid=" + obj.name + "," + self.base

    def get_attributes(self,obj):
        names = obj.full_name.split(" ")
        sn = names.pop()
        givenName = " ".join(names)
        s = {}
        s['objectClass']      = self.obj_class
        s['uid']              = [obj.name]
        s['cn']               = [self.iso2utf(obj.gecos)]
        s['sn']               = [self.iso2utf(sn)]
        s['givenName']        = [self.iso2utf(givenName)]
        s['userPassword']     = ["{%s}%s" % (config.get('ldap','hash').upper(), obj.passwd)]
        return s



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
