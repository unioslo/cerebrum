#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

import getopt
import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

def usage():
    print """Usage: email_domains.py -f filename
                    email_domains.py -d domainname -c ou_id
    -d, --domain  : register domain name in cerebrum
    -f, --file    : parse file and register domains in cerebrum
                    (one domain name per line)
    -c, --connect : ou_id to connect to
    -a, --all     : connect a domain to all ou's registered in cerebrum  
    """
    sys.exit(0)

def main():
    global db, logger
    
    logger = Factory.get_logger("console")    
    db = Factory.get("Database")()
    account = Factory.get("Account")(db)
    const = Factory.get("Constants")(db)
    db.cl_init(change_program="email_dom")
    creator = Factory.get("Account")(db)
    creator.clear()
    creator.find_by_name('bootstrap_account')
    infile = None
    reg_dom = connect = all = False
    all_ous = []
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:d:c:a',
                                   ['file=', 'domain=',
                                    'connect=', 'all'])
    except getopt.GetoptError:
        usage()

    for opt, val in opts:
        if opt in ('-d', '--domain'):
            reg_dom = True
            dom_name = val
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-c', '--connect'):
            if not reg_dom:
                logger.error('You need to use -d option as well.')
                sys.exit(1)
            connect = True
        elif opt in ('-a', '--all'):
            if not reg_dom:
                logger.error('You need to use -d option as well.')
                sys.exit(1)
            all = True

    if not reg_dom and infile == None:
        usage()

    if reg_dom:
        if infile:
            logger.error('Cannot use both -d and -f options.')
            sys.exit(1)
        process_domain(dom_name, connect)

    if infile:
        process_line(infile)

    if all:
        ou = Factory.get("OU")(db)
        all_ous = ou.list_all(filter_quarantined=True)

        for i in all_ous:
            process_domain(dom_name, i['ou_id'])
            
    db.commit()
    
def process_line(infile):
    stream = open(infile, 'r')        

    for l in stream:
        process_domain(str(l.strip()), False)
    stream.close()
    
def process_domain(dom, conn):
    edom = Email.EmailDomain(db)
    edom.clear()
    ou = Factory.get("OU")(db)
    ou.clear()

    try:
        edom.find_by_domain(dom)
    except Errors.NotFoundError:
        logger.info('No such domain %s found. Creating it!', dom)
        edom.populate(dom, 'E-mail domain')
        edom.write_db()
    if conn:
        try:
            ou.find(int(conn))
        except Errors.NotFoundError:
            logger.error('No such OU %s!', conn)
            sys.exit(1)
        connect_domain_ou(ou.entity_id, edom.email_domain_id)
        
def connect_domain_ou(ou_id, dom_id):
    ee_dom = Email.EntityEmailDomain(db)
    ee_dom.clear()
    try:
        ee_dom.find(ou_id)
    except Errors.NotFoundError:
        eed.populate_email_domain(dom_id)
        eed.write_db()

            
if __name__ == '__main__':
    main()
