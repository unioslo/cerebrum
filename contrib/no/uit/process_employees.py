#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
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


'''
This file is a Uit specific extension of Cerebrum.
It creates accounts for all persons in cerebrum that has a
employee affiliation and assigns account type accordingly.
It also sets ensures that all employee accounts has the default spreads 
defined in cereconf assigned to the account.
'''


import cerebrum_path
import cereconf
import getopt
import sys
import time
import datetime
import string
import mx
import xml.sax
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.Constants import Constants
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.xmlutils import GeneralXMLParser


person_list = []
logger = Factory.get_logger("cronjob")

class FailedUserCreateError(Exception):
    pass


class SLPDataParser(xml.sax.ContentHandler):
    """This class is used to iterate over all users in LT. """

    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function        
        xml.sax.parse(filename, self)
        
    def startElement(self, name, attrs):
        if name == 'data':
            pass
        elif name in ("arbtlf", "komm", "tils", "bilag",
                      "gjest", "rolle", "res", "permisjon"):
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


class execute:

    def __init__(self):
        #init variables
        self.db = Factory.get('Database')()
        self.person = Factory.get('Person')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.group = Factory.get('Group')(self.db)
        self.OU = Factory.get('OU')(self.db)
        self.employee_priority = 50


        self.db.cl_init(change_program='process_empl')
        self.emp_list = []
        # lag en liste over alle som har affiliation lik ansatt og som kommer fra SLP4
        self.existing_emp_list = self.person.list_affiliations(source_system=self.constants.system_lt,affiliation=self.constants.affiliation_ansatt,include_last=True,include_deleted=True)
        
        # lag liste over eksisterende kontoer og dets owner_id
        logger.info('Building owner2account cache')
        self.owner2account = dict()        
        for acc in self.account.list(filter_expired=False):
            self.owner2account.setdefault(acc['owner_id'],[]).append(acc['account_id'])
        logger.info('Init finished')



    def get_default_expire(self):
        today = mx.DateTime.today()       
        ff_start = mx.DateTime.DateTime(today.year, 6, 15)  # fellesferie starter ca her
        ff_slutt = mx.DateTime.DateTime(today.year, 8, 15)  # felesferie slutter ca her
        nextMonth = today + mx.DateTime.DateTimeDelta(30)     # default er 30 dager frem   
        
        # ikke sett default expire til en dato i fellesferien
        if nextMonth > ff_start and nextMonth < ff_slutt:
            return mx.DateTime.DateTime(today.year,9,1)   # 1. sept ....
        else:
            return nextMonth
        


    # This function creates a list of all employees that exists in uit_persons_YYYYMMDD
    # The list is used as authoritative data on which persons (and accounts) that is to
    # be updated in the database. Expire date on these persons employee accounts will be
    # set to the current date + 30 days.
    def parse_employee_xml(self,file):
        parse = SLPDataParser()

    def list_xml_fnr(self,person):
        fnr =("%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                                    int(person['fodtar']), int(person['personnr'])))
        person_list.append(fnr)
    
    def get_all_employees(self,pers_id,person_file):
        logger.info("Retreiving all persons...")
        our_source_sys = self.constants.system_lt
        id_type = self.constants.externalid_fodselsnr
        entity_type = self.constants.entity_person,
        empl_aff = self.constants.affiliation_ansatt
        p_list=[]
        if(pers_id !=0):
            p_entry=self.person.find(pers_id)
            t=({'person_id':int(pers_id),'birth_date' :self.person.birth_date})
            p_list.append(t)
        else:
            SLPDataParser(person_file,self.list_xml_fnr)
            for person in person_list:
                self.person.clear()
                self.person.find_by_external_id(id_type,person,our_source_sys,entity_type)
                t=({'person_id':int(self.person.entity_id),'birth_date' :self.person.birth_date})
                p_list.append(t)
        i=0
        for p in p_list:
            self.person.clear()
            p_id = p['person_id']
            #print "%s-person_id=%s" % (i,p_id)
            i+=1
            emp = self.person.list_affiliations(person_id=p_id,source_system=our_source_sys,
                                                affiliation=empl_aff)
            if (len(emp)>0):
                # person er ansatt
                self.process_employee(p_id,emp[0]['ou_id'])
                # delete this person from the existing_emp_list
                # Thus existing_emp_list will only contain employees already stored in the database
                # but missin in the import file.
                for emp in self.existing_emp_list:
                    if emp['person_id']==p_id:
                        self.existing_emp_list.remove(emp)
                        

        # the unprocessed accounts...
        # TODO: Do something about those that are no longer in import data!
        if (pers_id==0):
            i = 0
            for up in self.existing_emp_list:
                i += 1
                logger.debug("Persons no longer in import data: %s" % (up['person_id']))
            logger.debug("Persons no longer in import data: Count %d" % (i))
            

        
    def update_email(self,account_obj):
        em = Email.email_address(self.db)
        ad_email = em.get_employee_email(account_obj.entity_id,self.db)
        if (len(ad_email)>0):
            ad_email = ad_email[account_obj.account_name]
        else:
            # no email in ad_email table for this account.
            
            # IF this account has a student affiliation. do not update primary email address with an invalid code.
            # IF this account does NOT have a student affiliation. update the email primary address with the invalid code.
            acc_type = account_obj.list_accounts_by_type(account_id=account_obj.entity_id,
                                                         affiliation=self.constants.affiliation_student)
            if (len(acc_type)>0):
                ad_email = "%s@%s" % (account_obj.account_name,"mailbox.uit.no")
            else:
                no_mailbox_domain = cereconf.NO_MAILBOX_DOMAIN
                logger.warning("No ad email for account_id=%s,name=%s. defaulting to %s domain" % (account_obj.entity_id,account_obj.account_name,no_mailbox_domain))
                ad_email= "%s@%s" % (account_obj.account_name,no_mailbox_domain)
                logger.warning("ad_email = %s" % ad_email)
        
        current_email = ""
        try:
            current_email = account_obj.get_primary_mailaddress()
        except Errors.NotFoundError:
            # no current primary mail.
            pass
    
        if (current_email.lower() != ad_email.lower()):
            # update email!
            logger.debug("Email update needed old='%s', new='%s'" % ( current_email, ad_email))
            try:
                em.process_mail(account_obj.entity_id,"defaultmail",ad_email)
            except Exception:
                logger.critical("EMAIL UPDATE FAILED: account_id=%s , email=%s" % (account_obj.entity_id,ad_email))
                sys.exit(2)
        else:
            #current email = ad_email :=> we need to do nothing. all is ok....
            logger.debug("Email update not needed old='%s', new='%s'" % ( current_email, ad_email))
            pass
        
        # end update_mail()
                
                
        
        
    def process_employee(self,p_id,ou_id):
        
        #p_id=3651
        #ou_id=116
        logger.info("**************** Processing employee: person_id=%s,ou_id=%s *********************" % (p_id,ou_id))
        self.person.clear()
        self.person.find(p_id)
        #acc = self.person.get_primary_account(filter_expired=False) 
        acc=self.owner2account.get(p_id,None)
        if (not acc):
            # This person does not have an account.
            # create new account.
            try:
                acc = self.create_employee_account(ou_id)
            except Exception,msg:
                logger.error("Failed to create employee account for %s. reason: %s" %(self.person.entity_id,msg))
                return
        else:
            # If person has more than one account from earlier, which one to use
            # further? For now, use the one we first created... :-/ 
            acc.sort() 
            acc=acc[0]

        # Person has an account. update
        # First check if account name is "compatible"
        try:
            ac_tmp = Factory.get('Account')(self.db)
            ac_tmp.find(acc)
            ac_tmp_name = ac_tmp.get_name(self.constants.account_namespace)
        except Exception,m:
            logger.error("unable to process employee account for personid:%s, accountid:%s, Reason:%s" % (p_id,acc,m))
            return
        logger.info("found account name:%s" % ac_tmp_name)
        if(ac_tmp_name.isalpha()):
            # not a valid "employee" username. log error and continue with next
            logger.error("AccountID %s=%s does not conform with AD account naming rules!" % (acc,ac_tmp_name)) 
            return
        self.update_employee_account(acc,ou_id)

    def _promote_posix(self,account_id):
                

        group = Factory.get('Group')(self.db)
        pu = PosixUser.PosixUser(self.db)    
        ac = Factory.get('Account')(self.db)
        ac.find(account_id)
        uid = pu.get_free_uid()
        shell = self.constants.posix_shell_bash
        grp_name = "posixgroup"
        group.clear()
        group.find_by_name(grp_name,domain=self.constants.group_namespace)

        try:
            pu.populate(uid, group.entity_id, None, shell, parent=ac)
            pu.write_db()
        except Exception,msg:
            logger.error("Error during promote_posix. Error was: %s" % msg)
            return False
        
        # only gets here if posix user created successfully
        return True
       
    
    def update_employee_account(self,account_id,ou_id):
        logger.info("updating account:%s" % account_id)
        posix_user = PosixUser.PosixUser(self.db)        
        default_expire_date = self.get_default_expire()

        try:
            posix_user.find(account_id)
        except Errors.NotFoundError:
            logger.warn("POSIX ACCOUNT NOT FOUND FOR account_id=%s!. Trying to promote...." % (account_id))
            ret  = self._promote_posix(account_id)
            if ret:
                posix_user.clear()
                posix_user.find(account_id)
            else:
                logger.critical("Failed to create posix-account, cannot continue")
                sys.exit(1)
        except Exception,msg:
            logger.error("POSIX_USER find failed for account_id=%s!. Error was: %s" % (account_id,msg))
            logger.error("Cannot update posix-account for this user!")
            # raise NotFoundError instead????
            sys.exit(-1)
        
        old_gecos = posix_user.get_gecos()
        full_name = "%s %s" % (self.person.get_name(self.constants.system_lt,self.constants.name_first) ,
                               self.person.get_name(self.constants.system_lt,self.constants.name_last))
        new_gecos = posix_user.simplify_name(full_name,as_gecos=1)
        # update gcos                                       
        if (new_gecos != old_gecos):
            logger.info( "- updating gecos. Old name: %s, new name: %s" % (old_gecos,new_gecos))
            posix_user.gecos = new_gecos

        
        # update expire (what if person/user is marked as deleted?)
        current_expire =  posix_user.expire_date 
        if (posix_user.is_expired() or (default_expire_date > current_expire)):
            # This account is expired in cerebrum => update expire
            # or if our expire is further out than current expire => update
            logger.info("updating expire date old=%s, new=%s" % (current_expire,default_expire_date))
            posix_user.expire_date = "%s" % default_expire_date
        
        # - update affiliations (do we need to do more than ensure that account has ansatt-affil?)        
        # - update ou         
        # this is done by updating account-type
        logger.info("- updating account type")
        logger.info("setting account_type:%s,%s,%s" % (ou_id,self.constants.affiliation_ansatt,self.employee_priority))
        posix_user.set_account_type(ou_id,
                                    self.constants.affiliation_ansatt,
                                    self.employee_priority)

        # update homedir for current spreads
        def_spreads = cereconf.UIT_DEFAULT_EMPLOYEE_SPREADS
        logger.info("- updating spreads and homedirs")
        cur_spreads = posix_user.get_spread()
        for s in cur_spreads:
            posix_user.set_home_dir(s['spread'])

        for s in def_spreads:
            spread_id = int(self.constants.Spread(s))
            if ( not posix_user.has_spread(spread_id)):
                logger.info("- adding spread %s and setting homedir for it" % s)
                posix_user.add_spread(spread_id)
                posix_user.set_home_dir(spread_id)
        
        # update Email:
        self.update_email(posix_user)
        logger.info("- updated emailadress")

        # update groups
        self.update_groups(posix_user,ou_id,self.constants.affiliation_ansatt)
        logger.info("- updated groups")
                
        # finally, write changes to db
        posix_user.write_db()       


    def group_join(self,acc_id):
        """Add account_id to db_group."""

        if (not self.group.has_member(acc_id)):        
            try:
                logger.info("Trying to add group member")
                self.group.add_member(acc_id,
                                      self.constants.entity_account,
                                      self.constants.group_memberop_union)
            except:
                logger.error("adding account %s to %s failed",
                                  acc_id, list(self.group.get_names()))
        else:
            logger.debug("Account %s already member of %s" % (acc_id,self.group.group_name))
        return


    def locate_and_build(self,group_name, group_desc):
        """Locate a group named groupname in Cerebrum and build it if necessary."""


        if (self.group.group_name == group_name):
            return
        
        try:
            self.group.find_by_name(group_name)
        except Exception,m:
            logger.warn("Could not find group named %s, try to create! Error: %s" % (group_name,m))
            self.group.clear()
            creatorID = self.get_bootstrap_entity_id()
            self.group.populate(creatorID, self.constants.group_visibility_internal,
                           group_name, group_desc)
            self.group.write_db()
            self.group.add_spread(self.constants.spread_uit_ad_group)

        return self.group



    def update_groups(self,posixobj, ou_id,aff):
        #add user to uit-ans
        group_name='uit-tils'
        self.locate_and_build(group_name,'Selvalgt beskrivelse skal inn her')
        self.group_join(posixobj.entity_id)       

    
    def create_employee_account(self,ou_id):

        default_expire_date = self.get_default_expire()
        group = Factory.get('Group')(self.db)
        posix_user = PosixUser.PosixUser(self.db)

        # self.person object contains the person we would like to create an account for
        full_name = "%s %s" % (self.person.get_name(self.constants.system_lt,self.constants.name_first) ,
                              self.person.get_name(self.constants.system_lt,self.constants.name_last))
        
        # FIXME: Will break if person has other external ids than no_birthno
        personnr = self.person.get_external_id()
        personnr = personnr[0]['external_id']
        
        username = self.account.get_uit_uname(personnr,full_name,Regime='AD')
        
        grp_name = "posixgroup"
        group.clear()
        group.find_by_name(grp_name,domain=self.constants.group_namespace)
        logger.info("trying to create %s for %s" % (username,personnr))
        
        posix_user.populate(name = username,
                            owner_id = self.person.entity_id,
                            owner_type = self.constants.entity_person,
                            np_type = None,
                            creator_id = self.get_bootstrap_entity_id(),
                            expire_date = default_expire_date,
                            posix_uid = posix_user.get_free_uid(),
                            gid_id = int(group.entity_id),
                            gecos = posix_user.simplify_name(full_name,as_gecos=1),
                            shell = self.constants.posix_shell_bash
                            )
        try:
            posix_user.write_db()
          
            # set initial password
            password = posix_user.make_passwd(username)
            posix_user.set_password(password)
            posix_user.write_db()            
            logger.info("New posix-account created: ENTITY_ID=%s,account_name=%s,personname=%s" %  (posix_user.entity_id, posix_user.account_name, full_name))
            retval =  posix_user.entity_id
        except Exception,m:
            logger.error("Error in creating posix account for person %s (fnr=%s): reason: %s" % (full_name,personnr,m))
            raise FailedUserCreateError        
        posix_user.write_db()
        return retval
        
        
    def get_bootstrap_entity_id(self):
        try:
            id = self.__bootstrap_id
        except AttributeError:
            entity_name = Entity.EntityName(self.db)
            entity_name.find_by_name('bootstrap_account',self.constants.account_namespace)
            id = entity_name.entity_id
            self.__bootstrap_id = id
        return id


        
def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'p:f:l:d',['person_id','file','dryrun'])
    except getopt.GetoptError:
        usage()

    ret = 0
    person_id = 0
    person_file = 0
    dryrun = 0
    for opt,val in opts:
        if opt in('-p','--person_id'):
            person_id = val
        if opt in('-d','--dryrun'):
            dryrun = 1
        if opt in('-f','--file'):
            person_file = val
            
    source_file = 1   # don't need it at present time
    if (source_file == 0):
        usage()
    else:
        x_create = execute()
        x_create.get_all_employees(person_id,person_file)
        if (dryrun):
            x_create.db.rollback()
            logger.info("Dryrun, rollback changes")
        else:
            x_create.db.commit()
            logger.info("Committing all changes to DB")
            
                               
def usage():
    print """
    usage:: python process_employees.py 
    -p | --person_id : if you want to run through the whole process, but for
                       one person only, use this option with the person_id as the argument
    -f | --file      : xml file containing person information 
    """
    sys.exit(1)


if __name__=='__main__':
    main()

# arch-tag: b91dbb20-b426-11da-9571-e924a65eb821
