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
from Cerebrum import Person
from Cerebrum.modules import CLHandler
from Cerebrum.modules import ADUtils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('CLConstants')(db)
entity = Entity.Entity(db)
entityname = Entity.EntityName(db)
ou = Factory.get('OU')(db)
group = Factory.get('Group')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
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
				  clco.person_name_mod,
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
            if change_pw(ans['subject_entity'],change_params,ans['change_program']):
		cl.confirm_event(ans)
	    else:
		logger.warn('Failed changing password for %s ' % ans['subject_entity'])
        elif chg_type == clco.group_add or chg_type == clco.group_rem:
            group.clear()
            try:
                group.find(ans['dest_entity'])
            except Errors.NotFoundError:
                # Ignore this change; as the member entity it refers
                # to no longer seems to exists in Cerebrum, we're
                # unable to find a username for it (outside of the
                # changelog, and we'll process this entity's deletion
                # changelog entry later).
                continue
            if group.has_spread(int(co.spread_uio_ad_group)):
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

                group_name = id_to_name(ans['dest_entity'],'group')
		    
		if entity.has_spread(int(co.spread_uio_ad_account)):
		    #Adding account to group.	
		    member_name = id_to_name(ans['subject_entity'],'user')
		    
		elif entity.has_spread(int(co.spread_uio_ad_group)):
		    #Adding group to group.	
		    member_name = id_to_name(ans['subject_entity'],'group')
		
		else:
		    logger.debug('Group member not AD spread.')	
		    continue
	
                if chg_type == clco.group_add:
		    if group_add(member_name,group_name):
			cl.confirm_event(ans)

		    else:
			logger.debug('Failed adding %s to group %s' 
				% (member_name,group_name))

		else:
		    if group_rem(member_name,group_name):
			cl.confirm_event(ans)

		    else:
			logger.debug('Failed removing %s from group %s' 
				% (member_name,group_name))


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
	elif chg_type == clco.person_name_mod:
	    try:	
            	change_params = pickle.loads(ans['change_params'])
	    except EOFError:
		logger.warn('picle.load EOFError on change_id: %s' % ans['change_id'])
		continue
            if change_name(ans['subject_entity'],change_params):
		cl.confirm_event(ans)
	    else:
		logger.warn('Failed changing fullname on %s ' % ans['subject_entity'])


    cl.commit_confirmations()


def change_name(owner_id, name_param):
    
    #One Person can have more than one account. List all account belonging to person.
    if name_param['name_variant'] == co.name_full:	
        if debug:
	    logger.debug("owner_id:%s,name:%s,name-variant:%s" %   \
		 (owner_id,name_param['name'],name_param['name_variant']))
    	for acc in account.list_accounts_by_owner_id(owner_id):
	    try:
	    	account.clear()
	    	account.find(acc['account_id'])
	    except Errors.NotFoundErrors:
	    	if debug:
		    logger.debug("Not Found Error")	    		
	    	    return False		
    	    if account.has_spread(int(co.spread_uio_ad_account)):
		try:
	            person.clear()
        	    person.find(owner_id)
        	    full_name = person.get_name(int(co.system_cached), int(co.name_full)) 
        	    if not full_name:
			logger.debug('getting persons full_name failed, account.owner_id: %s' % person_id)
    		except Errors.NotFoundError:        
        	    #This account is missing a person_id.
	            full_name = account.account_name
 
       	    	sock.send('ALTRUSR&%s/%s&fn&%s\n' % (cereconf.AD_DOMAIN,
                                               account.account_name, name_param['name']))
	    	if sock.read() != ['210 OK']:
	    	    logger.debug('Failed update name of person %s, account %s' % (owner_id, acc['account_id']))
		    return False	
    return True	


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
	home = ADUtils.find_home_dir(entity_id, account_name, disk_spread)
       	sock.send('ALTRUSR&%s/%s&hdir&%s\n' % (cereconf.AD_DOMAIN,
                                               account_name, home))
	if sock.read() != ['210 OK']:
	    logger.debug('Failed update home directory %s' % account_name)


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
		if ADUtils.chk_quarantine(entity_id):
			del_spread(entity_id, co.spread_uio_ad_account, delete=False)
		else:
			add_spread(entity_id, co.spread_uio_ad_account)


def build_user(entity_id):

    account_name = id_to_name(entity_id,'user')

    if not account_name:
	return False
	
    ad_ou = cereconf.AD_LOST_AND_FOUND 

    sock.send('NEWUSR&LDAP://OU=%s,%s&%s&%s\n' % ( ad_ou, cereconf.AD_LDAP, account_name, account_name))

    if sock.read() == ['210 OK']:
	#Set a random password on user, bacause NEWUSR creates an
    	#account with blank password.

	if entity_id in passwords:
  	    #Set correct password if in an earlier changelog entry.
	    pw = passwords[entity_id]
	else:
	    #Set random password.
            pw = account.make_passwd(account_name)
            pw=pw.replace('%','%25')
            pw=pw.replace('&','%26')

        sock.send('ALTRUSR&%s/%s&pass&%s\n' % \
			(cereconf.AD_DOMAIN,account_name,pw))

        if sock.read() == ['210 OK']:
            (full_name, account_disable, home_dir, 
			cereconf.AD_HOME_DRIVE) = ADUtils.get_user_info(entity_id,
									account_name, disk_spread)

            sock.send(('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s'+
                       '&pexp&%s&ccp&%s\n') % (cereconf.AD_DOMAIN,
                                               account_name,
                                               full_name,
                                               account_disable,
                                               home_dir,
                                               cereconf.AD_HOME_DRIVE,
                                               cereconf.AD_PASSWORD_EXPIRE,
                                               cereconf.AD_CANT_CHANGE_PW))

            if sock.read() == ['210 OK']:
		logger.debug('Building user:%s' % account_name)
	    else:
		logger.debug('Error building user:%s' % account_name)
		return False

        else:
            logger.warn('Failed replacing password or Move account: %s' % account_name)
	    return False

	return True



def add_spread(entity_id, spread):
    if spread == co.spread_uio_ad_account:
        account_name = id_to_name(entity_id,'user')
	if not account_name:
	    return False

        if cereconf.AD_DEFAULT_OU=='0':
            ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)

        else:
	    ou.clear()
    	    ou.find(cereconf.AD_CERE_ROOT_OU_ID)
    	    ourootname='OU=%s' % ou.acronym
            pri_ou = ADUtils.get_primary_ou(entity_id)
            if not pri_ou:
                logger.debug("No account_type information for object %s" % id)
                ad_ou='CN=Users,%s' % (cereconf.AD_LDAP)
            else:
                ad_ou = ADUtils.id_to_ou_path(pri_ou, ourootname)


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
            (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE) = ADUtils.get_user_info(entity_id, account_name, disk_spread)

            sock.send(('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir&%s&hdr&%s'+
                       '&pexp&%s&ccp&%s\n') % (cereconf.AD_DOMAIN,
                                               account_name,
                                               full_name,
                                               account_disable,
                                               home_dir,
                                               cereconf.AD_HOME_DRIVE,
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

	    grplist = group.list_members(co.spread_uio_ad_account,None, True, True)
            for usrmemb in grplist[0]:
	    #We use only the Union part the group-space, as this is 
	    #the only supported operation in AD. The spread argument picks out 
	    #only account objects. group spread treated separate.

                account.clear()
                account.find(usrmemb[1]) #Pick out entity_id.

		if not account.is_expired():
                    name = account.get_name(int(co.account_namespace))
                    logger.debug('Add %s to %s' % (name,grp))
                    sock.send('ADDUSRGR&%s/%s&%s/%s\n' % 
			(cereconf.AD_DOMAIN, name, cereconf.AD_DOMAIN, grp))
                    if sock.read() != ['210 OK']:
                         logger.debug('Failed add %s to %s' % (name, grp))

		else:
		    logger.debug('Add_spread:Groupmember %s is expired' 
				% entity_id)

	    grpgrplist = group.list_members(co.spread_uio_ad_group,None, True, True)
            for grpmemb in grpgrplist[0]:
	    #We use only the Union part the group-space, as this is 
	    #the only supported operation in AD. The spread argument picks out 
	    #only account objects. 

		member_group = Factory.get('Group')(db)	
                member_group.clear()
                member_group.find(grpmemb[1])

		if not member_group.is_expired():
                    name = '%s-gruppe' % (member_group.group_name)
		    
                    if not group_add(name,grp):
                         logger.debug('Failed add %s to %s' % (name, grp))

		else:
		    logger.debug('Add_spread:Groupmember %s is expired' 
			% entity_id)


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
                logger.debug('Error getting WinNT from LDAP path for %s' 
			%  user)
            else:
                if cereconf.AD_LOST_AND_FOUND not in ADUtils.get_ad_ou(ldap[4:]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[4:], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() != ['210 OK']:
                        logger.debug('Error moving: %s to %s' 
				% (ldap[4:], cereconf.AD_LOST_AND_FOUND))

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
                if cereconf.AD_LOST_AND_FOUND not in ADUtils.get_ad_ou(ldap[0]):
                    sock.send('MOVEOBJ&%s&LDAP://OU=%s,%s\n' % (
                        ldap[0], cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP))
                    if sock.read() == ['210 OK']:
                        sock.send('LGROUP&%s/%s\n' % (cereconf.AD_DOMAIN, group_n))
                        result = sock.readgrp()

                        if result:
                            for line in result.splitlines():
                                if line != '210 OK':
                                    mem = line.split('&')
				    group_rem(mem[1],group_n)	

                    else:
                        logger.debug('Error moving: %s to %s' % (ldap[0], cereconf.AD_LOST_AND_FOUND))

    else:
        if debug:
            logger.debug('Delete spread: %s not an AD spread.' % spread)
        return True


def group_add(member_name,group_name):

    sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, member_name))
    ldap = sock.read()
    if ldap[0][0:3] != "210":
    	logger.debug('Error Transforming WinNT to LDAP for %s' % member_name)
    	return False	
    ldap_member = ldap[0][4:] 	

    sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, group_name))
    ldap2 = sock.read()
    if ldap2[0][0:3] != "210":
    	logger.debug('Error Transforming WinNT to LDAP for %s' % group_name)
	return False
    ldap_group = ldap2[0][4:] 	

    sock.send('ADDUSRGR&%s&%s\n' % ( ldap_member, ldap_group ))
    if sock.read() == ['210 OK']:
	return True
    return False


def group_rem(member_name,group_name):

    sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, member_name))
    ldap = sock.read()
    if ldap[0][0:3] != "210":
    	logger.debug('Error Transforming WinNT to LDAP for %s' % member_name)
    	return False
    ldap_member = ldap[0][4:] 	

    sock.send('TRANS&%s/%s\n' % ( cereconf.AD_DOMAIN, group_name))
    ldap2 = sock.read()
    if ldap2[0][0:3] != "210":
    	logger.debug('Error Transforming WinNT to LDAP for %s' % group_name)
        return False
    ldap_group = ldap2[0][4:] 	

    sock.send('DELUSRGR&%s&%s\n' % ( ldap_member, ldap_group ))
    if sock.read() == ['210 OK']:
	return True
    return False


def change_pw(account_id,pw_params,change_prog):

    account.clear()
    account.find(account_id)
    disable = '1';	

    if account.is_expired():
	#Account expired, That's OK, do nothing and return True.
	logger.debug('change_pw:Account %s is expired' % account_id)
	return True

    user = id_to_name(account_id,'user')
    if not user:
	logger.debug('change_pw:Could not resolve name: %s' % account_id)
   	return False	
        
    sock.send('TRANS&%s/%s\n' % (cereconf.AD_DOMAIN, user))
    ou_in_ad = sock.read()[0]
        
    if ou_in_ad[0:3] != '210':

	if account.has_spread(int(co.spread_uio_ad_account)):	
	    # The change password entry in the changelog appear before 
	    # add spread, we then build the user and set the pw.
            if build_user(account_id):	
	        return True
	elif change_prog == cereconf.AD_PW_EXCEPTION:
	    # Password change by process_students. Create disabled account to keep password changes.    
	    sock.send('NEWUSR&LDAP://OU=%s,%s&%s&%s\n' % ( cereconf.AD_PW_EXCEPTION_OU, cereconf.AD_LDAP, user, user))
    	    if sock.read() == ['210 OK']:
		logger.debug('change_pw:pw_exception account %s created' 
			% user)
	    else:
		logger.debug('change_pw:failed create pw_exception account %s' % user)
		return False	
		
	if set_pw(account_id,pw_params,user):	
	    #Created account, now change the password.
	    return True	

    else:	
	#Account in AD, we change the password.
	if set_pw(account_id,pw_params,user):	
	    return True	
	
    #The account is not in AD, not created with process_students, and not AD_spread.
    #That is OK, so we return true.	
    logger.debug('change_pw:Account %s no change criteria kicked in.' % account_id)
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
	logger.debug('set_pw:Assume user %s not created yet, store password for later use' % user)	
        passwords[account_id] = pw
	return True



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
    sock = ADUtils.SocketCom()
    quick_user_sync()
    sock.close()

# arch-tag: 4a6f6aad-20a9-474e-a9cb-cefddec96106
