# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Troms�, Norway
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
import string
import sys
import traceback
import getopt
import cerebrum_path
from Cerebrum.Utils import Factory 
from Cerebrum import Database
from Cerebrum import Utils
from Cerebrum import Account
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.modules import Email

class email_address:

    def __init__(self,db,logger=None):
        self.db = db
        self.account = Factory.get("Account")(db)
        self.constants = Factory.get("Constants")(db)
        self.person = Factory.get("Person")(db)
        self.ou = Factory.get("OU")(db)
        self.et = Email.EmailTarget(db)
        self.ea = Email.EmailAddress(db)
        self.edom = Email.EmailDomain(db)
        self.epat = Email.EmailPrimaryAddressTarget(db)
        if logger == None:
            self.logger = Factory.get_logger("cronjob")
        else:
            self.logger = logger

    def build_email_list(self):
        email_list = {}
        #print "creating email list"
        res = self.db.query("""SELECT account_name,local_part,domain_part
        FROM ad_email""")
        for entity in res:
            email="%s@%s" % (entity['local_part'],entity['domain_part'])
            email_list[entity['account_name']] = email

        #print "...done"
        return email_list
    
    def get_employee_email(self,account_id,db):
        email_list={}
        res = db.query("""SELECT ae.account_name,ae.local_part,ae.domain_part
        FROM ad_email ae, entity_name e
        WHERE ae.account_name = e.entity_name
        AND e.entity_id =:account_id""",{"account_id" : account_id})
        for entity in res:
            email="%s@%s" % (entity['local_part'],entity['domain_part'])
            email_list[entity['account_name']] = email
        return email_list
    

    def process_mail(self,account_id, type, addr):
        self.logger.debug("no.uit.email.process_mail")
        #stack= traceback.extract_stack()
        #stack=stack[0]
        #print "a"
        self.logger.debug("account_id to email.process_mail = %s" % account_id)
        #print "b"
        if (addr==None):
            #this account has no email address attached to it.
            # return None to the calling process
            return None
        addr = addr.lower()
        fld = addr.split('@')
        if len(fld) != 2:
            self.logger.error("Bad address: %s. Skipping", addr)
            return None
        # fi
        lp, dom = fld
        try:            
            self.logger.debug("ld = %s,dom = %s" % (lp,dom))
            self.edom.find_by_domain(dom)
            self.logger.debug("Domain found: %s: %d", dom, self.edom.email_domain_id)
        except Errors.NotFoundError:
            self.edom.populate(dom, "Generated by no.uit.process_mail.")
            self.edom.write_db()
            self.logger.debug("Domain created: %s: %d", dom, self.edom.email_domain_id)
        # yrt

        try:
            self.et.find_by_entity(int(account_id))
            self.logger.debug("EmailTarget found(account): %s: %d",
                         account_id, self.et.email_target_id)
        except Errors.NotFoundError:
            self.et.populate(self.constants.email_target_account, entity_id=int(account_id),
                        entity_type=self.constants.entity_account)
            self.et.write_db()
            self.logger.debug("EmailTarget created: %s: %d",
                         account_id, self.et.email_target_id)
        # yrt

        try:
            self.ea.find_by_address(addr)
            self.logger.debug("EmailAddress found: addr='%s': ea_id:%d", addr, self.ea.email_addr_id)
        except Errors.NotFoundError:
            self.ea.populate(lp, self.edom.email_domain_id, self.et.email_target_id)
            self.ea.write_db()
            self.logger.debug("EmailAddress created: addr='%s': ea_id='%d'", addr, self.ea.email_addr_id)
        # yrt

        if type == "depricated":
            try:
                self.epat.find(self.et.email_target_id)
                self.logger.debug("EmailPrimary found: %s: %d",
                             addr, self.epat.email_target_id)
                #self.epat.clear()
                #self.epat.populate(self.ea.email_addr_id, parent=self.et)
                #self.epat.write_db()
                
            except Errors.NotFoundError:
                if self.ea.email_addr_target_id == self.et.email_target_id:
                    self.epat.clear()
                    self.epat.populate(self.ea.email_addr_id, parent=self.et)
                    self.epat.write_db()
                    self.logger.debug("EmailPrimary created: %s: %d",
                                 addr, self.epat.email_target_id)
                else:
                    self.logger.error("EmailTarget mismatch: ea: %d, et: %d", 
                                 self.ea.email_addr_target_id, self.et.email_target_id)
                # fi
            # yrt
        elif (type == "no_primary_update"):
            # We are not to update primary email address. -> pass
            print "not updating primary email address"
            pass
        elif (type=="defaultmail"):
            #print "debug: before try:  self.ea.email_addr_target_id=%s,  self.et.email_target_id=%s" % (self.ea.email_addr_target_id ,elf.et.email_target_id)
            try:
                self.epat.find(self.et.email_target_id)
                self.logger.debug("EmailPrimary found: addr=%s,et=%d ea=%d" ,
                                   addr, self.epat.email_target_id, self.epat.email_primaddr_id)
                if (self.epat.email_primaddr_id != self.ea.email_addr_id):
                    self.logger.info("EmailPrimary NOT equal to this email id (%d), updating..." % self.ea.email_addr_id)

                    try:
                        self.epat.delete()  # deletes old emailprimary, ready to create new
                        self.epat.clear()
                        self.epat.populate(self.ea.email_addr_id, parent=self.et)
                        self.epat.write_db()
                        self.logger.debug("EmailPrimary created: addr='%s'(ea_id=%d): et_id%d", addr, self.ea.email_addr_id, self.epat.email_target_id)
                    except Exception, msg:
                        self.logger.error("EmailPrimaryAddess Failed to set for %s: ea: %d, et: %d\nReason:%s",
                                           addr, self.ea.email_addr_id, self.et.email_target_id,msg)                        
            except Errors.NotFoundError:
                if self.ea.email_addr_target_id == self.et.email_target_id:
                    self.epat.clear()
                    self.epat.populate(self.ea.email_addr_id, parent=self.et)
                    self.epat.write_db()
                    self.logger.debug("EmailPrimary created: addr='%s': et_id='%d', ea_id='%d'",
                                 addr, self.epat.email_target_id,self.ea.email_addr_id)
                else:
                    self.logger.error("EmailTarget mismatch: ea: %d, et: %d: EmailPrimary not set",
                                 self.ea.email_addr_target_id, self.et.email_target_id)
                # fi
                
                
#            try:
#                if self.ea.email_addr_target_id == self.et.email_target_id:
#                    self.epat.clear()
#                    self.epat.populate(self.ea.email_addr_id, parent=self.et)
#                    self.epat.write_db()
#                    self.logger.debug("EmailPrimary created: %s: %d",
#                                 addr, self.epat.email_target_id)
#                else:
#                    self.logger.error("EmailTarget mismatch: ea: %d, et: %d", 
#                                 self.ea.email_addr_target_id, self.et.email_target_id)
#                # fi           
#                
#            except Exception,msg:
#                    self.logger.error("EmailPrimaryAddess Failed to set: ea: %d, et: %d\nReason:%s",
#                                 self.ea.email_addr_target_id, self.et.email_target_id,msg)
#                
        # fi
    
        self.et.clear()
        self.ea.clear()
        self.edom.clear()
        self.epat.clear()
        # end process_mail




    def account_id2email_address(self,entity_id,email_list):
        logger = Factory.get_logger("console")

        # lets get account username
        #print "account_id2email_address. entity_id =%s" % entity_id
        try:
            self.account.clear()
            self.account.find(entity_id)
            account_name = self.account.get_account_name()

            #my_account_type = self.account.get_account_types(entity_id)
            my_account_type = self.account.get_account_types()
            #print "Account_name = %s" % account_name
        except Errors.NotFoundError:
            self.logger.debug("entity_id %s has no account" % entity_id)
            self.logger.debug("exiting..")
            sys.exit(1)
        #self.logger.debug("----")
        #print " starting on account: %s" %account_name 

        #student_counter = 0
        #ansatt_counter = 0

        emp_email = stud_email = None

        for i in my_account_type:

            #print "affiliation = %s" % i.affiliation
            if i.affiliation == self.constants.affiliation_student:
                email = "%s@student.uit.no" % (account_name)

                logger.debug("student account...")
                logger.debug("email =%s" % email)
                #return email # returning student email address
                stud_email = email
            elif i.affiliation == self.constants.affiliation_ansatt:
                #lets get email address for this employee user
                logger.debug("----")
                logger.debug("Employee account..")

                #if (isinstance(email_list)):
                if (account_name not in email_list):
                    # second attempt to get email address for employee.
                    # this time we check directly for this user against the ad_email table
                    email_list = self.get_employee_email(entity_id,self.db)
                if account_name in email_list:
                    email = email_list[account_name].rstrip()
                    throw_away,domain = email.split("@",1)
                    my_domain = domain.split(".",1)
                    if my_domain[0] == 'ad':
                        # not proper email address..lets run an extra check on this
                        logger.debug("only ad domain in email_file for this user...must check the stedkode table to get ou data")
                        # lets get ou info first
                        #self.ou.clear()
                        #self.ou.find(i.ou_id)
                        my_domain="asp"
                        #my_domain = self.check_email_address(account_name,default_email_conversion_list,self.ou.fakultet,self.ou.institutt,self.ou.avdeling)
                        email = "%s@%s.uit.no" % (throw_away,my_domain)
                    logger.debug("email address for AD account = %s" % email)
                    #return email
                    emp_email = email
                else:
                    #we have an employee account that doesnt have any email email address associated with it
                    # from AD.
                    #self.ou.clear()
                    #self.ou.find(i.ou_id)
                    my_domain="invalid"
                    #my_domain = self.check_email_address(account_name,default_email_conversion_list,self.ou.fakultet,self.ou.institutt,self.ou.avdeling)
                    logger.debug("WARNING -> account %s has no email address from AD. checking ou_data towards conversion file" % account_name)
                    email ="%s@%s.uit.no" % (account_name,my_domain) 
                    logger.debug("will use %s" % email)
                    #return email
                    emp_email = email
                
            else:
                # This account belongs to a person whos not a student or an employee
                # No email address registered on this account
                #return None
                pass

        if emp_email:
            return emp_email
        if stud_email:
            return stud_email

        logger.debug("ERROR. should never get here..exiting (account % s has no account_type)" % entity_id)
        sys.exit(1)
        
def main():
    db = Factory.get("Database")()
    logger=Factory.get_logger("console")
    #account = Factory.get("Account")(db)
    #constants = Factory.get("Constants")(db)
    #person = Factory.get("Person")(db)
    #ou = Factory.get("OU")(db)
    try:
        opts,args = getopt.getopt(sys.argv[1:],'p:',['person_id='])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    #person_id = 129249
    for opt,val in opts:
        if opt in('-p','--person_id'):
            person_id = val

    execute = email_address(db,logger)
    email_list = execute.build_email_list()
    
    ## This code will not update email_primary_adress table.
    ## We will need to check for person affiliation and change "defaultmail" to "ansattemail" 
    ## to set primary mail address.
    if person_id == 0:
        for pers in execute.person.list_persons():
            execute.person.find(pers['person_id'])
            for accounts in execute.person.get_accounts():
                email = execute.account_id2email_address(accounts['account_id'],email_list)
                execute.process_mail(accounts['account_id'],"defaultmail",email)
            execute.person.clear()
    else:
        execute.person.find(person_id)
        for accounts in execute.person.get_accounts():
            email = execute.account_id2email_address(accounts['account_id'],email_list)
            execute.process_mail(accounts['account_id'],"ansattemail",email)
            execute.person.clear()
    execute.db.commit()


def usage():
    print """ Usage: python Email.py [-p]
    If Email.py is run withouth any parameters it will create email addresses for all accounts in cerebrum.
    If the optional -p is used only the person with the given person_id will get a new email address.

    -p | --person_id : person_id of person to create email address for
    
    
    PS! This script will currently not update primary_email_address table!
    """

if __name__ == '__main__':
    main()

#hvis ansatt:
  # hvis something@noe (noe!=ad) -> bruk det jeg faar (something@noe).
  # hvis somethinge@ad           -> something@asp.uit.no

  # hvis ikke noe -> username@invalid.uit.no

#hvis student:
  # brukernavn@student.uit.no

# arch-tag: 84ba187a-b4f2-11da-9341-4834911ab5d3
