#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt, sys
import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import MountHost
from Cerebrum.modules import ADutilMixIn

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")


cereconf.AD_USE_MOUNT_HOST=False

class adfusync(ADutilMixIn.ADuserUtil):

    def __init__(self):
        url="http://%s:%i/" % (cereconf.AD_SERVER_HOST,
                               cereconf.AD_SERVER_PORT)
        super(adfusync, self).__init__(db, co, logger,
                                       url=url)
        self.logger = Factory.get_logger("cronjob")
        self.person = Factory.get('Person')(self.db)
        self.host = Factory.get('Host')(self.db)
        self.qua = Entity.EntityQuarantine(self.db)
        self.mh = MountHost.MountHost(self.db)


        
    def fetch_cerebrum_data(self, spread, disk_spread):
        """For all accounts that has spread, returns a list of dicts with
        the keys: uname, fullname, account_id, person_id, host_name
        """
        hid2hname = {}

        #Fetch the mapping person_id to full_name.
        pid2name = {}
        for row in self.person.list_persons_name(source_system=self.co.system_cached):
            pid2name.setdefault(int(row['person_id']), row['name'])
        self.logger.info("Fetched %i person names" % len(pid2name))


        # Fetch account-info.  Unfortunately the API doesn't provide all
        # required info in one function, so we do this in steps.

        aid2ainfo = {}
        for row in self.ac.list_account_home(home_spread=disk_spread,
                                        account_spread=spread,
                                        filter_expired=True,
                                        include_nohome=True):
            if row['host_id']:
                aid2ainfo[int(row['account_id'])] = {
                    'uname': row['entity_name'],
                    'host_id': int(row['host_id'])        
                    }
            else:
                aid2ainfo[int(row['account_id'])] = {
                    'uname': row['entity_name'],
                    }

        self.logger.info("Fetched %i accounts with ad_spread" % len(aid2ainfo))

        #Filter quarantined users.
        qcount = 0
        for row in self.qua.list_entity_quarantines(only_active=True,
                                               entity_types=co.entity_account):
            if not aid2ainfo.has_key(int(row['entity_id'])):
                continue
            else:
                if not aid2ainfo[int(row['entity_id'])].get('quarantine',False):
                    aid2ainfo[int(row['entity_id'])]['quarantine'] = True
                    qcount = qcount +1

        self.logger.info("Fetched %i quarantined accounts" % qcount)


        #Fetch mapping between account_id and person_id(owner_id).
        for row in self.ac.list():
            if not aid2ainfo.has_key(int(row['account_id'])):
                continue
            if row['owner_type'] != int(co.entity_person):
                continue
            aid2ainfo[int(row['account_id'])]['owner_id'] = int(row['owner_id'])

        ret = {}
    
        for ac_id, dta in aid2ainfo.items():
            # Important too have right encoding of strings or comparison will
            # fail Seems like AD LDAP mainly use utf-8, some web-pages
            # says that AD uses ANSI 1252 for DN.

            tmp = {'employeeNumber': unicode(str(ac_id),'UTF-8')}
        
            hostname = hid2hname.get(dta.get('host_id', None),None)
            if hostname and dta['uname']:
                tmp['homeDirectory'] = '\\\\%s\\%s' % (hostname, dta['uname']) 
            tmp['ACCOUNTDISABLE'] = dta.get('quarantine', False)

            if dta.has_key('owner_id'):
                pnames = pid2name.get(dta['owner_id'], None)
                if pnames == None:
                    logger.warn("%i is very new?" % dta['owner_id'])
                    tmp['displayName'] = unicode(dta['uname'],'UTF-8')
                else:
                    tmp['displayName'] = unicode(pnames,'ISO-8859-1')
            else:
                pass

            ret[dta['uname']] = tmp

        return ret



    def full_sync(self, type, delete_users, user_spread, disk_spread, dry_run):

        #Fetch AD-data.    
        adusers = self.fetch_ad_data()
        logger.info("Fetched %i ad-users" % len(adusers))

        #Fetch cerebrum data.
        cerebrumusers = self.fetch_cerebrum_data(user_spread, disk_spread) 
        logger.info("Fetched %i users" % len(cerebrumusers))

        #compare cerebrum and ad-data.
        changelist = self.compare(delete_users,cerebrumusers,adusers)    
        cerebrumusers = {}    
        adusers = {}    
        logger.info("Found %i number of changes" % len(changelist))

        #Perform changes.
        self.perform_changes(changelist, dry_run)    

    def get_default_ou(self, change = None):
        #Returns default OU in AD.
        return "OU=Brukere,%s" % cereconf.AD_LDAP

    def get_password(uname):
        password = ac.get_account_authentication(co.auth_type_pgp_offline)
        cleartext=self.ac.decrypt_password(co.auth_type_pgp_offline, password)
        return unicode(cleartext, 'iso-8859-1')



class adfgsync(ADutilMixIn.ADgroupUtil):
    #Groupsync Mixin

    def get_default_ou(self, change = None):
        #Returns default OU in AD.
        return "OU=Grupper,%s" % cereconf.AD_LDAP
       


def usage(exitcode=0):
    print """Usage:
    [--user_sync | --group_sync]
    [--delete_objects]
    [--disk_spread spread] 
    [--user_spread spread]
    [--dry_run]
    [--help]
    """

    sys.exit(exitcode)


def main():

    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['user_sync',
                                                      'group_sync',
                                                      'delete_objects',
                                                      'user_spread',
                                                      'disk_spread',
                                                      'group_spread',
                                                      'help',
                                                      'dry_run'])

    except getopt.GetoptError:
        usage(1)

    delete_objects = False
    disk_spread = co.spread_ntnu_ntnu_ad_user
    user_spread = co.spread_ntnu_ntnu_ad_user
    group_spread = co.spread_ntnu_group
    dry_run = False    
    user_sync = False
    group_sync = False
    
    for opt, val in opts:
        if opt == '--delete_objects':
            delete_users = True
        elif opt == '--user_sync':
            user_sync = True
        elif opt == '--group_sync':
            group_sync = True
        elif opt == '--disk_spread':
            disk_spread = getattr(co, val)  # TODO: Need support in Util.py
        elif opt == '--user_spread':
            user_spread = getattr(co, val)  # TODO: Need support in Util.py
        elif opt == '--group_spread':
            group_spread = getattr(co, val)  # TODO: Need support in Util.py
        elif opt == '--help':
            usage(1)
        elif opt == '--dry_run':
            dry_run = True

    if user_sync:
        ADfullUser = adfusync()    
        ADfullUser.full_sync('user', delete_objects, user_spread,
                             disk_spread, dry_run)

    if group_sync:
        ADfullGroup = adfgsync()
        ADfullGroup.full_sync('group', delete_objects, group_spread,
                              dry_run, user_spread)

if __name__ == '__main__':
    main()
