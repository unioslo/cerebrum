#!/local/bin/python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import cerebrum_path
import cereconf
import xmlrpclib
import operator

from Cerebrum import Errors
from Cerebrum.Utils import Factory
db = Factory.get('Database')()
db.cl_init(change_program="adfgsync")
group = Factory.get('Group')(db)
co = Factory.get('Constants')(db)

PASSORD = 'cerebrum:Cere7est'

server = xmlrpclib.Server("https://%s@%s:%i" % (
	PASSORD,
	cereconf.AD_SERVER_HOST,
	cereconf.AD_SERVER_PORT))

#logger = Factory.get_logger("console")


def fetch_cerebrum_data(spread):
	
	return group.search(spread)


def fetch_ad_data():
	return server.listObjects('group', True)


def fetch_ad_usrdata():
	#Empty the userattributes dict. Sentence below results in
	#distinguishedName and the default value sAMAccountName.
	server.setUserAttributes()

	return server.listObjects('user', True)



def full_sync(delete_groups, dry_run):
    
	#Fetch AD-data.
	adgroups = fetch_ad_data()		
        print "Fetched %i ad-groups" % len(adgroups)
#	logger.info("Fetched %i ad-groups" % len(adgroups))	

        for row in adgroups:
		print row

	#Fetch cerebrum data.
	print "group_spread:%i" % int(co.spread_ad_group)
	cerebrumgroups = fetch_cerebrum_data(int(co.spread_ad_group))
        print "Fetched %i groups" % len(cerebrumgroups)
#	logger.info("Fetched %i groups" % len(cerebrumgroups))


    #compare cerebrum and ad-data.
	changelist = compare(delete_groups, cerebrumgroups, adgroups)

	adusers = None
        print "Found %i number of changes" % len(changelist)
#	logger.info("Found %i number of changes" % len(changelist))


    #Perform changes. 	
	perform_changes(changelist, dry_run)	
	sync_groups(cerebrumgroups, dry_run)

	cerebrumgroups = None


def perform_changes(changelist, dry_run):
	for chg in changelist:
		if chg['type'] == 'createObject':
			ret = run_cmd(chg['type'], dry_run, 'Group', 
						'OU=grupper,OU=cerebrum,DC=NMH-TEST,DC=no', 
						chg['sAMAccountName'])
			if not ret[0]:
				print "Warning(creObj): %s" % ret[1]
				#logger.warn(ret[1])
		elif chg['type'] == 'deleteObject':
			run_cmd('bindObject', dry_run, chg['distinguishedName'])
			ret = run_cmd(chg['type'], dry_run)
			if not ret[0]:
				#logger.warn(ret[1])
				print "Warning(delObj) %s" % ret[1]
		else:
			#logger.warn("unknown type: %s" % chg['type'])
		        print "unknown type: %s" % chg['type']
			
	print "perform changes done"

def sync_groups(cerebrumgroups, dry_run):
	#To reduce traffic, we send current list of groupmembers to AD, and the
	#server ensures that each group have correct members.   

	#print "Fetching users in AD"
	#users_in_ad = fetch_ad_usrdata()


	for (grp_id, grp_name, grp_desc) in cerebrumgroups:
		#Only interested in union members(believe this is only type in use)
		print "group:%s" % grp_name

		group.clear()
		group.find(grp_id)				 
		user_memb = group.list_members(spread=co.spread_ad_account, get_entity_name=True)
		group_memb = group.list_members(spread=co.spread_ad_group, get_entity_name=True)
		members = []
		for usr in user_memb[0]:
		    #TODO: How to treat quarantined users???, some exist in AD, 
		    #others do not. They generate errors when not in AD. We still
		    #want to update group membership if in AD.

			#if usr[2] in users_in_ad:
			members.append(usr[2])

		for grp in group_memb[0]:
			print grp
			members.append('%s%s' % (grp[2],''))#cereconf.AD_GROUP_POSTFIX))
	
		dn = server.findObject('%s%s' % (grp_name,''))# cereconf.AD_GROUP_POSTFIX))
		if not dn:
                        print  "unknown group: %s%s" % (grp_name,'')# cereconf.AD_GROUP_POSTFIX)	
			#logger.debug("unknown group: %s%s" % (grp_name,'')# cereconf.AD_GROUP_POSTFIX))	
		else:
			server.bindObject(dn)
			res = server.syncMembers(members, False)
			if not res[0]:
				print "syncMembers %s failed for:%r" % (dn,res[1:])
				#logger.debug("syncMembers %s failed for:%r" % (dn,res[1:]))


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


def compare(delete_groups,cerebrumgrp,adgrp):
	print "compare started"
	changelist = []	 	

	for (grp_id, grp, description) in cerebrumgrp:

		if 'CN=%s%s,%s,%s' % (grp,'','OU=grupper','OU=cerebrum,DC=NMH-TEST,DC=no'# Trenger fiks av cereconf.py
				      #cereconf.AD_GROUP_POSTFIX, 
				      #cereconf.AD_DEFAULT_GROUP_OU,
				      #cereconf.AD_LDAP
					   ) in adgrp:
			adgrp.remove('CN=%s%s,%s,%s' % (grp,'','OU=grupper','OU=cerebrum,DC=NMH-TEST,DC=no'
							#cereconf.AD_GROUP_POSTFIX,
							#cereconf.AD_DEFAULT_GROUP_OU,
							#cereconf.AD_LDAP
							))
		else:
			#Group not in AD, create.
			print "match failed"
			changelist.append({'type': 'createObject',
					   'sAMAccountName' : '%s%s' % (grp,''),
									#cereconf.AD_GROUP_POSTFIX),
					   'description' : description})
 	
	#The remaining groups is surplus in AD.
	for adg in adgrp:
		#if adg.find(cereconf.AD_DO_NOT_TOUCH) >= 0:			
		#	pass
		#elif adg.find('CN=Builtin,%s' % cereconf.AD_LDAP) >= 0:
		#	pass
		#else:
		changelist.append({'type' : 'deleteObject','distinguishedName' : adg}) 

	return changelist



def main():

    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['delete_groups','help', 'dry_run'])
    except getopt.GetoptError:
        usage(1)

    delete_groups = False
    dry_run = False	
	
    for opt, val in opts:
        if opt == '--delete_groups':
            delete_groups = True
        elif opt == '--help':
            usage(1)
        elif opt == '--dry_run':
            dry_run = True

    full_sync(delete_groups, dry_run)
   


def usage(exitcode=0):
    print """Usage: [options]
    --delete_groups
    --dry_run
    --help
    """

    sys.exit(exitcode)

if __name__ == '__main__':
    main()
