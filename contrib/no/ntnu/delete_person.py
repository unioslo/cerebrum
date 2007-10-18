#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import sys
import cerebrum_path
import cereconf
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

import getopt
import logging
import time
import os
import traceback

import locale
locale.setlocale(locale.LC_ALL,'nb_NO')
dryrun = verbose = cascade = False
db = Factory.get('Database')()
db.cl_init(change_program='Manual')
const = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)

def delete_person(entity,cascade=False):
    print "Deleting Cerebrum-person with entity %s" % entity
    try:
        person.find(entity)
    except Errors.NotFoundError:
        print "Person with entity %s not found. Exiting.." % entity
        sys.exit(0)
    try:
        person.delete()
    except db.IntegrityError,ie:
        if cascade:
            # Remove traits
            for t in person.get_traits():
                person.delete_trait(t)
                person.write_db()
            # Remote spreads
            for s in person.get_spread():
                person.delete_spread(s)
                person.write_db()
            # Remove address
            for ea in person.get_entity_address():
                continue
                #person.delete_entity_address(ea.get('source_type'), ea.get('a_type'))
                #person.write_db()
            # Remove all affiliations
            for a in person.get_affiliations():
                ou = a.get('ou_id')
                affiliation = a.get('affiliation')
                source = a.get('source_system')
                person.delete_affiliation(ou_id, affiliation, source)
                person.write_db()
            # Remove contact info
            for c in person.get_contact_info():
                continue
                #person.delete_contact_info(source, type, pref='ALL')
                #person.write_db()
        else:
            print "Unable to delete person. Reason: %s" % str(ie)
            print "Run once more with cascade enabled"
            raise ie

def usage():
    print "RTFC"

def main():
    global dryrun,verbose,cascade
    opts,args = getopt.getopt(sys.argv[1:],
                       'hvdc',['help','personid=','cascade'])
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-c','--cascade'):
            cascade = True
        elif opt in ('-d','--dryrun'):
            dryrun = True
        elif opt in ('-v','--verbose'):
            verbose = True
        elif opt in ('--personid',):
            entity = val
            try:
                delete_person(entity,cascade)
            except:
                db.rollback()

            if dryrun:
                db.rollback()

if __name__ == '__main__':
    main()
