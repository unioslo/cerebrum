#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from Cerebrum.modules.EmailConstants import _EmailDomainCategoryCode
from Cerebrum.Constants import _PersonAffiliationCode


def usage():
    print("""Usage: email_domains.py -f filename
                    email_domains.py -d domainname -c ou_id
                    email_domains.py -d domainname -k uidaddr -c ou_id -i STUDENT
    -d, --domain     : register domain name in cerebrum
    -f, --file       : parse file and register domains in cerebrum
                       (one domain name per line)
    -c, --connect    : ou_id to connect to
    -a, --all        : connect a domain to all ou's registered in cerebrum
    -k, --category   : set category for domain. (only -d option)
    -i, --affiliation: set affiliation for connected ou_id
                       (only -c option)
    """)
    sys.exit(0)


def main():
    global db, const, logger
    
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
    category = aff = False
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:d:c:ak:i:',
                                   ['file=', 'domain=',
                                    'connect=', 'all',
                                    'category=', 'affiliation='])
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
            connect = val
        elif opt in ('-a', '--all'):
            if not reg_dom:
                logger.error('You need to use -d option as well.')
                sys.exit(1)
            all = True
        elif opt in ('-k', '--category'):
            if not reg_dom:
                logger.error('Only supported with the -d option.')
                sys.exit(1)
            category = val
        elif opt in ('-i', '--affiliation'):
            if not connect:
                logger.error('Only supported with the -c option.')
                sys.exit(1)
            aff = val
    
    if not reg_dom and infile is None:
        usage()

    if connect:
        try:
            tmp = connect.split(',')
            connect = tmp
        except:
            [connect]
        
    if reg_dom:
        if infile:
            logger.error('Cannot use both -d and -f options.')
            sys.exit(1)
        process_domain(dom_name, connect, category, aff)

    if infile:
        process_line(infile)

    if all:
        ou = Factory.get("OU")(db)
        all_ous = ou.search(filter_quarantined=True)

        for i in all_ous:
            process_domain(dom_name, i['ou_id'])
    db.commit()


def process_line(infile):
    stream = open(infile, 'r')        

    for l in stream:
        process_domain(str(l.strip()), False)
    stream.close()


def process_domain(dom, conn, cat, aff):
    edom = Email.EmailDomain(db)
    edom.clear()
    ou = Factory.get("OU")(db)
    ou.clear()

    c_cat = None
    if cat:
        for c in dir(const):
            tmp = getattr(const, c)
            if isinstance(tmp, _EmailDomainCategoryCode) and str(tmp) == cat:
                c_cat = tmp
        if not c_cat:
            logger.error('Could not find category "%s". Exiting.', cat)
            sys.exit(1)

    c_aff = None
    if aff:
        for c in dir(const):
            tmp = getattr(const, c)
            if isinstance(tmp, _PersonAffiliationCode) and str(tmp) == aff:
                c_aff = tmp
        if not c_aff:
            logger.error('Could not find affiliation "%s". Exiting.', aff)
            sys.exit(1)
    try:
        edom.find_by_domain(dom)
    except Errors.NotFoundError:
        logger.info('No such domain %s found. Creating it!', dom)
        edom.populate(dom, 'E-mail domain')
        edom.write_db()
    if conn:
        for o in conn:
            try:
                ou.clear()
                ou.find(int(o))
            except Errors.NotFoundError:
                logger.error('No such OU %s!', o)
                sys.exit(1)
            connect_domain_ou(ou.entity_id, edom.entity_id, c_aff)
    if c_cat:
        # Hack to get a hit when doing 'in'
        if (int(c_cat),) in edom.get_categories():
            logger.info('Email_category "%s" already populated.', cat)
        else:
            edom.add_category(c_cat)
            logger.info('Email_category "%s" added.', cat)


def connect_domain_ou(ou_id, dom_id, c_aff):
    ee_dom = Email.EntityEmailDomain(db)
    ee_dom.clear()
    try:
        ee_dom.find(ou_id, c_aff)
    except Errors.NotFoundError:
        ee_dom.populate_email_domain(dom_id, c_aff)
        ee_dom.write_db()

            
if __name__ == '__main__':
    main()
