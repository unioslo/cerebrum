#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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


import random
import sys
import re
import string
import crypt

# UIT imports
# added by: kennethj 20050308
import md5
import base64
import sha
import mx
import traceback
# UIT end


import cerebrum_path
import cereconf
from Cerebrum import Account
from Cerebrum import Errors

from Cerebrum import Utils
from Cerebrum.Utils import NotSet
from Cerebrum.modules import Email
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Utils import pgp_encrypt, Factory
from Cerebrum.modules.no.uit.Email import email_address

#from Cerebrum.modules.no.uit.Email import email_address

class AccountUiTMixin(Account.Account):
    """Account mixin class providing functionality specific to UiT.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies of the University of Tromsoe.

    kort forklart:
    den siste write_db() er den
    som kjøres. den kaller opp foreldrenes write_db. de kaller igjen opp
    sine foreldre(grunnet self.__super.write_db()) til
    man til slutt kaller Account sin write_db(). når den returnerer så
    fortsetter metodene der de kallte super()
    Man har bare en write_db() i
    hele Account etter at man har inkludert Mixins, men man får tak i
    foreldrene ved å bruke super()


    """

    #
    # Override username generator in core Account.py
    # Do it the UiT way!
    #
    def suggest_unames(self, ssn, fname, lname):
     
        #print "UIT version of suggest_unames(...) called"
    
        full_name = "%s %s" % (fname, lname)
        username = self.get_uit_uname(ssn,full_name)

        #print "UIT version of suggest_uames returns '%s'" % username
        return username
        
    
    def get_homedir_id(self,spread):
        # sjekk om denne konto id har en konto for denne spread,
        # returner homedir_id eller None
        ret = None
        try:
            home = self.get_home(spread)
            if (len(home)>0):
                ret = home['homedir_id']
        except Errors.NotFoundError:
            pass
        return ret

    
    
    def encrypt_password(self, method, plaintext, salt=None):
        """Returns the plaintext encrypted according to the specified
        method.  A mixin for a new method should not call super for
        the method it handles.
        UIT: mixin. added our own encryption methods, otherwise equal super()
        """
        
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_ssha):
            if salt is None:
                saltchars = string.ascii_letters + string.digits + "./"
                if method == self.const.auth_type_md5_crypt:
                    salt = "$1$" + Utils.random_string(8, saltchars)
                else:
                    salt = Utils.random_string(2, saltchars)
            if method == self.const.auth_type_ssha:
                # encodestring annoyingly adds a '\n' at the end of
                # the string, and OpenLDAP won't accept that.
                # b64encode does not, but it requires Python 2.4
                return base64.encodestring(sha.new(plaintext + salt).digest() +
                                           salt).strip()
            return crypt.crypt(plaintext, salt)
        elif method == self.const.auth_type_md4_nt:
            # Do the import locally to avoid adding a dependency for
            # those who don't want to support this method.
            import smbpasswd
            return smbpasswd.nthash(plaintext)
        elif method == self.const.auth_type_plaintext:
            return plaintext
        # UIT: added our encryption methods....
        elif method == self.const.auth_type_md5_crypt_hex:
            return self.enc_auth_type_md5_crypt_hex(plaintext)
        elif method == self.const.auth_type_md5_b64:
            return self.enc_auth_type_md5_b64(plaintext)
        raise ValueError, "Unknown method " + repr(method)

    def decrypt_password(self, method, cryptstring):
        """Returns the decrypted plaintext according to the specified
        method.  If decryption is impossible, NotImplementedError is
        raised.  A mixin for a new method should not call super for
        the method it handles.
        UIT: Added our enc methods.
        """
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_md4_nt,
                      self.const.auth_type_md5_crypt_hex,
                      self.const.auth_type_md5_b64):
            raise NotImplementedError, "Cant decrypt %s" % method
        elif method == self.const.auth_type_plaintext:
            return cryptstring
        raise ValueError, "Unknown method " + repr(method)

    def verify_password(self, method, plaintext, cryptstring):
        """Returns True if the plaintext matches the cryptstring,
        False if it doesnt.  If the method doesnt support
        verification, NotImplemented is returned.
        """
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_md4_nt,
                      self.const.auth_type_ssha,
                      self.const.auth_type_plaintext):
            salt = cryptstring
            if method == self.const.auth_type_ssha:
                salt = base64.decodestring(cryptstring)[20:]
            return (self.encrypt_password(method, plaintext, salt=salt) ==
                    cryptstring)
        raise ValueError, "Unknown method " + repr(method)

    
    
    #UIT: added encryption method
    # Added by: kennethj 20050803
    def enc_auth_type_md5_crypt_hex(self,plaintext,salt = None):
        plaintext = plaintext.rstrip("\n")
        m = md5.new()
        m.update(plaintext)
        encrypted = m.hexdigest()
        #print "plaintext %s = %s" % (plaintext,encrypted)
        return encrypted


    #UIT: added encryption method
    # Added by: kennethj 20050803
    def enc_auth_type_md5_b64(self,plaintext,salt = None):
        m = md5.new()
        m.update(plaintext)
        foo = m.digest()
        encrypted = base64.encodestring(foo)
        encrypted = encrypted.rstrip()
        return encrypted

    
    def enc_auth_type_md5_crypt(self, plaintext, salt=None):
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            s = []
            for i in range(8):
                s.append(random.choice(saltchars))
            salt = "$1$" + "".join(s)
        return crypt.crypt(plaintext, salt)
        

    
    def set_home_dir(self, spread):
        #print "Calling set_home_dir for account_id=%s, spread=%s" % (self.account_name,spread)
        path_prefix = cereconf.UIT_DEFAULT_HOMEPATH_PREFIX
        homeid = self.get_homedir_id(spread)
        account_name = self.account_name
        homepath = ('%s/%s/%s/%s') % (path_prefix,account_name[0],account_name[0:2],account_name)
        #print "setting %s as home path for %s on homedir_id='%s', spread=%d" % (homepath,account_name,homeid,spread)
        newid = -1
        if (homeid == None):
            #print "Inserting new homedir_id"
            newid = self.set_homedir(home=homepath,status=self.const.home_status_not_created)
        else:
            #print "Updating homedir_id=%s" % (homeid)
            newid = self.set_homedir(current_id=homeid,home=homepath,status=self.const.home_status_not_created)
            newid = homeid
            
        #print "Homedir_id before='%s' and after='%s'" % (homeid, newid)
        # update homedir for the spread
        self.set_home(spread,newid)



    def get_uit_uname(self,fnr,name,Regime=None):
        ssn = fnr
        if Regime == None:
            cstart=22
            query = "select user_name from legacy_users where ssn='%s' and source <>'AD'" % (ssn)
        else:
            cstart=0
            query = "select user_name from legacy_users where ssn='%s' and source ='AD'" % (ssn)
        #print "%s" % query
        db = Factory.get('Database')()
        db_row = db.query(query)
        for row in db_row:
            # lets see if this person already has an account in cerebrum with this username (From legacy_user)
            username= row['user_name']
            query = "select e.entity_id from entity_name e, account_info ai, entity_external_id eei \
            where e.entity_name='%s' and e.entity_id = ai.account_id and ai.owner_id = eei.entity_id \
            and eei.external_id='%s'" % (username,ssn)
            
            db_row2 = db.query(query)
            if(len(db_row2)>0):
                #This user already has an account in cerebrum with the username from the legacy table
                #Returning existing account_name
                #print "%s already has an account with user_name %s. returning this. " % (ssn,username)
                return username

            # was unable to find any existing accounts in cerebrum for this person with the
            # username from the legacy table.
            # lets return the first user_name in legacy_users for this person, that no one alrady has.
            for row in db_row:
                username = row['user_name']
                query = "select entity_id from entity_name where entity_name='%s'" % (username)
                db_row2 = db.query(query)
                if(len(db_row2) ==0 ):
                    #print "registered username %s for %s is free. returning this" % (ssn,username)
                    return username

        # The person has no account, or the user name registered in the legacy_table is
        # already taken by another user.
        # if we get here and regieme == AD, it means we cannot find a account in legacy
        # which can be used!  This is an consistenscy error!
        if (Regime=='AD'):
            if(len(db_row)==0):
                raise ValueError, "AD user has no registered username in legacy user."
            else:
                raise ValueError, "AD Username: %s,fnr: %s, in legacy table is taken by another person." % (username,ssn)

        # getting here means either that:
        # 1. the person does not have a previous account
        # 2. the persons username is already taken, and a new has to be created
        inits = self.get_uit_inits(name)
        if inits == 0:
            return inits
        new_username = self.get_serial(inits,cstart)
        #print "no legacy usernames for %s were free. created new %s" % (ssn,new_username)
        return new_username


# this func was synced with powaqqatsi 2006-03-03
#     def get_uit_uname(self,fnr,name,Regime=None):
#         ssn = fnr
#         if Regime == None:
#             cstart=22
#             query = "select user_name from legacy_users where ssn='%s' and source <>'AD'" % (ssn)
#         else:
#             cstart=0
#             query = "select user_name from legacy_users where ssn='%s' and source ='AD'" % (ssn)

#         #print "%s" % query
#         db = Factory.get('Database')()
#         db_row = db.query(query)
#         if(len(db_row) == 1):
#             # lets see if this username is taken.
#             # if it is not, lets update the users username
#             # if it is we must create a new username
#             username = db_row[0]['user_name']
#             query = "select entity_id from entity_name where entity_name='%s'" % username
#             #print "%s" % query
#             db_row = db.query(query)
#             if(len(db_row) == 0):
#                 # username does not exist cerebrum.
#                 #lets return the username from the legacy_table
#                 #print "GIVING: %s the old username %s from the legacy_users table" % (fnr,username)
#                 return username
#         # getting here means either that:
#         # 1. the person does not have a previous username
#         # 2. the persons username is already taken , and a new has to be created
#         inits = self.get_uit_inits(name)
#         if inits == 0:
#             return inits
#         new_username = self.get_serial(inits,cstart)
#         return new_username

    def get_serial(self,inits,cstart):

#        cstart = 22
        foo = ""
        found = False
        db = Factory.get('Database')()
        ac = Factory.get('Account')(db)

        while ((not found) and (cstart < 990)):
            # xxx999 is reserved for admin use
            uname = "%s%03d" % (inits, cstart)
            #print "uname = %s" % uname
            #ac = Account(db)
            ac.clear()
            query = "select * from entity_name where entity_name='%s'" % uname
            db_row = db.query(query)
            query2 = "select * from legacy_users where user_name='%s'" % uname
            db_row2 = db.query(query2)

            if((len(db_row) != 0) or (len(db_row2) != 0)):
                cstart += 1
                #try:
            else:
                found = True
                #ac.find_by_name(uname)
                #found = True
                #except Errors.NotFoundError:
                #print "new username will be: %s" % uname
        return uname

    def get_uit_inits(self,dname):
       #Gets the first 3 letters based upon the name of the user.
       #print "DNAME= %s" % dname
       orgname = dname
       dname = self.simplify_name(dname)
       #p = re.compile('[^a-zA-Z0-9]')
       #m =p.search(dname)
       #if m:
       #    # Person has characters not recognized in cerebrum, return empty username
       #    return 0
       dname = dname.replace('.',' ')
       dname = dname.replace('\'','')
       name = dname.split()
       name_length = len(name)

       if(name_length == 1):
           inits = name[0][0:3]
       else:
           inits = name[0][0:1] + name[-1][0:2]


#       if(name_length == 2):
#           if (len(name[0]) < 2):
#               inits = name[0][0:1] + name[-1][0:2]
#           else:
#               inits = name[0][0:1] + name[-1][0:2]
#       if(name_length == 3):
#           #inits = name[0][0:1] + name[1][0:1] + name[2][0:1]
#           inits = name[0][0:1] + name[-1][0:2]

##       Removed by bto001, 23-11-2005. 
##       Made redundant by calling self.simplify_name earlier in this method. 
#       inits = inits.replace('Æ','E')
#       inits = inits.replace('æ','e')
#       inits = inits.replace('Ø','O')
#       inits = inits.replace('ø','o')
#       inits = inits.replace('Å','A')
#       inits = inits.replace('å','a')
#       inits = inits.replace('Ä','A')
#       inits = inits.replace('ä','a')
#       inits = inits.replace('Ö','O')
#       inits = inits.replace('ö','e')
#       inits = inits.replace('ñ','n')
#       inits = inits.replace('é','e')
#       inits = inits.replace('è','e')
#       #inits = inits.replace('','u')
#       inits = inits.replace('ü','u')
#       inits = inits.replace('Ü','U')
#       inits = inits.lower()
       
       #sanity check
       p = re.compile('^[a-z]{3}$')
       if (p.match(inits)):
           return inits
       else:
           print "Sanity check failed: Returning %s for %s" % (inits,orgname)
           raise ValueError("ProgrammingError: A Non ascii-letter in uname!: '%s'" % inits)


#  def build_email_list(self,default_email_file=None):
#         email_list = {}

#         if default_email_file==None:
#             default_email_file = "/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/source_data/ad/AD_Emaildump.cvs"
       
#         file_handle = open(default_email_file,'r')
#         for line in file_handle:
#             uname,email = line.split(",",2)
#             email_list[uname] = email

#         return email_list
        

   #  def process_mail(account_id, type, addr):
#         logger = Factory.get_logger("console")
#         et = Email.EmailTarget(db)
#         ea = Email.EmailAddress(db)
#         edom = Email.EmailDomain(db)
#         epat = Email.EmailPrimaryAddressTarget(db)

#         addr = string.lower(addr)    

#         fld = addr.split('@')
#         if len(fld) != 2:
#             logger.error("Bad address: %s. Skipping", addr)
#             return None
#         # fi
    
#         lp, dom = fld
#         try:
#             edom.find_by_domain(dom)
#             logger.debug("Domain found: %s: %d", dom, edom.email_domain_id)
#         except Errors.NotFoundError:
#             edom.populate(dom, "Generated by import_uname_mail.")
#             edom.write_db()
#             logger.debug("Domain created: %s: %d", dom, edom.email_domain_id)
#         # yrt

#         try:
#             et.find_by_entity(int(account_id))
#             logger.debug("EmailTarget found(accound): %s: %d",
#                          account_id, et.email_target_id)
#         except Errors.NotFoundError:
#             et.populate(constants.email_target_account, entity_id=int(account_id),
#                         entity_type=constants.entity_account)
#             et.write_db()
#             logger.debug("EmailTarget created: %s: %d",
#                          account_id, et.email_target_id)
#         # yrt

#         try:
#             ea.find_by_address(addr)
#             logger.debug("EmailAddress found: %s: %d", addr, ea.email_addr_id)
#         except Errors.NotFoundError:
#             ea.populate(lp, edom.email_domain_id, et.email_target_id)
#             ea.write_db()
#             logger.debug("EmailAddress created: %s: %d", addr, ea.email_addr_id)
#         # yrt

#         if type == "defaultmail":
#             try:
#                 epat.find(et.email_target_id)
#                 logger.debug("EmailPrimary found: %s: %d",
#                              addr, epat.email_target_id)
#             except Errors.NotFoundError:
#                 if ea.email_addr_target_id == et.email_target_id:
#                     epat.clear()
#                     epat.populate(ea.email_addr_id, parent=et)
#                     epat.write_db()
#                     logger.debug("EmailPrimary created: %s: %d",
#                                  addr, epat.email_target_id)
#                 else:
#                     logger.error("EmailTarget mismatch: ea: %d, et: %d", 
#                                  ea.email_addr_target_id, et.email_target_id)
#                 # fi
#             # yrt
#         # fi
    
#         et.clear()
#         ea.clear()
#         edom.clear()
#         epat.clear()
#         # end process_mail




#     def account_id2email_address(self,entity_id,email_list,default_email_conversion_list=None):
#         logger = Factory.get_logger("console")
#         if default_email_conversion_list == None:
#             default_email_conversion_list = "/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/source_data/email_conversion_list.txt"
            
#             # lets get account username
#         try:
#             #self.account.clear()
#             #self.account.find(entity_id)
#             #account_name = self.account.get_account_name()
#             account_name = self.account_name
#             print "Account_name = %s" % account_name
#         except Errors.NotFoundError:
#             logger.debug("entity_id %s has no account" % entity_id)
#             logger.debug("exiting..")
#             sys.exit(1)
#         logger.debug("----")
#         #print " starting on account: %s" %account_name 
#         account_types = self.get_account_types()
#         #student_counter = 0
#         #ansatt_counter = 0
#         for i in account_types:
#             print "affiliation = %s" % i['affiliation']
#             logger.debug("affiliation = %s" % i.affiliation)
#             if i.affiliation == self.const.affiliation_student:
#                 email = "%s@student.uit.no" % (account_name)

#                 logger.debug("student account...")
#                 logger.debug("email =%s" % email)
#                 return email # returning student email address
#             elif i.affiliation == self.const.affiliation_ansatt:
#                 #lets get email address for this employee user
#                 logger.debug("----")
#                 logger.debug("Employee account..")
#                 if (account_name in email_list):
#                     email = email_list[account_name].rstrip()
#                     throw_away,domain = email.split("@",1)
#                     my_domain = domain.split(".",1)
#                     if my_domain[0] == 'ad':
#                         # not proper email address..lets run an extra check on this
#                         logger.debug("only ad domain in email_file for this user...must check the stedkode table to get ou data")
#                         # lets get ou info first
#                         self.ou.clear()
#                         self.ou.find(i.ou_id)
#                         my_domain="asp"
#                         #my_domain = self.check_email_address(account_name,default_email_conversion_list,self.ou.fakultet,self.ou.institutt,self.ou.avdeling)
#                         email = "%s@%s.uit.no" % (throw_away,my_domain)
#                     logger.debug("email address for AD account = %s" % email)
#                     return email
#                 else:
#                     #we have an employee account that doesnt have any email email address associated with it
#                     # from AD.
#                     self.ou.clear()
#                     self.ou.find(i.ou_id)
#                     my_domain="asp"
#                     #my_domain = self.check_email_address(account_name,default_email_conversion_list,self.ou.fakultet,self.ou.institutt,self.ou.avdeling)
#                     logger.debug("WARNING -> account %s has no email address from AD. checking ou_data towards conversion file" % account_name)
#                     email ="%s@%s.uit.no" % (account_name,my_domain) 
#                     logger.debug("will use %s" % email)
#                     return email
#         print "Error. account has no account_types"
#         logger.debug("ERROR. should never get here..exiting (account has no account_type)")
#         sys.exit(1)




#     def build_email_list(self,default_email_file=None):
#         email_list = {}

#         if default_email_file==None:
#             default_email_file = "/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/source_data/ad/AD_Emaildump.cvs"
       
#         file_handle = open(default_email_file,'r')
#         for line in file_handle:
#             uname,email = line.split(",",2)
#             email_list[uname] = email

#         return email_list
        
    #def enc_auth_type_md4_nt(self,plaintext,salt=None):
    #    import smbpasswd
    #    return smbpasswd.nthash(plaintext)

    def write_db(self):
        # Make sure Account is present in database.
#        print "UIT account: before super"
        ret = self.__super.write_db()
#        print "UIT Account.write_db sin __super.write_db() returns '%s'" % ret 
        if ret is not None:
#            # Account.write_db() seems to have made changes.  Verify
#            # that this Account has the email addresses it should,
#            # creating those not present.
#            print "##############"
#            print "testing access to write_db in uit account mixins"
#            print "email creation has to be done here. VERIFY IT that this works"
#            print "###############"
#
#            stack= traceback.extract_stack(limit=3)
#            #print "stack =%s" % stack
#            stack=stack[0]
#            (t1,t2,t3,t4)=stack
#            print "t1 = %s" % t1
#            print "stack = %s,%s,%s,%s" % (t1,t2,t3,t4)
#            if t1 =='process_students.py':
#                print "creating student email address"
#                email = email_address(self._db)
#                my_email = email.account_id2email_address(self.entity_id,self.const.affiliation_student,[]) # <- modules.no.uit.Email function
#                email.process_mail(self.entity_id,"defaultmail",my_email)
#            elif t1== 'process_employees.py':
#                print "creating employee email address"
#                email = email_address(self._db)
#                my_email = email.account_id2email_address(self.entity_id,self.const.affiliation_ansatt,[]) # <- modules.no.uit.Email function
#                email.process_mail(self.entity_id,"defaultmail",my_email)
#            #self.update_email_addresses()

            pass
	return ret

#    def update_email_addresses(self, set_primary = False):
#        # Find, create or update a proper EmailTarget for this
#        # account.
#        et = Email.EmailTarget(self._db)
#        target_type = self.const.email_target_account
#        if self.is_deleted() or self.is_reserved():
#            target_type = self.const.email_target_deleted
#        try:
#            et.find_by_email_target_attrs(entity_id = self.entity_id)
#            et.email_target_type = target_type
#        except Errors.NotFoundError:
#            # We don't want to create e-mail targets for reserved or
#            # deleted accounts, but we do convert the type of existing
#            # e-mail targets above.
#            if target_type == self.const.email_target_deleted:
#                return
#            et.populate(target_type, self.entity_id, self.const.entity_account)
#        et.write_db()
#        # For deleted/reserved users, set expire_date for all of the
#        # user's addresses, and don't allocate any new addresses.
#        ea = Email.EmailAddress(self._db)
#        if target_type == self.const.email_target_deleted:
#            expire_date = self._db.DateFromTicks(time.time() +
#                                                 60 * 60 * 24 * 180)
#            for row in et.get_addresses():
#                ea.clear()
#                ea.find(row['address_id'])
#                if ea.email_addr_expire_date is None:
#                    ea.email_addr_expire_date = expire_date
#                ea.write_db()
#            return
#        # if an account without email_server_target is found assign
#        # the appropriate server
#        est = Email.EmailServerTarget(self._db)
#        try:
#            est.find(et.email_target_id)
#        except Errors.NotFoundError:
#            if self.get_account_types():
#                est = self._update_email_server()
#            else:
#                # do not set email_server_target until account_type is registered
#                return
#        # Figure out which domain(s) the user should have addresses
#        # in.  Primary domain should be at the front of the resulting
#        # list.
#	# if the only address found is in EMAIL_DEFAULT_DOMAIN
#        # don't set default address. This is done in order to prevent
#        # adresses in default domain being sat as primary 
#	# TODO: account_types affiliated to OU's  without connected
#	# email domain don't get a default address
#        primary_set = False
#        ed = Email.EmailDomain(self._db)
#        ed.find(self.get_primary_maildomain())
#        domains = [ed.email_domain_name]
#	if ed.email_domain_name == cereconf.EMAIL_DEFAULT_DOMAIN:
#	    primary_set = True
#        if cereconf.EMAIL_DEFAULT_DOMAIN not in domains:
#            domains.append(cereconf.EMAIL_DEFAULT_DOMAIN)
#        # Iterate over the available domains, testing various
#        # local_parts for availability.  Set user's primary address to
#        # the first one found to be available.
#	# Never change any existing email addresses
#        try:
#            self.get_primary_mailaddress()
#	    primary_set = True
#        except Errors.NotFoundError:
#            pass
#	epat = Email.EmailPrimaryAddressTarget(self._db)
#        for domain in domains:
#            if ed.email_domain_name <> domain:
#                ed.clear()
#                ed.find_by_domain(domain)
#            # Check for 'cnaddr' category before 'uidaddr', to prefer
#            # 'cnaddr'-style primary addresses for users in
#            # maildomains that have both categories.
#            ctgs = [int(r['category']) for r in ed.get_categories()]
#            local_parts = []
#            if int(self.const.email_domain_category_cnaddr) in ctgs:
#                local_parts.append(self.get_email_cn_local_part(given_names=1, max_initials=1))
#                local_parts.append(self.account_name)
#            elif int(self.const.email_domain_category_uidaddr) in ctgs:
#                local_parts.append(self.account_name)
#	    for lp in local_parts:
#		lp = self.wash_email_local_part(lp)
#		# Is the address taken?
# 		ea.clear()
#		try:
#		    ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
#		    if ea.email_addr_target_id <> et.email_target_id:
#			# Address already exists, and points to a
#			# target not owned by this Account.
#                        continue
#		    # Address belongs to this account; make sure
#		    # there's no expire_date set on it.
#		    ea.email_addr_expire_date = None
#		except Errors.NotFoundError:
#		    # Address doesn't exist; create it.
#		    ea.populate(lp, ed.email_domain_id, et.email_target_id,
#				expire=None)
#		ea.write_db()
#                if not primary_set:
#                    epat.clear()
#                    try:
#                        epat.find(ea.email_addr_target_id)
#                        epat.populate(ea.email_addr_id)
#                    except Errors.NotFoundError:
#                        epat.clear()
#                        epat.populate(ea.email_addr_id, parent = et)
#                    epat.write_db()
#                    primary_set = True
#		self.update_email_quota()

    # TODO: check this method, may probably be done better
    def _update_email_server(self):
        est = Email.EmailServerTarget(self._db)
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        if self.is_employee():
            server_name = 'postboks'
        else:
            server_name = 'student_placeholder'
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(entity_id = self.entity_id)
        except Errors.NotFoundError:
            # Not really sure about this. it is done at UiO, but maybe it is not
            # right to make en email_target if one is not found??
            et.clear()
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        try:
            est.find_by_entity(self.entity_id)
            if est.server_id == es.entity_id:
                return est
        except:
            est.clear()
            est.populate(es.entity_id, parent = et)
            est.write_db()
        return est

#     def write_db(self):
#         try:
#             plain = self.__plaintext_password
#         except AttributeError:
#             plain = None
#         ret = self.__super.write_db()
#         if plain is not None:
#             ph = PasswordHistory.PasswordHistory(self._db)
#             ph.add_history(self, plain)
#         return ret

    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False

        
       
# def main():

#     execute = AccountUiTMixin()
#     email_list = execute.build_email_list()
#     for person in execute.person.list_persons():
#         execute.person.find(person['person_id'])
#         for accounts in execute.person.get_accounts():
#             email = execute.account_id2email_address(accounts['account_id'],email_list)
#             execute.process_mail(accounts['account_id'],"defaultmail",mail)
#         execute.person.clear()
#     attempt_commit()
# if __name__ == '__main__':
#     main()
