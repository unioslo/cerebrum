#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import cerebrum_path
import cereconf
import xmlrpclib


from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import MountHost
db = Factory.get('Database')()
db.cl_init(change_program="adfusync")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
person = Factory.get('Person')(db)
host = Factory.get('Host')(db)
qua = Entity.EntityQuarantine(db)
mh = MountHost.MountHost(db)
server = xmlrpclib.Server("https://%s:%i" % (cereconf.AD_SERVER_HOST,
		cereconf.AD_SERVER_PORT))
logger = Factory.get_logger("cronjob")


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
	for row in ac.list_account_home(home_spread=disk_spread, account_spread=spread, filter_expired=True, include_nohome=True):
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
	for row in qua.list_entity_quarantines(only_active=True, entity_types=co.entity_account):
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
	# Important too have right encoding of strings or comparison will fail.
	# Have not taken a throughout look, but it seems that AD LDAP use utf-8
	# Some web-pages says that AD uses ANSI 1252 for DN. I test on a point 
	# to point basis.	

		tmp = {
			#AccountID - populating the employeeNumber field in AD. 
			'employeeNumber': unicode(str(ac_id),'UTF-8'),
			}
		
		hostname = hid2hname.get(dta.get('host_id', None),None)
		if hostname and dta['uname']:
			tmp['homeDirectory'] = '\\\\%s\\%s' % (hostname, dta['uname']) 
		tmp['ACCOUNTDISABLE'] = dta.get('quarantine', False)

		if dta.has_key('owner_id'):
			pnames = pid2name.get(dta['owner_id'], None)
			if pnames is None:
				logger.warn("%i is very new?" % dta['owner_id'])
				tmp['displayName'] = unicode(dta['uname'],'UTF-8')
			else:
				tmp['displayName'] = unicode(pnames,'ISO-8859-1')
		else:
			pass
			#logger.info("Not a person:%s" % dta['uname'])

		ret[dta['uname']] = tmp

	return ret


def fetch_ad_data(dry_run):
	#Setting the userattributes to be fetched.
	server.setUserAttributes(cereconf.AD_ATTRIBUTES, cereconf.AD_ACCOUNT_CONTROL)

	return server.listObjects('user', True)


def full_sync(delete_users, disk_spread, dry_run):
    
	#Fetch AD-data.	
	adusers = fetch_ad_data(dry_run)		

	#print adusers
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

	for chg in changelist:
		if chg['type'] == 'NEWUSR':
	    
			if cereconf.AD_DEFAULT_OU == '0':
				ou = "cn=Users,%s" % cereconf.AD_LDAP
			else:
				ou = cereconf.AD_LDAP

			ret = run_cmd('createObject', dry_run, 'User', ou, chg['sAMAccountName'])
			if ret[0]:
				if not dry_run:
					logger.info("created user %s" % ret)
			else:
				logger.warning("create user %s failed: %r" % \
					(chg['sAMAccountName'], ret))

			pw = unicode(ac.make_passwd(chg['sAMAccountName']), 'iso-8859-1')

			ret = run_cmd('setPassword', dry_run, pw)
			if ret[0]:
				#Important not to enable a new account if setPassword fail,
				#it will have a blank password.

				del chg['type']
				if chg.has_key('distinguishedName'):
					del chg['distinguishedName']
				if chg.has_key('sAMAccountName'):
					del chg['sAMAccountName']

				for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():			
					if not chg.has_key(acc):
						chg[acc] = value	
			
				#Homedrive set to default value.
				chg['homeDrive'] = cereconf.AD_HOME_DRIVE

				ret = run_cmd('putProperties', dry_run, chg)
				if not ret[0]:
					logger.warning("putproperties on %s failed: %r" % \
						(chg['sAMAccountName'], ret))

				ret = run_cmd('setObject', dry_run)
				if not ret[0]:
					logger.warning("setObject on %s failed: %r" % \
						(chg['sAMAccountName'], ret))
			else:
				logger.warning("setPassword on %s failed: %s" % \
					(chg['sAMAccountName'], ret))

		else:

			ret = run_cmd('bindObject', dry_run, chg['distinguishedName'])
			if not ret[0]:
				logger.warning("bindObject on %s failed: %r" % \
					(chg['sAMAccountName'], ret))

			if chg['type'] == 'MOVEOBJ':

				ret = run_cmd('moveObject', dry_run, chg['ou'])
				if not ret[0]:
					logger.warning("moveObject on %s failed: %r" % \
						(chg['distinguishedName'], ret))


			elif chg['type'] == 'ALTRUSR':
				#Already binded,we do not want too sync the defaultvalues
				del chg['type']
				if chg.has_key('distinguishedName'):
					del chg['distinguishedName']
				if chg.has_key('sAMAccountName'):
					del chg['sAMAccountName']

				ret = run_cmd('putProperties', dry_run, chg)
				if not ret[0]:
					logger.warning("putproperties on %s failed: %r" % \
						(chg['sAMAccountName'], ret))

				ret = run_cmd('setObject', dry_run)
				if not ret[0]:
					logger.warning("setObject on %s failed: %r" % \
						(chg['sAMAccountName'], ret))


			elif chg['type'] == 'DELUSR':
				ret = run_cmd('deleteObject', dry_run)
				if not ret[0]:
					logger.warning("deleteObject on %s failed: %r" % \
						(chg['distinguishedName'], ret))
				else:
					logger.debug("deleteObject %s success" % \
						chg['distinguishedName'])
				
			else:
				logger.warning("Unknown type %s" % chg['type'])
	
	    
def run_cmd(command, dry_run, arg1=None, arg2=None, arg3=None):

	if dry_run:
		print('server.%s(%s,%s,%s)' % (command, arg1, arg2, arg3))
		#Assume success on all changes.
		return (True, command)
	else:
		cmd = getattr(server, command)
		if arg1 == None:
			ret = cmd()
		elif arg2 == None:
			ret = cmd(arg1)
		elif arg3 == None:
			ret = cmd(arg1, arg2)
		else:
			ret = cmd(arg1, arg2, arg3)

		return ret


def compare(delete_users,cerebrumusrs,adusrs):
	#The fields fetch from cerebrum should match the field populated in AD.
	#To avoid writing special rules.

	changelist = []	 	

	for usr, dta in adusrs.items():
		changes = {}    	
		if cerebrumusrs.has_key(usr):
			#User is both places, we want to check correct data.
			#Todo:check for correct OU.
			for attr in cereconf.AD_ATTRIBUTES:
			
				#Catching special cases.
		 		#Check against home drive.
				if attr == 'homeDrive':
					if adusrs[usr].has_key('homeDrive'):
						if adusrs[usr]['homeDrive'] != cereconf.AD_HOME_DRIVE:
							changes['homeDrive'] = cereconf.AD_HOME_DRIVE	
					else:
						changes['homeDrive'] = cereconf.AD_HOME_DRIVE	

				#Treating general cases
				else:
					if cerebrumusrs[usr].has_key(attr) and adusrs[usr].has_key(attr):	
						if adusrs[usr][attr] != cerebrumusrs[usr][attr]:
							changes[attr] = cerebrumusrs[usr][attr]	
					else:
						if cerebrumusrs[usr].has_key(attr):
							changes[attr] = cerebrumusrs[usr][attr]	
						elif adusrs[usr].has_key(attr):
							changes[attr] = ''	
		
			for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():			
				if cerebrumusrs[usr].has_key(acc):
					if adusrs[usr].has_key(acc) and \
						adusrs[usr][acc] == cerebrumusrs[usr][acc]:
						pass
					else:
						changes[acc] = cerebrumusrs[usr][acc]	

				else: 
					if adusrs[usr].has_key(acc) and adusrs[usr][acc] == value:
						pass
					else:
						changes[acc] = value
						
			#Setting LDAP path and action.	    
			#If any changes append to changelist.	
			if len(changes):
				changes['distinguishedName'] = adusrs[usr]['distinguishedName']
				changes['type'] = 'ALTRUSR'

	    	#after processing we delete from array.
			del cerebrumusrs[usr]

		else:	   	
	    	#Account not in Cerebrum, but in AD.
			if adusrs[usr]['distinguishedName'].find(cereconf.AD_DO_NOT_TOUCH) >= 0:
				pass
			elif adusrs[usr]['distinguishedName'].find(cereconf.AD_PW_EXCEPTION_OU) >= 0:
		    	#Account do not have AD_spread, but is in AD to 
		    	#register password changes, do nothing.
				pass

			else:
		    	#ac.is_deleted() or ac.is_expired() pluss a small rest of 
		    	#accounts created in AD, but that do not have AD_spread. 
				if delete_users == True:
					changes['type'] = 'DELUSR'
					changes['distinguishedName'] = adusrs[usr]['distinguishedName']
					logger.debug("User %s marked for deleteion" % adusrs[usr]['distinguishedName']) 
				else:
					#Disable account.
					if adusrs[usr]['ACCOUNTDISABLE'] == False:
						changes['distinguishedName'] = adusrs[usr]['distinguishedName']
						changes['type'] = 'ALTRUSR'
						changes['ACCOUNTDISABLE'] = True
						#commit changes
						changelist.append(changes)
						changes = {} 
   					#Moving account.
					if adusrs[usr]['distinguishedName'] != "LDAP://CN=%s,OU=%s,%s" % \
						(usr, cereconf.AD_LOST_AND_FOUND, cereconf.AD_LDAP):
						changes['type'] = 'MOVEOBJ'
						changes['distinguishedName'] = adusrs[usr]['distinguishedName']
						changes['ou'] = "OU=%s,%s" % \
							(cereconf.AD_LOST_AND_FOUND,cereconf.AD_LDAP)

	
		#Finished processing user, register changes if any.
		if len(changes):
			changelist.append(changes)

	
    #The remaining items in cerebrumusrs is not in AD, create user.
	for cusr, cdta in cerebrumusrs.items():
		changes={}
		#TODO:Should quarantined users be created?
		if cerebrumusrs[cusr]['ACCOUNTDISABLE']:
			#Quarantined, do not create.
			pass	
		else:
			#New user, create.
			changes = cdta
			changes['type'] = 'NEWUSR'
			changes['sAMAccountName'] = cusr
			changelist.append(changes)

	return changelist



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
