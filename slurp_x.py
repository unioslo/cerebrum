#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

''' This file is a UiT specific extension to Cerebrum
'''


import cerebrum_path
import cereconf
import getopt
import sys
import string
import os
import urllib
import datetime
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Constants import Constants
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email
import locale
locale.setlocale(locale.LC_ALL,"en_US.ISO-8859-1")

    
class execute:

    def __init__(self,logger_name):
        #init variables
        self.split_char = ":" # char used to split data from the source_file
        self.db = Factory.get('Database')()
        self.person = Factory.get('Person')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.OU = Factory.get('OU')(self.db)
        
        self.logger = Factory.get_logger(logger_name)
        self.db.cl_init(change_program='slurp_x')
        bootstrap_inst = self.account.search(name=cereconf.INITIAL_ACCOUNTNAME)
        bootstrap_id=bootstrap_inst[0]['account_id']
        #print "bootstrap_id = %s" % bootstrap_id

    #reads the input source file
    def get_guest_data(self):
        guest_host = cereconf.GUEST_HOST
        guest_host_dir = cereconf.GUEST_HOST_DIR
        guest_host_file = cereconf.GUEST_HOST_FILE
        guest_file = cereconf.GUEST_FILE
        ret = urllib.urlretrieve("http://%s%s%s" % (guest_host,guest_host_dir,guest_host_file),"%s" % (guest_file))
        return ret

    def read_data(self,file):

        data = []
        file_handle = open(file,"r")
        lines = file_handle.readlines()
        file_handle.close()
        for line in lines:
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue
            data.append(line)
        return data



    def get_sysX_person(self,sysX_id):

        p = Factory.get('Person')(self.db)
        external_id_type = self.constants.externalid_sys_x_id
        try:
            p.find_by_external_id(external_id_type,sysX_id)
            print "SysX person (%s) found" % (sysX_id)
        except Errors.NotFoundError:
            print "SysX person NOT found with sysX id=(%s) " % sysX_id
            pass
        return p

    


    def create_person2(self,data_list):
        try: 
            id,fodsels_dato,personnr,gender,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost,national_id,aproved = data_list.split(self.split_char)
        except ValueError,m:
            self.logger.error("VALUEERROR_create_person2: %s: Line=%s" % (m,data_list))
            return 1
        
        my_stedkode = Stedkode(self.db)
        my_stedkode.clear()
        self.person.clear()
        self.logger.debug("Trying to process %s %s ID=%s, national_id=%s,aproved=%s" % (fornavn,etternavn,id,national_id,aproved))
        aproved = aproved.rstrip()


        if (aproved != 'Yes'):
            self.logger.error("Processing person: %s %s (id=%s)not yet approved, not stored in BAS." % (fornavn, etternavn,id))
            return 1,bruker_epost
        else:
            #person is approved!
            if (personnr != ""):
                # person has a norwegian ssn. use standard method.
                external_id_type = self.constants.externalid_fodselsnr
                external_id = personnr
                try:
                    fnr = fodselsnr.personnr_ok(personnr)
                except fodselsnr.InvalidFnrError:
                    self.logger.warn("Ugyldig f�dselsnr: %s" % personnr)
                    return 1,bruker_epost

                (year,mon,day) = fodselsnr.fodt_dato(fnr)
                gender = self.constants.gender_male
                if(fodselsnr.er_kvinne(fnr)):
                    gender = self.constants.gender_female

                try:
                    self.person.find_by_external_id(external_id_type,external_id)
                    print "found person obj with id_type=%s" % external_id_type
                except Errors.NotFoundError:
                    # person not found with norwegian ssn, try to locate with sysX id.
                    if (national_id != "NO"):
                        print "has nor-snn, but not found with it. try to locate as sysX"
                        self.person = self.get_sysX_person(id)
            else:
                # foreigner without norwegian ssn, use SysX-id as external-id.
                external_id_type = self.constants.externalid_sys_x_id
                external_id = id
                date_field = fodsels_dato.split(".")
                year = date_field[2]
                mon =  date_field[1]
                day =  date_field[0]
                if(gender=='M'):
                    gender = self.constants.gender_male
                elif(gender=='F'):
                    gender = self.constants.gender_female
                
                self.person = self.get_sysX_person(id)


        self.logger.info("Processing person: name=%s %s , id_type=%s, id=%s" % (fornavn,etternavn,external_id_type,external_id))

        # person object located, populate...
        self.person.populate(self.db.Date(int(year),int(mon),int(day)),gender)
        
        self.person.affect_names(self.constants.system_x,self.constants.name_first,self.constants.name_last,self.constants.name_full)
        self.person.populate_name(self.constants.name_first,fornavn)
        self.person.populate_name(self.constants.name_last,etternavn)

        fullt_navn = "%s %s" % (fornavn,etternavn)
        self.person.populate_name(self.constants.name_full,fullt_navn)
        self.person.affect_external_id(self.constants.system_x,external_id_type)
        self.person.populate_external_id(self.constants.system_x,external_id_type,external_id)
        
        # setting affiliation and affiliation_status
        orig_affiliation = affiliation
        affiliation = int(self.constants.PersonAffiliation(affiliation))
        affiliation_status = int(self.constants.PersonAffStatus(orig_affiliation,affiliation_status.lower()))

        # get ou_id of stedkode used
        fakultet = ou[0:2]
        institutt = ou[2:4]
        avdeling = ou[4:6]
        my_stedkode.find_stedkode(fakultet,institutt,avdeling,cereconf.DEFAULT_INSTITUSJONSNR)
        ou_id = my_stedkode.entity_id

        # populate the person affiliation table
        self.person.populate_affiliation(int(self.constants.system_x),
                                         int(ou_id),
                                         int(affiliation),
                                         int(affiliation_status)
                                         )

        # Update last-seen date
        try:
            self.person.set_affiliation_last_date(int(self.constants.system_x),
                                                  int(ou_id),
                                                  int(affiliation),
                                                  int(affiliation_status)
                                                  )
        except AttributeError:
            # in case this is a new person object...
            pass
        except Errors.ProgrammingError:
            pass


        #write the person data to the database
        op = self.person.write_db()
        if op is None:
            self.logger.info("**** EQUAL ****")
        elif op == True:
            self.logger.info("**** NEW ****")
        elif op == False:
            self.logger.info("**** UPDATE ****")
        self.db.commit()


    def expire_date_conversion(self,expire_date):
        # historical reasons dictate that dates may be received on the format dd.mm.yyyy
        # if this is the case, we need to convert it to yyyy-mm-dd
        day,month,year = expire_date.split("-",2)
        expire_date="%s-%s-%s" % (year,month,day)
        return expire_date


    def update_account(self,data_list):
        num_new_list = []
        num_old_list = []
        id,fodsels_dato,personnr,gender,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost,national_id,aproved = data_list.split(self.split_char)
        # need to check and update the following data: affiliation,expire_date,gecos,ou and spread

        #update expire_date
        my_date= expire_date.split("-")
        if (self.account.is_expired() and (datetime.date(int(my_date[0]),int(my_date[1]),int(my_date[2])) > datetime.date.today())):
            # This account is expired in cerebrum. expire_date from the guest database
            # is set in the future. need to update expire_date in the database
            self.logger.info("updating expire date to: %s" % expire_date)
            self.account.expire_date = expire_date

        # update gecos
        full_name = "%s %s" % (fornavn,etternavn) # check if equal first? # check name from personobject? to 
        self.account.gecos = self.account.simplify_name(full_name,as_gecos=True)

        #update ou and affiliation (setting of account_type)
        self.OU.clear()
        self.OU.find_stedkode(ou[0:2],ou[2:4],ou[4:6],cereconf.DEFAULT_INSTITUSJONSNR)

        #my_account_types = self.account.get_account_types()
        if(affiliation=="MANUELL"):
            self.account.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=400)
        elif(affiliation=="TILKNYTTET"):
            self.account.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=350)
        else:
            raise errors.ValueError("invalid affiliation: %s in guest database" % (affiliation))

        #update spread
        old_spreads = self.account.get_spread()
        if (spreads):
            spread_list = string.split(spreads,",")
        else:
            spread_list = []
        spread_list.append('ldap@uit') # <- default spread for ALL sys_x users/accounts.
        for i in spread_list:
            num_new_list.append(int(self.constants.Spread(i)))
        for o in old_spreads:
            num_old_list.append(int(self.constants.Spread(o['spread'])))

        for new_spread in num_new_list:
            if new_spread not in num_old_list:
                self.account.add_spread(int(new_spread))
            # also check and update homedir for each spread!
            self.account.set_home_dir(int(new_spread))

        # updates done. write
        self.account.write_db()


    def create_account(self,data_list):
        data_list = data_list.rstrip()

        try:
            id,fodsels_dato,personnr,gender,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost,national_id,aproved = data_list.split(self.split_char)
        except ValueError,m:
            self.logger.error("data_list:%s##%s" % (data_list,m))
            sys.exit(1)
        posix_user = PosixUser.PosixUser(self.db)
        group = Factory.get('Group')(self.db)
        self.person.clear()
        posix_user.clear()
        group.clear()
        self.OU.clear()
        my_accounts = None
        self.account = Factory.get('Account')(self.db)

        num_new_list = []
        num_old_list = []
        spread_list = string.split(spreads,",")



        if (aproved != 'Yes'):
            self.logger.error("Person %s %s (id=%s) not approved! Do not create account" % (fornavn, etternavn, id))
            return 1,bruker_epost
        else:
            #person is approved!
            if (personnr != ""):
                # person has a norwegian ssn. use standard method.
                external_id_type = self.constants.externalid_fodselsnr
                external_id = personnr
                try:
                    fnr = fodselsnr.personnr_ok(personnr)
                except fodselsnr.InvalidFnrError:
                    self.logger.warn("Ugyldig f�dselsnr: %s" % personnr)
                    return 1,bruker_epost

                (year,mon,day) = fodselsnr.fodt_dato(fnr)
                gender = self.constants.gender_male
                if(fodselsnr.er_kvinne(fnr)):
                    gender = self.constants.gender_female

                try:
                    self.person.find_by_external_id(external_id_type,external_id)
                except Errors.NotFoundError:
                    # person not found with norwegian ssn, try to locate with sysX id.
                    if (national_id != "NO"):
                        self.person = self.get_sysX_person(id)
            else:
                # foreigner without norwegian ssn, use SysX-id as external-id.
                external_id_type = self.constants.externalid_sys_x_id
                external_id = id
                date_field = fodsels_dato.split(".")
                year = date_field[2]
                mon =  date_field[1]
                day =  date_field[0]
                if(gender=='M'):
                    gender = self.constants.gender_male
                elif(gender=='F'):
                    gender = self.constants.gender_female
                self.person = self.get_sysX_person(id)


        self.logger.info("Processing account for person: name=%s %s , id_type=%s, id=%s" % (fornavn,etternavn,external_id_type,external_id))
        try:
            account_list = self.person.get_accounts(filter_expired=False)
            self.account.find(account_list[0][0])
            self.update_account(data_list)
            return account_list[0][0], bruker_epost
            #account_types = self.account.get_account_types(filter_expired=False)
            #for account_type in account_types:
            #    #print "account_type[affiliation] = %s" % account_type['affiliation']
            #    if ((account_type['affiliation']==self.constants.affiliation_manuell)
            #        or (account_type['affiliation']==self.constants.affiliation_tilknyttet)):
            #        self.update_account(data_list)
        except Errors.NotFoundError:
            pass
        except IndexError:
            pass
             

        if(len(account_list) == 0):
            self.logger.debug("create new account")
            spread_list = string.split(spreads,",")
            spread_list.append('ldap@uit') # <- default spread for ALL sys_x users/accounts.

            full_name = "%s %s" % (fornavn,etternavn)
            if(national_id !='NO'):
                username = self.account.get_uit_uname(id,full_name,'AD')
            else:
                if('AD_account' in spread_list):
                    username = self.account.get_uit_uname(personnr,full_name,'AD')
                else:
                    username = self.account.get_uit_uname(personnr,full_name)
            
            group.find_by_name("posixgroup",domain=self.constants.group_namespace)
            new_expire_date = self.expire_date_conversion(expire_date)

            bootstrap_inst = self.account.search(name=cereconf.INITIAL_ACCOUNTNAME)
            bootstrap_id=bootstrap_inst[0]['account_id']
            posix_user.populate(name = username,
                                owner_id = self.person.entity_id,
                                owner_type = self.constants.entity_person,
                                np_type = None,
                                creator_id = bootstrap_id,
                                expire_date = expire_date,
                                posix_uid = posix_user.get_free_uid(),
                                gid_id = group.entity_id,
                                gecos = full_name,
                                shell = self.constants.posix_shell_bash
                                )
            try:
                posix_user.write_db()
                
                # add the correct spreads to the account
                for spread in spread_list:
                    #print "%s,%s,%s" % (posix_user.entity_id,int(self.constants.entity_account),int(self.constants.group_memberop_union))
                    posix_user.add_spread(int(self.constants.Spread(spread)))
                    posix_user.set_home_dir(int(self.constants.Spread(spread)))
                
                    
                #group.add_member(posix_user.entity_id,int(self.constants.entity_account),int(self.constants.group_memberop_union))
                posix_user.set_password(posix_user.make_passwd(username))
                posix_user.write_db()
                # lets set the account_type table
                # need: oi_id, affiliation and priority
                self.OU.find_stedkode(ou[0:2],ou[2:4],ou[4:6],cereconf.DEFAULT_INSTITUSJONSNR)

                if(affiliation=="MANUELL"):
                    posix_user.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=400)
                elif(affiliation=="TILKNYTTET"):
                    posix_user.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=350)
                else:
                    raise errors.ValueError("invalid affiliation: %s in guest database" % (affiliation))


                #posix_user.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)))
                if(bruker_epost !=""):
                    self.send_mail(bruker_epost,username,spread_list)

                if(bruker_epost==''):
                    if "AD_account" in spread_list:
                        domain ="%s" % cereconf.NO_MAILBOX_DOMAIN
                    else:
                        domain="student.uit.no"
                    bruker_epost="%s@%s" % (username,domain)

                    
                if("AD_account" in spread_list):
                    #only send email to nybruker@asp.uit.no if AD_account is one of the chosen spreads.
                    # removed by request from ASP team, may be inserted againg in the future
                    #self.send_ad_email(full_name,personnr,ou,affiliation_status,expire_date,hjemmel,kontaktinfo,bruker_epost,ansvarlig_epost)
                    pass
                self.confirm_registration(personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost,username)
                return  posix_user.entity_id,bruker_epost
            except Errors:
                self.logger.error("Error in creating posix account for person %s" % personnr)
                return 1,bruker_epost
 
            posix_user.write_db()
        else:
            logger.error("Should never get here: New account, but account_list not empty")


    def send_ad_email(self,name,ssn,ou,type,expire_date,why,contact_data,external_email,registrator_email):
        ad_message="""
%s har sendt inne en foresp�rsel om ny AD konto. F�lgende data er registrert om denne personen.

Navn: %s
personnummer:%s
stedkode: %s
type:%s
utl�ps dato:%s
grunn: %s
kontakt data: %s
ekstern epost: %s

""" % (registrator_email,name,ssn,ou,type,expire_date,why,contact_data,external_email)

        SENDMAIL="/usr/sbin/sendmail -fnybruker2@asp.uit.no"
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From: bas-admin@cc.uit.no\n")
        p.write("To: nybruker2@asp.uit.no\n")
        p.write("Bcc: kenneth.johansen@cc.uit.no\n")
        p.write("subject: Registrering av ny AD bruker\n")
        p.write("\n")
        p.write("%s" % ad_message)
        sts = p.close()
        if sts != None:
            self.logger.error("Sendmail exit status: %s for send_ad_email" % sts)


    def verify_foreign(self,personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost):

        verify_message="""F�lgende data om en utenlandsk person er motatt i system-X. Personen m� godkjennes.

Personnr: %s
Fornavn: %s
Etternavn: %s
ou: %s
Tilknytning: %s
Tilknytnings type: %s
utl�ps dato: %s
skal eksporteres til disse ende systemene: %s
Hjemmel: %s
kontakt info: %s
Ekstern epost: %s
Ansvarlig epost: %s

""" % (personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,bruker_epost,ansvarlig_epost)
        SENDMAIL="/usr/sbin/sendmail -fsys-x-admin@cc.uit.no"
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From: bas-admin@cc.uit.no\n")
        p.write("To: sys-x-admin@cc.uit.no\n")
        p.write("subject: Registrering av utenlandsk bruker\n")
        p.write("\n")
        p.write("%s" % verify_message)
        sts = p.close()
        if sts != None:
            self.logger.error("Sendmail exit status: %s for confirm registration" % sts)

    def confirm_registration(self,personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost,username):
        confirm_message="""
F�lgende data er motatt og behandlet i system X.

Personnr: %s
Fornavn: %s
Etternavn: %s
ou: %s
Tilknytning: %s
Tilknytnings type: %s
utl�ps dato: %s
skal eksporteres til disse ende systemene: %s
Hjemmel: %s
kontakt info: %s
Ekstern epost: %s
Ansvarlig epost: %s

Personen har f�tt tildelt brukernavnet:%s


""" % (personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,bruker_epost,ansvarlig_epost,username)
        SENDMAIL="/usr/sbin/sendmail -f%s" % (ansvarlig_epost)
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From: bas-admin@cc.uit.no\n")
        p.write("To: %s\n" % ansvarlig_epost)
        p.write("Bcc: kenneth.johansen@cc.uit.no\n")
        p.write("subject: Ny bruker er n� behandlet.\n")
        p.write("\n")
        p.write("%s" % confirm_message)
        sts = p.close()
        if sts != None:
            self.logger.error("Sendmail exit status: %s for confirm registration" % sts)
        
        
    def send_mail(self,email_address,user_name,spreads):
        #This function sends an email to the email_address given
        if "AD_account" in spreads:
            message="""
Translation in english follows.
        
Dette er en automatisk generert epost. Du er registrert i BAS og har f�tt tildelt ett brukernavn:%s og ett passord.
For � aktivere kontoen din m� du ta kontakt med din lokale personal konsulent.
\n
I samsvar med de data som ble registrert ved din innmeldelse vil du bli eksponert til disse systemene: %s.
I tilfellet FRIDA kan det ta opp til ett par virkedager f�r kontoen er klar.
Har du noen sp�rsm�l kan du ta kontakt med orakel@uit.no eller bas-admin@cc.uit.no. \n
-----------------------------------------------------------------------------------

This is an automated message. You are now registered in BAS and have received the username:%s and a password.
To activate your account you need to contact the local personnel coordinator.
\n
According to the data registered you will be exported to the following systems: %s.
Notice that it may take a few days before your FRIDA account is activated.
If you have any questions you can either contact orakel@uit.no or bas-admin@cc.uit.no\n
        """ % (user_name,spreads,user_name,spreads)
        else:
            message="""
Translation in english follows.
        
Dette er en automatisk generert epost. Du er registrert i BAS og har f�tt tildelt ett brukernavn:%s og ett passord.
For � aktivere kontoen din m� du g� til orakel tjenesten ved uit. http://uit.no/orakel.
\n
I samsvar med de data som ble registrert ved din innmeldelse vil du bli eksponert til disse systemene: %s.
I tilfellet FRIDA kan det ta opp til ett par virkedager f�r kontoen er klar.
Har du noen sp�rsm�l kan du ta kontakt med orakel@uit.no eller bas-admin@cc.uit.no. \n
-----------------------------------------------------------------------------------

This is an automated message. You are now registered in BAS and have received a username:%s and a password.
To activate your account you need to visit the oracle service at uit.  http://uit.no/orakel
\n
According to the data registered you will be exported to the following systems: %s.
Notice that it may take a few days before your FRIDA account is activated.
If you have any questions you can either contact orakel@uit.no or bas-admin@cc.uit.no\n
        """ % (user_name,spreads,user_name,spreads)

        SENDMAIL="/usr/sbin/sendmail -f%s" % (email_address)
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From: bas-admin@cc.uit.no\n")
        p.write("To: %s\n" % email_address)
        p.write("Bcc: kenneth.johansen@cc.uit.no\n")
        p.write("subject: Registrering av bruker\n")
        p.write("\n")
        p.write("%s" % message)
        sts = p.close()
        if sts != None:
            self.logger.error("Sendmail exit status: %s for send_mail" % sts)


def main():

    logger_name = cereconf.DEFAULT_LOGGER_TARGET

    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:l:u',['source_file','logger-name','update',])
    except getopt.GetoptError:
        usage()

    ret = 0
    source_file = 0
    update = 0
    for opt,val in opts:
        if opt in('-s','--source_file'):
            source_file = val
        if opt in ('-u','--update'):
            update = 1
        if opt in ('l','--logger-name'):
            logger_name = val

    x_create=execute(logger_name)
    if (source_file == 0):
        if (update):
            x_create.logger.info("Retreiving Guest data")
            x_create.get_guest_data()
        else:
            usage()
    else:
        if(update ==1):
            x_create.get_guest_data()
        data = x_create.read_data(source_file)
        for line in data:
            ret = x_create.create_person2(line)
        x_create.db.commit()
        #sys.exit(1)
        #accounts needs to be created after person objects are stored
        #Therefore we need to traverse the list again and generate
        #accounts.
        for line in data:
            ret,bruker_epost = x_create.create_account(line)
            #print "ret = %s,epost=%s" % (ret,bruker_epost)
            x_create.db.commit()
            if ((ret != 1) and (bruker_epost != "")):
                email_class = Email.email_address(x_create.db)
                email_class.process_mail(ret,"defaultmail",bruker_epost)
                email_class.db.commit()
            else:
                x_create.logger.warn("Failed to update email on account_id=%s, email=%s" % (ret,bruker_epost))
               
        x_create.db.commit()
        
                               
def usage():
    print """
    usage:: python slurp_x.py -s
    -s file | --source_file file : source file containing information needed to create
                                   person and user entities in cerebrum
    -u      | --update_data      : updates the datafile containing guests from the guest database
    -l name | --logger_name name : change default logger target
    """
    sys.exit(1)


if __name__=='__main__':
    main()

# arch-tag: badbe824-b426-11da-846c-fe4d7376a8b8
