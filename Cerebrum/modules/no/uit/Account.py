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
        elif Regime == "ONE":
            cstart=0
            query = "select user_name from legacy_users where ssn='%s'" % (ssn)
        else:
            cstart=0
            query = "select user_name from legacy_users where ssn='%s' and source ='AD'" % (ssn)
        #print "%s" % query
        db = self._db
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
                raise Errors.IntegrityError, "ssn:%s already has an account=%s. Error trying to create a new account" % (ssn,username)

            # was unable to find any existing accounts in cerebrum for this person with the
            # username from the legacy table.
            # lets return the first user_name in legacy_users for this person, that no one alrady has.
            for row in db_row:
                username = row['user_name']
                query = "select entity_id from entity_name where entity_name='%s'" % (username)
                db_row2 = db.query(query)
                if((len(db_row2) ==0) and (not username.isalpha())):
                    #print "registered username %s for %s is free. returning this" % (ssn,username)
                    return username

        # The person has no account, or the user name registered in the legacy_table is
        # already taken by another user.
        # if we get here and regieme == AD, it means we cannot find a account in legacy
        # which can be used!  This is an consistenscy error!
        #if (Regime=='AD'):
        #    if(len(db_row)==0):
        #        raise ValueError, "AD user has no registered username in legacy user."
        #    else:
        #        raise ValueError, "AD Username: %s,fnr: %s, in legacy table is taken by another person." % (username,ssn)

        # getting here means either that:
        # 1. the person does not have a previous account
        # 2. the persons username is already taken, and a new has to be created
        inits = self.get_uit_inits(name)
        if inits == 0:
            return inits
        new_username = self.get_serial(inits,cstart)
        #print "no legacy usernames for %s were free. created new %s" % (ssn,new_username)
        return new_username



    def get_serial(self,inits,cstart):

        foo = ""
        found = False
        db = self._db
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

       
       #sanity check
       p = re.compile('^[a-z]{3}$')
       if (p.match(inits)):
           return inits
       else:
           print "Sanity check failed: Returning %s for %s" % (inits,orgname)
           raise ValueError("ProgrammingError: A Non ascii-letter in uname!: '%s'" % inits)


    def set_password(self, plaintext):
        # Override Account.set_password so that we get a copy of the
        # plaintext password. To be used in self.write_db() when/if we implement password history
        self.__plaintext_password = plaintext
        self.__super.set_password(plaintext)



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

    def write_db(self):
        try:
            plain = self.__plaintext_password
        except AttributeError:
            plain = None
        ret = self.__super.write_db()
        if plain is not None:
            # uncomment these two when/if we want password history        
            #ph = PasswordHistory.PasswordHistory(self._db)
            #ph.add_history(self, plain)
            pass
        return ret


    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False


# arch-tag: 8379aa52-b4f2-11da-9493-e299b169bb25
