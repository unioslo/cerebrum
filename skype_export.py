#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2017 University of Tromso, Norway
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


__doc__ = """ Usage: %s [-o <filename> | --outfile <filename>] [--logger-name]
-h | --help : this text
-s | --spread : spreadname (default SITO if this is not set)
-a | -authoritative_source_system : source system (default SITO)
-o | --out : output filename

This script generats a csv file containing the following information:
name,email and tlf for every person having accounts with spread as given with the
-s option.  The script was created to list persons having SITO spread
for use towards skype 

export format: 
<NAVN>;[TELEFON...];<BRUKERNAVN>;<EPOST>
"""

# generic imports
import getopt
import sys
import os
from pprint import pprint
import xml.sax.xmlreader
import xml.sax.saxutils

# cerebrum imports
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

# global variables
db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)

#
# list all accounts with correct spread and return account and owner data.
#
# format on returned data:
# person_dict = {person_id : {person_name : name,  
#                             person_tlf : tlf,  
#                             {accounts : [{account_name : somename,
#                                           account_id : someid,
#                                            expire_date : some_expire_date, 
#                                            email : [email1..emailN]
#                                           }]
#                            }
#               }
def get_data(spread=None,source_system=None):
    global person
    global account
    person_dict = {}

    set_source_system = const.system_cached
    set_spread  =  const.Spread(spread)
    set_name_variant = int(const.name_full)

    account_list = account.list_accounts_by_type(filter_expired = True,account_spread = set_spread)
    for accounts in account_list:
        account.clear()
        person.clear()

        account.find(accounts['account_id'])
        person.find(accounts['person_id'])

        logger.debug("processing account id:%s" % account.entity_id)
        if person.entity_id not in person_dict.keys():
            person_dict[person.entity_id] = {'fullname' : person.get_name(source_system = set_source_system,variant = set_name_variant),
                                             'tlf' : get_person_tlf(person),
                                             'accounts' : []}
        
            
        ac_name = account.get_account_name()
        ac_email = account.get_primary_mailaddress()
        ac_expire_date = account.get_account_expired()
        if ac_expire_date == False:
            ac_expire_date = 'Not expired'
            
        if len(person_dict[person.entity_id]['accounts']) == 0:
            person_dict[person.entity_id]['accounts'].append({'account_name' : ac_name, 'expire_date': ac_expire_date, 'email' : ac_email,'account_id' : int(account.entity_id)})
        else:
            logger.debug("person:%s has more than 1 account" % (person.entity_id))
            append_me =  True
            for acc in person_dict[person.entity_id]['accounts']:
                if account.entity_id == acc['account_id']:
                    # already exists. do not append
                    logger.debug("...but account:%s has already been registered on person:%s. nothing done." % (account.entity_id,person.entity_id))
                    append_me= False
            if append_me:
                logger.debug("appending new account:%s" % account.entity_id)
                person_dict[person.entity_id]['accounts'].append({'account_name' : ac_name, 'expire_date': ac_expire_date, 'email' : ac_email,'account_id' : account.entity_id})
                
 
    return person_dict
#
# Get all phonenr for a given person
#
def get_person_tlf(person):
    phone_list = []
    source_system = const.system_tlf

    # get work phone
    retval = person.get_contact_info( type = const.contact_phone)
    for val in retval:
        if val[4] not in phone_list:
            phone_list.append(val[4]) 

    # get mobile
    retval = person.get_contact_info(type = const.contact_mobile_phone)
    for val in retval:
        if val[4] not in phone_list:
            phone_list.append(val[4])

    return phone_list


#
# write data to file
#
def write_file(data_list,outfile):
    header = "NAVN;TELEFON;BRUKERNAVN;EPOST\n"
    print "outfile:%s" % outfile
    fp = open(outfile,'w')
    fp.write(header)
    for data in data_list.items():
        pprint(data[1])
        person_name = data[1]['fullname']
        person_tlf = ','.join(data[1]['tlf'])
        person_account_data = ''
        for account in data[1]['accounts']:
            account_name = account['account_name']
            account_email =account['email']
            account_info = "%s;%s" % (account_name,account_email)
            person_account_data +=account_info
        line = "%s;%s;%s\n" % (person_name,person_tlf,account_info)
        fp.write(line)
    fp.close()
            
#
# main function
#
def main():

    default_spread = 'SITO'
    default_source = 'SITO'
    default_out = ''
    try:
        opts,args = getopt.getopt(sys.argv[1:],'ho:s:a:',['help','out=','spread=','authoritative_source_system='])
    except getopt.GetoptError,m:
        usage(1,m)
    
    for opt, value in opts:
        if opt in ('-h','--help'):
            usage(1)
        if opt in ('-o','--out'):
            outfile = value
        if opt in ('-s','--spread'):
            default_spread = value
        if opt in ('-a','--authoritative_source_system'):
            default_source = value

    logger.debug("outfile:%s" % outfile)
    logger.debug("spread: %s" % default_spread)
    logger.debug("source: %s" % default_source)
    
    data_list = get_data(default_spread,default_source) # collects: person names, tlf and campus
    write_file(data_list,outfile)

#
# list usage incase of script parameter error
#
def usage(exitcode = 0, msg = None):
    if msg:
        print msg
    print __doc__
    sys.exit(exitcode)

if __name__ == "__main__":
    main()
