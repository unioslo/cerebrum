#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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
import re

import cerebrum_path
import cereconf
import nwutils
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
ent_name = Entity.EntityName(db)
group = Factory.get('Group')(db)
account = Factory.get('Account')(db)

delete_users = 1
delete_groups = 0
domainusers = []
#For test,
max_nmbr_users = 100

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
        
        OUs.append(nextou[0])
        iso_ou = unicode(nextou[0],'utf-8').encode('iso-8859-1')
    if not 'ou=%s,%s' % (cereconf.NW_LOST_AND_FOUND,cereconf.NW_LDAP_ROOT) in OUs:
        utf8name = unicode('%s,%s' % (cereconf.NW_LOST_AND_FOUND,cereconf.NW_LDAP_ROOT),
                            'iso-8859-1').encode('utf-8')
        attrs = []
        # first attr is mandatory in eDirectory
        attrs.append( ("ObjectClass", "OrganizationalUnit") )
        attrs.append( ("Description","Cerebrum-OU") )
        try:
            LDAPHandle.CreateObject('%s' % utf8name, attrs)
        except:
            print "Failed creating ",utf8name
        
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
                name_utf8 = unicode(name, 'iso-8859-1').encode('utf-8')
                if not name_utf8.replace('/','\/') in OUs:
                    print "INFO:creating %s\n" % name
                    attrs = []
                    # first attr is mandatory in eDirectory
                    attrs.append( ("ObjectClass", "OrganizationalUnit") )
                    attrs.append( ("Description","Cerebrum-OU") )
                    try:
                        LDAPHandle.CreateObject('%s' % name_utf8, attrs)
                    except:
                        print "Failed creating ",name
            chldrn = ou.list_children(co.perspective_fs)
            find_children(child['ou_id'], name)

    ou.clear()
    root_id = cereconf.NW_CERE_ROOT_OU_ID # ou.root()
    children = find_children(root_id, cereconf.NW_LDAP_ROOT)


def full_user_sync(spread_str):
    """Checking each user in eDirctory, and compare with Cerebrum information."""
    # TODO:Mangler en mer stabil sjekk på hvilken OU brukeren hører hjemme
    # utfra cerebrum
        
    global domainusers
    print 'INFO: Starting full_user_sync at', nwutils.now()
    entity = Entity.Entity(db)
    users = {}
#    spread_code = int(getattr(co, 'spread_HiST_nds_stud_aft'))
#    rows = entity.list_all_with_spread(spread_code)

    # All changes we want to 'spread' (mv to quick-sync)
#    changelog = db.get_log_events(start_id=0, max_id=None, 
#                     types=(co.account_password,co.person_name_mod,
#                            co.spread_add)) 
    
    spreadusers = get_objects('user', spread_str)

    eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=user)')
    for (eDirUsr, eDirUsrAttr) in eDir:
        # This better be created by us if we should touch it
        # Every object in eDirectory created by us has Cerebrum as first 8 letters
        # in description attribute
        if not touchable(eDirUsrAttr):
           continue
        domainusers.append(eDirUsr)
        isousr = unicode(eDirUsrAttr['cn'][0],'utf-8').encode('iso-8859-1' )
        # Uncomment to empty eDir for all users with 'Cerebrum' in desc.
        # They will flow into eDir again later in this func
        # LDAPHandle.DeleteObject(eDirUsr)
        # continue
        if isousr in spreadusers:
            user_id = spreadusers[isousr]
            utfcrbm_ou = unicode(user_id[1], 'iso-8859-1').encode('utf-8')
            utf8_dn = unicode('cn=%s,%s' % (isousr, user_id[1]), 'iso-8859-1').encode('utf-8')

            if 'cn=%s,%s' % (isousr,utfcrbm_ou) != eDirUsr:
                # MOVE
                print "Move: %s to %s" % (eDirUsr, user_id[1])
                try:
                    utf8_dn = "%s,%s" % (eDirUsrAttr['cn'][0], utfcrbm_ou)
                    LDAPHandle.RenameObject(eDirUsr, utf8_dn)                    
                except:    
                    print "WARNING: move user failed, ", eDirUsr, 'to', user_id[1]
            # UPDATE
            (g_name,s_name,account_disable,home_dir) = nwutils.get_user_info(user_id[0],eDirUsrAttr['cn'][0])
            g_name = unicode(g_name, 'iso-8859-1').encode('utf-8')
            s_name = unicode(s_name, 'iso-8859-1').encode('utf-8')

            if account_disable is '1':
                account_disable = 'TRUE'
            else:
                account_disable = 'FALSE'
                
            print eDirUsrAttr
            attrs = []
            op = nwutils.op_check(eDirUsrAttr, 'givenName', g_name)
            if op is not None:
                attrs.append( (op, "givenName", g_name) )
            op = nwutils.op_check(eDirUsrAttr, 'sn', s_name)
            if op is not None:
                attrs.append( (op, "sn", s_name) )
            op = nwutils.op_check(eDirUsrAttr, 'loginDisabled', account_disable)
            if op is not None:
                attrs.append( (op, "loginDisabled", account_disable) )
            op = nwutils.op_check(eDirUsrAttr, 'homeDirectory', home_dir)
            if op is not None:
                attrs.append( (op, "homeDirectory", home_dir) )
            op = nwutils.op_check(eDirUsrAttr, 'passwordAllowChange', cereconf.NW_CAN_CHANGE_PW)
            if op is not None:
                attrs.append( (op, "passwordAllowChange", cereconf.NW_CAN_CHANGE_PW) )

            if attrs:
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
        print "\nINFO:creating %s" % user
        utf8_dn = unicode('cn=%s,%s' % (user, user_id[1]), 'iso-8859-1').encode('utf-8')
        
        (g_name,s_name,account_disable,home_dir) = nwutils.get_user_info(user_id[0],user)
        attrs = []
        # ObjectClass and sn are mandatory on person in eDirectory
        attrs.append( ("ObjectClass", "user" ) )
        attrs.append( ("givenName", unicode(g_name, 'iso-8859-1').encode('utf-8') ) )
        attrs.append( ("sn", unicode(s_name, 'iso-8859-1').encode('utf-8') ) )
        attrs.append( ("homeDirectory", home_dir ) )
        attrs.append( ("description","Cerebrum-managed") )
        attrs.append( ("passwordAllowChange", cereconf.NW_CAN_CHANGE_PW) )
        attrs.append( ("PasswordExpire", cereconf.NW_PASSWORD_EXPIRE) )
        attrs.append( ("loginDisabled", account_disable) )
        attrs.append( ("userPassword", "muuuhhhhaaaaaa") )
        try:                
            LDAPHandle.CreateObject(utf8_dn, attrs)
            domainusers.append(utf8_dn)
        except:
            print "WARNING: Failed creating ", user_id[0]
 

# If we run grp_sync without user_sync first
def gen_domain_users():

    global domainusers
    try:
        eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=user)')
        for (eDirUsr, eDirUsrAttr) in eDir:
            domainusers.append(eDirUsr)
    except:
        print "WARNING: Could not get users from ", cereconf.NW_LDAP_ROOT



#helper to clean up in AD-LDAP while testing
def del_our_groups():
    eDir = LDAPHandle.GetObjects(cereconf.NW_LDAP_ROOT, '(objectclass=group)')
 
    for (eDirGrp, eDirGrpAttr) in eDir:
        print "Deleting eDirectory Group:", eDirGrp
        if not touchable(eDirGrpAttr):
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
        if not touchable(eDirGrpAttr):
           continue
        print "Our: ", eDirGrp
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
            group.find(grp_id[0])
            memblist = []
            for grpmemb in group.get_members():
                try:
                    ent_name.clear()
                    ent_name.find(grpmemb)            
                    if ent_name.has_spread(int(getattr(co, spread_str))):
                        name = ent_name.get_name(int(co.account_namespace))
                        if not name in memblist:
                            ou_id = nwutil.get_primary_ou(ent_name.entity_id, co.account_namespace)
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
        attrs.append( ("description", "Cerebrum") )
        utf8_dn = unicode('cn=%s,%s' % (grp, spreadgroups[grp][1]), 'iso-8859-1').encode('utf-8')
        try:  
            LDAPHandle.CreateObject(utf8_dn, attrs)
        except:
            print "WARNING: Failed creating group", grp
            continue
        print "Created ",grp,"in ", spreadgroups[grp][1]
        group.clear()
        group.find(spreadgroups[grp][0])
        for grpmemb in group.get_members():
            try:
                ent_name.clear()
                ent_name.find(grpmemb)
                name = ent_name.get_name(int(co.account_namespace))
                try:
                    ou_id = nwutils.get_primary_ou(ent_name.entity_id, co.account_namespace)
                    crbrm_ou = nwutils.get_crbrm_ou(ou_id)
                except:
                    print "WARNING: Could not get primary OU for %s(%d)" % (name, grpmemb)
                    continue
                utf8membr_dn = unicode('cn=%s,%s' % (name, spreadgroups[grp][1]), 'iso-8859-1').encode('utf-8')
                if utf8membr_dn in domainusers:
                    print 'INFO:Add', utf8membr_dn, 'to', utf8_dn
                    attrs = []
                    attrs.append( ("member", utf8membr_dn) )
                    try:
                        LDAPHandle.AddAttributes(utf8_dn, attrs)
                    except:    
                        print 'WARNING: Failed add', membr_dn, 'to', utf8_dn
                else:
                    print 'WARNING: Group member', utf8membr_dn, 'does not exist in eDirectory'
            except Errors.NotFoundError:
                print "WARNING: Could not find group member ",grpmemb," in db"



def touchable(attrs):
    """Given attributes and their values we determine if we are allowed to
       modify this object"""
    if attrs.has_key('description'):
        if attrs['description'][0][0:8] == 'Cerebrum':
           return True
    return False


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
    print entity_type, spread_str
    global max_nmbr_users
    entity = Entity.Entity(db)
    grp_postfix = ''
    spread_id = int(getattr(co, spread_str))
#    rows = entity.list_all_with_spread(spread_id)
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
    else:
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.NW_GROUP_POSTFIX
    ulist = {}
    count = 0    

    ou.clear()
    ou.find(cereconf.NW_CERE_ROOT_OU_ID)
    ourootname='ou=%s' % ou.acronym
    
    for row in ent_name.list_all_with_spread(spread_id):
        if count >= max_nmbr_users: break
        id = row['entity_id']
        ent_name.clear()
        ent_name.find(id)
        if ent_name.entity_type != e_type: continue
        name = ent_name.get_name(namespace)
        try:
            pri_ou = nwutils.get_primary_ou(id,namespace)
        except Errors.NotFoundError:
            print "Unexpected error /me thinks"
        if not pri_ou:
            print "WARNING: no primary OU found for",name,"in namespace",namespace
            pri_ou = cereconf.NW_DEFAULT_OU_ID
        count = count+1
        crbrm_ou = nwutils.id_to_ou_path(pri_ou ,ourootname)
        id_and_ou = id, crbrm_ou
        obj_name = '%s%s' % (name, grp_postfix)
        ulist[obj_name]=id_and_ou    
        
    print "INFO: Found %s nmbr of objects" % (count)
    return ulist



                    
if __name__ == '__main__':
    LDAPHandle = nwutils.LDAPConnection(cereconf.NW_LDAPHOST, cereconf.NW_LDAPPORT,
                                    binddn=cereconf.NW_ADMINUSER, password=cereconf.NW_PASSWORD, scope='sub')
#    LDAPHandle = nwutils.LDAPConnection(cereconf.NW_LDAPHOST, cereconf.NW_LDAPPORT,
#                                    "", "", scope='sub')
#    arg = get_args()
#    full_ou_sync()
    full_user_sync('spread_HiST_nds_stud_aft')
#    gen_domain_users()
#    del_our_groups()
#    full_group_sync('spread_HiST_nds_stud_aft_group')

