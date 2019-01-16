#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from __future__ import unicode_literals


import random
import sys
import re
import string
import crypt

# UIT imports
# added by: kennethj 20050308
import hashlib
import base64
import mx               # kbj005: is this needed?
import traceback        # kbj005: is this needed?
# UIT end


import cerebrum_path
import cereconf
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.utils import transliterate
from Cerebrum import Utils
from Cerebrum.Utils import NotSet
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Utils import pgp_encrypt, Factory, prepare_string
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
    som kj�res. den kaller opp foreldrenes write_db. de kaller igjen opp
    sine foreldre(grunnet self.__super.write_db()) til
    man til slutt kaller Account sin write_db(). n�r den returnerer s�
    fortsetter metodene der de kallte super()
    Man har bare en write_db() i
    hele Account etter at man har inkludert Mixins, men man f�r tak i
    foreldrene ved � bruke super()


    """

    #
    # UiO has discontinued this function in cerebrum. copied their now-deleted version
    # into our Account.py
    #
    _simplify_name_cache = [None] * 4

    def simplify_name(self, s, alt=0, as_gecos=0):
        """Convert string so that it only contains characters that are
        legal in a posix username.  If as_gecos=1, it may also be
        used for the gecos field"""
        key = bool(alt) + (bool(as_gecos) * 2)
        try:
            (tr, xlate_subst, xlate_match) = self._simplify_name_cache[key]
        except TypeError:
            xlate = {'�': 'Dh', '�': 'dh',
                     '�': 'Th', '�': 'th',
                     '�': 'ss'}
            if alt:
                xlate.update({'�': 'ae', '�': 'ae',
                              '�': 'aa', '�': 'aa'})
            xlate_subst = re.compile(r'[^a-zA-Z0-9 -]').sub

            def xlate_match(match):
                return xlate.get(match.group(), "")
            tr = dict(zip(map(chr, xrange(0200, 0400)), ('x',) * 0200))
            tr.update(dict(zip(
                '����������������������������������������������������������'
                '{[}]|�\\����',
                'AOAaooaAAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuuyy'
                'aAaAooO"--\'')))
            for ch in filter(tr.has_key, xlate):
                del tr[ch]
            tr = string.maketrans("".join(tr.keys()), "".join(tr.values()))
            if not as_gecos:
                # lowercase the result
                tr = tr.lower()
                xlate = dict(zip(xlate.keys(), map(str.lower, xlate.values())))
            self._simplify_name_cache[key] = (tr, xlate_subst, xlate_match)

        xlated = xlate_subst(xlate_match, s.translate(tr))

        # normalise whitespace and hyphens: only ordinary SPC, only
        # one of them between words, and none leading or trailing.
        xlated = re.sub(r'\s+', " ", xlated)
        xlated = re.sub(r' ?-+ ?', "-", xlated).strip(" -")
        return xlated



    #
    # SITO accounts will have their own namespace as describe here
    #
    # sit� username will be on the following format:S-XXXNNN
    #
    # S = The letter S
    # XXX = letters generated based on fname and lname
    # NNN = unique numeric identifier
    #
    def suggest_unames_sito(self,ssn,fname,lname):
        full_name = "%s %s" % (fname, lname)
        sito_username = self.get_sito_uname(ssn,full_name)
        return sito_username


    #
    # Override username generator in core Account.py
    # Do it the UiT way!
    #
    def suggest_unames(self, ssn, fname, lname):
        full_name = "%s %s" % (fname, lname)
        username = self.get_uit_uname(ssn,full_name)
        return [username]



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


    def verify_password_old(self, method, plaintext, cryptstring):
        """
        Support UiT added encryption methods, for other methods call super()
        """
        if method in ( self.const.auth_type_md5_crypt_hex,
                       self.const.auth_type_md5_b64):
            raise NotImplementedError, "Verification for %s not implemened yet" % method
        return self.__super.verify_password(method, plaintext, cryptstring)

    def verify_password(self, method, plaintext, cryptstring):
        """Returns True if the plaintext matches the cryptstring,
        False if it doesn't.  If the method doesn't support
        verification, NotImplemented is returned.
        """
        self.logger.warn("method:%s, cryptstring:%s" % (method,cryptstring))
        if method in (self.const.auth_type_md5_crypt,
                      self.const.auth_type_md5_b64,
                      self.const.auth_type_ha1_md5,
                      self.const.auth_type_crypt3_des,
                      self.const.auth_type_md4_nt,
                      self.const.auth_type_ssha,
                      self.const.auth_type_sha256_crypt,
                      self.const.auth_type_sha512_crypt,
                      self.const.auth_type_plaintext):
            salt = cryptstring
            if method == self.const.auth_type_ssha:
                salt = base64.decodestring(cryptstring)[20:]
            """ return (self.encrypt_password(method, plaintext, salt=salt) ==
                    cryptstring or self.encrypt_password(method, plaintext,
                                                         salt=salt,
                                                         binary=True) ==
                    cryptstring) """
            return (self.encrypt_password(method, plaintext, salt=salt) == cryptstring)
        raise ValueError("Unknown method %r" % method)

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
        self.logger.warning('plaintext is:%s' % plaintext)
        m = hashlib.md5()
        m.update(plaintext.encode('utf-8'))
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
            

    #
    # Create sito usernames
    #
    def get_sito_uname(self,fnr,name,Regime=None):
        create_new = True
        cstart=0
        step=1
        legacy_type='P'
        

        new_ac=Factory.get('Account')(self._db)
        p = Factory.get('Person')(self._db)
        try:
            p.find_by_external_id(self.const.externalid_fodselsnr,fnr)
        except Errors.NotFoundError:
            logger.warning("sito person is missing fnr. Account not created")
            raise Errors.ProgrammingError("Trying to create account for person:%s that does not exist!" % fnr)

        except Exception,m:
            print m
            raise Errors.ProgrammingError("Unhandled exception: %s",str(m))
        else:
            person_id = p.entity_id

        person_accounts = self.list_accounts_by_owner_id(person_id,filter_expired=False)
        
        
        # regexp for checking username format
        p=re.compile('^[a-z]{3}[0-9]{3}-s$')
             

        # getting here implies that  person does not have a previous account in BAS
        # create a new username
        inits = self.get_uit_inits(name)
        if inits == 0:
            return inits
        #new_username = self.get_serial(inits,cstart,step=step,postfix='-s')
        new_username = self.get_serial(inits,cstart,step=step,postfix=cereconf.USERNAME_POSTFIX['sito'])
        username="%s" %(new_username,)
        
        return username


    def get_uit_uname(self,fnr,name,Regime=None):
        """ UiT function that generates a username.
        It checks our legacy_users table for entries from our legacy systems
        
        Input:
        fnr=Norwegian F�dselsnr, 11 digits
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
                    #raise Errors.IntegrityError("Legacy account %s not owned by person %s in BAS!" (legacy_username,fnr))
                    self.logger.warn("Legacy account %s not owned by person %s in BAS, continue with next (if any) legacy username" %(legacy_username,fnr))
                    continue
             
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



    def get_serial(self,inits,cstart,step=1,postfix=None):

        found = False
        db = self._db
        ac = Factory.get('Account')(db)
        while ((not found) and (cstart <= 999) and (cstart >=0)):
            # xxx999 is reserved for admin use

            if(postfix != None):
                uname = "%s%03d%s" % (inits, cstart,postfix)
            else:
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
       dname = transliterate.for_posix(dname)
      
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


    def list_all(self, spread=None,filter_expired=False):

        """List all users,  optionally filtering the
        results on account spread and expiry.
        """

        where = ["en.entity_id=ai.account_id and en.entity_id=ei.entity_id"]
        tables = ['[:table schema=cerebrum name=entity_name] en']
        params = {}
        if spread is not None:
            # Add this table before account_info for correct left-join syntax
            where.append("es.entity_id=ai.account_id")
            where.append("es.spread=:account_spread")
            tables.append(", [:table schema=cerebrum name=entity_spread] es")
            params['account_spread'] = spread
            
        tables.append(', [:table schema=cerebrum name=account_info] ai')
        tables.append(', [:table schema=cerebrum name=entity_info] ei')
        if filter_expired:
            where.append("(ai.expire_date IS NULL OR ai.expire_date > [:now])")

        where = " AND ".join(where)
        tables = "\n".join(tables)
        
        sql =  """
        SELECT ai.account_id, en.entity_name, ai.expire_date, ei.created_at
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
        
