#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2007  University of Oslo, Norway
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

import cerebrum_path
import cereconf

import getopt
import sys, os

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import Email

def write_email_file(email_data, outfile):
    stream = open(outfile, 'w')
    for k in email_data:
        line = k + ':' + email_data[k] + '\n'
        stream.write(line)

def get_valid_email_addrs(et):
    addrs = [(r['local_part'], r['domain'])       
             for r in et.get_addresses()]
    return ["%s@%s" % a for a in addrs]

def generate_email_data():
    all_accounts = account.search(spread=constants.spread_email_account)
    all_email_data = {}
    es = Email.EmailServer(db)
    for k in all_accounts:
        account.clear()
        account.find(k['account_id'])
        email_server = None
        # fetch primary address
        try:
            primary = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.warn("No primary address for %s", account.account_name)
            continue
        # find email target for this account
        et = Email.EmailTarget(db)
        et.clear()
        try:
            et.find_by_target_entity(account.entity_id)
        except Errors.NotFoundError:
            logger.warn("No e-mail target for %s", account.account_name)
            continue
        # fetch all valid adresses for account
        valid_addrs = get_valid_email_addrs(et)
        if not et.email_server_id:
            logger.warn("No server registered for %s", account.account_name)
            email_server = "N/A"
        else:
            email_server = et.email_server_id
        if email_server != "N/A":
            es.clear()    
            es.find(et.email_server_id)
            email_server = es.name
        valid = "valid:"
        for a in valid_addrs:
            valid = valid + a + ':'
        all_email_data[account.account_name] = 'default:' + primary + ':' + valid + email_server
    return all_email_data
    
def usage():
    print """Usage: dump_email_data.py
    -f, --file    : File to write.
    """
    sys.exit(0)

def main():
    global db, constants, account
    global logger, outfile, person

    outfile = None
    logger = Factory.get_logger("cronjob")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:',
                                   ['file='])
    except getopt.GetoptError:
        usage()

    dryrun = False
    for opt, val in opts:
        if opt in ('-f', '--file'):
            outfile = val

    if outfile is None:
        outfile = '/cerebrum/var/cache/MAIL/mail_data.dat'

    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    email_data = generate_email_data()
    write_email_file(email_data, outfile)

if __name__ == '__main__':
    main()

