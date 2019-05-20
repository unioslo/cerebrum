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
"""
This script generats a csv file containing the following information:
name,email and tlf for every person having accounts with spread as given with
the -s option.  The script was created to list persons having SITO spread
for use towards skype

export format:
<NAVN>;[TELEFON...];<BRUKERNAVN>;<EPOST>
"""

import argparse
import logging
from pprint import pprint

import cereconf
from Cerebrum import logutils
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

default_spread = 'SITO'
default_source = 'SITO'


def get_data(db, spread=None, source_system=None):
    """
    List all accounts with correct spread and return account and owner data.

    format on returned data:
    person_dict = {person_id : {person_name : name,
                                person_tlf : tlf,
                                {accounts : [{account_name : somename,
                                              account_id : someid,
                                               expire_date : some_expire_date,
                                               email : [email1..emailN]
                                              }]
                               }
                  }
    :param db: Cerebrum database
    :param basestring spread: name of a spread e.g 'SITO'
    :param basestring source_system: name of  a source system e.g 'SITO'
    :return: dict
    """
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    person_dict = {}

    set_source_system = source_system or co.system_cached
    set_spread = co.Spread(spread)
    set_name_variant = int(co.name_full)

    account_list = ac.list_accounts_by_type(filter_expired=True,
                                            account_spread=set_spread)
    for accounts in account_list:
        ac.clear()
        pe.clear()

        ac.find(accounts['account_id'])
        pe.find(accounts['person_id'])

        logger.debug("processing account id:%s", ac.entity_id)
        if pe.entity_id not in person_dict.keys():
            person_dict[pe.entity_id] = {
                'fullname': pe.get_name(source_system=set_source_system,
                                        variant=set_name_variant),
                'tlf': get_person_tlf(co, pe),
                'accounts': []}

        ac_name = ac.get_account_name()
        ac_email = ac.get_primary_mailaddress()
        ac_expire_date = ac.get_account_expired()
        if ac_expire_date is False:
            ac_expire_date = 'Not expired'

        if len(person_dict[pe.entity_id]['accounts']) == 0:
            person_dict[pe.entity_id]['accounts'].append(
                {'account_name': ac_name, 'expire_date': ac_expire_date,
                 'email': ac_email, 'account_id': int(ac.entity_id)})
        else:
            logger.debug(
                "person:%s has more than 1 account", pe.entity_id)
            append_me = True
            for acc in person_dict[pe.entity_id]['accounts']:
                if ac.entity_id == acc['account_id']:
                    # already exists. do not append
                    logger.debug(
                        "...but account:%s has already been registered on "
                        "person:%s. nothing done.",
                        ac.entity_id, pe.entity_id)
                    append_me = False
            if append_me:
                logger.debug("appending new account:%s", ac.entity_id)
                person_dict[pe.entity_id]['accounts'].append(
                    {'account_name': ac_name, 'expire_date': ac_expire_date,
                     'email': ac_email, 'account_id': ac.entity_id})

    return person_dict


#
# Get all phonenr for a given person
#
def get_person_tlf(const, person):
    phone_list = []

    # get work phone
    retval = person.get_contact_info(type=const.contact_phone)
    for val in retval:
        if val[4] not in phone_list:
            phone_list.append(val[4])

            # get mobile
    retval = person.get_contact_info(type=const.contact_mobile_phone)
    for val in retval:
        if val[4] not in phone_list:
            phone_list.append(val[4])

    return phone_list


#
# write data to file
#
def write_file(data_list, outfile):
    header = "NAVN;TELEFON;BRUKERNAVN;EPOST\n"
    print("outfile:{0}".format(outfile))
    fp = open(outfile, 'w')
    fp.write(header)
    for data in data_list.items():
        pprint(data[1])
        person_name = data[1]['fullname']
        person_tlf = ','.join(data[1]['tlf'])
        person_account_data = ''
        for account in data[1]['accounts']:
            account_name = account['account_name']
            account_email = account['email']
            account_info = "%s;%s" % (account_name, account_email)
            person_account_data += account_info
        line = "%s;%s;%s\n" % (person_name, person_tlf, account_info)
        fp.write(line)
    fp.close()


#
# main function
#
def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--out',
                        required=True,
                        dest='outfile')
    parser.add_argument('-s', '--spread',
                        default=default_spread)
    parser.add_argument('-a', '--authoritative_source_system',
                        dest='source',
                        default=default_source)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf(cereconf.DEFAULT_LOGGER_TARGET, args)

    logger.debug("outfile:%s", args.outfile)
    logger.debug("spread: %s", args.spread)
    logger.debug("source: %s", args.source)

    db = Factory.get('Database')()
    db.cl_init(change_program='skype_export')

    data_list = get_data(db, args.spread,
                         args.source)
    write_file(data_list, args.outfile)


if __name__ == "__main__":
    main()
