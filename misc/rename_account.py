#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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




import sys
import time
import re
import getopt
import datetime


import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.no.uit import Email



today = time.strftime("%Y%m%d")
#logger_name = 'console'

logger = None

class Changer:
    global logger


    def __init__(self):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.account_old = Factory.get('Account')(self.db)
        self.account_new = Factory.get('Account')(self.db)
        self.constants = Factory.get('Constants')(self.db)
#        self.ent_name = Entity.EntityName(self.db)
        #self.pu_old = PosixUser.PosixUser(self.db)
        #self.pu_new = PosixUser.PosixUser(self.db)
        #self.logger = Factory.get_logger(logger_name)
        self.db.cl_init(change_program='ren_acc')
        #self.logger=Factory.get_logger("cronjob")
        self.logger=Factory.get_logger("console")
    def rename_account(self,old_name,new_name):

        ret_value = None

        try:
            #self.pu_old.find_by_name(old_name)
            self.account_old.find_by_name(old_name)
        except Errors.NotFoundError:
            self.logger.error("Account '%s' not found!" % (old_name))
            sys.exit(-1)
        else:
            self.logger.info("Account '%s'(id=%s) located..." % (old_name,self.account_old.entity_id))

        try:
            self.account_new.find_by_name(new_name)
        except Errors.NotFoundError:
            self.logger.info("Account '%s' free, GOOOODIE" % (new_name))
            self.account_new.clear()
        else:
            self.logger.info("New account '%s' is already in use. Cannot continue" % new_name)
            sys.exit(-1)


        # Old account found, new account name free! Do work!


        self.account_old.update_entity_name(self.co.account_namespace,new_name)
        self.account_old.write_db()


        self.logger.info("TESTING")
        # write_db does not update object instace variables (ie account_name
        # after a call to update_entity_name. so create a new object instance
        # based on new account name, and update its email and homes.
        self.account_new.find_by_name(new_name)
        spreads = self.account_new.get_spread()
        for s in spreads:
            int_s = int(s[0])
            self.account_new.set_home_dir(int_s)
            self.logger.info(" - updated homedir for spread %d (?)" % (int_s))

        ret_value = self.update_email(self.account_new, old_name, new_name)
        try:
            self.account_new.write_db()
        except Exception,m:
            self.logger.error("Failed writing updates to database: %s" % (m))
        return ret_value



    def commit(self):
        self.db.commit()
        self.logger.info("Commited all changes to database")        

    def rollback(self):
        self.db.rollback()
        self.logger.info("DRYRUN: Rolled back all changes")    


    def update_email(self,account_obj, old_name, new_name):
        ret_value = None

        current_email = ""
        try:
            current_email = account_obj.get_primary_mailaddress()
        except Errors.NotFoundError:
            # no current primary mail.
            pass
        
        em = Email.email_address(self.db)
        ad_email = em.get_employee_email(account_obj.entity_id,self.db)
        if (len(ad_email)>0):
            ad_email = ad_email[account_obj.account_name]
        elif current_email.split('@')[1] == cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES:
            if  current_email.split('@')[0] == account_obj.account_name:
                ad_email = current_email
            else:
                ad_email = "%s@%s" % (account_obj.account_name, cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES)
        else:

            # no email in ad_email table for this account.            
            # IF this account has a student affiliation.
            #   do not update primary email address with an invalid code.
            # IF this account does NOT have a student affiliation.
            #   update the email primary address with the invalid code.
            acc_type = account_obj.list_accounts_by_type(account_id=account_obj.entity_id,
                                                         affiliation=self.constants.affiliation_student)
            if (len(acc_type)>0):
                ad_email = "%s@%s" % (account_obj.account_name,cereconf.NO_MAILBOX_DOMAIN)
            else:
                no_mailbox_domain = cereconf.NO_MAILBOX_DOMAIN
                self.logger.warning("No ad email for account_id=%s,name=%s. defaulting to %s domain" %
                                    (account_obj.entity_id,account_obj.account_name,no_mailbox_domain))
                ad_email= "%s@%s" % (account_obj.account_name,no_mailbox_domain)
                self.logger.warning("ad_email = %s" % ad_email)
    
        if (current_email.lower() != ad_email.lower()):
            # update email!
            self.logger.debug("Email update needed old='%s', new='%s'" % ( current_email, ad_email))
            try:
                em.process_mail(account_obj.entity_id, ad_email, True)
                
                # MAIL PERSON INFO
                person_info = {}
                person_info['OLD_USER'] = old_name
                person_info['NEW_USER'] = new_name
                person_info['OLD_MAIL'] = current_email
                person_info['NEW_MAIL'] = ad_email
                ret_value = person_info
                
            except Exception, e:
                self.logger.critical("EMAIL UPDATE FAILED: account_id=%s , email=%s :: %s" % (account_obj.entity_id,ad_email, e))
                sys.exit(2)
        else:
            #current email = ad_email :=> we need to do nothing. all is ok....
            self.logger.debug("Email update not needed old='%s', new='%s'" % ( current_email, ad_email))
            pass

        return ret_value
        
        # end update_mail()




def usage(exitcode=0):
    print """Usage: extend_account.py -o name -n newname [-h] [-d]  
    -h | --help : show this message
    -d | --dryrun : do not commit changes to database
    -o | --old <name> : old account name to change (REQUIRED)
    -n | --new <name> : new account name set as new (REQUIRED)
    --logger_name <name> : logger target to use

    """

    if (exitcode==1):
        print "You must supply a old account name!"
    elif (exitcode==2):
        print "You must supply a new account name!"
    
    sys.exit(exitcode)



def main():
    #global logger_name
    
    dryrun = False
    old_name = None
    new_name = None
    #today = datetime.date.today()
#    new_expire_date = today + datetime.timedelta(days=numdays)
    try:
        opts, args = getopt.getopt(sys.argv[1:],'hdn:o:l:',['help','dryrun','new=','old=','logger='])
    except getopt.GetoptError,m:
        print "wrong arguments:%s" % m
        usage(1)


    for opt, val in opts:
        if opt in ['-h', '--help']:
            usage(0)
        elif opt in ['-d', '--dryrun']:
            dryrun=True
        elif opt in ['-n', '--new']:
            new_name=val
        elif opt in ['-o', '--old']:
            old_name=val
        elif opt in [ '-l', '--logger']:
            logger_name = val
            print "logger name=%s" % logger_name
            
    if not old_name:
        usage(1)

    if not new_name:
        usage(2)
           

    worker=Changer()
    #worker.logger = Factory.get_logger(logger_name)
    send_user_mail = None


    co = Factory.get('Constants')(worker.db)
    ac = Factory.get('Account')(worker.db)
    pe = Factory.get('Person')(worker.db)
        
    # Find person full name (old)
    ac.find_by_name(old_name)
    pe.find(ac.owner_id)
    old_person_name = pe.get_name(co.system_cached, co.name_full)
    ac.clear()
    pe.clear()
    print "old_name:%s" % old_name
    print "new name:%s" % new_name
    send_user_mail = worker.rename_account(old_name,new_name)


    if dryrun:
        worker.rollback()
    else:

        # Find person full name (new)
        ac.find_by_name(new_name)
        pe.find(ac.owner_id)
        new_person_name = pe.get_name(co.system_cached, co.name_full)

        print "Old name: ", new_person_name
        print "New name: ", old_person_name
        
        resp = raw_input("Are you sure you want to write to databasestore y/[N]:")
        resp = resp.capitalize()
        while ((resp !='Y') and (resp !='N')):
            resp = raw_input("Please answer Y or N: ")
            resp = resp.capitalize()
        if (resp == 'Y'):
 
            legacy_info = {}

            print old_name, new_name
            #ac.find_by_name(new_name)
            #pe.find(ac.owner_id)
            
            legacy_info['user_name'] = old_name
            try:
                legacy_info['ssn'] = pe.get_external_id(id_type=co.externalid_fodselsnr)[0]['external_id']
            except:
                legacy_info['ssn'] = None
            legacy_info['source'] = 'MANUELL'
            legacy_info['type'] = 'P'
            legacy_info['comment'] = '%s - Renamed from %s to %s.' % (today, old_name, new_name)
            legacy_info['name'] = pe.get_name(co.system_cached, co.name_full)           
            
            try:
                mydb = Factory.get('Database')()
                query = "insert into legacy_users values ('%s', '%s', '%s', '%s', '%s', '%s')" % (legacy_info['user_name'],
                                                                                                  legacy_info['ssn'],
                                                                                                  legacy_info['source'],
                                                                                                  legacy_info['type'],
                                                                                                  legacy_info['comment'],
                                                                                                  legacy_info['name'])
                print "query=%s\n" % query
                mydb.query(query)
                mydb.commit()
            except:
                print "Could not write to legacy_users. Username is probably already reserved.\n"


            # Sending email to SUT queue in RT
            if not dryrun:
                account_expired = '';
                if ac.is_expired():
                    account_expired = ' Imidlertid er ikke kontoen aktiv, men kan reaktiveres når som helst.'
            
                #Utils.sendmail('star-gru@orakel.uit.no', #TO
                #               'bas-admin@cc.uit.no', #SENDER
                #               'Brukernavn endret (%s erstattes av %s)' % (old_name, new_name), #TITLE
                #               'Brukernavnet %s er endret til %s. Videresend e-post, flytt filer, e-post, osv. fra %s til %s.%s' %
                #               (old_name, new_name, old_name, new_name, account_expired), #BODY
                #               cc=None,
                #               charset='iso-8859-1',
                #               debug=False)
                #print "mail sent to star-gru@orakel.uit.no\n"


            # Sending email to PORTAL queue in RT
            if False and not dryrun:
                account_expired = '';
                if ac.is_expired():
                    account_expired = ' Imidlertid er ikke kontoen aktiv, men kan reaktiveres når som helst.'

                Utils.sendmail('vevportal@rt.uit.no', #TO
                               'bas-admin@cc.uit.no', #SENDER
                               'Brukernavn endret (%s erstattes av %s)' % (old_name, new_name), #TITLE
                               'Brukernavnet %s er endret til %s.' %
                               (old_name, new_name), #BODY
                               cc=None,
                               charset='iso-8859-1',
                               debug=False)
                print "mail sent to vevportal@rt.uit.no\n"

            
            # Sending email to AD nybrukere if necessary
            mailto_ad = False
            try:
                spreads = ac.get_spread()
                for spread in spreads:
                    if spread['spread'] == co.spread_uit_ad_account:
                        mailto_ad = True
                        break
            except:
                print "No AD spread found."

            riktig_brukernavn = ' Nytt brukernavn er %s.' % (new_name)

            if ac.is_expired():
                riktig_brukernavn += ' Imidlertid er ikke kontoen aktiv, og vil kun sendes til AD når den blir reaktivert.'

            # if False and mailto_ad and not dryrun:
            #     Utils.sendmail('nybruker2@asp.uit.no', #TO
            #                    'bas-admin@cc.uit.no', #SENDER
            #                    'Brukernavn endret', #TITLE
            #                    'Brukernavnet %s er endret i BAS.%s' %
            #                    (old_name, riktig_brukernavn), #BODY
            #                    cc=None,
            #                    charset='iso-8859-1',
            #                    debug=False)
            #     print "mail sent to nybruker2@asp.uit.no\n"

            pe.clear()
            ac.clear()

            if send_user_mail is not None:
                # SEND MAIL TO OLD AND NEW ACCOUNT + "BCC" to bas-admin!
                sender = 'orakel@uit.no'
                recipient = send_user_mail['OLD_MAIL']
                cc = [send_user_mail ['NEW_MAIL'],]

                template = cereconf.CB_SOURCEDATA_PATH + '/templates/rename_account.tmpl'

                result = Utils.mail_template(recipient, template, sender=sender, cc=cc,
                                        substitute=send_user_mail, charset='utf-8', debug=dryrun)
                
                #print "Mail sent to: %s" % (recipient)
                #print "cc to %s" % (cc)
                
                if dryrun:
                    print "\nDRYRUN: mailmsg=\n%s" % result

                # BCC
                recipient = 'bas-admin@cc.uit.no'
                template = cereconf.CB_SOURCEDATA_PATH + '/templates/rename_account.tmpl'
                result = Utils.mail_template(recipient, template, sender=sender,
                                        substitute=send_user_mail, charset='utf-8', debug=dryrun)

                #print "BCC sent to: %s" % (recipient)
            #worker.rollback();
            worker.commit()
        else:
            worker.rollback()
       


if __name__ == '__main__':
    main()
