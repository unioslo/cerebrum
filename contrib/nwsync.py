#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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

import sys
import time
import pickle
import re

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
import nwutils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ou = OU.OU(db)
ent_name = Entity.EntityName(db)
group = Group.Group(db)
account = Account.Account(db)
cl = CLHandler.CLHandler(db)
clco = Factory.get('CLConstants')(db)

delete_users = 0
delete_groups = 0
domainusers = []
#For test,
max_nmbr_users = 10000


def create_ou(iso_ou):
    utf8name = unicode(iso_ou, 'iso-8859-1').encode('utf-8')
    attrs = []
    # first attr is mandatory in eDirectory
    attrs.append( ("objectClass", "OrganizationalUnit") )
    attrs.append( ("description","Cerebrum-OU") )
    try:
        LDAPHandle.CreateObject('%s' % utf8name, attrs)
        print "INFO:created %s\n" % utf8name
    except:
        print "Failed creating ",utf8name


def full_ou_sync():

    #Will not delete OUs only create new ones.
    print 'INFO: Starting full_ou_sync at', nwutils.now()
    OUs = []

    eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=organizationalUnit)')
    for nextou in eDir:
#        try:
#            LDAPHandle.DeleteObject(nextou[0])
#        except:
#            pass
#        continue

        iso_ou = unicode(nextou[0],'utf-8').encode('iso-8859-1')
        OUs.append(iso_ou)
#    return
     
    def find_children(parent_id,parent_acro):

        ou.clear()
        ou.find(parent_id)
        chldrn = ou.list_children(co.perspective_fs)

        for child in chldrn:
            name=parent_acro
            ou.clear()
            ou.find(child['ou_id'])
            if ou.acronym:
                name = 'ou=%s,%s' % (ou.acronym, parent_acro)
                if not name in OUs:
                    create_ou(name)
            chldrn = ou.list_children(co.perspective_fs)
            find_children(child['ou_id'], name)
    if cereconf.NW_LDAP_USEOUS:
        ou.clear()
        root_id = cereconf.NW_CERE_ROOT_OU_ID # ou.root()
        children = find_children(root_id, cereconf.NW_LDAP_ROOT)
    else:
 #       if not 'ou=stud,ou=HiST3,ou=user,o=NOVELL' in OUs:
 #           create_ou('ou=stud,ou=HiST3,ou=user,o=NOVELL')
 #       if not 'ou=ans,ou=HiST3,ou=user,o=NOVELL' in OUs:
 #           create_ou('ou=ans,ou=HiST3,ou=user,o=NOVELL')
        if not cereconf.NW_LDAP_STUDOU in OUs:
            create_ou(cereconf.NW_LDAP_STUDOU)
        if not cereconf.NW_LDAP_ANSOU in OUs:
            create_ou(cereconf.NW_LDAP_ANSOU)
        if not 'ou=%s,%s' % (cereconf.NW_LOST_AND_FOUND,cereconf.NW_LDAP_ROOT) in OUs:
            create_ou('ou=%s,%s' % (cereconf.NW_LOST_AND_FOUND,cereconf.NW_LDAP_ROOT))


def full_user_sync(spread_str):
    """Checking each user in eDirctory, and compare with Cerebrum information."""
    # TODO:Mangler en mer stabil sjekk på hvilken OU brukeren hører hjemme
    # utfra cerebrum
        
    global domainusers
    print 'INFO: Starting full_user_sync at', nwutils.now()
    entity = Entity.Entity(db)
    users = {}
    
    spreadusers = get_objects('user', spread_str)
    passwords = db.get_log_events_date(type=(int(co.account_password),)) 
    
    print "INFO: Base LDAP OU: ", cereconf.NW_LDAP_ROOT
    eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=user)')
    for (eDirUsr, eDirUsrAttr) in eDir:
        # This better be created by us if we should touch it
        # Every object in eDirectory created by us has Cerebrum as first 8 letters
        # in description attribute
        print eDirUsr
        if not nwutils.touchable(eDirUsrAttr):
           continue
        domainusers.append(eDirUsr)
        isousr = unicode(eDirUsrAttr['cn'][0],'utf-8').encode('iso-8859-1' )
        # Uncomment to empty eDir for all users with 'Cerebrum' in desc.
        # They will flow into eDir again later in this func
        if (eDirUsr != cereconf.NW_ADMINUSER):
           print "Sletter", eDirUsr
           LDAPHandle.DeleteObject(eDirUsr)
           continue
        if isousr in spreadusers:
            user_id = spreadusers[isousr]
            
            # Finn brukerens nyeste passord, i klartekst.
            pwd_rows = [row for row in passwords
                    if row.subject_entity == user_id[0]]
            try:
               pwd = pickle.loads(pwd_rows[-1].change_params)['password']
            except:
                type, value, tb = sys.exc_info()
                print "Aiee! %s %s" % (str(type), str(value))
                pwd = ''
                continue

            (g_name,s_name,account_disable,home_dir, aff, ext_id) = nwutils.get_user_info(user_id[0],eDirUsrAttr['cn'][0], spread=int(getattr(co, spread_str)))
            utf8_ou = nwutils.get_utf8_ou('user', user_id[1], aff)
            utf8_dn = unicode('cn=%s,' % isousr, 'iso-8859-1').encode('utf-8') + utf8_ou
            if utf8_dn != eDirUsr:
            # MOVE
                print "Move: %s to %s" % (eDirUsr, user_id[1])
                try:
                    utf8_dn = "%s,%s" % (eDirUsrAttr['cn'][0], utf8_ou)
                    LDAPHandle.RenameObject(eDirUsr, utf8_dn)                    
                except:    
                    print "WARNING: move user failed, ", eDirUsr, 'to', user_id[1]
            # UPDATE
            g_name = unicode(g_name, 'iso-8859-1').encode('utf-8')
            s_name = unicode(s_name, 'iso-8859-1').encode('utf-8')

            if account_disable is '1':
                account_disable = 'TRUE'
            else:
                account_disable = 'FALSE'
                
            print eDirUsrAttr
            attrs = []
            fullName = unicode(g_name, 'iso-8859-1').encode('utf-8') +" "+ unicode(s_name, 'iso-8859-1').encode('utf-8')
            op = nwutils.op_check(eDirUsrAttr, 'fullName', fullName)
            if op is not None:
                attrs.append( ("fullName",  fullName) )
                attrs.append( (op, "givenName", g_name) )
                attrs.append( (op, "sn", s_name) )
            op = nwutils.op_check(eDirUsrAttr, 'loginDisabled', account_disable)
            if op is not None:
                attrs.append( (op, "loginDisabled", account_disable) )
            op = nwutils.op_check(eDirUsrAttr, 'homeDirectory', home_dir)
            if op is not None:
                attrs.append( (op, "ndsHomeDirectory", home_dir) )
            op = nwutils.op_check(eDirUsrAttr, 'passwordAllowChange', cereconf.NW_CAN_CHANGE_PW)
            if op is not None:
                attrs.append( (op, "passwordAllowChange", cereconf.NW_CAN_CHANGE_PW) )
#            attrs.append( ( ldap.MOD_DELETE, "userPassword", ) )
#            attrs.append( ( ldap.MOD_ADD, "userPassword", pwd) )
            try:
                LDAPHandle.RawModifyAttributes(utf8_dn, attrs)
            except:
                print "WARNING: Error updating attributes for", isousr
            del spreadusers[isousr]
        else:
            if delete_users:
                try:
                    LDAPHandle.DeleteObject(eDirUsr)
                except:
                    print "WARNING: Error deleting", isousr
            else:
                print "WARNING: Move deleted users not implemented"
                # Move it to somewhere ??
#                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(fields[1]):
#                    sock.send('ALTRUSR&%s/%s&dis&1\n' % ( cereconf.AD_DOMAIN, fields[3]))
#                    if sock.read() != ['210 OK']:
#                        print 'WARNING: Error disabling account', fields[3]
#                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (fields[1], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
#                    if sock.read() != ['210 OK']:
#                        print 'WARNING: Error moving, ', fields[3], 'to', cereconf.AD_LOST_AND_FOUND                   
    
    for user in spreadusers:
        # The remaining accounts in the list should be created.
        user_id = spreadusers[user]

        # Finn brukerens nyeste passord, i klartekst.
        pwd_rows = [row for row in passwords
                if row.subject_entity == user_id[0]]
        try:
            pwd = pickle.loads(pwd_rows[-1].change_params)['password']
        except:
            type, value, tb = sys.exc_info()
            print "Aiee! %s %s" % (str(type), str(value))
            pwd = ''
            continue

        (g_name,s_name,account_disable,home_dir,aff,ext_id) = nwutils.get_user_info(user_id[0], user, spread=int(getattr(co, spread_str)))
        utf8_ou = nwutils.get_ldap_usr_ou(user_id[1], aff)
        utf8_dn = unicode('cn=%s,' % user, 'iso-8859-1').encode('utf-8') + utf8_ou
        attrs = []
        # ObjectClass and sn are mandatory on person in eDirectory
        attrs.append( ("ObjectClass", "user" ) )
        attrs.append( ("givenName", unicode(g_name, 'iso-8859-1').encode('utf-8') ) )
        attrs.append( ("sn", unicode(s_name, 'iso-8859-1').encode('utf-8') ) )
        fullName = unicode(g_name, 'iso-8859-1').encode('utf-8') +" "+ unicode(s_name, 'iso-8859-1').encode('utf-8')
        attrs.append( ("fullName",  fullName) )
        utf8_home = unicode("cn=DEVNET-PUBLIC_VOL1,o=NOVELL#0#USER\\HiST3", 'iso-8859-1').encode('utf-8')
 #       attrs.append( ("ndsHomeDirectory",  utf8_home) )
        attrs.append( ("description","Cerebrum;%d;%s" % (ext_id, nwutils.now()) ) )
        attrs.append( ("passwordAllowChange", cereconf.NW_CAN_CHANGE_PW) )
        attrs.append( ("loginDisabled", account_disable) )
        passwd = unicode("ÆøÅS0mething", 'iso-8859-1').encode('utf-8')
        attrs.append( ("userPassword", passwd) )
        try:                
            LDAPHandle.CreateObject(utf8_dn, attrs)
            print "INFO:New user %s" % utf8_dn
            domainusers.append(utf8_dn)
        except:
            type, value, tb = sys.exc_info()
            print "ERROR: %s %s" % (str(type), str(value))
            print "WARNING: Failed creating", utf8_dn
 

# If we run grp_sync without user_sync first
def gen_domain_users():

    global domainusers
    try:
        eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=user)')
        for (eDirUsr, eDirUsrAttr) in eDir:
            domainusers.append(eDirUsr)
    except:
        print "WARNING: Could not get users from ", cereconf.NW_LDAP_ROOT



#helper to clean up in NW-LDAP while testing
def del_our_groups():
    eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=group)')
 
    for (eDirGrp, eDirGrpAttr) in eDir:
        print "Deleting eDirectory Group:", eDirGrp
        if not nwutil.touchable(eDirGrpAttr):
           continue
        LDAPHandle.DeleteObject(eDirGrp)
   
   
    
def full_group_sync(spread_str):
    """Checking each group in eDirectory, and compare with Cerebrum"""
    print 'INFO: Starting full_group_sync at', nwutils.now()
    global domainusers
    adgroups = {}
    spreadgroups = get_objects('group', spread_str)
    eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=group)')
 
    for (eDirGrp, eDirGrpAttr) in eDir:
        print "eDirectory Group:", eDirGrp
        if not nwutil.touchable(eDirGrpAttr):
           continue
        isogrp = unicode(eDirGrpAttr['cn'][0],'utf-8').encode('iso-8859-1' )
        if isogrp in spreadgroups:
            grp_id = spreadgroups[isogrp]
            print 'INFO: updating group:', isogrp
            utfcrbm_ou = unicode(grp_id[1], 'iso-8859-1').encode('utf-8')    
            utf8_dn = unicode('cn=%s,%s' % (isogrp, grp_id[1]), 'iso-8859-1').encode('utf-8')
            # Should we move it?
            if utf8_dn != eDirGrp:
                try:
                    LDAPHandle.RenameObject(eDirGrp, utf8_dn)                    
                except:    
                    print "WARNING: move group failed, ", isogrp, 'to', grp_id[1]
            # Figure who (DN) is in this group (Cerebrum)
            group.clear()
            for row in group.list_affiliations(group_id=grp_id[0]):
                affiliation = row['affiliation']
            group.find(grp_id[0])

            memblist = []
            for grpmemb in group.get_members():
                try:
                    ent_name.clear()
                    ent_name.find(grpmemb)            
                    if ent_name.has_spread(int(getattr(co, spread_str))):
                        name = ent_name.get_name(int(co.account_namespace))
                        if not name in memblist:
                            ou_id = nwutil.get_primary_ou(ent_name.entity_id)
                            crbrm_ou = nwutil.get_crbrm_ou(ou_id)
                            memblist.append("cn=%s,%s" % (name, utfcrbm_ou))
                except Errors.NotFoundError:
                    print "WARNING: Could not find groupmemb,", grpmemb

            eDirMembrs = eDirGrpAttr['members']
            
            # Remove members
            for membr in eDirMembrs:
                isomembr = unicode(membr,'utf-8').encode('iso-8859-1' )
                if isomembr in memblist:
                    memblist.remove(isomembr)
                else:
                    try:
                        attrs = []
                        attrs.append( ("member", membr) )
                        LDAPHandle.DeleteAttributes(eDirGrp, attrs)                    
                    except:    
                        print "WARNING: remove member from %s failed, " % isogrp
            # Add members
            for memb in memblist:
                utf8_membr = unicode(memb, 'iso-8859-1').encode('utf-8')
                if utf8_membr in domainusers:
                    try:
                        attrs = []
                        attrs.append( ("member", utf8_mebr) )
                        LDAPHandle.AddAttributes(eDirGrp, attrs)                    
                    except:    
                        print "WARNING: Failed add %s to %s, " % (memb, isogrp)
                else:
                    print "WARNING:groupmember",memb,"in group",isogrp,"not in AD"
            del spreadgroups[isogrp]
        # eDirectory group not found in Cerebrum
        else:
            if delete_groups:
                try:
                    LDAPHandle.DeleteObject(eDirGrp)
                except:
                    print 'WARNING: Error deleting ', isogrp
            elif cereconf.NW_LOST_AND_FOUND not in nwutils.get_nw_ou(eDirGrp):
                utf8_dn = unicode('cn=%s,%s,%s' % (isogrp, cereconf.NW_LOST_AND_FOUND, cereconf.NW_LDAP_ROOT), 'iso-8859-1').encode('utf-8')
                try:
                    LDAPHandle.RenameObject(eDirGrp, utf8_dn)                    
                except:    
                    print "WARNING: move group failed, ", eDirGrp, 'to', cereconf.NW_LOST_AND_FOUND
            else:
                print "INFO: A deleted group is pending purge in %s,%s" % (cereconf.NW_LOST_AND_FOUND, cereconf.NW_LDAP_ROOT)
    for grp in spreadgroups:
        # The remaining is new groups and should be created.
        attrs = []
        attrs.append( ("ObjectClass", "group") )
        attrs.append( ("description", "Cerebrum-group") )
        if grp.find('stud') != -1:
            aff = co.affiliation_student
        else:
            aff = co.affiliation_ansatt    
        utf8_ou = nwutils.get_utf8_ou('group', grp[1], aff)
        utf8_dn = "cn=%s,%s" % (unicode(grp, 'iso-8859-1').encode('utf-8'), utf8_ou)

#        utf8_dn = unicode('cn=%s,%s' % (grp, spreadgroups[grp][1]), 'iso-8859-1').encode('utf-8')
        try:  
            LDAPHandle.CreateObject(utf8_dn, attrs)
        except:
            print "WARNING: Failed creating group ", utf8_dn
            continue
        print "Created ",utf8_dn
        group.clear()
        group.find(spreadgroups[grp][0])
        for grpmemb in group.get_members():
            try:
                ent_name.clear()
                ent_name.find(grpmemb)
                name = ent_name.get_name(int(co.account_namespace))
                utf8membr_ou = nwutils.get_utf8_ou('user', grpmemb, aff)
                utf8membr_dn = unicode('cn=%s,' % name, 'iso-8859-1').encode('utf-8') + utf8membr_ou
                if utf8membr_dn in domainusers:
                    print 'INFO:Add', utf8membr_dn, 'to', utf8_dn
                    attrs = []
                    attrs.append( ("member", utf8membr_dn) )
                    try:
                        LDAPHandle.AddAttributes(utf8_dn, attrs)
                    except:    
                        print 'WARNING: Failed add', utf8membr_dn, 'to', utf8_dn
                        continue
                    attrs = []
                    attrs.append( ("groupMembership", utf8_dn) )
                    try:
                        LDAPHandle.AddAttributes(utf8membr_dn, attrs)
                    except:    
                        print 'WARNING: Failed giving', utf8membr_dn, 'group membership to', utf8_dn
                        continue
                    attrs = []
                    attrs.append( ("securityEquals", utf8_dn) )
                    try:
                        LDAPHandle.AddAttributes(utf8membr_dn, attrs)
                    except:    
                        print 'WARNING: Failed giving', utf8membr_dn, 'security equal to', utf8_dn
                        continue
                else:
                    print 'WARNING: Group member', utf8membr_dn, 'does not exist in eDirectory'
            except Errors.NotFoundError:
                print "WARNING: Could not find group member ",grpmemb," in db"






def get_args():
    global delete_users
    global delete_groups
    for arrrgh in sys.argv:
        if arrrgh == '--delete_users':
            delete_users = 1
        elif arrrgh == '--delete_groups':
            delete_groups = 1


def get_objects(entity_type, spread_str):
    #get all objects with spread 'spread_str', in a hash identified by name with id and ou.
    global max_nmbr_users
    entity = Entity.Entity(db)
    grp_postfix = grp_prefix = ''
    spread_id = int(getattr(co, spread_str))
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
    else:
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.NW_GROUP_POSTFIX
        grp_prefix = cereconf.NW_GROUP_PREFIX
    ulist = {}
    count = 0    

    ou.clear()
    ou.find(cereconf.NW_CERE_ROOT_OU_ID)
    ourootname='ou=%s' % ou.acronym
    
    for row in ent_name.list_all_with_spread(spread_id):
        pri_ou = 0
        if count >= max_nmbr_users: break
        id = row['entity_id']
        ent_name.clear()
        ent_name.find(id)
        if ent_name.entity_type != e_type: continue
        name = ent_name.get_name(namespace)
        try:
            pri_ou = nwutils.get_primary_ou(id)
        except Errors.NotFoundError:
            print "Unexpected error /me thinks"
        if not pri_ou:
            print "WARNING: no primary OU found for",name,"in namespace",namespace
            pri_ou = cereconf.NW_DEFAULT_OU_ID
        count = count+1
        crbrm_ou = nwutils.id_to_ou_path(pri_ou ,ourootname)
        id_and_ou = id, crbrm_ou
        obj_name = '%s%s%s' % (grp_prefix, name, grp_postfix)
        ulist[obj_name]=id_and_ou    
        
    print "INFO: Found %s nmbr of objects" % (count)
    return ulist



                    
if __name__ == '__main__':
    print 'INFO: Starting Novell eDirectory full sync at', nwutils.now()
    LDAPHandle = nwutils.LDAPConnection(cereconf.NW_LDAPHOST, cereconf.NW_LDAPPORT,
                                    binddn=cereconf.NW_ADMINUSER, password=cereconf.NW_PASSWORD, scope='sub')
#    LDAPHandle = nwutils.LDAPConnection(cereconf.NW_LDAPHOST, cereconf.NW_LDAPPORT,
#                                    "", "", scope='sub')
#    arg = get_args()
#    full_ou_sync()
    full_user_sync('spread_HiST_nds_stud_aft')
#    gen_domain_users()
#    del_our_groups()
    full_group_sync('spread_HiST_nds_stud_aft_group')

# arch-tag: 765ec9d3-4ebe-4ee8-95fb-01edd32c09c4
