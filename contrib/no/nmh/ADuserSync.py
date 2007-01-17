#!/local/bin/python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import cerebrum_path
import cereconf
import xmlrpclib
import sre

from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
db = Factory.get('Database')()
db.cl_init(change_program="skeleton")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
group = Factory.get('Group')(db)
person = Factory.get('Person')(db)
qua = Entity.EntityQuarantine(db)

#
# Diverse som egentlig skal stå i cereconf
#
PASSORD = 'cerebrum:Cere7est'
AD_ATTRIBUTES=( "displayName","homeDrive","homeDirectory","sn","givenName")
AD_HOME_DRIVE_STUDENT = "K"
AD_HOME_DIRECTORY_STUDENT = '\\\\ZIDANE\\users$\\'
AD_HOME_DRIVE_ANNSATT = "J"
AD_HOME_DIRECTORY_ANNSATT = '\\\\ZIDANE\\users$\\'


# brukt til testing
#AD_HOME_DIRECTORY_ANNSATT = '\\\\dc-torfu\\TESTSHARE\\'


server = xmlrpclib.Server("https://%s@%s:%i" % (
    PASSORD,
    cereconf.AD_SERVER_HOST,
    cereconf.AD_SERVER_PORT))

def get_ad_data():
    #Setting the userattributes to be fetched.
    server.setUserAttributes(AD_ATTRIBUTES, cereconf.AD_ACCOUNT_CONTROL)
    return server.listObjects('user', True)

def get_cerebrum_data():
    pid2name = {}
    
    #for row in person.list_persons_name(source_system=co.system_cached):
    #    pid2name.setdefault(int(row['person_id']), row['name'])
    
    pid2name = person.getdict_persons_names(name_types = (co.name_full,co.name_first,co.name_last))

    print "Fetched %i person names" % len(pid2name)

    aid2ainfo = {}
    #
    # collecting acount id and username
    #
    for row in ac.list_account_home(account_spread=co.spread_ad_account, filter_expired=True, include_nohome=True):
        aid2ainfo[int(row['account_id'])] = { 'uname' : row['entity_name'] }
        
    #
    # Get lists for affiliatio_annsatt, affiliation_student, affiliation_admin
    #
    # Merk at verdien av affiliation = navnet på OU (bør vel egentlig settes i cereconf?)
    #
    # Studenter
    #
    count = 0
    for row in ac.list_accounts_by_type(affiliation=co.affiliation_student):
        if aid2ainfo.has_key(int(row['account_id'])):
            aid2ainfo[int(row['account_id'])]['affiliation'] = 'studenter'
            count = count +1
    print "added %d studenter" % count       

    # Annsatte (merk, overskriver studenter)
    #
    count = 0
    for row in ac.list_accounts_by_type(affiliation=co.affiliation_tilknyttet):
        if aid2ainfo.has_key(int(row['account_id'])):
            aid2ainfo[int(row['account_id'])]['affiliation'] = 'administrative' 
            count = count +1
    print "added %d annsatte" % count  

    # Faglig annsatte (merk, overskriver annsatte _og_ studenter)
    #
    count = 0
    for row in ac.list_accounts_by_type(ou_id=17726):
        if aid2ainfo.has_key(int(row['account_id'])):
            aid2ainfo[int(row['account_id'])]['affiliation'] = 'faglige' 
            count = count +1
    print "added %d fagligannsatte" % count  

    
    #print "Fetched %i accounts with ad_spread" % len(aid2ainfo)
    #Filter quarantined users.
    count = 0
    for row in qua.list_entity_quarantines(only_active=True, entity_types=co.entity_account):
        if not aid2ainfo.has_key(int(row['entity_id'])):
            continue
        else:
            if not aid2ainfo[int(row['entity_id'])].get('quarantine',False):
                aid2ainfo[int(row['entity_id'])]['quarantine'] = True
                count = count +1
                
    print "Fetched %i quarantined accounts" % count
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
        #
        # Legg til info om student/annsatt
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
    #
    # regex til a plukke ut ou
    #    
    exp = sre.compile('CN=[^,]+,OU=([^,]+)')
    print "testing %d users for cerebrum/AD membership and changes" % len(adusers)

    for usr, dta in adusers.items():
        if cerebrumusers.has_key(usr):
            # User defined both in AD and cerebrum, need to check data
            changes = {}
            #
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

            # test OU in AD for users
            ou = exp.match(dta['distinguishedName'])
            if ou.group(1):
                if ou.group(1) == cerebrumusers[usr]['affiliation']:
                    pass
                else:
                    changes['affiliation'] = cerebrumusers[usr]['affiliation']
                    changes['type'] = 'MOVEUSR'

                # test homeDrive og homeDir sammtidig        
                if ou.group(1) == "studenter":
                    if (dta['homeDrive'] == AD_HOME_DRIVE_STUDENT and
                    dta['homeDirectory'] == "%s%s" % (AD_HOME_DIRECTORY_STUDENT,usr)):
                        # Ting stemmer
                        pass
                    else:
                        changes['homeDrive'] = AD_HOME_DRIVE_STUDENT
                        changes['homeDirectory'] = "%s%s" % (AD_HOME_DIRECTORY_STUDENT,usr)
                        if not changes.has_key('type'):
                            changes['type'] = 'UPDATEUSR'
                else:
                    if (dta['homeDrive'] == AD_HOME_DRIVE_ANNSATT and
                    dta['homeDirectory'] == "%s%s" % (AD_HOME_DIRECTORY_ANNSATT,usr)):
                        # Ting stemmer
                        pass
                    else:
                        changes['homeDrive'] = AD_HOME_DRIVE_ANNSATT
                        changes['homeDirectory'] = "%s%s" % (AD_HOME_DIRECTORY_ANNSATT,usr)
                        if not changes.has_key('type'):
                            changes['type'] = 'UPDATEUSR'

                        
            else:
                #
                # Not posible to determine OU for user
                #
                print "Not match for DN: %s" % dta['distinguishedName']                
            # Delete user from cerebrumusers
            del cerebrumusers[usr]
            
        else:
            # User is in AD but not in cerebrum, delete user
            # safe since we only get data from the cerebrum OU
            
            # ignores users in cerebrum deleted           
            ou = exp.match(dta['distinguishedName'])
            if ou.group(1) == 'cerebrum_deleted':
                print "ignoring %s" % usr
            else:
                changes['type'] = 'DELUSR'
                changes['distinguishedName'] = adusers[usr]['distinguishedName']
            
                
        #If any changes append to changelist.
        if len(changes):
            changes['distinguishedName'] = adusers[usr]['distinguishedName']
            changelist.append(changes)    
            
            
    print "creating %d users" % len(cerebrumusers)         
    #The remaining items in cerebrumusrs is not in AD, create user.
    for cusr, cdta in cerebrumusers.items():
        changes={}
        #TODO:Should quarantined users be created?
        if cerebrumusers[cusr]['ACCOUNTDISABLE']:
            #Quarantined, do not create.
            pass
        else:
            #New user, create.
            changes = cdta
            changes['type'] = 'NEWUSR'
            changes['sAMAccountName'] = cusr
            changelist.append(changes)
            
    return changelist

def create_user(elem):
    #
    # TO DO: legg til resten av AD data
    #
    ou = "OU=%s,%s" % (elem['affiliation'],cereconf.AD_LDAP)

    if elem['affiliation'] == 'studenter':
        elem['homeDirectory'] = "%s%s" %(AD_HOME_DIRECTORY_studenter,elem['sAMAccountName'])
        elem['homeDrive'] = AD_HOME_DRIVE_studenter
    else:
        elem['homeDirectory'] = "%s%s" %(AD_HOME_DIRECTORY_ANNSATT,elem['sAMAccountName'])
        elem['homeDrive'] = AD_HOME_DRIVE_ANNSATT

    print elem
    print "\n"
            
    ret = run_cmd('createObject', 'User', ou, elem['sAMAccountName'])
    if ret[0]:
        print "created user %s" % ret
    else:
        print "create user %s failed: %r" % (elem['sAMAccountName'], ret)
        
    pw = unicode(ac.make_passwd(elem['sAMAccountName']), 'iso-8859-1')
    ret = run_cmd('setPassword', pw)
    if ret[0]:
        del elem['type']
        #if elem.has_key('distinguishedName'):
        #    del elem['distinguishedName']
        #if elem.has_key('sAMAccountName'):
        #    del elem['sAMAccountName']

        for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
            if not elem.has_key(acc):
                elem[acc] = value

        ret = run_cmd('putProperties', elem)
        if not ret[0]:
            print "Faen, putProperties feila (%s)" % elem


        print "Creating homeDirectory %s\n" % elem['homeDirectory']
        ret = run_cmd('createHomedir')
        if not ret:
            print "createHomedir funka ikke (%s)" % ret[0]

            
        ret = run_cmd('setObject')
        if not ret[0]:
            print "setObject on %s failed: %r" % (elem['sAMAccountName'], ret)
    else:
        print "setPassword on %s failed: %s" % (elem['sAMAccountName'], ret)
            

def move_user(chg):
    ret = run_cmd('bindObject',chg['distinguishedName'])
    if not ret[0]:
        print "bindObject on %s failed: %r" % (chg['sAMAccountName'], ret)      
    else:
        ou = "OU=%s,%s" % (chg['affiliation'], cereconf.AD_LDAP)
        ret = run_cmd('moveObject',ou)
        if not ret[0]:
            print "move_user failed? %s" % ret
        else:
            print "move sucsess? %s" % ret

def del_user(chg):
    print "flytter %s til cerebrum_deleted" % chg
    chg['type'] = 'MOVEUSR'
    chg['affiliation'] = 'cerebrum_deleted'
    move_user(chg)
    
"""
    ret = run_cmd('bindObject',chg['distinguishedName'])
    if not ret[0]:
        print "bindObject on %s failed: %r" % (chg['sAMAccountName'], ret)
    else:
        ret = run_cmd('deleteObject')
    if not ret[0]:
        print "deleteObject on %s failed %s" % (chg['sAMAccountName'], ret)
"""

def update_user(chg):
    print "updating %s" % chg  
    ret = run_cmd('bindObject',chg['distinguishedName'])
    if not ret[0]:
        print "bindObject on %s failed: %r" % (chg['sAMAccountName'], ret)
    else:
        ret = run_cmd('putProperties',chg)
    if not ret[0]:
        print "putProperties on %s failed %s" % (chg['sAMAccountName'], ret)
    else:
        run_cmd('setObject')
    if not ret[0]:
        print "setObject on %s failed %s" % (chg['sAMAccountName'], ret)
        
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



c_data = {}
c_data = get_cerebrum_data()

ad_data = {}
ad_data = get_ad_data()


print "fetched %d users from cerebrum, %d from AD" %(len(c_data),len(ad_data))
changes = compare(ad_data,c_data)


print "performing %d changes" % len(changes)
perform_changes(changes)


    
