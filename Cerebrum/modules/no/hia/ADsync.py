
#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006, 2007 University of Oslo, Norway
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

"""
Replces functions in ADutilMixIn.py that has to be modiifed for
use at ADsync at UiA.

"""


import sys
import cereconf
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Utils
from Cerebrum import QuarantineHandler
from Cerebrum.modules import ADutilMixIn
from Cerebrum import Errors
import cPickle


class ADFullUserSync(ADutilMixIn.ADuserUtil):

    def _filter_quarantines(self, user_dict):
        """
        Filter quarantined accounts

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        def apply_quarantines(entity_id, quarantines):
            q_types = []
            for q in quarantines:
                q_types.append(q['quarantine_type'])
            if not user_dict.has_key(entity_id):
                return
            qh = QuarantineHandler.QuarantineHandler(self.db, q_types)
            if qh.should_skip():
                del(user_dict[entity_id])
            if qh.is_locked():
                user_dict[entity_id]['ACCOUNTDISABLE'] = True

        prev_user = None
        user_rows = []
        for row in self.ac.list_entity_quarantines(only_active=True):
            if prev_user != row['entity_id'] and prev_user is not None:
                apply_quarantines(prev_user, user_rows)
                user_rows = [row]
            else:
                user_rows.append(row)
            prev_user = row['entity_id']
        else:
            if user_rows:
                apply_quarantines(prev_user, user_rows)


    def _fetch_mail_info(self, user_dict):
        """
        Fetch primary email address and all valid addresses
        for users in user_dict.
        Add info to user_dict if found. For the AD 'mail' attribute
        add key/value pair 'mail'/<primary address>. For the
        AD 'proxyaddresses' attribute add key/value pair
        'proxyaddresses'/<list of all valid addresses>. The addresses
        in the proxyaddresses list are preceded by address type. In
        capital letters if it is the default address.

        Also write Exchange attributes for those accounts that have
        that spread.

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        from Cerebrum.modules.Email import EmailDomain, EmailTarget, EmailQuota
        etarget = EmailTarget(self.db)
        rewrite = EmailDomain(self.db).rewrite_special_domains
        equota = EmailQuota(self.db)

        #find primary address and set mail attribute
        for row in etarget.list_email_target_primary_addresses(
                target_type = self.co.email_target_account):
            v = user_dict.get(int(row['target_entity_id']))
            if not v:
                continue
            try:
                v['mail'] = "@".join(
                    (row['local_part'], rewrite(row['domain'])))
            except TypeError:
                pass  # Silently ignore
        
        #TODO: Try-cath for exceptions here?
        #Set proxyaddresses attribute
        for k,v in user_dict.items():
            etarget.clear()
            etarget.find_by_target_entity(int(k))
            v['proxyAddresses'] = []
            for r in etarget.get_addresses(special=False):
                addr = "@".join((r['local_part'], rewrite(r['domain'])))
                if addr == v['mail']:
                    v['proxyAddresses'].insert(0,("SMTP:" + addr))
                else:
                    v['proxyAddresses'].append(("smtp:" + addr))
           
        #Set homeMDB and Quota-info for Exchange users
        for k,v in user_dict.items():
            self.ac.clear()
            if v['Exchange']:
                try:
                    self.ac.find_by_name(v['TEMPuname'])
                except Errors.NotFoundError:
                    continue

                #mdb = self.ac.get_trait(self.co.trait_exchange_mdb)
                #if mdb['exchange_mdb']:
                    #v['homeMDB'] = mdb['exchange_mdb'] + "," + cereconf.AD_EX_MDB_SERVER
                #else:
                    #self.logger.warning("Error getting homeMDB for accountid: %i" % int(k))  
                #For aa ha en gyldig mailbox store paa testmiljoet:
                v['homeMDB'] = "CN=Mailbox Database,CN=First Storage Group,CN=InformationStore,CN=CB-EX-SIS-TEST,CN=Servers,CN=Exchange Administrative Group (FYDIBOHF23SPDLT),CN=Administrative Groups,CN=cb-sis-test,CN=Microsoft Exchange,CN=Services,CN=Configuration,DC=cb-sis-test,DC=intern"
                equota.clear()
                equota.find_by_target_entity(int(k))
                try:
                    q_soft = equota.get_quota_soft()
                    q_hard = equota.get_quota_hard()
                except Errors.NotFoundError:
                    self.logger.warning("Error getting EmailQuota for accountid: %i. Setting default." 
                                     % int(k))  
                #set a default quota
                if (q_soft is None or q_hard is None):
                    self.logger.warning("Error getting EmailQuota for accountid: %i. Setting default." 
                                     % int(k))
                    if q_soft is None:
                        q_soft = cereconf.AD_EX_QUOTA_SOFT_DEFAULT
                    if q_hard is None:
                        q_hard = cereconf.AD_EX_QUOTA_HARD_DEFAULT
                #Mailquota in Cerebrum is in MB, Exchange wants KB.
                #mDBStorageQuota is set to 90% of mDBOverQuotaLimit
                v['mDBOverHardQuotaLimit'] = q_hard * 1024
                v['mDBOverQuotaLimit'] = v['mDBOverHardQuotaLimit'] * q_soft // 100
                v['mDBStorageQuota'] = v['mDBOverQuotaLimit'] * 90 // 100

    
    def _get_contact_info(self, user_dict):
        """
        Get contact info: phonenumber and title. Personal title takes presedence.

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        for v in user_dict.values(): 
            self.person.clear()
            try:
                self.person.find(v['TEMPownerId'])
            except Errors.NotFoundError:
                self.logger.warning("Getting contact info: Skipping ownerid=%s,no valid account found"
                                 , v['TEMPownerId'])
                continue
            phones = self.person.get_contact_info(type=self.co.contact_phone)
            if not phones:
                v['telephoneNumber'] = ''
            else:
                v['telephoneNumber'] = phones[0]['contact_value']
            personal_title = ''
            work_title = ''
            try:
                work_title = unicode(self.person.get_name(
                        self.co.system_sap, self.co.name_work_title), 'ISO-8859-1') 
            except Errors.NotFoundError:
                pass
            try:
                personal_title = unicode(self.person.get_name(
                        self.co.system_sap,self.co.name_personal_title), 'ISO-8859-1') 
            except Errors.NotFoundError:
                pass
            if personal_title:
                v['title'] = personal_title
            elif work_title:
                v['title'] = work_title
            else:
                v['title'] = ''
                        

    def get_default_ou(self):
        """
        Return default OU for users. burde vaere i cereconf?
        """
        return "OU=Brukere,%s" % self.ad_ldap

            

    def fetch_cerebrum_data(self, spread, exchange_spread):
        """
        Fetch relevant cerebrum data for users with the given spread.
        One spread indicating export to AD, and one spread indicating
        that is should also be prepped and activated for Exchange 2007.

        @param spread: ad account spread for a domain
        @type spread: _SpreadCode
        @param exchange_spread: exchange account spread
        @type exchange_spread: _SpreadCode
        @rtype: dict
        @return: a dict {uname: {'adAttrib': 'value'}} for all users
        of relevant spread. Typical attributes::
        
          # canonicalName er et 'constructed attribute' (fra dn)
          'displayName': String,          # Fullt navn
          'givenName': String,            # fornavn
          'sn': String,                   # etternavn
          'mail': String,                 # default e-post adresse
          'Exchange' : Bool,              # Flag - skal i Exchange eller ikke 
          'msExchPoliciesExcluded' : int, # Exchange verdi
          'deliverAndRedirect' : Bool,    # Exchange verdi
          'mDBUseDefault' : Bool,         # Exchange verdi
          'msExchHideFromAddressLists' : Bool, # Exchange verdi
          'userPrincipalName' : String    # brukernavn@domene
          'telephoneNumber' : String      # tlf
          'title' : String                # tittel
          'mailNickname' : String         # brukernavn
          'targetAddress' : String        # ekstern adresse
          'mDBOverHardQuotaLimit' : int   # epostkvote
          'mDBOverQuotaLimit' : int       # epostkvote
          'mDBStorageQuota' : int         # epostkvote
          'proxyAddresses' : Array        # Alle gyldige epost adresser
          'ACCOUNTDISABLE'                # Flag, used by ADutilMixIn
        """

        self.person = Utils.Factory.get('Person')(self.db)

        #
        # Find all users with relevant spread
        #
        tmp_ret = {}
        spread_res = self.ac.search(spread=spread)
        for row in spread_res:
            tmp_ret[int(row['account_id'])] = {
                'Exchange' : False,
                'msExchPoliciesExcluded' : cereconf.AD_EX_POLICIES_EXCLUDED,
                'deliverAndRedirect' : cereconf.AD_DELIVER_AND_REDIRECT,
                'mDBUseDefault' : cereconf.AD_EX_MDB_USE_DEFAULTS,
                'msExchHideFromAddressLists' : cereconf.AD_EX_HIDE_FROM_ADDRESS_LIST,
                'TEMPownerId': row['owner_id'],
                'TEMPuname': row['name'],
                'ACCOUNTDISABLE': False
                }
        self.logger.info("Fetched %i person with spread %s" % (len(tmp_ret),spread))

        set1 = set([row['account_id'] for row in spread_res])
        set2 = set([row['account_id'] for row in self.ac.search(spread=exchange_spread)])
        set_res = set1.intersection(set2)
        ij = 0
        for row_account_id in set_res:
            tmp_ret[int(row_account_id)]['Exchange'] = True
            ij += 1
        self.logger.info("Fetched %i person with both spread %s and %s" % (ij,spread,exchange_spread))

        #
        # Remove/mark quarantined users
        #
        self._filter_quarantines(tmp_ret)

        #
        # Set person names
        #
        pid2names = {}
        for row in self.person.list_persons_name(
                source_system = self.co.system_cached,
                name_type     = [self.co.name_first,
                                 self.co.name_last]):
            pid2names.setdefault(int(row['person_id']), {})[
                int(row['name_variant'])] = row['name']
        for v in tmp_ret.values():
            names = pid2names.get(v['TEMPownerId'])
            if names:
                firstName = unicode(names.get(int(self.co.name_first), ''), 'ISO-8859-1')
                lastName = unicode(names.get(int(self.co.name_last), ''), 'ISO-8859-1')
                v['givenName'] = firstName
                v['sn'] = lastName
                v['displayName'] = "%s %s" % (firstName, lastName)
        self.logger.info("Fetched %i person names" % len(pid2names))

        #
        # Set mail info
        #
        self._fetch_mail_info(tmp_ret)
        
        #
        # Set contact info: phonenumber and title
        #
        self._get_contact_info(tmp_ret)

        #
        # Assign derived attributes
        #
        for v in tmp_ret.values():
            #TODO: derive domain part from LDAP DC components
            v['userPrincipalName'] = v['TEMPuname'] + "@uia.no"
            v['mailNickname'] =  v['TEMPuname']
            if v['Exchange'] is False:
                v['targetAddress'] = v['mail']

        #
        # Sort dict on uname instead of accountid
        #
        ret = {}
        for k, v in tmp_ret.items():
            ret[v['TEMPuname']] = v
            del(v['TEMPuname'])
            del(v['TEMPownerId'])
          
        return ret

    
    def find_Exchange_changes(self, cerebrumusers, adusers):
        """
        Check if any Exchange specific values have changed for 
        account.

        @param cerebrumusers: account_id -> account info mapping
        @type cerebrumusers: dict
        @param adusers: account_id -> account info mapping
        @type adusers: dict
        @rtype: list
        @return: a list over users with changes i the Exchange values
        """
        exch_user = []
        for usr, dta in cerebrumusers.items():
            exch_change = False
            if cerebrumusers[usr]['Exchange']:
                if adusers.has_key(usr):
                #User is both places, we want to compare for changes
                #TBD: Anymore changes values that must trigger Update-Recipient?
                    mail_attrs = ['homeMDB', 'mailNickname']
                    for mail_attr in mail_attrs:
                        if adusers[usr].has_key(mail_attr):
                            if cerebrumusers[usr][mail_attr] != \
                                    adusers[usr][mail_attr]:
                                exch_change = True
                        else:
                            exch_change = True
                else:
                    #New user
                    exch_change = True
            if exch_change:
                exch_user.append(usr)
        return exch_user
                


    def store_sid(self, objtype, name, sid):
        """
        Store AD object SID to cerebrum database for given user

        @param objtype: type of AD object
        @type objtype: String
        @param name: user name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # husk aa definere AD som kildesystem
        #TBD: Check if we create a new object for a entity that already
        #have a externalid_accountsid defined in the db and delete old?
        if objtype == 'account':
            self.ac.clear()
            self.ac.find_by_name(name)
            self.ac.affect_external_id(self.co.system_ad, self.co.externalid_accountsid)
            self.ac.populate_external_id(self.co.system_ad, self.co.externalid_accountsid, sid)
            self.ac.write_db()


    def create_object(self, chg, dry_run):
        """
        Creates AD account object and populates given attributes

        @param chg: account_id -> account info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        if chg.has_key('OU'):
            ou = chg['OU']
        else:
            ou = self.get_default_ou()
        ret = self.run_cmd('createObject', dry_run, 'User', ou,
                              chg['sAMAccountName'])
        if not ret[0]:
            self.logger.warning("create user %s failed: %r" % \
                           (chg['sAMAccountName'], ret))
        else:
            if not dry_run:
                self.logger.info("created user %s" % ret)
                self.store_sid('account',chg['sAMAccountName'],ret[2])
            pw = unicode(self.ac.make_passwd(chg['sAMAccountName']),
                         'iso-8859-1')
            ret = self.run_cmd('setPassword', dry_run, pw)
            if not ret[0]:
                self.logger.warning("setPassword on %s failed: %s" % \
                               (chg['sAMAccountName'], ret))
            else:
                #Important not to enable a new account if setPassword
                #fail, it will have a blank password.
                uname = ""
                del chg['type']
                if chg.has_key('distinguishedName'):
                    del chg['distinguishedName']
                if chg.has_key('sAMAccountName'):
                    uname = chg['sAMAccountName']       
                    del chg['sAMAccountName']               
                #Setting default for undefined AD_ACCOUNT_CONTROL values.
                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if not chg.has_key(acc):
                        chg[acc] = value                
                ret = self.run_cmd('putProperties', dry_run, chg)
                if not ret[0]:
                    self.logger.warning("putproperties on %s failed: %r" % \
                                   (uname, ret))
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r",uname, ret)


    
    def compare(self, delete_users,cerebrumusrs,adusrs):
        """
        Check if any values for account need be updated in AD

        @param cerebrumusers: account_id -> account info mapping
        @type cerebrumusers: dict
        @param adusers: account_id -> account info mapping
        @type adusers: dict
        @param delete_users: Delete or move unwanted users
        @type delete_users: Flag
        @rtype: list
        @return: a list over dicts with changes to AD objects
        """
        #Keys in dict from cerebrum must match fields to be populated in AD.

        changelist = []     

        for usr, dta in adusrs.items():
            changes = {}        
            if cerebrumusrs.has_key(usr):
                #User is both places, we want to check correct data.

                #Checking for correct OU.
                if cerebrumusrs[usr].has_key('OU'):
                    ou = cerebrumusrs[usr]['OU']
                else:
                    tmp = self.get_default_ou()
                    ou = tmp
                if adusrs[usr]['distinguishedName'] != 'CN=%s,%s' % (usr,ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                                adusrs[usr]['distinguishedName']
                    #Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                for attr in cereconf.AD_ATTRIBUTES:            
                    #Catching special cases.
                    #Check against home drive.
                    if attr == 'homeDrive':
                        home_drive = self.get_home_drive(cerebrumusrs[usr])         
                        if adusrs[usr].has_key('homeDrive'):
                            if adusrs[usr]['homeDrive'] != home_drive:
                                changes['homeDrive'] = home_drive
                    # xmlrpclib appends chars [' and '] to this attribute for some reason
                    elif attr == 'msExchPoliciesExcluded':
                        if adusrs[usr].has_key('msExchPoliciesExcluded'):
                            tempstring = str(adusrs[usr]\
                                                 ['msExchPoliciesExcluded']).replace("['","")
                            tempstring = tempstring.replace("']","")
                            if  tempstring == cerebrumusrs[usr]['msExchPoliciesExcluded']:
                                pass
                            else:
                                changes['msExchPoliciesExcluded'] = \
                                    cerebrumusrs[usr]['msExchPoliciesExcluded']
                        else:
                            changes['msExchPoliciesExcluded'] = \
                                cerebrumusrs[usr]['msExchPoliciesExcluded']
                            
                    #Treating general cases
                    else:
                        if cerebrumusrs[usr].has_key(attr) and \
                               adusrs[usr].has_key(attr):
                            if isinstance(cerebrumusrs[usr][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False
                                                                
                                if isinstance(adusrs[usr][attr],(str,int,long,unicode)):
                                    #Transform single-value to a list for comparison.
                                    val2list = []
                                    val2list.append(adusrs[usr][attr])
                                    adusrs[usr][attr] = val2list
                                                                        
                                for val in cerebrumusrs[usr][attr]:
                                    if val not in adusrs[usr][attr]:
                                        Mchange = True
                                                                                
                                if Mchange:
                                    changes[attr] = cerebrumusrs[usr][attr]
                            else:
                                if adusrs[usr][attr] != cerebrumusrs[usr][attr]:
                                    changes[attr] = cerebrumusrs[usr][attr] 
                        else:
                            if cerebrumusrs[usr].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrumusrs[usr][attr] != "": 
                                    changes[attr] = cerebrumusrs[usr][attr] 
                            elif adusrs[usr].has_key(attr):
                                #Delete value
                                changes[attr] = ''      

                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    
                    if cerebrumusrs[usr].has_key(acc):
                        if adusrs[usr].has_key(acc) and \
                               adusrs[usr][acc] == cerebrumusrs[usr][acc]:
                            pass
                        else:
                            changes[acc] = cerebrumusrs[usr][acc]   
                    else: 
                        if adusrs[usr].has_key(acc) and adusrs[usr][acc] == \
                               value:
                            pass
                        else:
                            changes[acc] = value
                                                
                #Submit if any changes.
                if len(changes):
                    changes['distinguishedName'] = 'CN=%s,%s' % (usr,ou)
                    changes['type'] = 'alter_object'

                #after processing we delete from array.
                del cerebrumusrs[usr]

            else:
                #Account not in Cerebrum, but in AD.                
                if [s for s in cereconf.AD_DO_NOT_TOUCH if
                    adusrs[usr]['distinguishedName'].find(s) >= 0]:
                    pass
                elif adusrs[usr]['distinguishedName'].find(cereconf.AD_PW_EXCEPTION_OU) >= 0:
                    #Account do not have AD_spread, but is in AD to 
                    #register password changes, do nothing.
                    pass
                else:
                    #ac.is_deleted() or ac.is_expired() pluss a small rest of 
                    #accounts created in AD, but that do not have AD_spread. 
                    if delete_users == True:
                        changes['type'] = 'delete_object'
                        changes['distinguishedName'] = adusrs[usr]['distinguishedName']
                    else:
                        #Disable account.
                        if adusrs[usr]['ACCOUNTDISABLE'] == False:
                            changes['distinguishedName'] = adusrs[usr]['distinguishedName']
                            changes['type'] = 'alter_object'
                            changes['ACCOUNTDISABLE'] = True
                            #commit changes
                            changelist.append(changes)
                            changes = {}
                        #Hide Account from Exchange
                        hideAddr = False
                        if adusrs[usr].has_key('msExchHideFromAddressLists'):
                            if adusrs[usr]['msExchHideFromAddressLists'] == False:
                                hideAddr = True
                        else:
                            hideAddr = True
                        if hideAddr:
                            changes['distinguishedName'] = adusrs[usr]['distinguishedName']
                            changes['type'] = 'alter_object'
                            changes['msExchHideFromAddressLists'] = True
                            #commit changes
                            changelist.append(changes)
                            changes = {}
                        #Moving account.
                        if adusrs[usr]['distinguishedName'] != "CN=%s,OU=%s,%s" % \
                               (usr, cereconf.AD_LOST_AND_FOUND,self.ad_ldap):
                            changes['type'] = 'move_object'
                            changes['distinguishedName'] = adusrs[usr]['distinguishedName']
                            changes['OU'] = "OU=%s,%s" % \
                                (cereconf.AD_LOST_AND_FOUND,self.ad_ldap)

            #Finished processing user, register changes if any.
            if len(changes):
                changelist.append(changes)

        #The remaining items in cerebrumusrs is not in AD, create user.
        for cusr, cdta in cerebrumusrs.items():
            changes={}
            #TBD: Should quarantined users be created?
            if cerebrumusrs[cusr]['ACCOUNTDISABLE']:
                #Quarantined, do not create.
                pass    
            else:
                #New user, create.
                changes = cdta
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = cusr
                changelist.append(changes)
                changes['homeDrive'] = self.get_home_drive(cdta)

        return changelist


    def full_sync(self, delete, spread, dry_run, exchange_spread=None):

        self.logger.info("Starting user-sync(delete = %s, dry_run = %s)" % \
                             (delete, dry_run))     

        #Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(spread, exchange_spread)
        self.logger.info("Fetched %i cerebrum users" % len(cerebrumdump))

        #Fetch AD-data.     
        self.logger.debug("Fetching AD data...")
        addump = self.fetch_ad_data()       
        self.logger.info("Fetched %i ad-users" % len(addump))
                
        #Getting users that shall have Exchange mailbox
        exch_users = self.find_Exchange_changes(cerebrumdump, addump)

        #compare cerebrum and ad-data.
        changelist = self.compare(delete, cerebrumdump, addump)
        self.logger.info("Found %i number of changes" % len(changelist))

        #Perform changes.
        self.perform_changes(changelist, dry_run)

        #updating Exchange
        for usr in exch_users:
            self.logger.debug("Running Update-Recipient for user '%s' against Exchange" % usr)
            ret = self.run_cmd('run_UpdateRecipient', dry_run, usr)
            if not ret[0]:
                self.logger.warning("run_UpdateRecipient on %s failed: %r" % (usr, ret))
        self.logger.info("Ran Update-Recipient against Exchange for %i users" % len(exch_users))

        #Cleaning up.
        addump = None
        cerebrumdump = None   

        #Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished user-sync")


              
##################################################


class ADFullGroupSync(ADutilMixIn.ADgroupUtil):

        
    def fetch_cerebrum_data(self, spread, exchange_spread):
        """
        Fetch relevant cerebrum data for groups with the given spread.
        One spread indicating export to AD, and one spread indicating
        that it should also be prepped and activated for Exchange 2007.

        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param exchange_spread: exchange group spread
        @type exchange_spread: _SpreadCode
        @rtype: dict
        @return: a dict {grpname: {'adAttrib': 'value'}} for all groups
        of relevant spread. Typical attributes::
        
        'displayName': String,          # gruppenavn
        'mail': String,                 # default e-post adresse
        'Exchange' : Bool,              # Flag - skal i Exchange eller ikke 
        'msExchPoliciesExcluded' : int, # Exchange verdi
        'msExchHideFromAddressLists' : Bool, # Exchange verdi
        'mailNickname' : String         # gruppenavn
        'proxyAddresses' : String       # default e-post adresse
        'displayNamePrintable' : String # gruppenavn
        'description' : String          # beskrivelse
        'groupType' : Int               # type gruppe
        """
        #
        # Get groups with the  spreads
        #
        #Hvorfor maa jeg gjoere dette med constants og int?
        #Maa ikke gjoeres i andre AD sync..
        grp_dict = {}
        spread_res = self.group.search(spread=int(self.co.Spread(spread)))
        for row in spread_res:
            gname = unicode(row[1], 'ISO-8859-1')
            grp_dict[cereconf.AD_GROUP_PREFIX + gname] = {
                'groupType' : cereconf.AD_GROUP_TYPE,
                'Exchange' : False,
                'description' : unicode(row[2], 'ISO-8859-1'),
                'msExchPoliciesExcluded' : cereconf.AD_EX_POLICIES_EXCLUDED,
                'OU' : self.get_default_ou(),
                'grp_id' : row[0],
                'msExchHideFromAddressLists' : False
                }
        self.logger.info("Fetched %i groups with spread %s" % (len(grp_dict),spread))
        set1 = set([row[1] for row in spread_res])
        set2 = set([row[1] for row in self.group.search(spread=int(self.co.Spread(exchange_spread)))])
        set_res = set1.intersection(set2)
        ij = 0
        for row_set_res in set_res:
            grp_dict[cereconf.AD_GROUP_PREFIX + row_set_res]['Exchange'] = True
            ij += 1
        self.logger.info("Fetched %i groups with both spread %s and %s" % (ij,spread,exchange_spread))

        #
        # Assign derived attributes
        #
        for grp_name in grp_dict:
            v = grp_dict[grp_name]
            v['displayName'] = grp_name
            v['displayNamePrintable'] = grp_name
            if v['description'] is None:
                v['description'] = "Not available"
            if v['Exchange'] is True:
                v['proxyAddresses'] = "SMTP:" + grp_name + "@" + cereconf.AD_GROUP_EMAIL_DOMAIN
                v['mailNickname'] = grp_name
                v['mail'] = grp_name + "@" + cereconf.AD_GROUP_EMAIL_DOMAIN
                
        return grp_dict

    
    def fetch_ad_list(self):
        """
        Gets a list over groups in AD with distinguished names

        @rtype: dict
        @return: dict over AD groups with OU info.
        """
        ad_list = self.server.listObjects('group', True)
        ad_dict = {}
        for element in ad_list:
            part = element.partition(",")
            if part[1] and part[2] and part[0].find("CN=") > -1:
                ad_dict[part[0].replace("CN=","")] = {
                    'distinguishedName' : element,
                    'OU' : part[2] 
                    }
        return ad_dict

    
    def delete_and_filter(self, ad_dict, cerebrum_dict, dry_run, delete_groups):
        """
        Goes through the dict of the groups in AD, and checks if it is 
        a group that shall be synced from cerebrum. If it is, but the group
        is not in our defult OU we will move it there. If it is not we remove
        it from the dict so we will pay no attention to the group when we sync,
        but only after checking if it is in our OU. If it is we delete it.

        @param ad_dict : account_id -> account info mapping
        @type ad_dict : dict
        @param cerebrum_dict : account_id -> account info mapping
        @type cerebrum_dict : dict
        @param delete_users: Delete or not unwanted groups
        @type delete_users: Flag
        @param dry_run: Flag
        """
        for grp_name, v in ad_dict.items():
            if not cerebrum_dict.has_key(grp_name):
                if self.ad_ldap in ad_dict[grp_name]['OU']:
                    match = None
                    for dont in cereconf.AD_DO_NOT_TOUCH:
                        if dont in ad_dict[grp_name]['OU']:
                            match = True
                            break
                    #an unknown group in OUs under our control and not i DO_NOT_TOUCH -> delete
                    if not match:
                        if not delete_groups:
                            self.logger.debug("delete is False. Don't delete group: %s", grp_name)
                        else:
                            self.logger.debug("delete_groups = %s, deleting group %s",
                                              delete_groups, grp_name)
                            self.run_cmd('bindObject', dry_run, 
                                         ad_dict[grp_name]['distinguishedName'])
                            self.delete_object(ad_dict[grp_name], dry_run)
                #does not concern us (anymore), delete from dict.
                del ad_dict[grp_name]
    

    def fetch_ad_data(self, ad_dict):
        """
        Get group attributes from AD and update dict

        @param ad_dict : account_id -> account info mapping
        @type ad_dict : dict
        """
        self.server.setGroupAttributes(cereconf.AD_GRP_ATTRIBUTES)
        for grp_name in ad_dict:
            v = ad_dict[grp_name]
            retstring = self.server.bindObject(v['distinguishedName'])
            if retstring[0] is True:
                #TBD: This is sloooooow!
                grp_prop = self.server.getObjectProperties(cereconf.AD_GRP_ATTRIBUTES)[1]
                for element in grp_prop:
                    if grp_prop[element] != False:
                        ad_dict[grp_name][element] = grp_prop[element]
            else:
                self.logger.warning("Group cannot be found now: %s", grp_name)
                

               
    def sync_group_info(self, ad_dict, cerebrum_dict, dry_run):
        """
        Check if any values about groups other than group members
        should be updated in AD

        @param ad_dict : account_id -> account info mapping
        @type ad_dict : dict
        @param cerebrum_dict : account_id -> account info mapping
        @type cerebrum_dict : dict
        @param dry_run: Flag
        """
        #Keys in dict from cerebrum must match fields to be populated in AD.
        #Already removed groups from ad_dict not i cerebrum_dict
        changelist = [] 

        for grp in cerebrum_dict:
            changes = {}   
            if ad_dict.has_key(grp):
                #group in both places, we want to check correct data
                
                #Checking for correct OU.
                if cerebrum_dict[grp].has_key('OU'):
                    ou = cerebrum_dict[grp]['OU']
                else:
                    ou = self.get_default_ou()
                if ad_dict[grp]['OU'] != ou:
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                                ad_dict[grp]['distinguishedName']
                    #Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                #Comparing group info 
                for attr in cereconf.AD_GRP_ATTRIBUTES:            
                    #Catching special cases.
                    # xmlrpclib appends chars [' and '] to this attribute for some reason
                    if attr == 'msExchPoliciesExcluded':
                        if ad_dict[grp].has_key('msExchPoliciesExcluded'):
                            tempstring = str(ad_dict[grp]['msExchPoliciesExcluded']).replace("['","")
                            tempstring = tempstring.replace("']","")
                            if  tempstring == cerebrum_dict[grp]['msExchPoliciesExcluded']:
                                pass
                            else:
                                changes['msExchPoliciesExcluded'] = cerebrum_dict[grp]['msExchPoliciesExcluded']
                        else:
                            changes['msExchPoliciesExcluded'] = cerebrum_dict[grp]['msExchPoliciesExcluded']
                            
                    #Treating general cases
                    else:
                        if cerebrum_dict[grp].has_key(attr) and \
                               ad_dict[grp].has_key(attr):
                            if isinstance(cerebrum_dict[grp][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False
                                                                
                                if isinstance(ad_dict[grp][attr],(str,int,long,unicode)):
                                    #Transform single-value to a list for comparison.
                                    val2list = []
                                    val2list.append(ad_dict[grp][attr])
                                    ad_dict[grp][attr] = val2list
                                                                        
                                for val in cerebrum_dict[grp][attr]:
                                    if val not in ad_dict[grp][attr]:
                                        Mchange = True
                                                                                
                                if Mchange:
                                    changes[attr] = cerebrum_dict[grp][attr]
                            else:
                                if ad_dict[grp][attr] != cerebrum_dict[grp][attr]:
                                    changes[attr] = cerebrum_dict[grp][attr] 
                        else:
                            if cerebrum_dict[grp].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrum_dict[grp][attr] != "": 
                                    changes[attr] = cerebrum_dict[grp][attr] 
                            elif ad_dict[grp].has_key(attr):
                                #Delete value
                                changes[attr] = '' 

                #Submit if any changes.
                if len(changes):
                    changes['distinguishedName'] = 'CN=%s,%s' % (grp,ou)
                    changes['type'] = 'alter_object'
                    changelist.append(changes)
                    changes = {}
            else:
                #The remaining items in cerebrum_dict is not in AD, create group.
                changes={}
                changes = cerebrum_dict[grp]
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = grp
                changelist.append(changes)
            
        return changelist

    

    def get_default_ou(self):
        """
        Return default OU for groups. Burde vaere i cereconf?
        """
        return "OU=Group,%s" % self.ad_ldap
    

    def store_sid(self, objtype, name, sid):
        """
        Store AD object SID to cerebrum database for given group

        @param objtype: type of AD object
        @type objtype: String
        @param name: group name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # husk aa definere AD som kildesystem
        #TBD: Check if we create a new object for a entity that already
        #have an externalid_groupsid defined in the db and delete old?
        if objtype == 'group':
            crbname = name.replace(cereconf.AD_GROUP_PREFIX,"")
            self.group.clear()
            self.group.find_by_name(crbname)
            self.group.affect_external_id(self.co.system_ad, self.co.externalid_groupsid)
            self.group.populate_external_id(self.co.system_ad, self.co.externalid_groupsid, sid)
            self.group.write_db()


    def create_object(self, chg, dry_run):
        """
        Creates AD group object and populates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        if chg.has_key('OU'):
            ou = chg['OU']
        else:
            ou = self.get_default_ou()
        
        self.logger.debug('CREATE %s', chg)
        ret = self.run_cmd('createObject', dry_run, 'Group', ou, 
                      chg['sAMAccountName'])
        if not ret[0]:
            self.logger.warning("create group %s failed: %r" % \
                                (chg['sAMAccountName'],ret[1]))
        elif not dry_run:
            self.store_sid('group',chg['sAMAccountName'],ret[2])
            del chg['type']
            if chg.has_key('distinguishedName'):
                del chg['distinguishedName']
            #if chg.has_key('sAMAccountName'):
            #    del chg['sAMAccountName']               
            ret = self.server.putGroupProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on %s failed: %r" % \
                                    (chg['sAMAccountName'], ret))
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r" % \
                                        (chg['sAMAccountName'], ret))
            


    def alter_object(self, chg, dry_run):
        """
        Binds to AD group objects and updates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        distName = chg['distinguishedName']                 
        #Already binded
        del chg['type']             
        del chg['distinguishedName']

        #ret = self.run_cmd('putGroupProperties', dry_run, chg)
        #run_cmd in ADutilMixIn.py not written for group updates
        if not dry_run:
            ret = self.server.putGroupProperties(chg)
        else:
            ret = (True, 'putGroupProperties')
        if not ret[0]:
            self.logger.warning("putGroupProperties on %s failed: %r" % \
                           (distName, ret))
        else:
            ret = self.run_cmd('setObject', dry_run)
            if not ret[0]:
                self.logger.warning("setObject on %s failed: %r" % \
                               (distName, ret))         


    def sync_group_members(self, cerebrum_dict, group_spread, user_spread, dry_run):
        """
        Update group memberships in AD

        @param cerebrum_dict : group_name -> group info mapping
        @type cerebrum_dict : dict
        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param user_spread: ad account spread for a domain
        @type user_spread: _SpreadCode
        @param dry_run: Flag
        """
        #To reduce traffic, we send current list of groupmembers to AD, and the
        #server ensures that each group have correct members.   

        entity2name = dict([(x["entity_id"], x["entity_name"]) for x in 
                           self.group.list_names(self.co.account_namespace)])
        entity2name.update([(x["entity_id"], x["entity_name"]) for x in
                           self.group.list_names(self.co.group_namespace)])        

        for grp in cerebrum_dict:
            grp_name = grp.replace(cereconf.AD_GROUP_PREFIX,"")
            grp_id = cerebrum_dict[grp]['grp_id']
            self.logger.debug("Sync group %s" % grp_name)

            #TODO: How to treat quarantined users???, some exist in AD, 
            #others do not. They generate errors when not in AD. We still
            #want to update group membership if in AD.
            members = list()
            for usr in self.group.search_members(group_id=grp_id,
                                                 member_spread=int(self.co.Spread(user_spread))):
                user_id = usr["member_id"]
                if user_id not in entity2name:
                    self.logger.debug("Missing name for account id=%s", user_id)
                    continue
                members.append(entity2name[user_id])
                self.logger.debug2("Try to sync member account id=%s, name=%s",
                                   user_id, entity2name[user_id])

            for grp in self.group.search_members(group_id=grp_id,
                                                 member_spread=int(self.co.Spread(group_spread))):
                group_id = grp["member_id"]
                if group_id not in entity2name:
                    self.logger.debug("Missing name for group id=%s", group_id)
                    continue
                members.append('%s%s' % (cereconf.AD_GROUP_PREFIX,
                                         entity2name[group_id]))                          
                self.logger.debug2("Try to sync member group id=%s, name=%s",
                                   group_id, entity2name[group_id])
                
            dn = self.server.findObject('%s%s' %
                                        (cereconf.AD_GROUP_PREFIX,grp_name))
            if not dn:
                self.logger.debug("unknown group: %s%s",
                                  cereconf.AD_GROUP_PREFIX,grp_name)
            elif dry_run:
                self.logger.debug("Dryrun: don't sync members")
            else:
                self.server.bindObject(dn)
                res = self.server.syncMembers(members, False, False)
                if not res[0]:
                    self.logger.warning("syncMembers %s failed for:%r" %
                                      (dn, res[1:]))
             



    def full_sync(self, delete, spread, dry_run, user_spread,exchange_spread=None):

        self.logger.info("Starting group-sync(delete = %s, dry_run = %s)" % \
                             (delete, dry_run))     

        #Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(spread, exchange_spread)
        self.logger.info("Fetched %i cerebrum groups" % len(cerebrumdump))
        
        
        #Fetch list of groups in AD.     
        self.logger.debug("Fetching list of groups in AD...")
        addump = self.fetch_ad_list()       
        self.logger.info("Fetched %i ad-groups" % len(addump))

        #Filter AD-list
        self.logger.debug("Filtering list of AD groups...")
        self.delete_and_filter(addump, cerebrumdump, dry_run, delete)
        self.logger.info("Syncing %i ad-groups after filtering" % len(addump))

        #Fetch AD data
        self.logger.debug("Fetching AD data...")
        self.fetch_ad_data(addump)       

        #Compare groups and attributes (not members)
        self.logger.debug("Syncing group info...")
        changelist = self.sync_group_info(addump, cerebrumdump, dry_run)

        #Perform changes
        self.perform_changes(changelist, dry_run)

        #Syncing group members
        self.logger.info("Starting sync of group members")
        self.sync_group_members(cerebrumdump,spread, user_spread, dry_run)

        #Cleaning up.
        addump = None
        cerebrumdump = None   

        #Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished group-sync")

