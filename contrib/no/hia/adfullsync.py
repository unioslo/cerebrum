#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
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
import re
import getopt
from Cerebrum.extlib import logging

import cerebrum_path
import cereconf
import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import ADAccount
from Cerebrum.modules import ADObject
from Cerebrum import Person

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ad_object = ADObject.ADObject(db)
ad_account = ADAccount.ADAccount(db)
ou = Factory.get('OU')(db)
ent_name = Entity.EntityName(db)
group = Factory.get('Group')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)

global delete_users
global delete_groups
delete_users = 0
delete_groups = 0
adusers = []
#for test.
max_nmbr_users = 10000

def logger(text):
    print text,"\n"

def full_user_sync():
    """Checking each user in AD, and compare with cerebrum information."""

    print 'INFO: Starting, full user sync', adutils.now()    
    global adusers
    logger("Entering full_user_sync")
    cbusers = {}
    cbusers = get_objects('user')
    # Initialize socket, to avoid timeout. 	
    sock = adutils.SocketCom()    	
    sock.send('LUSERS&LDAP://%s&0\n' % (cereconf.AD_LDAP),out=0)
    receive = sock.readgrp(out=0).splitlines()
    for line in receive[1:-1]:
        ldappath = line.split('&')[1]
	sock.send('LUSER&%s\n' % ldappath)
	adout = sock.read(out=0)[0]
	if adout[:3] != '210':
	   logger("Failed LUSER&%s" % ldappath)	 
	   continue
	adfields = adout[4:].split('&')
	#########
	#
	# The ad-server fields.
	# name - ad account user name.
	# fn   - Full name.
	# up   - winnt path.
	# hdir - home directory defined in ad.
	# hdr  - drive letter of hdir.
	# pf   - user profile path.
	# ls   - logon script.
	# pexp - password expire flag.
	# ccp  - cant change password flag.
	# dis  - account disabled flag.
	#
	#########
	adusrinfo = {}	
	for f in range(0,len(adfields)-2,2):
	    adusrinfo[adfields[f]] = adfields[f+1]
	adusers.append(adusrinfo['name'])


	if adusrinfo['name'] in cbusers:
	    cbusrid = cbusers[adusrinfo['name']]

	    #Checking if user is in correct OU.
            if ldappath != 'LDAP://CN=%s,%s' % (adusrinfo['name'],cbusrid[1]):
            	sock.send('MOVEOBJ&%s&LDAP://%s\n' % (ldappath,cbusrid[1]))
            	if sock.read() != ['210 OK']:
                    logger("Failed move user to CN=%s,%s" % \
		    (adusrinfo['name'],cbusrid[1]))

            (full_name, account_disable) \
		= adutils.get_user_info(cbusrid[0],adusrinfo['name'])
	    try:
                if ((full_name, account_disable, \
		cereconf.AD_CANT_CHANGE_PW, cereconf.AD_PASSWORD_EXPIRE) \
		!= (adusrinfo['fn'], adusrinfo['dis'], adusrinfo['ccp'], \
                    adusrinfo['pexp'] )):
                    sock.send("ALTRUSR&%s/%s&fn&%s&dis&%s&pexp&%s&ccp&%s\n" % ( cereconf.AD_DOMAIN, adusrinfo['name'], full_name, 
		    account_disable, cereconf.AD_PASSWORD_EXPIRE, cereconf.AD_CANT_CHANGE_PW))
                    
                    if sock.read() != ['210 OK']:
                        logger("Error updating fields for %s" % \
				adusrinfo['name'])
            except IndexError:
                logger("list index out of range, for %s" % \
		adusrinfo['name'])
            del cbusers[adusrinfo['name']]
        elif adusrinfo['name'] in cereconf.AD_DONT_TOUCH:
            pass
        else:
            if delete_users:
                sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN,
			adusrinfo['name']))
                if sock.read() != ['210 OK']:
                    logger("Error deleting %s" % adusrinfo['name'])
            else:
                if cereconf.AD_LOST_AND_FOUND not in \
		    adutils.get_ad_ou(ldappath):
                    sock.send('ALTRUSR&%s/%s&dis&1\n' % 
		    (cereconf.AD_DOMAIN, adusrinfo['name']))
                    if sock.read() != ['210 OK']:
                        logger("Error disabling account" % 
			adusrinfo['name'])

                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (ldappath, \
		    cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        logger("Error moving %s to %s" % \
                               (adusrinfo['name'], cereconf.AD_LOST_AND_FOUND))

    for user in cbusers:
        # The remaining accounts in the list should be created.
	cbusrid = cbusers[user]		
        sock.send('NEWUSR&LDAP://%s&%s&%s\n' % (cbusrid[1] ,user, user))
        if sock.read() == ['210 OK']:
            #logger("Created user %s in %s" % (user, cbusrid[1]))
	    #Set random password.
            passw = account.make_passwd(user)
            passw=passw.replace('%','%25')
            passw=passw.replace('&','%26')
            (full_name, account_disable) = \
                        adutils.get_user_info(cbusrid[0], user)
            sock.send('ALTRUSR&%s/%s&pass&%s&fn&%s&dis&%s&pexp&%s&ccp&%s\n' % \
                      (cereconf.AD_DOMAIN, user, passw, full_name, \
                       account_disable, cereconf.AD_PASSWORD_EXPIRE, \
                       cereconf.AD_CANT_CHANGE_PW))
            if sock.read() != ['210 OK']:
		logger("Failed ALTRUSR %s" % user)   
                sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN, user))
                if sock.read() != ['210 OK']:
                    logger("Failed DELUSR %s,after failed ALTRUSR" % user)
        else:
            logger("Failed create user %s in %s" % (user ,cbusrid[1]))
    sock.close()
                    
	    	
def full_group_sync():
    """Checking each group in AD, and compare with cerebrum"""
    logger("Starting full_group_sync")
    global adusers
    cbgroups = {}
    cbgroups = get_objects('group')
    # Initialize socket, to avoid timeout. 	
    sock = adutils.SocketCom()    	
    sock.send('LGROUPS&LDAP://%s\n' % (cereconf.AD_LDAP))
    receive = sock.readgrp().splitlines()  	
    for line in receive[1:-1]:
        fields = line.split('&')
	ldappath = fields[1]
	grpname = fields[3]
        if grpname in cbgroups:
            cbgrpid = cbgroups[grpname]
            #Place group in correct OU.
            if 'LDAP://CN=%s,%s' % (grpname,cbgrpid[1]) != ldappath:
                sock.send('MOVEOBJ&%s&LDAP://%s\n' % (ldappath, cbgrpid[1]))
                if sock.read() != ['210 OK']:
                    logger("Move user %s to %s failed" % \
		    (grpname, cbgrpid)) 

	    #Finding members of group in cerebrum.
            group.clear()
            group.find(cbgrpid[0])
            memblist = []
            for membid in group.get_members():
                try:
                    ent_name.clear()
                    ent_name.find(membid)                   
                    if ent_name.has_spread(co.spread_hia_ad_account):
                        membname = ent_name.get_name(int(co.account_namespace))
                        if not membname in memblist:
                            memblist.append(membname)
                except Errors.NotFoundError:
                    logger("Could not find name of entity %s" % membid)
	    
	    #Finding members of group in AD.
            sock.send('LGROUP&%s/%s\n' % (cereconf.AD_DOMAIN, grpname))
            result = sock.readgrp().splitlines()
            for line in result:
                if line != '210 OK':
                    mem = line.split('&')
                    if mem[1] in memblist:
                        memblist.remove(mem[1])
                    else:
                        sock.send("DELUSRGR&%s/%s&%s/%s\n" % \
			(cereconf.AD_DOMAIN, mem[1], cereconf.AD_DOMAIN, 
			grpname))
                        if sock.read() != ['210 OK']:
                            logger("Failed delete %s from %s" % \
			    (mem[1], grpname))
            for memb in memblist:
		sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, 
		memb, cereconf.AD_DOMAIN, grpname))
                if sock.read() != ['210 OK']:
                    logger("Failed add %s to %s" % (memb, grpmemb)) 
            del cbgroups[grpname]

        elif fields[3] in cereconf.AD_DONT_TOUCH:
            pass
        else:
            if delete_groups:
                sock.send('DELGR&%s/%s\n' % (cereconf.AD_DOMAIN, grpmemb))
                if sock.read() != ['210 OK']:
                    logger("Error deleting %s" % grpmemb)
            else:
                if cereconf.AD_LOST_AND_FOUND not in \
		    adutils.get_ad_ou(ldappath):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % \
		    (ldappath, cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        logger("Error moving %s to %s" % (grpname, \
			cereconf.AD_LOST_AND_FOUND))


    for grp in cbgroups:
        # The remaining is new groups and should be created.
        sock.send('NEWGR&LDAP://%s&%s&%s\n' % (cbgroups[grp][1], grp, grp))
        res = sock.read()
	if res == ['210 OK']:
            group.clear()
            group.find(cbgroups[grp][0])
            for grpmemb in group.get_members():
                try:
                    ent_name.clear()
                    ent_name.find(grpmemb)
                    name = ent_name.get_name(int(co.account_namespace))
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, \
		    name, cereconf.AD_DOMAIN, grp))
		    res = sock.read()
                    if res != ['210 OK']:
                    	logger("Failed add %s to %s:%s" % \
			(name, grp, res))
                except Errors.NotFoundError:
                    logger("Could not resolve entity name %s" % name)
        else:
            logger("Create group %s in %s failed:%s" % \
	    (grp, cbgroups[grp][1], res))    
    sock.close()


def get_objects(entity_type):
    #Get all objects with spread ad, in a hash identified 
    #by name with the cerebrum id and ou.
    global max_nmbr_users
    grp_postfix = ''
    if entity_type == 'user':
        namespace = int(co.account_namespace)
        spread = int(co.spread_hia_ad_account)
    else:
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.AD_GROUP_POSTFIX
        spread = int(co.spread_hia_ad_group)
    ulist = {}
    count = 0    
    
    for row in ent_name.list_all_with_spread(spread):
        count = count+1
        if count > max_nmbr_users: break
	ent_name.clear()
        ent_name.find(row['entity_id'])
        name = ent_name.get_name(namespace)
        if entity_type == 'user':
            account.clear()
            account.find(row['entity_id'])
            cbou = ""
            try:
                pers_id = account.owner_id
                affiliations = person.list_affiliations(person_id=pers_id)
                for aff in affiliations:
                    if int(co.affiliation_ansatt) in aff:
                        cbou = 'OU=user,OU=ans,%s' % cereconf.AD_LDAP
                    elif int(co.affiliation_student) in aff:
                        cbou = 'OU=user,OU=stud,%s' % cereconf.AD_LDAP
            except Errors.NotFoundError:
                pass
            if cbou:
                ulist[name]=(int(row['entity_id']), cbou)
            else:
                logger("Missing affiliation on %s" % (row['entity_id']))
        else:
      	    cbou = 'OU=grp,%s' % cereconf.AD_LDAP            
            ulist['%s%s' % (name,grp_postfix)]=(int(row['entity_id']), cbou)
    logger("Found %s nmbr of objects" % (count))
    return ulist


def usage(exitcode=0):
    print """adfullsync.py [-h] [--delete_users] [--delete_groups]"""
    sys.exit(exitcode)		    
 
 
if __name__ == '__main__':

    try:
        opts, args = getopt.getopt(sys.argv[1:],"h",\
	["delete_users","delete_groups","help"])
    except getopt.GetoptError:
        usage()

    for o, a in opts:
        if o == '--delete_users':
            delete_users = 1
        if o == '--delete_groups':
            delete_groups = 1
	if o in ('-h','--help'):
	    usage()


    full_user_sync()
    full_group_sync()


# arch-tag: 105728b2-ef16-420a-bc77-e06a7db75552
