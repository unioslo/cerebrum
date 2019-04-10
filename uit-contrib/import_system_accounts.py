#! /usr/bin/env python
# -*- coding: utf-8 -*-
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

"""
Script that processes a list of system accounts that reside in an XML file.
These accounts will be imported/updated in Cerebrum, they will be owned
by a Group entity (e.g. they are non-personal accounts) for administrative
purposes mainly.

XML Structure
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<data>
  <account>
    <account_name></account_name>
    <account_type></account_type>
    <initial_pass></initial_pass>
    <gecos></gecos>
    <contact_info>
      <email></email>
      <url></url>
    </contact_info>
    <spreads>
      <spread></spread>
    </spreads>
    <expire_date></expire_date>
  </account>
</data>

*** account_name *** MANDATORY (element and character data)
3 chars + 3 digits
Is used to check if the account exists.
 - If the account exists, it loads the account.
 - If the account doesn't exists, it will create one

*** account_type *** MANDATORY (element and character data)
code_str from account_code table
Ex.: FD (Felles Drift)
     FI (Felles Intern)
     F (Forening)
     K (Kurs)
     M (Maskin)
     programvare (Programvarekonto)
     P (Prosess)
     T (Testkonto)
Is set at account creation, and can be changed later.
     
*** initial_pass *** MANDATORY (element)
String
Is set at account creation, and can will not be changed by the script later.

*** gecos *** MANDATORY (element)
String
Is set at account creation, and can be changed later

*** contact_info *** MANDATORY (element and at least one sub-element, with or without character data)
email and url - both Strings
Are set at account creation, and can be changed later.
If a tag is omitted the contact info will be deleted.

*** spreads *** MANDATORY (element, and at least one sub-element, with or without character data)
spread is a valid spread (ldap@uit, etc.)
Multiple spread tags are allowed. Spreads are set at account creation, and can
be added and removed (if omitted) by the script later.

*** expire_date *** MANDATORY (element)
'Never' (without quotes) or a date on ISO format (YYYYMMDD or YYYY-MM-DD will work for sure)
The expire date will be set at account creation, and can be changed later.
The expire date is never set furhter in the future than the default_stay_alive_time.
If Never, the expire date will be set to now() + default_stay_alive_time in weeks.
If expire_date is < now() + default_stay_alive_time in weeks, expire_date is used directly
If expire_date is >= now() + default_stay_alive_time in weeks, expire_date is like Never
If no expire_date is set at all, it will default to today

"""
from __future__ import unicode_literals
import sys
import getopt

import xml.sax

import cerebrum_path
import cereconf
from Cerebrum.utils import transliterate

from mx import DateTime
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
#from Cerebrum.modules.no.uit import Email
from Cerebrum import Errors


#from Cerebrum.modules.xmlutils import GeneralXMLParser


system_accounts_cache = []

logger = None
default_logger = 'cronjob'
default_source_dir = '%s/var/source/system_accounts' %  (cereconf.CB_PREFIX)
default_system_accounts_file = 'system_accounts.xml'
default_stay_alive_time = 4 #Weeks

default_creator_id = default_owner_id = default_source_system = valid_contact_types = None
db = None


# ********** <XML FILE PARSING>

class SystemAccountsParser(xml.sax.ContentHandler):
    """This class is used to iterate over all accounts in system account file. """
    global logger

    def __init__(self, info_file, call_back_function):
        self.account = {}
        self.elementstack = []
        self.chardata = ""
        self.call_back_function = call_back_function
        xml.sax.parse(info_file, self)

    def startElement(self, name, attrs):
        if len(self.elementstack) == 0:
            if name == "data":
                logger.debug("Data level reached")
            else:
                logger.warn("Unknown element on data level: %s" % name)
        elif len(self.elementstack) == 1:
            if name == "account":
                logger.debug("Account level reached")
                self.account = {}
            else:
                logger.warn("Unknown element on account level: %s" % name)
        elif self.elementstack[-1] == "account":
            if name in ('account_name','initial_pass', 'gecos', 'contact_info', 'expire_date', 'spreads', 'account_type'):
                logger.debug("Inside account level - %s " % name)
            else:
                logger.warn("Unknown element inside account level: %s" % name)
        elif self.elementstack[-1] == "spreads":
            if name in ('spread'):
                logger.debug("Inside spreads level - %s" % name)
            else:
                logger.warn("Unknown element inside spreads level: %s" % name)            
        elif self.elementstack[-1] == "contact_info":
            if name in ('email', 'url'):
                logger.debug("Inside contact_info level - %s" % name)
            else:
                logger.warn("Unknown element inside contact_info level: %s" % name)            
                
        self.elementstack.append(name)
        self.chardata = ""

            
    def endElement(self, name):
        logger.debug("Leaving element")
        if name == "account":
            self.call_back_function(self.account)
        elif name == "data":
            pass
        elif name == self.elementstack[-1]:
            if name == 'spread':
                if not self.account.has_key('spreads'):
                    self.account['spreads'] = []
                self.account['spreads'].append(self.chardata)
            elif name in ('email','url'):
                if not self.account.has_key('contact_info'):
                    self.account['contact_info'] = {}
                self.account['contact_info'][name] = self.chardata
            elif name in ('spreads', 'contact_info'):
                pass
            else:
                self.account[name] = self.chardata
        self.elementstack.pop()


    def characters(self, character):
        self.chardata = self.chardata + character


def system_account_callback(account):
    '''Process each account element returned from XML parser'''
    global system_accounts_cache
    system_accounts_cache.append(account)

# ********** </XML FILE PARSING>


# ********* <ACCOUNT CREATION AND UPDATING>

def process_account(account_data):
    global db, default_creator_id, default_owner_id, default_owner_type, \
           default_source_system, valid_contact_types, default_stay_alive_time

    gr = Factory.get('Group')(db)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    pu = PosixUser.PosixUser(db)
    new_account = False

    # Data sanity check
    try:
        account_name = account_data['account_name']
        account_type = account_data['account_type']
        account_type_id = int(co.Account(account_type.encode('iso-8859-1')))
        initial_pass = account_data['initial_pass']
        gecos = account_data['gecos']
        contact_info = account_data['contact_info']
        spreads = account_data['spreads']

        # Max time an account will stay valid after account stops coming from
        # the file
        base_date = DateTime.now() + DateTime.oneWeek * default_stay_alive_time
        if account_data['expire_date'] == 'Never':
            expire_date = base_date
        elif DateTime.Parser.DateFromString(account_data['expire_date']) > base_date:
            expire_date = base_date
        else:
            expire_date = DateTime.Parser.DateFromString(account_data['expire_date'])
    except Exception as msg:
        logger.error("Invalid account data, account not processed. %s", msg)
        return

    logger.info("Processing system account: %s" % account_name)

    # Check if account needs to be created
    try:
        logger.info("Resolving given account name: %s" % account_name)
        ac.find_by_name(account_name)
        logger.info("Account found. Proceeding to updating some fields.")
    except Exception:
        logger.error("Given account name does not exist. Account must be created.")
        ac.clear()
        ac.populate(account_name,
                    co.entity_group,
                    default_owner_id,
                    account_type_id,
                    default_creator_id,
                    expire_date)
        ac.set_password(initial_pass)
        ac.write_db()
        new_account = True

    # Check if owner change is needed
    if ac.owner_id != default_owner_id:
        logger.info("Owner must be changed from %s to %s", ac.owner_id,
                    default_owner_id)
        # Delete account types (affiliations)
        for acc_aff in ac.get_account_types():
            ac.del_account_type(acc_aff['ou_id'], acc_aff['affiliation'])

        # Change owner and owner type of account
        ac.owner_id = default_owner_id
        ac.owner_type = default_owner_type
        ac.np_type = account_type_id
        ac.write_db()
        logger.info("Changed owner, owner type and np_type to %s, %s and %s",
                    default_owner_id, default_owner_type, account_type_id)

    # Check for np_type changes
    if (ac.np_type != account_type_id):
        ac.np_type = account_type_id
        ac.write_db()
        logger.info("Changed np_type to %s" % (account_type_id))

    # If account has quarantines - remove them and reset password for security
    # reasons (?)
    # Don't do it for now... .maybe later. (20080222)

    # Assure posix user is ok
    try:
        logger.info("Resolving posix user")
        pu.find(ac.entity_id)
    except Errors.NotFoundError:
        logger.warn("Posix account not found. Trying to promote....")
        uid = pu.get_free_uid()
        shell = co.posix_shell_bash
        grp_name = "posixgroup"
        gr.find_by_name(grp_name, domain=co.group_namespace)
        try:
            pu.clear()
            pu.populate(uid, gr.entity_id, None, shell, parent=ac)
            pu.write_db()
            logger.info("...promotion ok!")
        except Exception as msg:
            logger.error("Error promoting. Error message follows: %s", msg)
            sys.exit(1)

    # Update account type (np_type)
    if ac.np_type != account_type_id:
        logger.info("Updating account type to %s" % account_type)
        ac.np_type = account_type_id
        ac.write_db()

    # Gecos treatment
    old_gecos = ""
    if not new_account:
        old_gecos = pu.get_gecos()
    new_gecos = transliterate.for_gecos(gecos)
    if (new_gecos != old_gecos):
        logger.info("Updating gecos. Old name: %s, new name: %s", old_gecos,
                    new_gecos)
        pu.gecos = new_gecos
        pu.write_db()

    # Update expire date
    logger.info("Updating expire date to %s" % expire_date)
    pu.expire_date = "%s" % expire_date
    pu.write_db()

    # Updating homedir for existing spreads
    logger.info("Updating homedirs for current spreads")
    cur_spreads = pu.get_spread()
    for spread in cur_spreads:
        pu.set_home_dir(spread['spread'])

    # Adding spreads
    for spread in spreads:
        if spread == '':
            continue

        try:
            spread_id = int(co.Spread(spread.encode("iso-8859-1")))
        except Exception, msg:
            logger.error("Skipping invalid spread (%s)." % spread)
            continue

        ac.set_spread_expire(spread=spread_id,
                             expire_date=expire_date,
                             entity_id=ac.entity_id)

        if (not pu.has_spread(spread_id)):
            logger.info("Adding spread %s and setting homedir for it" % spread)
            pu.add_spread(spread_id)
            pu.set_home_dir(spread_id)

    # Deleting spreads not in authoritative system accounts XML file
    old_spreads = ac.get_spread()
    for spread in old_spreads:
        spread = spread[0]  # WHY THIS???
        if not str(co.Spread(spread)).decode() in spreads:
            logger.info("Deleting obsolete spread %s" % str(co.Spread(spread)))
            ac.clear_home(spread)
            ac.delete_spread(spread)

    # Adding / Updating contact information
    for contact in contact_info:
        logger.info("Processing contact info %s" % contact)
        # Check if contact type already exists
        old_contact = ac.get_contact_info(default_source_system,
                                          valid_contact_types[contact.upper()])
        if old_contact != []:
            logger.info("Contact info exists - check if update is needed...")
            # If contact type exists, check if it needs updating
            if old_contact[0]['contact_value'] != contact_info[contact]:
                logger.info("Update needed, will delete value and add later.")
                ac.delete_contact_info(default_source_system,
                                       valid_contact_types[contact.upper()],
                                       pref='ALL')
                old_contact = []
            else:
                logger.info("No update needed.")

        # Add or "Update" contact info
        if old_contact == []:
            logger.info("Adding contact info %s with value %s", contact,
                        contact_info[contact])
            ac.add_contact_info(default_source_system,
                                valid_contact_types[contact.upper()],
                                contact_info[contact])

# ********* </ACCOUNT CREATION AND UPDATING>





        
def main():

    global logger, default_logger, default_source_dir, default_system_accounts_file, system_accounts_cache, \
           db, default_creator_id, default_owner_id, default_owner_type, default_source_system, valid_contact_types
    
    logger = Factory.get_logger(default_logger)

    filename = default_system_accounts_file
    path = default_source_dir
    dryrun = False

    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:p:d',['filename=', 'path=', 'dryrun'])
    except getopt.GetoptError:
        usage()

    for opt,val in opts:
        if opt in('-f','--filename'):
            filename = val
        elif opt in('-p','--path'):
            path = val
        elif opt in('-d','--dryrun'):
            dryrun = True

    if path != "" and path[-1] != "/":
        path = path + "/"

    file = path+filename
    
    logger.info('Starting to cache system accounts from %s' % file)
    SystemAccountsParser(file, system_account_callback)
    logger.info('Finished caching system accounts')

    # Get default values
    logger.info("Caching default values to use in account processing...")
    db = Factory.get('Database')()
    db.cl_init(change_program='activate_account')
    
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = ac.entity_id
    default_owner_id = ac.owner_id
    default_owner_type = ac.owner_type
    
    default_source_system = co.system_sysacc
    valid_contact_types = {}
    valid_contact_types[co.contact_email.str] = co.contact_email
    valid_contact_types[co.contact_url.str] = co.contact_url
    logger.info("Finished caching default values.")
    
    logger.info('Starting to process accounts')
    for account in system_accounts_cache:
        process_account(account)
    logger.info('Finished processing accounts')

    if dryrun:
        logger.info("Rolling back changes!")
        db.rollback()
    else:
        logger.info("Commiting changes!")
        db.commit()


def usage():
    global default_source_dir, default_system_accounts_file
    print """
    usage: python import_system_accounts.py 
    -f | --file  : XML file with System Accounts (default is '%s')
    -p | --path  : Path to XML file (default is '%s')
    -d | --dryrun: will not commit changes to DB
    """ % (default_system_accounts_file, default_source_dir)
    sys.exit(1)



if __name__=='__main__':
    main()

