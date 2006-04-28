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
            print "WARNING: unknown element: %s" % name

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
        self.OU = Factory.get('OU')(self.db)
        
        self.logger = Factory.get_logger('console')
        #self.logger = Factory.get_logger('cronjob')
        

        self.db.cl_init(change_program='process_empl')
        self.emp_list = []
        # lag en liste over alle som har affiliation lik ansatt og som kommer fra SLP4
        self.existing_emp_list = self.person.list_affiliations(source_system=self.constants.system_lt,affiliation=self.constants.affiliation_ansatt,include_last=True,include_deleted=True)

    # This function creates a list of all employees that exists in uit_persons_YYYYMMDD
    # The list is used as authoritative data on which persons (and accounts) that is to
    # be updated in the database. Expire date on these persons employee accounts will be
    # set to the current date + 60 days.
    def parse_employee_xml(self,file):
        parse = SLPDataParser()

    def list_xml_fnr(self,person):
        fnr =("%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                                    int(person['fodtar']), int(person['personnr'])))
        person_list.append(fnr)
    
    def get_all_employees(self,pers_id,person_file):
        self.logger.info("Retreiving all persons...")
        self.logger.info("Retreiving persons done")
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
                        
                    
        # end get_all_employees

        
    def update_email(self,account_obj):
        em = Email.email_address(self.db)
        ad_email = em.get_employee_email(account_obj.entity_id,self.db)
        print "CHECK2 %s: %s" % (account_obj.account_name,ad_email)
        if (len(ad_email)>0):
            ad_email = ad_email[account_obj.account_name]
        else:
            # no email in ad_email table for this account.
            
            # IF this account has a student affiliation. do not update primary email address with an invalid code.
            # IF this account does NOT have a student affiliation. update the email primary address with the invalid code.
            acc_type = account_obj.list_accounts_by_type(account_id=account_obj.entity_id,
                                                         affiliation=self.constants.affiliation_student)
            if (len(acc_type)>0):
                print "Account Type has student aff: %s" % (acc_type) # is it active???                
                ad_email = "%s@%s" % (account_obj.account_name,"student.uit.no")
            else:
                no_mailbox_domain = cereconf.NO_MAILBOX_DOMAIN
                self.logger.warning("No ad email for account_id=%s,name=%s. defaulting to %s domain" % (account_obj.entity_id,account_obj.account_name,no_mailbox_domain))
                ad_email= "%s@%s" % (account_obj.account_name,no_mailbox_domain)
                self.logger.warning("ad_email = %s" % ad_email)
        
        current_email = ""
        try:
            current_email = account_obj.get_primary_mailaddress()
        except Errors.NotFoundError:
            # no current primary mail.
            pass
    
        if (current_email.lower() != ad_email.lower()):
            # update email!
            self.logger.debug("Email update needed old='%s', new='%s'" % ( current_email, ad_email))
            try:
                em.process_mail(account_obj.entity_id,"defaultmail",ad_email)
            except Exception:
                self.logger.critical("EMAIL UPDATE FAILED: account_id=%s , email=%s" % (account_obj.entity_id,ad_email))
                sys.exit(2)
        else:
            #current email = ad_email :=> we need to do nothing. all is ok....
            self.logger.debug("Email update not needed old='%s', new='%s'" % ( current_email, ad_email))
            pass
        
        # end update_mail()
                
                
        
        
    def process_employee(self,p_id,ou_id):
        
        #p_id=3651
        #ou_id=116
        self.logger.info("**************** Processing employee: person_id=%s,ou_id=%s *********************" % (p_id,ou_id))
        self.person.clear()
        self.person.find(p_id)
        acc = self.person.get_primary_account()
        has_account = False
        if (acc):
            # Person already has an account.
            # need to update: spread and affiliation
            try:
                ac_tmp = Factory.get('Account')(self.db)
                ac_tmp.find(acc)
                ac_types = ac_tmp.get_account_types()
                for a in ac_types:
                    self.logger.info("Update_account(p_id=%s,acc_id=%s):  " % (p_id,acc))
                    has_account = True
                    self.update_employee_account(acc,ou_id)
                ac_tmp_name = ac_tmp.get_name(self.constants.account_namespace)
                if(not ac_tmp_name.isalpha()):
                    # The existing account has a valid username for AD export.
                    # lets update the affiliation,spread and email address.
                    def_spreads = cereconf.UIT_DEFAULT_EMPLOYEE_SPREADS
                    ac_tmp.set_account_type(ou_id,self.constants.affiliation_ansatt)
                    has_account=True
                    self.update_email(ac_tmp)
                    for s in def_spreads:
                        spread_id = int(self.constants.Spread(s))
                        if (not ac_tmp.has_spread(spread_id)):
                            self.logger.info("- adding spread %s for account:%s" % (s,acc.entity_id))
                            ac_tmp.add_spread(spread_id)
                else:
                    self.logger.warn("Account %s does not have a valid user name:%s. need to create new AD user" % (acc.entity_id,ac_tmp_name))
            except Exception,m:
                self.logger.warn("unable to update spread,affiliation and email for account: %s: Reason:%s" % (acc,m))
        if (not has_account):
            # This person does not have an account.
            # create new account.
            try:
                acc = self.create_employee_account(ou_id)

                # why do we commit after each create???
                self.db.commit()
            except Exception,msg:
                self.logger.error("Failed to create employee account for %s. reason: %s" %(self.person.entity_id,msg))                                

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
            self.logger.error("Error during promote_posix. Error was: %s" % msg)
            return False
        
        # only gets here if posix user created successfully
        return True
       
    
    def update_employee_account(self,account_id,ou_id):
        posix_user = PosixUser.PosixUser(self.db)
        today = datetime.datetime.now()
        nextMonth = today + datetime.timedelta(days=90) 
        time_stamp = nextMonth.date()
        default_expire_date ="%s" % time_stamp

        try:
            posix_user.find(account_id)
        except Errors.NotFoundError:
            self.logger.warn("POSIX ACCOUNT NOT FOUND FOR account_id=%s!. Trying to promote...." % (account_id))
            ret  = self._promote_posix(account_id)
            if ret:
                posix_user.clear()
                posix_user.find(account_id)
            else:
                self.logger.critical("Failed to create posix-account, cannot continue")
                sys.exit(1)
        except Exception,msg:
            self.logger.error("POSIX_USER find failed for account_id=%s!. Error was: %s" % (account_id,msg))
            self.logger.error("Cannot update posix-account for this user!")
            # raise NotFoundError instead????
            sys.exit(-1)
        
        old_gecos = posix_user.get_gecos()
        full_name = "%s %s" % (self.person.get_name(self.constants.system_lt,self.constants.name_first) ,
                               self.person.get_name(self.constants.system_lt,self.constants.name_last))
        new_gecos = posix_user.simplify_name(full_name,as_gecos=1)
        # update gcos                                       
        if (new_gecos != old_gecos):
            self.logger.info( "- updating gecos. Old name: %s, new name: %s" % (old_gecos,new_gecos))
            posix_user.gecos = new_gecos

        
        # update expire (what if person/user is marked as deleted?)
        #if (posix_user.expire_date != None):
        #    self.logger.info("- updating expire date")
        #    #posix_user.expire_date = None
        posix_user.expire_date = default_expire_date
        
        # - update affiliations (do we need to do more than ensure that account has ansatt-affil?)        
        # - update ou         
        # this is done by updating account-type
        # do we need to remove other account_types that this account has??
        self.logger.info("- updating account type")
        posix_user.set_account_type(ou_id,self.constants.affiliation_ansatt)

        # update homedir for current spreads
        def_spreads = cereconf.UIT_DEFAULT_EMPLOYEE_SPREADS
        #def_spreads_id = []
        #for s in def_spreads:
        #    def_spreads_id.append(int(self.constants.Spread(s)))
        
        self.logger.info("- updating spreads and homedirs")
        cur_spreads = posix_user.get_spread()
        for s in cur_spreads:
            #if s not in def_spreads_id:
            #    print "DEBUG: spread %s not in default_spreads_id %s" % (s,def_spreads_id)
            #    #posix_user.clear_home(s)
            #    #posix_user.delete_spread(s)
            #else:
            posix_user.set_home_dir(s['spread'])

        for s in def_spreads:
            spread_id = int(self.constants.Spread(s))
            if ( not posix_user.has_spread(spread_id)):
                self.logger.info("- adding spread %s and setting homedir for it" % s)
                posix_user.add_spread(spread_id)
                posix_user.set_home_dir(spread_id)
        
        # update Email:
        self.update_email(posix_user)
        self.logger.info("- updating emailadress")

                
        # finally, write changes to db
        posix_user.write_db()
        

    
    def create_employee_account(self,ou_id):
        today = datetime.datetime.now()
        nextMonth = today + datetime.timedelta(days=90) 
        time_stamp = nextMonth.date()
        default_expire_date ="%s" % time_stamp

        group = Factory.get('Group')(self.db)
        posix_user = PosixUser.PosixUser(self.db)

        # self.person object contains the person we would like to create an account for
        full_name = "%s %s" % (self.person.get_name(self.constants.system_lt,self.constants.name_first) ,
                              self.person.get_name(self.constants.system_lt,self.constants.name_last))
        
        personnr = self.person.get_external_id()
        personnr = personnr[0]['external_id']
        
        username = self.account.get_uit_uname(personnr,full_name,Regime='AD')
        
        grp_name = "posixgroup"
        group.clear()
        group.find_by_name(grp_name,domain=self.constants.group_namespace)
        #print "POSIX: %i" % group.entity_id
        self.logger.info("trying to create %s for %s" % (username,personnr))
        
        posix_user.populate(name = username,
                            owner_id = self.person.entity_id,
                            owner_type = self.constants.entity_person,
                            np_type = None,
                            creator_id = self.get_bootstrap_entity_id(),
                            expire_date = default_expire_date,
                            posix_uid = posix_user.get_free_uid(),
                            gid_id = int(group.entity_id),
                            #                                gid_id = 199,
                            gecos = posix_user.simplify_name(full_name,as_gecos=1),
                            shell = self.constants.posix_shell_bash
                            )
        try:
            posix_user.write_db()
            
            # add the correct spreads to the account
            spread_list = cereconf.UIT_DEFAULT_EMPLOYEE_SPREADS
            for spread in spread_list:
                self.logger.info("Working on spread %s: %s,%s,%s" % (spread,posix_user.entity_id,
                                                          int(self.constants.entity_account),
                                                          int(self.constants.group_memberop_union)))
                posix_user.add_spread(int(self.constants.Spread(spread)))
                posix_user.set_home_dir(int(self.constants.Spread(spread)))
                
                    
            #group.add_member(posix_user.entity_id,int(self.constants.entity_account),int(self.constants.group_memberop_union))
            posix_user.set_password(personnr)
            posix_user.write_db()
            # lets set the account_type table
            posix_user.set_account_type(ou_id,self.constants.affiliation_ansatt)
            posix_user.write_db()
            
            # Update the email adress!
            self.update_email(posix_user)
            
            self.logger.info("New posix-account created: ENTITY_ID=%s,account_name=%s,personname=%s" %  (posix_user.entity_id, posix_user.account_name, full_name))
            retval =  posix_user.entity_id
        except Errors:
            self.logger.error("Error in creating posix account for person %s (fnr=%s)" % (full_name,personnr))
            return  -1
        
        #posix_user.get_homedir_id(self.constants.spread_uit_ldap_person)
        posix_user.write_db()
        return retval
        
        
    def get_bootstrap_entity_id(self):
        entity_name = Entity.EntityName(self.db)
        entity_name.find_by_name('bootstrap_account',self.constants.account_namespace)
        return entity_name.entity_id
        
def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'p:f:',['person_id','file'])
    except getopt.GetoptError:
        usage()

    ret = 0
    person_id = 0
    person_file = 0
    for opt,val in opts:
        if opt in('-p','--person_id'):
            person_id = val
        if opt in('-f','--file'):
            person_file = val
            
    source_file = 1   # don't need it at present time
    if (source_file == 0):
        usage()
    else:
        x_create = execute()
        x_create.get_all_employees(person_id,person_file)
        #print "entry=%s" % x_create.existing_emp_list
        #x_create.delete_employee_spreads(x_create.existing_emp_list)
        x_create.db.commit()
                               
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
