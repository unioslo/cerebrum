#!/local/bin/python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2006 University of Oslo, Norway
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

import getopt
import sys
import cerebrum_path
import cereconf
import xmlrpclib
import sre

from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory


def get_ad_data():
    # which user attributes should be fetched for users at NMH
    server.setUserAttributes(cereconf.AD_ATTRIBUTES, cereconf.AD_ACCOUNT_CONTROL)
    return server.listObjects('user', True)


def get_cerebrum_data():
    pid2name = {}
    
    pid2name = person.getdict_persons_names(name_types = (co.name_full,
                                                          co.name_first,
                                                          co.name_last))

    logger.debug("Fetched %i person names", len(pid2name))

    aid2ainfo = {}
    
    #
    # find account id's and names
    #
    for row in ac.list_account_home(account_spread=co.spread_ad_account,
                                    filter_expired=True,
                                    include_nohome=True):
        aid2ainfo[int(row['account_id'])] = { 'uname' : row['entity_name'] }
        
    #
    # Get lists for affiliatio_ansatt, affiliation_student, affiliation_admin


    # Students
    #
    count = 0
    for row in ac.list_accounts_by_type(affiliation=co.affiliation_student):
        if aid2ainfo.has_key(int(row['account_id'])):
            aid2ainfo[int(row['account_id'])]['affiliation'] = cereconf.AD_STUDENT_OU
            count = count +1
    logger.info("Added %d students", count)

    # Staff (overrides information registered for students) 
    #
    count = 0
    for row in ac.list_accounts_by_type(affiliation=co.affiliation_tilknyttet):
        if aid2ainfo.has_key(int(row['account_id'])):
            aid2ainfo[int(row['account_id'])]['affiliation'] = cereconf.AD_ADMINISTRATION_OU
            count = count +1
    logger.info("Added %d administrative employees", count)

    # Faculty (overrides information registered for staff and students)
    #
    count = 0
    for row in ac.list_accounts_by_type(ou_id=cereconf.CEREBRUM_FAGANSATT_OU_ID):
        if aid2ainfo.has_key(int(row['account_id'])):
            aid2ainfo[int(row['account_id'])]['affiliation'] = cereconf.AD_FAGANSATT_OU
            count = count +1
    logger.info("Added %d faculty", count)  

    # Remove quarantined users
    #
    count = 0
    for row in qua.list_entity_quarantines(only_active=True, entity_types=co.entity_account):
        if not aid2ainfo.has_key(int(row['entity_id'])):
            continue
        else:
            if not aid2ainfo[int(row['entity_id'])].get('quarantine',False):
                aid2ainfo[int(row['entity_id'])]['quarantine'] = True
                count = count +1
    logger.info("Fetched %i quarantined accounts", count)
    
    # Mapp accounts to owners (account_id to person_id).
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
            # AccountID - populating the employeeNumber field in AD.
            # Is this really necessary seeing as we do not actually have employee
            # numbers at NMH? 
            'employeeNumber': unicode(str(ac_id),'UTF-8'),
            }

        # Register student/employee information
        #
        if dta.has_key('affiliation'):
            tmp['affiliation']=dta['affiliation']   
        
        tmp['ACCOUNTDISABLE'] = dta.get('quarantine', False)
        
        if dta.has_key('owner_id'):
            # pnames er dict
            pnames = pid2name.get(dta['owner_id'], None)
            if pnames is None:
                continue
            else:
                # sett displayName
                if pnames[int(co.name_full)] is None:
                    tmp['displayName'] = unicode(dta['uname'],'UTF-8')
                else:
                    tmp['displayName'] = unicode(pnames[int(co.name_full)],'ISO-8859-1')
                # sett firsname
                if pnames[int(co.name_first)] is None:
                    tmp['givenName'] = unicode(dta['uname'],'UTF-8')
                else:
                    tmp['givenName'] = unicode(pnames[int(co.name_first)],'ISO-8859-1')                
                # sett lastname
                if pnames[int(co.name_last)] is None:
                    tmp['sn'] = unicode(dta['uname'],'UTF-8')
                else:
                    tmp['sn'] = unicode(pnames[int(co.name_last)],'ISO-8859-1')   
                
        else:
            pass
        if tmp.has_key('affiliation'):
            ret[dta['uname']] = tmp
    return ret
        

def compare(adusers,cerebrumusers):
    changelist = []
    
    # picking correct ou requires use of 
    #    
    exp = sre.compile('CN=[^,]+,OU=([^,]+)')
    logger.info("Checking %d accounts for Cerebrum/AD-membership and changes" % len(adusers))

    for usr, dta in adusers.items():
        if cerebrumusers.has_key(usr):
            # User defined both in AD and cerebrum, check data
            changes = {}
            
            # test sn, givenName, displayName
            # 
            # Hack:
            if not dta.has_key('sn'):
                dta['sn'] = None;
                
            if not dta.has_key('givenName'):
                dta['givenName'] = None
                
            if not dta.has_key('displayName'):
                dta['displayName'] = None

            if not dta.has_key('homeDrive'):
                dta['homeDrive'] = None

            if not dta.has_key('profilePath'):
                dta['profilePath'] = None

            if not dta.has_key('homeDirectory'):
                dta['homeDirectory'] = None 
                        
            if not dta['sn'] == cerebrumusers[usr]['sn']:
                changes['sn'] = cerebrumusers[usr]['sn']
                changes['type'] = 'UPDATEUSR'

            if not dta['givenName'] == cerebrumusers[usr]['givenName']:
                changes['givenName'] = cerebrumusers[usr]['givenName']
                changes['type'] = 'UPDATEUSR'  

            if not dta['displayName'] == cerebrumusers[usr]['displayName']:
                changes['displayName'] = cerebrumusers[usr]['displayName']
                changes['type'] = 'UPDATEUSR'

            # test AD_OU for users
            ou = exp.match(dta['distinguishedName'])
            if ou.group(1):
                if ou.group(1) == cerebrumusers[usr]['affiliation']:
                    pass
                else:
                    changes['affiliation'] = cerebrumusers[usr]['affiliation']
                    changes['type'] = 'MOVEUSR'

                # test homeDrive og homeDir
                if ou.group(1) == "studenter":
                    if (dta['homeDrive'] == cereconf.AD_HOME_DRIVE_STUDENT and
                        dta['homeDirectory'] == "%s%s" % (cereconf.AD_HOME_DIRECTORY_STUDENT, usr) and
                        dta['profilePath'] == "%s%s" % (cereconf.AD_PROFILE_PATH_STUDENT, usr)):
                        # no changes
                        pass
                    else:
                        changes['homeDrive'] = cereconf.AD_HOME_DRIVE_STUDENT
                        changes['homeDirectory'] = "%s%s" % (cereconf.AD_HOME_DIRECTORY_STUDENT, usr)
                        changes['profilePath'] = "%s%s" % (cereconf.AD_PROFILE_PATH_STUDENT, usr)
                        if not changes.has_key('type'):
                            changes['type'] = 'UPDATEUSR'
                else:
                    if (dta['homeDrive'] == cereconf.AD_HOME_DRIVE_ANSATT and
                        dta['homeDirectory'] == "%s%s" % (cereconf.AD_HOME_DIRECTORY_ANSATT, usr) and
                        dta['profilePath'] == None):
                        # no changes
                        pass
                    else:
                        changes['homeDrive'] = cereconf.AD_HOME_DRIVE_ANSATT
                        changes['homeDirectory'] = "%s%s" % (cereconf.AD_HOME_DIRECTORY_ANSATT,usr)
                        changes['profilePath'] = ''
                        if not changes.has_key('type'):
                            changes['type'] = 'UPDATEUSR'
            else:
                
                # Impossible to determine OU for a given account
                #
                logger.warn("No DN-match for: %s", dta['distinguishedName'])
            # remove account info from cerebrumusers
            #
            del cerebrumusers[usr]
        else:
            # User is in AD but not in cerebrum, delete user
            # safe since we only get data from the cerebrum OU
            # ignore account in "cerebrum deleted"
            #
            ou = exp.match(dta['distinguishedName'])
            if ou.group(1) == cereconf.AD_CEREBRUM_DELETED
                logger.debug("Ignoring deleted account %s", usr)
            else:
                changes['type'] = 'DELUSR'
                changes['distinguishedName'] = adusers[usr]['distinguishedName']
            
                
        # Append changes to changelist.
        #
        if len(changes):
            changes['distinguishedName'] = adusers[usr]['distinguishedName']
            changelist.append(changes)    
            
            
    logger.info("Creating %d accounts in AD", len(cerebrumusers))
    
    # Add accounts still registered in cerebrumusers to AD
    for cusr, cdta in cerebrumusers.items():
        changes={}
        # TODO:Should quarantined users be created?
        #
        if cerebrumusers[cusr]['ACCOUNTDISABLE']:
            # quarantined, do not create.
            #
            pass
        else:
            # Create account in AD
            #
            changes = cdta
            changes['type'] = 'NEWUSR'
            changes['sAMAccountName'] = cusr
            changelist.append(changes)
            
    return changelist

def create_user(elem):
   
    ou = "OU=%s,%s" % (elem['affiliation'], cereconf.AD_LDAP)

    if elem['affiliation'] == cereconf.AD_STUDENT_OU:
        elem['homeDirectory'] = "%s%s" %(cereconf.AD_HOME_DIRECTORY_STUDENT, elem['sAMAccountName'])
        elem['homeDrive'] = cereconf.AD_HOME_DRIVE_STUDENT
    else:
        elem['homeDirectory'] = "%s%s" %(cereconf.AD_HOME_DIRECTORY_ANSATT, elem['sAMAccountName'])
        elem['homeDrive'] = cereconf.AD_HOME_DRIVE_ANSATT
    logger.debug("Creating account %s, homedir %s, homedrive %s" % (elem['sAMAccountName'],
                                                                    elem['homeDirectory'],
                                                                    elem['homeDrive']))
    ret = run_cmd('createObject', 'User', ou, elem['sAMAccountName'])
    if ret[0]:
        logger.info("Succesfully created account %s", elem['sAMAccountName'])
    else:
        logger.error("Create account failed for %s", elem['sAMAccountName'])

    # temporary password is registered for all created accounts
    # this password wil be overridden by adpwdsync
    #
    pw = unicode(ac.make_passwd(elem['sAMAccountName']), 'iso-8859-1')
    ret = run_cmd('setPassword', pw)
    if ret[0]:
        del elem['type']
        
        for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
            if not elem.has_key(acc):
                elem[acc] = value

        ret = run_cmd('putProperties', elem)

        if not ret[0]:
            logger.warn("Could not register properties for account %s", elem['sAMAaccountName'])

        logger.debug("Creating homeDirectory %s", elem['homeDirectory'])
        ret = run_cmd('createHomedir')
        if not ret:
            logger.error("Could not create homedir for %s, (%s)" % (elem['sAMAaccountName'], elem['homeDirectory']))
            
        ret = run_cmd('setObject')
        if not ret[0]:
            logger.error("setObject on %s failed", elem['sAMAccountName'])
    else:
        logger.error("Could not set password for account %s", elem['sAMAccountName'])
            

def move_user(chg):
    ret = run_cmd('bindObject', chg['distinguishedName'])
    if not ret[0]:
        logger.warn("Could not find object %s (bindObject failed)", (chg['distinguishedName']))
    else:
        ou = "OU=%s,%s" % (chg['affiliation'], cereconf.AD_LDAP)
        ret = run_cmd('moveObject', ou)
        if not ret[0]:
            logger.error("Failed to move account %s.", chg['distinguishedName'])
        else:
            logger.warn("Moved account %s", chg['distinguishedName'])


def del_user(chg):
    logger.info("Moving account %s to ou for non-active users", chg['distinguishedName'])
    chg['type'] = 'MOVEUSR'
    chg['affiliation'] = cereconf.AD_CEREBRUM_DELETED
    move_user(chg)

    
def update_user(chg):
    logger.info("Updating account %s", chg)
    ret = run_cmd('bindObject',chg['distinguishedName'])
    if not ret[0]:
        logger.error("Could not update account %s (bindObject failed)", chg['sAMAccountName'])
    else:
        ret = run_cmd('putProperties',chg)
    if not ret[0]:
        logger.error("Could not update properties for %s (putProperties failed)", chg['sAMAccountName'])
    else:
        run_cmd('setObject')
    if not ret[0]:
        logger.error("setObject on %s failed", chg['sAMAccountName'])

        
def perform_changes(changes):
    for chg in changes:
        if chg['type'] == 'NEWUSR':
            create_user(chg)
        elif chg['type'] == 'MOVEUSR' :
            move_user(chg)
        elif chg['type'] == 'DELUSR':
            del_user(chg)
        elif chg['type'] == 'UPDATEUSR':
            update_user(chg)

        
def run_cmd(command, arg1=None, arg2=None, arg3=None):
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


def main():
    global db, co, ac, group, person, qua, logger
    global server   
    c_data = {}
    ad_data = {}
    
    db = Factory.get('Database')()
    db.cl_init(change_program="adusync")
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)
    qua = Entity.EntityQuarantine(db)
    logger = Factory.get_logger("cronjob")
    
    passwd = db._read_password(cereconf.AD_SERVER_HOST,
                               cereconf.AD_SERVER_UNAME)

    # Connect to AD-service at NMH
    #
    server = xmlrpclib.Server("https://%s@%s:%i" % (passwd,
                                                    cereconf.AD_SERVER_HOST,
                                                    cereconf.AD_SERVER_PORT))
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['help', 'dry_run'])
    except getopt.GetoptError:
        usage(1)

    dry_run = False	
	
    for opt, val in opts:
        if opt == '--help':
            usage(1)
        elif opt == '--dry_run':
            dry_run = True


    c_data = get_cerebrum_data()

    ad_data = get_ad_data()


    changes = compare(ad_data,c_data)
    logger.info("Will perform %d changes", len(changes))

    if not dry_run:
        perform_changes(changes)


def usage(exitcode=0):
    print """Usage: [options]
    --dry_run
    --help
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
