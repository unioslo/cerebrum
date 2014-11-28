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
import hashlib
import base64
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
from Cerebrum.modules.no.uit.DiskQuota import DiskQuota
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Utils import pgp_encrypt, Factory, prepare_string
from Cerebrum.modules.Email import EmailAddress
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
    def add_spread(self, spread):
        #
        # Pre-add checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uit' NIS domain.
        if spread == self.const.spread_ifi_nis_user \
               and int(self.const.spread_uit_nis_user) not in spreads:
            raise self._db.IntegrityError, \
                  "Can't add ifi spread to an account without uit spread."

        # Gather information on present state, to be used later.  Note
        # that this information gathering must be done before we pass
        # control to our superclass(es), as the superclass methods
        # might change the state.
        #
        # exchange-relatert-jazz
        # this code (up to and including 'pass') may be removed
        # after Exchange roll-out, as it has been decided that all
        # new mail-boxes will be created in Exchange and any old 
        # mailboxes restored to Exchange
        # Jazz (2013-11)
        state = {}
        if spread == self.const.spread_uit_imap:
            # exchange-relatert-jazz
            # no account should have both IMAP and Exchange spread at the
            # same time, as this will create a double mailbox
            if self.has_spread(self.const.spread_exchange_account):
                raise self._db.IntegrityError, \
                    "Can't add IMAP-spread to an account with Exchange-spread."
            # Is this account already associated with an Cyrus
            # EmailTarget?
            et = Email.EmailTarget(self._db)
            try:
                et.find_by_target_entity(self.entity_id)
                if et.email_server_id:
                    state['email_server_id'] = et.email_server_id
            except Errors.NotFoundError:
                pass

        if spread == self.const.spread_exchange_account:
            # no account should have both IMAP and Exchange spread at the
            # same time, as this will create a double mailbox
            if self.has_spread(self.const.spread_uit_imap):
                raise self._db.IntegrityError, \
                    "Can't add Exchange-spread to an account with IMAP-spread."
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)
        #
        # Additional post-add magic
        #
        # exchange-relatert-jazz
        if spread == self.const.spread_exchange_account:
            # exchange-relatert-jazz
            es = Email.EmailServer(self._db)
            es.clear()
            # we could probably define a cereconf var to hold this
            # default (dummy) server value, but I hope that, since it
            # is not actually used in Exchange, the whole
            # server-reference may de removed from EmailTarget after
            # migration to Exchange is completed (it should be done,
            # no matter if Baardj says differently :-)). Jazz (2013-11)
            es.find_by_name('mail')
            # Check if the account already is associated with an
            # EmailTarget. If so, we are most likely looking at an
            # account restore (or else an anomaly in the cerebrum-db)
            # We should keep the EmailTarget, but make sure that
            # target_type is refreshed to "account" and target_server
            # is refreshed to dummy-exchange server. We are, at this
            # point, not interessted in any target-data.
            et = Email.EmailTarget(self._db)
            try:
                et.find_by_target_entity(self.entity_id)
                et.email_server_id = es.entity_id
                et.email_target_type =  self.const.email_target_account
                # We store a bit of state. Need to do this to know if we should
                # mangle filters
                is_new = False
            except Errors.NotFoundError:
                # No EmailTarget found for account, creating one
                # after the migration to Exchange is completed this
                # part may be done by update_email_addresses,
                # but since we need to support both exchange and
                # imap for a while, it's easiest to create the 
                # target manually
                et.populate(self.const.email_target_account,
                            self.entity_id,
                            self.const.entity_account,
                            server_id=es.entity_id)
                # We store a bit of state. Need to do this to know if we should
                # mangle filters
                is_new = True
            et.write_db()   
            self.update_email_quota(force=True, 
                                    spread=self.const.spread_exchange_account)
            # register default spam and filter settings
            self._UiT_default_spam_settings(et)
            if is_new:
                self._UiT_default_filter_settings(et)
            # The user's email target is now associated with an email
            # server, try generating email addresses connected to the
            # target.
            self.update_email_addresses()
        # exchange-relatert-jazz
        # this code (up to and including 'update_email_addresse') 
        # may be removed after Exchange roll-out, as it has been 
        # decided that all new mail-boxes will be created in Exchange
        # and any old mailboxes restored to Exchange
        # Jazz (2013-11)
        if spread == self.const.spread_uit_imap:
            # Unless this account already has been associated with an
            # Cyrus EmailTarget, we need to do so.
            if et.email_server_id:
                old_server = et.email_server_id
            et = self._UiT_update_email_server(self.const.email_server_type_cyrus)
            # Make sure that Cyrus is told about the quota, the
            # previous call probably didn't change the database value
            # and therefore didn't add a request.
            # this is not very good, we should do something about
            # update_email_quota not using order_cyrus_action and
            # order_cyrus_action in general.
            self.update_email_quota(force=True)
            # register default spam and filter settings
            self._UiT_default_spam_settings(et)
            self._UiT_default_filter_settings(et)
            # The user's email target is now associated with an email
            # server; try generating email addresses connected to the
            # target.
            self.update_email_addresses()
        elif spread == self.const.spread_ifi_nis_user:
            # Add an account_home entry pointing to the same disk as
            # the uit spread
            try:
                tmp = self.get_home(self.const.spread_uit_nis_user)
                self.set_home(spread, tmp['homedir_id'])
            except Errors.NotFoundError:
                pass  # User has no homedir for this spread yet
        elif spread == self.const.spread_uit_notes_account:
            if self.owner_type == self.const.entity_group:
                raise self._db.IntegrityError, \
                      "Cannot add Notes-spread to a non-personal account."
        return ret
    
    # exchange-relatert-jazz
    # added a check for reservation from electronic listing
    def owner_has_e_reservation(self):
        # this method may be applied to any Cerebrum-instances that
        # use trait_public_reservation
        person = Factory.get('Person')(self._db)
        try:
            person.find(self.owner_id)
        except Errors.NotFoundError:
            # no reservation may exist unless account is owned by a
            # person-object 
            return False
        return person.has_e_reservation()


    def is_employee(self):
        for r in self.get_account_types():
            if r['affiliation'] == self.const.affiliation_ansatt:
                return True
        return False
    
    def wants_auth_type(self, method):
        if method == self.const.Authentication("PGP-guest_acc"):
            # only store this type for guest accounts
            return self.get_trait(self.const.trait_uit_guest_owner) is not None
        return self.__super.wants_auth_type(method)

    def clear_home(self, spread):
        """Remove disk quota before clearing home."""

        try:
            homeinfo = self.get_home(spread)
        except Errors.NotFoundError:
            pass
        else:
            dq = DiskQuota(self._db)
            dq.clear(homeinfo['homedir_id'])
        return self.__super.clear_home(spread)

    def _clear_homedir(self, homedir_id):
        # Since disk_quota has a FK to homedir, we need this override
        dq = DiskQuota(self._db)
        dq.clear(homedir_id)
        return self.__super._clear_homedir(homedir_id)

    def set_homedir(self, *args, **kw):
        """Remove quota information when the user is moved to a disk
        without quotas or where the default quota is larger than his
        existing explicit quota."""
        
        ret = self.__super.set_homedir(*args, **kw)
        if kw.get('current_id') and kw.get('disk_id'):
            disk = Factory.get("Disk")(self._db)
            disk.find(kw['disk_id'])
            def_quota = disk.get_default_quota()
            dq = DiskQuota(self._db)
            try:
                info = dq.get_quota(kw['current_id'])
            except Errors.NotFoundError:
                pass
            else:
                if def_quota is False:
                    # No quota on new disk, so remove the quota information.
                    dq.clear(kw['current_id'])
                elif def_quota is None:
                    # No default quota, so keep the quota information.
                    pass
                else:
                    if (info['override_expiration'] and
                        DateTime.now() < info['override_expiration']):
                        old_quota = info['override_quota']
                    else:
                        old_quota = info['quota']
                    if old_quota <= def_quota:
                        dq.clear(kw['current_id'])
        return ret

    #
    # Override username generator in core Account.py
    # Do it the UiT way!
    #
    def suggest_unames(self, ssn, fname, lname):
        full_name = "%s %s" % (fname, lname)
        username = self.get_uit_uname(ssn,full_name)
        return username


    def encrypt_password(self, method, plaintext, salt=None):
        """
        Support UiT added encryption methods, for other methods call super()
        """

        if method == self.const.auth_type_md5_crypt_hex:
            return self.enc_auth_type_md5_crypt_hex(plaintext)
        elif method == self.const.auth_type_md5_b64:
            return self.enc_auth_type_md5_b64(plaintext)
        return self.__super.encrypt_password(method, plaintext, salt=salt)


    def decrypt_password(self, method, cryptstring):
        """
        Support UiT added encryption methods, for other methods call super()
        """
        if method in (self.const.auth_type_md5_crypt_hex,
                      self.const.auth_type_md5_b64):
            raise NotImplementedError, "Cant decrypt %s" % method
        return self.__super.decrypt_password(method, cryptstring)


    def verify_password(self, method, plaintext, cryptstring):
        """
        Support UiT added encryption methods, for other methods call super()
        """
        if method in ( self.const.auth_type_md5_crypt_hex,
                       self.const.auth_type_md5_b64):
            raise NotImplementedError, "Verification for %s not implemened yet" % method
        return self.__super.verify_password(method, plaintext, cryptstring)

    
    #UIT: added encryption method
    # Added by: kennethj 20050803
    def enc_auth_type_md5_crypt_hex(self,plaintext,salt = None):
        plaintext = plaintext.rstrip("\n")
        m = hashlib.md5()
        m.update(plaintext)
        encrypted = m.hexdigest()
        #print "plaintext %s = %s" % (plaintext,encrypted)
        return encrypted


    #UIT: added encryption method
    # Added by: kennethj 20050803
    def enc_auth_type_md5_b64(self,plaintext,salt = None):
        m = hashlib.md5()
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
        path_prefix = cereconf.UIT_DEFAULT_HOMEPATH_PREFIX
        account_name = self.account_name
        new_path = ('%s/%s/%s/%s') % (path_prefix,account_name[0],account_name[0:2],account_name)
        #print "Try setting %s as home path for account '%s' spread='%d'" % (new_path,account_name,spread)
        create_new = False
        new_id = None
        try:
            old_home=self.get_home(spread)
        except Errors.NotFoundError:
            #create new home
            #print "No home for this spread, create!"
            h_id = self.set_homedir(home=new_path,status=self.const.home_status_not_created)
            self.set_home(spread,h_id)
        else:
            old_path = old_home['home']
            old_id = old_home['homedir_id']
            if old_path != new_path:
                # update needed for this spread!
                print "old home (%s) not equal to new (%s), update homedir entry" % (old_path,new_path)                
                self.set_homedir(current_id=old_id,home=new_path)
            else:
                pass
                #print "no update needed"

        #print "Finish"
            


    def get_uit_uname(self,fnr,name,Regime=None):
        """ UiT function that generates a username.
        It checks our legacy_users table for entries from our legacy systems
        
        Input:
        fnr=Norwegian Fødselsnr, 11 digits
        name=Name of the person we are generating a username for
        Regime=Optional

        Returns:
        a username on the form 'abc012' <three letters><tree digits>


        When we get here we know that this person does not have any account
        in BAS from before! That is someone else's responibility, sp no need
        to check for that.

        We must check:
        legacy_user => any entries where ssn matches fnr param?
          yes:
            if one or more usernames
              use first that matches username format
              if none matches username
                format genereate new
            else genereate new username            
          no:
            generate new username,

        """
        # assume not found in 
        create_new = True

        if Regime=="ADMIN":
            cstart=999
            step=-1
            legacy_type='SYS'
        else:
            cstart=0
            step=1
            legacy_type='P'
            
        legacy_sql = """
        SELECT user_name FROM [:table schema=cerebrum name=legacy_users]
        WHERE ssn=:ssn and type=:type
        ORDER BY source,user_name
        """
        legacy_binds = { 'ssn': fnr,
                         'type': legacy_type}

        legacy_data=self._db.query(legacy_sql,legacy_binds)

        new_ac=Factory.get('Account')(self._db)
        p = Factory.get('Person')(self._db)
        try:
            p.find_by_external_id(self.const.externalid_fodselsnr,fnr)
        except Errors.NotFoundError:
            try:
                p.find_by_external_id(self.const.externalid_sys_x_id,fnr)
            except Errors.NotFoundError:
                raise Errors.ProgrammingError("Trying to create account for person:%s that does not exist!" % fnr)
            else:
                person_id = p.entity_id

        except Exception,m:
            print m
            raise Errors.ProgrammingError("Unhandled exception: %s",str(m))
        else:
            person_id = p.entity_id

        person_accounts = self.list_accounts_by_owner_id(person_id,filter_expired=False)
        
        
        # regexp for checking username format
        p=re.compile('^[a-z]{3}[0-9]{3}$')

        for legacy_row in legacy_data:
            legacy_username=legacy_row['user_name']            
            if not p.match(legacy_username):
                # legacy username not in <three letters><three digits> format
                #print "Found UNusable legacy username: '%s', skipping" % (legacy_username)
                continue

            # valid username found in legacy for this ssn
            # check that its not already used in BAS!
            new_ac.clear()
            try:
                cb_acc=new_ac.find_by_name(legacy_username)
            except Errors.NotFoundError:
                # legacy username not found in BAS.
                #print "Legacy '%s' found, and free. using..." % (legacy_username)
                username = legacy_username
                create_new=False
                break
            else:
                # legacy_username tied to fnr already used in BAS. We have an error situation!
                if new_ac.owner_id==person_id:
                    #and used by same person
                    raise Errors.ProgrammingError("Person %s already has account %s in BAS!" %(fnr,new_ac.account_name))
                else:
                    #and used by another person!
                    raise Errors.IntegrityError("Legacy account %s not owned by person %s in BAS!" (legacy_username,fnr))
             
        if create_new:
            # getting here implies that  person does not have a previous account in BAS
            # create a new username
            inits = self.get_uit_inits(name)
            if inits == 0:
                return inits
            new_username = self.get_serial(inits,cstart,step=step)
            username=new_username
            
        return username



    def get_uit_uname_old(self,fnr,name,Regime=None):
        ssn = fnr
        step=1
        if Regime == None:
            cstart=22
            query = "select user_name from legacy_users where ssn='%s' and source <>'AD' and type='P'" % (ssn)
        elif Regime == "ONE":
            cstart=0
            query = "select user_name from legacy_users where ssn='%s' and type='P'" % (ssn)
        elif Regime == "ADMIN":
            cstart=999
            step = -1
            query = "select user_name from legacy_users where ssn='%s' and type='SYS'" % (ssn)
        else:
            cstart=0
            query = "select user_name from legacy_users where ssn='%s' and source ='AD' and type='P'" % (ssn)
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
            for row3 in db_row:
                username = row3['user_name']
                query = "select entity_id from entity_name where entity_name='%s'" % (username)
                db_row2 = db.query(query)
                if((len(db_row2) ==0) and (not username.isalpha())):
                    #print "registered username %s for %s is free. returning this" % (ssn,username)
                    return username

        # getting here means either that:
        # 1. the person does not have a previous account
        # 2. the persons username is already taken, and a new has to be created
        inits = self.get_uit_inits(name)
        if inits == 0:
            return inits
        new_username = self.get_serial(inits,cstart,step=step)
        #print "no legacy usernames for %s were free. created new %s" % (ssn,new_username)
        return new_username



    def get_serial(self,inits,cstart,step=1):

        found = False
        db = self._db
        ac = Factory.get('Account')(db)
        while ((not found) and (cstart <= 999) and (cstart >=0)):
            # xxx999 is reserved for admin use
            uname = "%s%03d" % (inits, cstart)
            ac.clear()
            query = "select * from entity_name where entity_name='%s'" % uname
            db_row = db.query(query)
            query2 = "select * from legacy_users where user_name='%s'" % uname
            db_row2 = db.query(query2)

            if((len(db_row) != 0) or (len(db_row2) != 0)):
                cstart += step
            else:
                found = True

        if (not found):
            #did not find free serial...
            print "CRITICAL: Unable to find serial: inits=%s,cstart=%d,step=%d" % (inits,cstart,step)
            sys.exit(1)
                
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


    def list_all(self, spread=None,filter_expired=False):
 
        """List all users,  optionally filtering the
        results on account spread and expiry.
        """

        where = ["en.entity_id=ai.account_id"]
        tables = ['[:table schema=cerebrum name=entity_name] en']
        params = {}
        if spread is not None:
            # Add this table before account_info for correct left-join syntax
            where.append("es.entity_id=ai.account_id")
            where.append("es.spread=:account_spread")
            tables.append(", [:table schema=cerebrum name=entity_spread] es")
            params['account_spread'] = spread
            
        tables.append(', [:table schema=cerebrum name=account_info] ai')
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        where = " AND ".join(where)
        tables = "\n".join(tables)
        
        sql =  """
        SELECT ai.account_id, en.entity_name, ai.expire_date, ai.create_date
        FROM %s
        WHERE %s""" % (tables, where)
        
        return self.query(sql, params)
        
    def getdict_accid2mailaddr(self, filter_expired=True):
        ret = {}
        target_type = int(self.const.email_target_account)
        namespace = int(self.const.account_namespace)
        ed = Email.EmailDomain(self._db)
        where = "en.value_domain = :namespace"
        if filter_expired:
            where += " AND (ai.expire_date IS NULL OR ai.expire_date > [:now])"
        for row in self.query("""
        SELECT en.entity_id, ea.local_part, ed.domain
        FROM [:table schema=cerebrum name=account_info] ai
        JOIN [:table schema=cerebrum name=entity_name] en
          ON en.entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_target] et
          ON et.target_type = :targ_type AND
             et.target_entity_id = ai.account_id
        JOIN [:table schema=cerebrum name=email_primary_address] epa
          ON epa.target_id = et.target_id
        JOIN [:table schema=cerebrum name=email_address] ea
          ON ea.address_id = epa.address_id
        JOIN [:table schema=cerebrum name=email_domain] ed
          ON ed.domain_id = ea.domain_id
        WHERE """ + where,
                              {'targ_type': target_type,
                               'namespace': namespace}):
            ret[row['entity_id']] = '@'.join((
                row['local_part'],
                ed.rewrite_special_domains(row['domain'])))
        return ret


    # TODO: check this method, may probably be done better
    def _update_email_server(self):
        es = Email.EmailServer(self._db)
        et = Email.EmailTarget(self._db)
        if self.is_employee():
            server_name = 'postboks'
        else:
            server_name = 'student_placeholder'
        es.find_by_name(server_name)
        try:
            et.find_by_email_target_attrs(target_entity_id = self.entity_id)
        except Errors.NotFoundError:
            et.populate(self.const.email_target_account,
                        self.entity_id,
                        self.const.entity_account)
            et.write_db()
        if not et.email_server_id:
            et.email_server_id = es.entity_id
            et.write_db()
        return et

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


    def write_legacy_user(self,user_name,ssn=None,source=None, 
                    type=None,comment=None,name=None):
        """
        Insert or update legacy user info in our legacy_users table
        
        @param user_name: Legacy username. Required.
        @type user_name: String. 
        
        @param ssn: A norwegian ssn. No validation is done on this.
        @type ssn: String. 
        
        @param source: Describes legacy system user_name comes from 
        @type ssn: String. 
        
        @param type: What type is this legacy name. Examples. P for personal, 
            SYS for system account.
        @type ssn: String. 
        
        @param comment: A description of this entry
        @type ssn: String. 
        
        @param name: Name of owner.
        @type ssn: String. 
        """

        if not user_name:
            raise Errors.ProgrammingError,"user_name parameter cannot be empty"

        params=dict()
        values=list()
        if ssn:
            values.append('ssn')
            params['ssn']=ssn
        if source:
            values.append('source')
            params['source']=source
        if type:
            values.append('type')
            params['type']=type
        if comment:
            values.append('comment')
            params['comment']=comment
        if name:
            values.append('name')
            params['name']=name
        
        legacy=self.search_legacy(user_name=user_name)
        if legacy:
            valuelist=list()
            for attr in values:
                valuelist.append("%s=:%s"%(attr,attr))
            qry = """
            UPDATE [:table schema=cerebrum name=legacy_users]
            SET %s
            WHERE user_name=:user_name
            """ % (','.join(valuelist))
        else:
            values.append('user_name')
            valuelist=','.join(values)
            paramlist=list()
            for attr in values:
                paramlist.append(":%s"%attr)
            qry = """
            INSERT INTO [:table schema=cerebrum name=legacy_users]
            (%s) 
            VALUES (%s)
            """ % (','.join(values),','.join(paramlist))
            
        params['user_name']=user_name
        self.execute(qry,params)


    # exchange-related-jazz
    def delete_spread(self, spread):
        #
        # Pre-remove checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        if not spread in spreads:  # user doesn't have this spread
            return
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uit' NIS domain.
        if spread == self.const.spread_uit_nis_user \
               and int(self.const.spread_ifi_nis_user) in spreads:
            raise self._db.IntegrityError, \
                  "Can't remove uit spread to an account with ifi spread."

        if spread == self.const.spread_ifi_nis_user \
               or spread == self.const.spread_uit_nis_user:
            self.clear_home(spread)

        # Remove IMAP user
        # TBD: It is currently a bit uncertain who and when we should
        # allow this.  Currently it should only be used when deleting
        # a user.
        # exchange-related-jazz
        # this code, up to and including the TBD should be removed
        # when migration to Exchange is completed as it wil no longer
        # be needed. Jazz (2013-11)
        # 
        if (spread == self.const.spread_uit_imap and
            int(self.const.spread_uit_imap) in spreads):
            et = Email.EmailTarget(self._db)
            et.find_by_target_entity(self.entity_id)
            self._UiT_order_cyrus_action(self.const.bofh_email_delete,
                                         et.email_server_id)
            # TBD: should we also perform a "cascade delete" from EmailTarget?
        # exchange-relatert-jazz
        # Due to the way Exchange is updated we no longer need to
        # register a delete request in Cerebrum. Setting target_type
        # to deleted should generate an appropriate event which then
        # may be used to remove the mailbox from Exchange in the
        # agreed maner (export to .pst-file, then remove-mailbox). A
        # clean-up job should probably be implemented to remove
        # email_targets that have had status deleted for a period of
        # time. This will however remove the e-mailaddresses assigned
        # to the target and make their re-use possible. Jazz (2013-11)
        # 
        if spread == self.const.spread_uit_exchange:
            et = Email.EmailTarget(self._db)
            et.find_by_target_entity(self.entity_id)
            et.email_target_type = self.const.email_target_deleted
            et.write_db()
        # (Try to) perform the actual spread removal.
        ret = self.__super.delete_spread(spread)
        return ret

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules.PosixUser import PosixUser

        if isinstance(self, PosixUser):
            # TODO: Kill the ARsystem user to limit range og legal characters
            if len(name) > 16:
                return "too long (%s)" % name
            if re.search("^[^A-Za-z]", name):
                return "must start with a character (%s)" % name
            if re.search("[^A-Za-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return False


    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        # TBD: will domain ever be anything else?
        if domain == self.const.account_namespace:
            ea = Email.EmailAddress(self._db)
            for row in ea.search(local_part=uname, filter_expired=False):
                return False
        return self.__super.validate_new_uname(domain, uname)


    def delete_legacy_user(self,user_name):
        """
        Delete a user from our legacy user table
        
        @param user_name: Name of legacy account to delete. 
        @type user_name: String.
        """
        if not user_name:
            raise Errors.ProgrammingError,"user_name parameter cannot be empty"

        self.execute("""DELETE FROM [:table schema=cerebrum name=legacy_users]
        WHERE user_name=:user_name""",{'user_name':user_name})        

        
    def search_legacy(self,user_name=None,ssn=None,source=None,
                           type=None,comment=None,name=None):  
        """
        Search for infomations from our legacy table
        Comment and Name may contain wild-cards. Other parameters
        are tested for equality.
        
        @param user_name: Legacy username
        @type user_name: String. 
        
        @param ssn: A norwegian ssn.
        @type ssn: String. 
        
        @param source: Describe where it comes from 
        @type ssn: String. 
        
        @param type: What type is it
        @type ssn: String. 
        
        @param comment:A description of this entry
        @type ssn: String. 
        
        @param name: Name of owner 
        @type ssn: String. 
        
        """
        filter=[]
        params=dict()
    
        if user_name:
            filter.append('user_name=:user_name')
            params['user_name']=user_name        
        if ssn:
            filter.append('ssn=:ssn')
            params['ssn']=ssn
        if source:
            filter.append('source=:source')
            params['source']=source
        if type:
            filter.append('type=:type')
            params['type']=type
        if comment:
            comment = prepare_string(comment, None)
            filter.append('comment like :comment')
            params['comment']=comment
        if name:
            name = prepare_string(name, None)
            filter.append('name like :name')
            params['name']=name
    
        where=""
        if filter:
            where="WHERE %s" % (" AND ".join(filter))
            
        qry="""
        SELECT user_name,ssn,source,type,comment,name 
        FROM [:table schema=cerebrum name=legacy_users]
        %s
        """ % where
        return(self.query(qry,params))
        
