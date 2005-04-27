#!/usr/bin/env python
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
import re
import pickle
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import CLHandler
import adutils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
ou = Factory.get('OU')(db)
group = Factory.get('Group')(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)
logger = Factory.get_logger("cronjob")

delete_users = 0
delete_groups = 0
debug = False
passwords = {}

def quick_user_sync():

    answer = cl.get_events('ad', (clco.group_add,
                                  clco.group_rem,
                                  clco.account_password,
                                  clco.spread_add,
                                  clco.spread_del,
                                  clco.quarantine_add,
                                  clco.quarantine_del,
                                  clco.quarantine_mod,
                                  clco.quarantine_refresh,
                                  clco.account_home_added,
                                  clco.account_home_updated,
				  clco.homedir_update,
				  clco.homedir_add,
				  clco.homedir_remove))

    for ans in answer:	
        chg_type = ans['change_type_id']
        if debug:
            logger.debug("change_id: %s" % ans['change_id'])
        cl.confirm_event(ans)
        if chg_type == clco.account_password:
	    try:	
            	change_params = pickle.loads(ans['change_params'])
	    except EOFError:
		logger.warn('picle.load EOFError on change_id: %s' % ans['change_id'])
		continue
            if change_pw(ans['subject_entity'],change_params):
		cl.confirm_event(ans)
	    else:
		logger.warn('Failed changing password for %s ' % ans['subject_entity'])
        elif chg_type == clco.group_add or chg_type == clco.group_rem:
            entity.clear()
            try:
                entity.find(ans['subject_entity'])
            except Errors.NotFoundError:
                # Ignore this change; as the member entity it refers
                # to no longer seems to exists in Cerebrum, we're
                # unable to find a username for it (outside of the
                # changelog, and we'll process this entity's deletion
                # changelog entry later).
                continue
            if entity.has_spread(int(co.spread_uio_ad_account)):
                group.clear()
		try:
		    g_obj = group.find(ans['dest_entity'])
		except Errors.NotFoundError:
		    # Ignore this change; as the member entity it refers
		    # to no longer seems to exists in Cerebrum, we're
		    # unable to find a username for it (outside of the
		    # changelog, and we'll process this entity's deletion
		    # changelog entry later).
		    continue
	        if group.has_spread(int(co.spread_uio_ad_group)):
                    account_name = id_to_name(ans['subject_entity'],'user')
		    if not account_name:
	    		return False
                    group_name = id_to_name(ans['dest_entity'],'group')
		    if not group_name:
	    		return False
                    if debug:
                        logger.debug("account:%s,group_name:%s" % (account_name,group_name))
                    if chg_type == clco.group_add:
                        if group_add(account_name,group_name):
			    cl.confirm_event(ans)
			else:
		            logger.debug('Failed adding %s to group %s' % (account_name,group_name))
                    else:
			if group_rem(account_name,group_name):
			    cl.confirm_event(ans)
			else:
			    logger.debug('Failed removing %s from group %s' % (account_name,group_name))
		else:
                    if debug:
                        logger.debug('%s add/rem group: missing spread_uio_ad_group' % ans['dest_entity'])
            else:
                if debug:
                    logger.debug('%s add/rem group: missing spread_uio_ad_account' % ans['subject_entity'])

        elif chg_type == clco.spread_add:
            change_params = pickle.loads(ans['change_params'])
            if add_spread(ans['subject_entity'], change_params['spread']):
		cl.confirm_event(ans)
        elif chg_type == clco.spread_del:
            change_params = pickle.loads(ans['change_params'])
            if del_spread(ans['subject_entity'], change_params['spread']):
		cl.confirm_event(ans)
	elif (chg_type == clco.quarantine_add or
              chg_type == clco.quarantine_del or
              chg_type == clco.quarantine_mod or
              chg_type == clco.quarantine_refresh):
	    change_quarantine(ans['subject_entity'])
	elif (chg_type == clco.account_home_updated or
              chg_type == clco.account_home_added or 
	      chg_type == clco.homedir_update or 
	      chg_type == clco.homedir_add or
	      chg_type == clco.homedir_remove):
	    move_account(ans['subject_entity'])
    cl.commit_confirmations()


def move_account(entity_id):
    account.clear()
    account.find(entity_id)
    if account.is_expired():
	logger.debug('move_account:Account %s is expired' % entity_id)
	return False
    if account.has_spread(int(co.spread_uio_ad_account)):
	account_name = id_to_name(entity_id, 'user')
	if not account_name:
	    return False
	home = adutils.find_home_dir(entity_id, account_name, disk_spread)
       	sock.send('ALTRUSR&%s/%s&hdir&%s\n' % (cereconf.AD_DOMAIN,
                                               account_name, home))
	if sock.read() != ['210 OK']:
	    logger.warn('Failed update home directory %s' % account_name)


def change_quarantine(entity_id):
    account.clear()
    try:
	account.find(entity_id)
	if account.is_expired():
	    logger.debug('change_quarantine:Account %s is expired' % entity_id)
	    return False
    except Errors.NotFoundError:
	# The entity exists, but account information deleted, ignore
	# further processing.
	return False
    if account.has_spread(int(co.spread_uio_ad_account)):
    	if adutils.chk_quarantine(entity_id):
	    del_spread(entity_id, co.spread_uio_ad_account,
                       delete=False)
    	else:
	    account_name = id_to_name(entity_id,'user')
	    if not account_name:
	    	return False	
	    ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)		
            sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, account_name))
            ou_in_ad = sock.read()[0]
            if ou_in_ad[0:3] == '210':
                #Account already in AD, we move to correct OU.
                sock.send('MOVEOBJ&%s&LDAP://%s\n' % ( ou_in_ad[4:],ad_ou ))

                if sock.read() == ['210 OK']:
                    sock.send(('ALTRUSR&%s/%s&dis&0&pexp&%s&ccp&%s\n') % (cereconf.AD_DOMAIN,
                                               account_name,
                                               cereconf.AD_PASSWORD_EXPIRE,
                                               cereconf.AD_CANT_CHANGE_PW))
		    if sock.read() != ['210 OK']:
			logger.debug("Failed enabling account %s" % account_name)
                else:
                    logger.debug("Failed move user %s" % account_name)
            else:
                logger.debug("Failed getting AD_OU, %s, creating..." %  account_name)
                add_spread(entity_id, co.spread_uio_ad_account)

def build_user(entity_id):
    account_name =id_to_name(entity_id,'user')
    if not account_name:
	return False
	
    ad_ou = cereconf.AD_LOST_AND_FOUND 

    sock.send('NEWUSR&LDAP://OU=%s,%s&%s&%s\n' % ( ad_ou, cereconf.AD_LDAP, account_name, account_name))
    #Set a random password on user, bacause NEWUSR creates an
    #account with blank password.
    if sock.read() == ['210 OK']:
	if entity_id in passwords:
	#Set correct password if in an earlier changelog entry.
	    pw = passwords[entity_id]
	else:
	    #Set random password.
            pw = account.make_passwd(account_name)
            pw=pw.replace('%','%25')
            pw=pw.replace('&','%26')
        sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,account_name,pw))
        if sock.read() == ['210 OK']:
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE,
             login_script) = adutils.get_user_info(entity_id, account_name,
                                                   disk_spread)

            sock.send(('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s'+
                       '&pexp&%s&ccp&%s\n') % (cereconf.AD_DOMAIN,
                                               account_name,
                                               full_name,
                                               account_disable,
                                               home_dir,
                                               cereconf.AD_HOME_DRIVE,
                                               login_script,
                                               cereconf.AD_PASSWORD_EXPIRE,
                                               cereconf.AD_CANT_CHANGE_PW))
            if sock.read() == ['210 OK']:
		logger.debug('Builded user:%s' % account_name)
        else:
            logger.warn('Failed replacing password or Move account: %s' % account_name)





def add_spread(entity_id, spread):
    if spread == co.spread_uio_ad_account:
        account_name = id_to_name(entity_id,'user')
	if not account_name:
	    return False
	ou.clear()
    	ou.find(cereconf.AD_CERE_ROOT_OU_ID)
    	ourootname='OU=%s' % ou.acronym

        if cereconf.AD_DEFAULT_OU=='0':
            ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
        else:
            pri_ou = adutils.get_primary_ou(entity_id)
            if not pri_ou:
                logger.debug("No account_type information for object %s" % id)
                ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
            else:
                ad_ou = adutils.id_to_ou_path(pri_ou, ourootname)


        sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, account_name))
        ou_in_ad = sock.read()[0]
        if ou_in_ad[0:3] == '210':
            #Account already in AD, we move to correct OU.
            sock.send('MOVEOBJ&%s&LDAP://%s\n' % ( ou_in_ad[4:],ad_ou ))
        else:
            sock.send('NEWUSR&LDAP://%s&%s&%s\n' % ( ad_ou, account_name, account_name))
            #Set a random password on user, bacause NEWUSR creates an
            #account with blank password.
            if sock.read() == ['210 OK']:
		if entity_id in passwords:
		    #Set correct password if in an earlier changelog entry.
		    pw = passwords[entity_id]
		else:
		    #Set random password.
                    pw = account.make_passwd(account_name)
                    pw=pw.replace('%','%25')
                    pw=pw.replace('&','%26')
                sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,account_name,pw))
            else:
                logger.debug('Failed creating new user %s' % account_name)

        if sock.read() == ['210 OK']:
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE,
             login_script) = adutils.get_user_info(entity_id, account_name,
                                                   disk_spread)

            sock.send(('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s&ls&%s'+
                       '&pexp&%s&ccp&%s\n') % (cereconf.AD_DOMAIN,
                                               account_name,
                                               full_name,
                                               account_disable,
                                               home_dir,
                                               cereconf.AD_HOME_DRIVE,
                                               login_script,
                                               cereconf.AD_PASSWORD_EXPIRE,
                                               cereconf.AD_CANT_CHANGE_PW))
            if sock.read() == ['210 OK']:
                #Make sure that the user is in the groups he should be.
                for row in group.list_groups_with_entity(entity_id):
                    group.clear()
                    group.find(row['group_id'])
                    if group.has_spread(int(co.spread_uio_ad_group)):
                        grp_name = '%s-gruppe' % (group.group_name)
                        if not group_add(account_name,grp_name):
                            logger.debug('Add user %s to group %s failed' % (account_name,grp_name))

        else:
            logger.warn('Failed replacing password or Move account: %s' % account_name)
            return False

    elif spread == co.spread_uio_ad_group:
        grp=id_to_name(entity_id,'group')
        if not grp:
	    return False
        if cereconf.AD_DEFAULT_OU=='0':
            ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
        else:
            ou.clear()
            ou.find(cereconf.AD_CERE_ROOT_OU_ID)
            ourootname='OU=%s' % ou.acronym
            ad_ou = id_to_ou_path(cereconf.AD_DEFAULT_OU,ourootname)

	sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, grp))
        ou_in_ad = sock.read()[0]
        if ou_in_ad[0:3] == '210':
            #Account already in AD, we move to correct OU.
            sock.send('MOVEOBJ&%s&LDAP://%s\n' % ( ou_in_ad[4:],ad_ou ))
	else:
            sock.send('NEWGR&LDAP://%s&%s&%s\n' % ( ad_ou, grp, grp))
        if sock.read() == ['210 OK']:
            group.clear()
            group.find(entity_id)
            for grpmemb in group.get_members():
                account.clear()
                account.find(grpmemb)
		if account.is_expired():
		    #Groupmember is expired and is not added to group.	
		    logger.debug('Add_spread:Groupmember %s is expired' % entity_id)
                    if account.has_spread(co.spread_uio_ad_account):
                        name = account.get_name(int(co.account_namespace))
                        logger.debug('Add %s to %s' % (name,grp))
                        sock.send('ADDUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, name, cereconf.AD_DOMAIN, grp))
                        if sock.read() != ['210 OK']:
                            logger.debug('Failed add %s to %s' % (name, grp))
	    return True
        logger.debug('Failed create group %s in OU Users' % grp)
    else:
        if debug:
            logger.debug('Add spread: %s not an ad_spread' %  spread) 
        return True


def del_spread(entity_id, spread, delete=delete_users):

    if spread == co.spread_uio_ad_account:
        user=id_to_name(entity_id,'user')
	if not user:
	    return False
        if delete:
            sock.send('DELUSR&%s/%s\n' % (cereconf.AD_DOMAIN, user))
            if sock.read() != ['210 OK']:
                logger.debug('Error deleting %s' %  user)
        else:
            sock.send('ALTRUSR&%s/%s&dis&1\n' % ( cereconf.AD_DOMAIN, user))
            if sock.read() != ['210 OK']:
                logger.debug('Error disabling account %s' % user)

            sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, user))
            ldap = sock.read()[0]
            if ldap[0:3] != "210":
                logger.debug('Error getting WinNT from LDAP path for %s' %  user)
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(ldap[4:]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[4:], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        logger.debug('Error moving: %s to %s' % (ldap[4:], cereconf.AD_LOST_AND_FOUND))

    elif spread == co.spread_uio_ad_group:
        group_n=id_to_name(entity_id,'group')
	if not group_n:
	    return False
        if delete_groups:
            sock.send('DELGR&%s/%s\n' % (cereconf.AD_DOMAIN, group_n))
            if sock.read() != ['210 OK']:
                logger.debug('Error deleting %s' % group_n)
        else:
            sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, group_n))
            ldap = sock.read()
            if ldap[0][0:3] != "210":
                logger.debug('Error Transforming WinNT to LDAP for %s' % group_n)
            else:
                if cereconf.AD_LOST_AND_FOUND not in adutils.get_ad_ou(ldap[0]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[0], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() == ['210 OK']:
                        sock.send('LGROUP&%s/%s\n' % (cereconf.AD_DOMAIN, group_n))
                        result = sock.readgrp()

                        if result:
                            for line in result.splitlines():
                                if line != '210 OK':
                                    mem = l.split('&')
                                    sock.send('DELUSRGR&%s/%s&%s/%s\n' % (cereconf.AD_DOMAIN, mem[1], cereconf.AD_DOMAIN, group_n))
                                    if sock.read() != ['210 OK']:
                                        logger.debug('Failed delete %s from %s') % (member, group_n)
                    else:
                        logger.debug('Error moving: %s to %s' % (ldap[0], cereconf.AD_LOST_AND_FOUND))

    else:
        if debug:
            logger.debug('Delete spread: %s not an AD spread.' % spread)
        return True


def group_add(account_name,group_name):
    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % ( cereconf.AD_DOMAIN,account_name, cereconf.AD_DOMAIN,group_name ))
    if sock.read() == ['210 OK']:
	return True
    return False


def group_rem(account_name,group_name):
    sock.send('DELUSRGR&%s/%s&%s/%s\n' % ( cereconf.AD_DOMAIN,account_name, cereconf.AD_DOMAIN,group_name ))
    if sock.read() == ['210 OK']:
	return True
    return False


def change_pw(account_id,pw_params):
    account.clear()
    account.find(account_id)
    if account.is_expired():
	logger.debug('change_pw:Account %s is expired' % account_id)
	return False
    user = id_to_name(account_id,'user')
    if not user:
	return False
    if account.has_spread(int(co.spread_uio_ad_account)):
        sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, user))
        ou_in_ad = sock.read()[0]
        if ou_in_ad[0:3] != '210':
	    build_user(account_id)	
	set_pw(account_id,pw_params,user)	
        return True


def set_pw(account_id,pw_params,user):

    if not pw_params.has_key('password'):
	return False
    pw=pw_params['password']
    #Convert password so that it don't mess up the communication protocol.
    pw=pw.replace('%','%25')
    pw=pw.replace('&','%26')
    sock.send('ALTRUSR&%s/%s&pass&%s\n' % (cereconf.AD_DOMAIN,user,pw))
    if sock.read() == ['210 OK']:
	return True
    else:
	#Remember password from changelog, if user not yet created in AD.
        passwords[account_id] = pw


def id_to_name(id,entity_type):
    grp_postfix = ''
    if entity_type == 'user':
        e_type = int(co.entity_account)
        namespace = int(co.account_namespace)
    elif entity_type == 'group':
        e_type = int(co.entity_group)
        namespace = int(co.group_namespace)
        grp_postfix = cereconf.AD_GROUP_POSTFIX
    try:
        entityname.clear()
        entityname.find(id)
        name = entityname.get_name(namespace)
        obj_name = "%s%s" % (name,grp_postfix)
    except Errors.NotFoundError:
	logger.debug('id %s missing, probably deleted' % id)
	return False
    return obj_name


def usage(exitcode=0):
    print """Usage: [options]
    --delete_users
    --delete_groups
    --disk_spread spread (mandatory)
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['delete_users', 'delete_groups',
                                    'disk_spread='])
    except getopt.GetoptError:
        usage(1)
    disk_spread = None
    for opt, val in opts:
        if opt == '--delete_users':
            delete_users = True
        elif opt == '--delete_groups':
            delete_groups = True
        elif opt == '--disk_spread':
            disk_spread = getattr(co, val)  # TODO: Need support in Util.py
    if not disk_spread:
        usage(1)
    sock = adutils.SocketCom()
    quick_user_sync()
    sock.close()

# arch-tag: 4a6f6aad-20a9-474e-a9cb-cefddec96106
