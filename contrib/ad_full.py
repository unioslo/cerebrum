#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import string
import cerebrum_path
import cereconf
import pickle
import adutils

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import MountHost
db = Factory.get('Database')()
db.cl_init(change_program="ad_full")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
person = Factory.get('Person')(db)
host = Factory.get('Host')(db)
qua = Entity.EntityQuarantine(db)
mh = MountHost.MountHost(db)




def fetch_cerebrum_data(spread,disk_spread):
    """For all accounts that has spread, returns a list of dicts with the keys:
    uname, fullname, account_id, person_id, host_name
"""

    #Fetch mapping from mounthost table  
    mh2hid = {}	
    for row in mh.list_all():
	mh2hid[int(row['mount_host_id'])] = row['mount_name']
    logger.info("Fetched %i MountHosts" % len(mh2hid))

    #Fetch the mapping host_id to name and change for mounthosts entries.
    hid2hname = {}
    for row in host.search():
	if mh2hid.get(int(row['host_id']),None):
	    hid2hname[int(row['host_id'])] = mh2hid[int(row['host_id'])]
	else: 
            hid2hname[int(row['host_id'])] = row['name']
    logger.info("Fetched %i Hosts" % len(hid2hname))

    #Fetch the mapping person_id to full_name.
    pid2name = {}
    for row in person.list_persons_name(source_system=co.system_cached):
        pid2name.setdefault(int(row['person_id']), row['name'])
    logger.info("Fetched %i person names" % len(pid2name))


    # Fetch account-info.  Unfortunately the API doesn't provide all
    # required info in one function, so we do this in steps.

    aid2ainfo = {}
    for row in ac.list_account_home(home_spread=disk_spread, account_spread=spread,
                          filter_expired=True, include_nohome=True):
	if row['host_id']:
	    aid2ainfo[int(row['account_id'])] = {
            	'uname': row['entity_name'],
	    	'host_id': int(row['host_id'])	    
	    	}
	else:
	    aid2ainfo[int(row['account_id'])] = {
            	'uname': row['entity_name'],
	    	}
    logger.info("Fetched %i accounts with ad_spread" % len(aid2ainfo))


    #Filter quarantined users.
    qcount = 0
    for row in qua.list_entity_quarantines(only_active=True,
		entity_types=co.entity_account):
	if not aid2ainfo.has_key(int(row['entity_id'])):
	    continue
	else:
	    if not aid2ainfo[int(row['entity_id'])].get('quarantine',False):
	    	aid2ainfo[int(row['entity_id'])]['quarantine'] = True
  	    	qcount = qcount +1

    logger.info("Fetched %i quarantined accounts" % qcount)


    #Fetch mapping between account_id and person_id(owner_id).
    for row in ac.list():
        if not aid2ainfo.has_key(int(row['account_id'])):
            continue
        if row['owner_type'] != int(co.entity_person):
            continue
        aid2ainfo[int(row['account_id'])]['owner_id'] = int(row['owner_id'])

    ret = {}
    
    for ac_id, dta in aid2ainfo.items():
        tmp = {
            'account_id': ac_id,
            }
        tmp['host_name'] = hid2hname.get(dta.get('host_id', None),None)
	tmp['quarantine'] = dta.get('quarantine', False)

        if dta.has_key('owner_id'):
            pnames = pid2name.get(dta['owner_id'], None)
            if pnames is None:
                logger.warn("%i is very new?" % dta['owner_id'])
                continue
            tmp['fullname'] = pnames
        else:
	    pass
	    #logger.info("Not a person:%s" % dta['uname'])

        ret[dta['uname']] = tmp

    return ret


def fetch_ad_data():

    #Opening socket. 
    adusers = {}
    sock = adutils.SocketCom()          
    sock.send('LUSERS&LDAP://%s&1\n' % (cereconf.AD_LDAP))
    receive = sock.readgrp(out=0).splitlines()
    for line in receive[1:-2]:
        adfields = line[4:].split('&')
        #########
        #
        # The ad-server fields.
	# path - full ldap path
        # name - ad account user name.
        # fn   - Full name.
        # up   - winnt path.
        # hdir - home directory defined in ad.
        # hdr  - drive letter.
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
	name = adusrinfo['name']
	del adusrinfo['name']
        adusers[name] = adusrinfo

    return adusers

def full_sync(delete_users, disk_spread, dry_run):
    
    #Fetc AD-data.	
    adusers = fetch_ad_data()		

    logger.info("Fetched %i ad-users" % len(adusers))	

    #Fetch cerebrum data.
    cerebrumusers = fetch_cerebrum_data(co.spread_uio_ad_account, disk_spread)

    logger.info("Fetched %i users" % len(cerebrumusers))


    #compare cerebrum and ad-data.
    changelist = compare(delete_users,cerebrumusers,adusers)	
    cerebrumusers = {}	
    adusers = {}	
    logger.info("Found %i number of changes" % len(changelist))

    #Perform changes.	
    perform_changes(changelist, dry_run)	


def perform_changes(changelist, dry_run):

    sock = adutils.SocketCom()

    for chg in changelist:
 	if chg['type'] == 'NEWUSR':
	      	    
	    dis = '0'	
	    if chg['quarantine'] == True:
		dis = '1'		
	    	
	    if chg.has_key('fullname'):	
		fn = chg['fullname']
	    else:
	        fn = chg['user']

	    #Create a random password.
            pw = ac.make_passwd(chg['user'])
            pw=pw.replace('%','%25')
            pw=pw.replace('&','%26')

	    #TODO:create in correct OU.
	    command = "NEWUSR&LDAP://CN=Users,%s&%s&%s" % \
		    ( cereconf.AD_LDAP, chg['user'], chg['user'])

	    command2 = "ALTRUSR&LDAP://CN=%s,CN=Users,%s&pass&%s" % \
		    (chg['user'], cereconf.AD_LDAP, pw)


	    #TODO:Some values is only possible to set with WinNT path.
            command3 = ('ALTRUSR&%s/%s&fn&%s&dis&%s&hdir' +
			'&\\\\%s\\%s&hdr&%s&pexp&%s&ccp&%s') % \
					     (cereconf.AD_DOMAIN,
					      chg['user'],
                                              fn,
                                              dis, 
                                              chg['host_name'],  
					      chg['user'],	
                                              cereconf.AD_HOME_DRIVE,
                                              cereconf.AD_PASSWORD_EXPIRE,
                                              cereconf.AD_CANT_CHANGE_PW)

	    ret = run_command(command, dry_run, sock)
	    if ret != True:
		logger.warning("Create user %s fail, err:%s" % (chg['user'],ret))

	    ret = run_command(command2, dry_run, sock)	
	    if ret != True:
		logger.warning("Change password on %s failed, err:%s" % \
		    (chg['user'],ret))
 		
	    ret = run_command(command3, dry_run, sock)	
	    if ret != True:
		logger.warning("ALTRUSR %s failed, err:%s" % (chg['user'],ret))

	elif chg['type'] == 'MOVEOBJ':

	    command = "%s&%s&%s" % (chg['type'],chg['path'],chg['ou'])
	
	    ret = run_command(command, dry_run, sock)
	    if ret != True:
		logger.warning("MOVEOBJ %s failed, err:%s" % (chg['path'], ret))


	else:
	    type = chg['type']
	    path = chg['path']
	    command = '%s&%s' % (type, path)
	    del chg['type']
	    del chg['path'] 
	    for field,data in chg.items():
	    	command = '%s&%s&%s' % (command, field, data)

	    ret = run_command(command, dry_run, sock)
	    if ret != True:
	    	logger.warning("%s on %s failed, err:%s" % (type, path, ret))
	
	    
    sock.close()	

def run_command(cmd, dry_run, sock):
    if dry_run == True:
	print(cmd)
	return True
    else:
	sock.send('%s\n' % cmd)
	retrn = sock.read()
	if retrn == ['210 OK']:
	    return True 
	else: 
	    return retrn	


def compare(delete_users,cerebrumusrs,adusrs):

    changelist = []	 	

    for usr, dta in adusrs.items():
	changes = {}    	
	if cerebrumusrs.has_key(usr):
	    #User is both places, we want to check correct data.

	    #Checking full name.
	    if 	cerebrumusrs[usr].has_key('fullname'):	
		    if adusrs[usr]['fn'] != cerebrumusrs[usr]['fullname']:
		    	changes['fn'] = cerebrumusrs[usr]['fullname']	
	    else:
	    	if adusrs[usr]['fn'] != usr:
		    changes['fn'] = usr	
		
	    #checking against disable.
	    tmp = '0'	
	    if cerebrumusrs[usr]['quarantine'] == True:
		tmp = '1'	
	    if tmp != adusrs[usr]['dis']:
	    	changes['dis'] = tmp
		
 	    #Check against home drive.
	    if adusrs[usr]['hdr'] != cereconf.AD_HOME_DRIVE:
		#TODO:Can only change with WinNT path,rewrite server.
		#changes['hdr'] = cereconf.AD_HOME_DRIVE	
		pass

	    #Checking password expire. 
	    if adusrs[usr]['pexp'] != cereconf.AD_PASSWORD_EXPIRE:
		#TODO:Can only change with WinNT path,rewrite server
		#changes['pexp'] = cereconf.AD_PASSWORD_EXPIRE	
		pass

	    #Checking Cant change password.
	    if adusrs[usr]['ccp'] != cereconf.AD_CANT_CHANGE_PW:
		#TODO:Can only change with WinNT path,rewrite server.
		#changes['ccp'] = cereconf.AD_CANT_CHANGE_PW
		pass

	    #Checking against home.
	    if adusrs[usr]['hdir'] != "\\\\%s\%s" % (cerebrumusrs[usr]['host_name'],usr):		
		changes['hdir'] = "\\\\%s\%s" % (cerebrumusrs[usr]['host_name'],usr)

	    #TODO:Check that user is in correct OU.

	    #Setting LDAP path and action.	    
   	    #If any changes append to changelist.	
	    if len(changes):
		changes['path'] = adusrs[usr]['path']
		changes['type'] = 'ALTRUSR'

	    #after processing we delete from array.
	    del cerebrumusrs[usr]
	else:	   	
	    #Account not in Cerebrum, but i AD.
	    if adusrs[usr]['path'].find(cereconf.AD_DO_NOT_TOUCH) < 0:
		if adusrs[usr]['path'].find(cereconf.AD_PW_EXCEPTION_OU) >= 0:
		    #Account do not have AD_spread, but is in AD to 
		    #register password changes, do nothing.
		    pass	
	        else:
		    #ac.is_deleted() or ac.is_expired() pluss a small rest of 
		    #accounts created in AD, but that do not have AD_spread. 
		    if delete_users == True:
		    	changes['type'] = 'DELUSR'
		    	changes['path'] = adusrs[usr]['path']
		    else:
		    	if adusrs[usr]['path'] != "LDAP://CN=%s,OU=%s,%s" % \
	    	            (usr, cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP):
			    changes['type'] = 'MOVEOBJ'
		            changes['path'] = adusrs[usr]['path']
		            changes['ou'] = "LDAP://OU=%s,%s" % \
		                (cereconf.AD_LOST_AND_FOUND,cereconf.AD_LDAP)


	
	#Finished processing user register changes if any.
	if len(changes):
	    changelist.append(changes)

	
    #The remaining items in cerebrumusrs is not in AD, create user.
    for cusr, cdta in cerebrumusrs.items():
	changes={}
	#TODO:Should quarantined users actually be created?
	if cerebrumusrs[cusr]['quarantine'] == True:
	    #Quarantined, do not create.
	    pass	
	else:
	    #New user, create.
	    changes = cdta
	    changes['type'] = 'NEWUSR'
	    changes['user'] = cusr
	    changelist.append(changes)

    return changelist

logger = Factory.get_logger("cronjob")

def main():

    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['delete_users', 'disk_spread=',
                                    'help', 'dry_run'])
    except getopt.GetoptError:
        usage(1)

    delete_users = False
    disk_spread = None
    dry_run = False	
	
    for opt, val in opts:
        if opt == '--delete_users':
            delete_users = True
        elif opt == '--disk_spread':
            disk_spread = getattr(co, val)  # TODO: Need support in Util.py
        elif opt == '--help':
            usage(1)
        elif opt == '--dry_run':
            dry_run = True

    if not disk_spread:
        usage(1)

    full_sync(delete_users, disk_spread, dry_run)
   


def usage(exitcode=0):
    print """Usage: [options]
    --delete_users
    --disk_spread spread (mandatory)
    --dry_run
    --help
    """

    sys.exit(exitcode)

if __name__ == '__main__':
    main()
