#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2004 University of Oslo, Norway
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


progname = __file__.split("/")[-1]
__doc__="""This script creates accounts for all persons in cerebrum that has a
employee affiliation and 
- assigns account affiliation accordingly.
- assign default spreads employee accounts as defined in cereconf.
- creates email address
- creates homedir

usage:: %s [options] 

options is    
    -f | --file     : xml file containing person information 
    -h | --help     : show this
    -d | --dryrun   : do not change DB
    --logger-name name   : log name to use 
    --logger-level level : log level to use
""" % ( progname, )


import getopt
import sys
import time
import os
import mx
import xml.sax
from sets import Set

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory # , simple_memoize
from Cerebrum.Constants import Constants
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.xmlutils import GeneralXMLParser
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError
from mx.DateTime import now

#init variables
db = Factory.get('Database')()
db.cl_init(change_program=progname)
logger = Factory.get_logger("cronjob")

person = Factory.get('Person')(db)
temp_acc = Factory.get('Account')(db)
account = Factory.get('Account')(db)
const = Factory.get('Constants')(db)
group = Factory.get('Group')(db)
ou = Factory.get('OU')(db)
sko = Stedkode.Stedkode(db)
#sko = Factory.get('Stedkode')(db)
person_list = []
TODAY=mx.DateTime.today().strftime("%Y-%m-%d")
default_filename='paga_persons_%s.xml' % (TODAY,)
default_person_file=os.path.join(cereconf.DUMPDIR,'employees',default_filename)
dryrun = False

class PagaDataParser(xml.sax.ContentHandler):
    """
    This class is used to iterate over all users in PAGA. 
    """

    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name == 'data':
            pass
        elif name in ("tils", "gjest", "permisjon"):
            pass
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = attrs[k].encode('iso8859-1')
        else:
            logger.error("unknown element: %s in slp4 file" % name)

    def endElement(self, name):
        if name == "person":
            self.call_back_function(self.p_data)


class ExistingAccount(object):
    def __init__(self, fnr, uname, expire_date):
        self._affs=list()
        self._new_affs=list()
        self._expire_date= expire_date
        self._fnr=fnr        
        self._owner_id=None
        self._uid=None
        self._home=dict()
        self._quarantines=list()
        self._spreads=list()
        self._traits=list()
        self._email=None
        self._uname=uname
        self._gecos=None

    def append_affiliation(self, affiliation, ou_id,priority):
        self._affs.append((affiliation, ou_id,priority))

    def append_new_affiliations(self,affiliation,ou_id):
        self._new_affs.append((affiliation, ou_id, None))

    def append_quarantine(self, q):
        self._quarantines.append(q)
    
    def append_spread(self, spread):
        self._spreads.append(spread)

    def append_trait(self, trait_code, trait_str):
        self._traits.append((trait_code, trait_str))
    
    def get_affiliations(self):
        return self._affs

    def get_new_affiliations(self):
        return self._new_affs

    def get_email(self):
        return self._email

    def get_expire_date(self):
        return self._expire_date
        
    def get_fnr(self):
        return self._fnr
        
    def get_gecos(self):
        return self._gecos
    
    def get_posix(self):
        return self._uid

    def get_home(self, spread):
        return self._home.get(spread, (None, None))

    def get_home_spreads(self):
        return self._home.keys()
        
    def get_quarantines(self):
        return self._quarantines   

    def get_spreads(self):
        return self._spreads        
    
    def get_traits(self):
        return self._traits
    
    def get_uname(self):
        return self._uname
    
    def has_affiliation(self, aff_cand):
        return aff_cand in [aff for aff, ou in self._affs]

    def has_homes(self):
        return len(self._home) > 0
    
    def set_email(self,email):
        self._email=email
        
    def set_posix(self, uid):
        self._uid=uid

    def set_gecos(self,gecos):
        self._gecos=gecos

    def set_home(self, spread, home, homedir_id):
        self._home[spread]=(homedir_id, home)


class ExistingPerson(object):
    def __init__(self,person_id=None):
        self._affs=list()
        self._groups=list()
        self._spreads=list()
        self._accounts=list()
        self._primary_accountid=None
        self._personid=person_id
        self._fullname=None
        self._deceased_date=None

    def append_account(self,acc_id):
        self._accounts.append(acc_id)

    def append_affiliation(self, affiliation, ou_id, status):
        self._affs.append((affiliation, ou_id, status))

    def append_group(self, group_id):
        self._groups.append(group_id)

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_affiliations(self):
        return self._affs

    def get_new_affiliations(self):
        return self._new_affs

    def get_fullnanme(self):
        return self._full_name

    def get_groups(self):
        return self._groups
    
    def get_personid(self):
        return self._personid

    def get_primary_account(self):
        if self._primary_accountid:
            return self._primary_accountid[0]
        else:
            return self.get_account()

    def get_spreads(self):
        return self._spreads
    
    def has_account(self):
        return len(self._accounts) > 0       
        
    def get_account(self):
        return self._accounts[0]

    def get_account(self):
        return self._accounts[0]

    def set_primary_account(self,ac_id,priority):
        if self._primary_accountid:
            old_id,old_pri=self._primary_accountid
            if priority<old_pri:
                self._primary_accountid=(ac_id, priority)
        else:
            self._primary_accountid=(ac_id, priority)

    def set_personid(self,id):
        self._personid=id
        
    def set_fullname(self,full_name):
        self._fullname=full_name

    def set_deceased_date(self,deceased_date):
        self._deceased_date = deceased_date

    def get_deceased_date(self):
        return self._deceased_date


def is_ou_expired(ou_id):
    ou.clear()
    try:
        ou.find(ou_id)
    except EntityExpiredError, msg:
        return True
    else:
        return False
#is_ou_expired = simple_memoize(is_ou_expired)


def get_creator_id():
    entity_name = Entity.EntityName(db)
    entity_name.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
        const.account_namespace)
    id = entity_name.entity_id    
    return id
#get_creator_id=simple_memoize(get_creator_id)

def get_sko(ou_id):
    sko.clear()
    try:
        #sko.find_by_perspective(ou_id,const.perspective_fs)
        sko.find(ou_id)
    except Errors.NotFoundError:
        # Persons has an affiliation to a non-fs ou.
        # Return NoneNoneNone
        #print "unable to find stedkode. Return NoneNoneNone"
        return "NoneNoneNone"
    return "%02s%02s%02s" % (sko.fakultet,sko.institutt,sko.avdeling)
#get_sko=simple_memoize(get_sko)

def get_expire_date():
    """ calculate a default expire date
    Take into consideration that we do not want an expiredate  
    in the general holiday time in Norway
    """
    today = mx.DateTime.today()       
    ff_start = mx.DateTime.DateTime(today.year, 6, 15)
    ff_slutt = mx.DateTime.DateTime(today.year, 8, 15)
    nextMonth = today + mx.DateTime.DateTimeDelta(30)

    # ikke sett default expire til en dato i fellesferien
    if nextMonth > ff_start and nextMonth < ff_slutt:
        #fellesferien. Bruk 1 sept istedet.
        return mx.DateTime.DateTime(today.year,9,1)
    else:
        return nextMonth

def get_existing_accounts():

    #get persons that comes from Paga and their accounts
    logger.info("Loading persons...")
    tmp_persons={}
    pid2fnr = {}
    person_obj=Factory.get('Person')(db)


    # getting deceased persons
    deceased = person_obj.list_deceased()

    for row in person_obj.list_external_ids(id_type=const.externalid_fodselsnr, 
                                            source_system=const.system_paga):
        if (not pid2fnr.has_key(int(row['entity_id']))):
            pid2fnr[int(row['entity_id'])] = row['external_id']
            tmp_persons[row['external_id']] = \
                ExistingPerson(person_id=int(row['entity_id']))

        if deceased.has_key(int(row['entity_id'])):
            tmp_persons[row['external_id']].set_deceased_date(deceased[int(row['entity_id'])])

    logger.info("Loading person affiliations...")
    for row in person.list_affiliations(source_system=const.system_paga,
                                        fetchall=False):
        tmp = pid2fnr.get(int(row['person_id']), None)
        if tmp is not None:
            if is_ou_expired(row['ou_id']):
                logger.error("Skipping affiliation to ou_id %s (expired) for " \
                             "person %s" % (row['ou_id'],int(row['person_id'])))
                continue
            tmp_persons[tmp].append_affiliation(int(row['affiliation']), 
                                                int(row['ou_id']), 
                                                int(row['status']))

    logger.info("Loading accounts...")
    tmp_ac={}
    account_obj=Factory.get('Account')(db)
    for row in account_obj.search(expire_start=None):
        a_id=row['account_id']       
        if not row['owner_id'] or not pid2fnr.has_key(int(row['owner_id'])):
            continue
        account_name = row.name
        if (account_name.endswith(cereconf.USERNAME_POSTFIX['sito'])):  
            # this is a sito account, do not process as part of uit employees
            logger.debug("%s is a sito account, do not process as part of paga" % account_name)
            continue
           
        #    logger.debug('account id:%s has sito spread, not added to list' %row['account_id'])
        #    continue

        tmp_ac[int(a_id)] = ExistingAccount(pid2fnr[int(row['owner_id'])],
                                                    row['name'],
                                                    row['expire_date'])

    # Posixusers
    logger.info("Loading posixinfo...")
    posix_user_obj=PosixUser.PosixUser(db)
    for row in posix_user_obj.list_posix_users():
        tmp=tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_posix(int(row['posix_uid']))
                
    # quarantines
    logger.info("Loading account quarantines...")
    for row in account_obj.list_entity_quarantines(
        entity_types=const.entity_account):
        tmp=tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))

    # Spreads
    logger.info("Loading spreads... %s " % cereconf.EMPLOYEE_SPREADLIST) 
    spread_list= [int(const.Spread(x)) for x in cereconf.EMPLOYEE_SPREADLIST]
    for spread_id in spread_list:
        is_account_spread=is_person_spread=False
        spread=const.Spread(spread_id)
        if spread.entity_type == const.entity_account:
            is_account_spread=True
        elif spread.entity_type == const.entity_person:
            is_person_spread=True
        else:
            logger.warn("Unknown spread type")
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            if is_account_spread:
                tmp=tmp_ac.get(int(row['entity_id']), None)
            if is_person_spread:
                tmp=tmp_persons.get(int(row['entity_id']), None)
            if tmp is not None:
                tmp.append_spread(int(spread_id))
    

    # Account Affiliations
    logger.info("Loading account affs...")
    for row in account_obj.list_accounts_by_type(filter_expired=False,
                                                 primary_only=False,
                                                 fetchall=False):
        tmp=tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            if is_ou_expired(int(row['ou_id'])):
                #logger.error("Skipping affiliation to ou_id %s (expired) for " \
                #     "account %s." % (row['ou_id'],int(row['account_id'])))
                continue
            tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']),
                                   int(row['priority']))
            

##    # traits
##    logger.info("Loading traits...")
##
##    for row in account_obj.list_traits(const.trait_whatever):
##        tmp=tmp_ac.get(int(row['entity_id']), None)
##        if tmp is not None:
##            tmp.append_trait(const.trait_whatever,row['strval'])


    ## persons accounts....
    for ac_id, tmp in tmp_ac.items():
        fnr = tmp_ac[ac_id].get_fnr()
        tmp_persons[fnr].append_account(ac_id)        
        for aff in tmp.get_affiliations():
            aff,ou_id,pri = aff
            tmp_persons[fnr].set_primary_account(ac_id,pri)

    logger.info(" found %i persons and %i accounts" % (
        len(tmp_persons), len(tmp_ac)))
    return tmp_persons, tmp_ac  


def _promote_posix(acc_obj):

    group = Factory.get('Group')(db)
    pu = PosixUser.PosixUser(db)
    uid = pu.get_free_uid()
    shell = const.posix_shell_bash
    grp_name = "posixgroup"
    group.clear()
    group.find_by_name(grp_name,domain=const.group_namespace)
    try:
        pu.populate(uid, group.entity_id, None, shell, parent=acc_obj)
        pu.write_db()
    except Exception,msg:
        logger.error("Error during promote_posix. Error was: %s" % msg)
        return False
    # only gets here if posix user created successfully
    logger.info("%s promoted to posixaccount (uidnumber=%s)" %  \
        (acc_obj.account_name, uid))
    return True


def create_employee_account(fnr):
    owner=persons.get(fnr)
    if not owner:
        logger.error("Cannot create account to person %s, not from paga" % fnr)
        return None

    p_obj=Factory.get('Person')(db)
    p_obj.find(owner.get_personid())
    
    first_name=p_obj.get_name(const.system_cached, const.name_first)
    last_name=p_obj.get_name(const.system_cached, const.name_last)    

    acc_obj = Factory.get('Account')(db)    
    uname = acc_obj.suggest_unames(fnr, first_name, last_name)[0]
    acc_obj.populate(uname,
                     const.entity_person,
                     p_obj.entity_id,
                     None,
                     get_creator_id(), 
                     get_expire_date())
                     
    try:
        acc_obj.write_db()
    except Exception,m:
        logger.error("Failed create  for %s, uname=%s, reason: %s" % \
            (fnr, uname, m))
    else:
        password = acc_obj.make_passwd(uname)
        acc_obj.set_password(password)
    tmp = acc_obj.write_db()
    logger.debug("Created account %s(%s), write_db=%s" % \
            (uname,acc_obj.entity_id,tmp))

    #register new account obj in existing accounts list
    accounts[acc_obj.entity_id]=ExistingAccount(fnr, uname, None)
    return acc_obj.entity_id


def _handle_changes(a_id,changes):
        
    do_promote_posix=False
    ac=Factory.get('Account')(db)
    ac.find(a_id)
    for chg in changes:
        ccode,cdata=chg
        if ccode=='spreads_add':
            for s in cdata:
                #print "cdata[s] is: %s" % s
                ac.add_spread(s)
                ac.set_home_dir(s)
        elif ccode=='quarantine_add':
            ac.add_entity_quarantine(cdata,get_creator_id())
        elif ccode=='quarantine_del':
            ac.delete_entity_quarantine(cdata)
        elif ccode=='set_ac_type':
            ac.set_account_type(cdata[0], cdata[1])
        elif ccode=='gecos':
            ac.gecos=cdata
        elif ccode=='expire_date':
            ac.expire_date=cdata
        elif ccode=='promote_posix':
            do_promote_posix=True
        elif ccode=='update_mail':
            update_email(a_id, cdata)
        else:
            logger.error("Changing %s/%d: Unknown changecode: %s, " \
            "changedata=%s" % (ac.account_name,a_id,ccode,cdata))
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(ac)
    logger.info("All changes written for %s/%d" % (ac.account_name,a_id))
        
        
def _populate_account_affiliations(account_id, fnr):
    """
    Assert that the account has the same employee affiliations as the person.
    """
    tmp_ou = Factory.get('OU')(db)
    changes=[]
    tmp_affs=accounts[account_id].get_affiliations()
    account_affs=list()
    for aff,ou,pri in tmp_affs:
        account_affs.append((aff,ou))

    logger.debug("Person %s has affs=%s" %  \
        (fnr, persons[fnr].get_affiliations()))
    logger.debug("Account_id=%s,Fnr=%s has account affs=%s" % \
        (account_id, fnr,account_affs))

    ou_list = tmp_ou.list_all_with_perspective(const.perspective_fs)
     
    for aff, ou, status in persons[fnr].get_affiliations():
        valid_ou = False
        for i in ou_list: 
            if i[0] == ou:
                valid_ou = True

        if valid_ou == False:
            logger.debug("ignoring aff:%s, ou:%s, status:%s" %(aff,ou,status))
            # we have an account affiliation towards and none FS ou. ignore it.
            continue
        if not (aff,ou) in account_affs:
            changes.append(('set_ac_type', (ou, aff)))
            accounts[account_id].append_new_affiliations(aff,ou)
    return changes


class Build:
    
    def __init__(self):
        self.source_personlist=list()

    def load_fnr_from_xml(self,person):        
        self.source_personlist.append(person['fnr'])

    def parse(self,person_file):
        logger.info("Loading %s" % person_file)
        PagaDataParser(person_file,self.load_fnr_from_xml)
        logger.info("File parsed")

    def process_all(self):
        for fnr in self.source_personlist:
            self.process_person(fnr)


    def _calculate_spreads(self,acc_affs,new_affs):

        default_spreads= [int(const.Spread(x)) for x in cereconf.EMPLOYEE_DEFAULT_SPREADS]
        logger.debug("acc_affs=%s, new_affs=%s" % (acc_affs,new_affs))
        all_affs = acc_affs+new_affs
        logger.debug("all_affs=%s" % (all_affs,))
        #do not build uit.no addresses for affs in these sko's
        no_exchange_skos =cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO
        tmp=Set()
        for aff,ou_id,pri in all_affs:
            sko=get_sko(ou_id)
            for x in no_exchange_skos:
                if sko.startswith(x):
                    tmp.add(( aff,ou_id,pri))
                    break

        # need atleast one aff to give exchange spread
        logger.debug("acc_affs=%s,in filter=%s, result=%s" % (Set(all_affs),tmp,Set(all_affs)-tmp))
        if Set(all_affs)-tmp:
            default_spreads.append(int(const.Spread('exchange_mailbox')))
        return default_spreads


    def process_person(self, fnr):
        logger.info("Process person %s" % (fnr))
        p_obj=persons.get(fnr,None)
        if not p_obj:
            logger.error("Unknown person %s." % (fnr,))
            return None

        changes=[]
        # check if person has an account
        if not p_obj.has_account():
            logger.warn("fnr: %s does not have an account" % fnr)
            acc_id=create_employee_account(fnr)
        else:
            acc_id=p_obj.get_primary_account()
        acc_obj=accounts[acc_id]
        logger.info("Update account %s/%d" % (acc_obj.get_uname(),acc_id))

        # check if account is a posix account
        if not acc_obj.get_posix():
            changes.append(('promote_posix',True))

        # Update expire if needed
        current_expire= str(acc_obj.get_expire_date())
        new_expire = str(get_expire_date())

        # expire account if person is deceased
        new_deceased = False
        if p_obj.get_deceased_date() is not None:
            new_expire = str(p_obj.get_deceased_date())
            logger.debug("current_expire:%s, new_expire:%s" % (current_expire,new_expire))
            if current_expire != new_expire:
                logger.warn("Account owner deceased: %s" % (acc_obj.get_uname()))
                new_deceased = True
        if (new_expire > current_expire) or new_deceased or current_expire == 'None':
            changes.append(('expire_date',"%s" % new_expire))
 
        #check account affiliation and status        
        changes.extend(_populate_account_affiliations(acc_id,fnr))
        
        #check gecos?
        # Har ikke personnavn tilgjengelig pr nuh..

        #make sure user has correct spreads
        if p_obj.get_affiliations():
            # if person has affiliations, add spreads
            default_spreads=self._calculate_spreads(acc_obj.get_affiliations(),acc_obj.get_new_affiliations())
            def_spreads=Set(default_spreads)
            cb_spreads=Set(acc_obj.get_spreads())
            to_add=def_spreads - cb_spreads
            if to_add:
                changes.append(('spreads_add',to_add))

            # Set spread expire date
            # Always use new expire to avoid PAGA specific spreads to be
            # extended because of mixed student / employee accounts
            for ds in def_spreads:
                account.set_spread_expire(spread=ds, expire_date=new_expire, entity_id=acc_id)

        #check quarantines
        for qt in acc_obj.get_quarantines():
            # employees should not have tilbud quarantine.
            if qt==const.quarantine_tilbud:
                changes.append(('quarantine_del',qt))

        if changes:
            logger.debug("Changes [%i/%s]: %s" % (
                acc_id, 
                fnr, 
                repr(changes)))
            _handle_changes(acc_id,changes)
        if(dryrun == False):
            db.commit()

def main():
    global persons,accounts
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:d',
            ['file=','dryrun','help','ssn='])
    except getopt.GetoptError,m:
        usage(1,m)
        
    person_file = default_person_file
    dryrun = False
    ssn=None
    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        elif opt in('-f','--file'):
            person_file = val
        elif opt in ('--ssn'):
            ssn=val
        elif opt in ('-h','--help'):
            usage()


    conf_ok=True
    for attr in ['EMPLOYEE_FILTER_EXCHANGE_SKO','EMPLOYEE_DEFAULT_SPREADS',
                 'EMPLOYEE_SPREADLIST']:
        try:
            tmp=getattr(cereconf,attr)
        except AttributeError,m:
            logger.critical("Attr %s missing from your cereconf" % attr)
            conf_ok=False

    if not conf_ok:
        sys.exit(1)

    persons, accounts = get_existing_accounts()
    build=Build()
    build.parse(person_file)
    if ssn:
        build.process_person(ssn)
    else:
        build.process_all()
    
    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage(exitcode=0,msg=None):
    if msg: print msg        
    print __doc__
    sys.exit(exitcode)


if __name__=='__main__':
    main()
