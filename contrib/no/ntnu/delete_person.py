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
import sys

import locale
locale.setlocale(locale.LC_ALL,'nb_NO')
dryrun = verbose = cascade = False
db = Factory.get('Database')()
db.cl_init(change_program='Manual')
const = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)


def check_commit(fun, *args, **kw):
    try:
        fun(*args, **kw)
    except db.IntegrityError, e:
        print 'Error while %s: %s' % (fun.func_name, str(e))
        db.rollback()
    else:
        if dryrun:
            db.rollback()
        else:
            db.commit()

def delete_person(entity):
    print "Deleting Cerebrum-person with entity %s" % entity
    person.clear()
    try:
        person.find(entity)
    except Errors.NotFoundError, e:
        print "Person with entity %s not found" % entity
        return
    do_delete_person(person)


def delete_person_by_externalid(id, type, source):
    print id, type, source
    print "Deleting Cerebrum-person with %s id %s" %  (type, id)
    person.clear()
    try:
        person.find_by_external_id(type, id, source)
    except Errors.NotFoundError, e:
        print "Person with id %s not found. Exiting.." % id
        return
    do_delete_person(person)
    
    

def do_delete_person(person):
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
        person.delete_entity_address(ea['source_type'], ea['a_type'])
        person.write_db()
    # Remove all affiliations
    for a in person.get_affiliations():
        ou_id = a['ou_id']
        affiliation = a['affiliation']
        source = a['source_system']
        person.delete_affiliation(ou_id, affiliation, source)
        person.write_db()
    # Remove contact info
    for c in person.get_contact_info():
        person.delete_contact_info(source, type, pref='ALL')
        person.write_db()
    person.delete()

def usage():
    print "RTFC"

def main():
    global dryrun,verbose,cascade
    opts,args = getopt.getopt(sys.argv[1:],
                       'hvdc',['help','dryrun', 'verbose',
                               'type=', 'source=', 'list=', 'personid='])
    type=None
    source=None
    delete_list=[]
    
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-d','--dryrun'):
            dryrun = True
        elif opt in ('-v','--verbose'):
            verbose = True
        elif opt in ('--type',):
            type = const.EntityExternalId(val)
            int(type)
        elif opt in ('--source',):
            source = const.AuthoritativeSystem(val)
            int(source)
        elif opt in ('--list',): 
            for line in open(val).readlines():
                delete_list.append(line.strip())
        elif opt in ('--personid',):
            delete_list.append(val)

    if type is not None:
        for i in delete_list:
            check_commit(delete_person_by_externalid, i, type, source)
    else:
        for i in delete_list:
            check_commit(delete_person, int(i))



if __name__ == '__main__':
    main()
