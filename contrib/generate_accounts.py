#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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

"""Script for creating accounts for persons by given criterias.

Note that a person will only get one account max. TODO: this should be able to
override by an argument.

TODO: add functionality for only affecting new person affiliations instead, e.g.
only new employeed from the last 7 days. This is usable e.g. for UiO.
"""

import sys
import os.path
import getopt
from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum import Errors, Constants
from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
db.cl_init(change_program="generate_accounts")
co = Factory.get('Constants')(db)

def usage(exitcode=0):
    print """Usage: %(file)s --aff AFFS [options]

    %(doc)s

    --aff AFFILIATIONS      Only persons with the given affiliations and/or
                            statuses will get an account. Can be comma
                            separated. Example:

                                ANSATT,TILKNYTTET/ekstern,STUDENT/fagperson

    --commit                Actually commit the work. The default is dryrun.

    -h --help               Show this and quit.
    """ % {'file': os.path.basename(sys.argv[0]),
           'doc': __doc__}
    sys.exit(exitcode)

def str2aff(affstring):
    """Get a string with an affiliation or status and return its constant."""
    aff = affstring.split('/', 1)
    if len(aff) > 1:
        aff = co.PersonAffStatus(aff[0], aff[1])
    else:
        aff = co.PersonAffiliation(affstring)
    try:
        int(aff)
    except Errors.NotFoundError:
        raise Exception("Unknown affiliation: %s" % affstring)
    return aff

def create_account(pe, ac, creator_id):
    """Give a person a new account."""
    ac.clear()
    # TODO: not sure if usernames should be handled by create() instead
    name = (pe.get_name(co.system_cached, co.name_first),
            pe.get_name(co.system_cached, co.name_last))
    names = ac.suggest_unames(domain=co.account_namespace, fname=name[0], lname=name[1])
    if len(names) < 1:
        logger.warn('Person %d has no name, skipping', pe.entity_id)
        return
    ac.create(name=names[0], owner_type=pe.entity_type, owner_id=pe.entity_id,
              np_type=None, creator_id=creator_id)
    logger.debug("Account %s created", names[0])

    # give the account the person's affiliations
    for row in pe.list_affiliations(person_id=pe.entity_id):
        ac.set_account_type(ou_id=row['ou_id'], affiliation=row['affiliation'])
        ac.write_db()
        logger.debug("Gave %s aff %s to ou_id=%s", names[0],
                     co.PersonAffiliation(row['affiliation']), row['ou_id'])
    return True

def process(affiliations, commit=False):
    """Go through the database for new persons and give them accounts."""
    logger.info("generate_accounts started")

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator_id = ac.entity_id

    # cache those who already has an account
    has_account = set(row['owner_id'] for row in
                      ac.search(owner_type=co.entity_person, expire_start=None))
    logger.debug("%d people already have an account" % len(has_account))

    # sort by affiliation and status
    statuses = tuple(af for af in affiliations 
                     if isinstance(af, Constants._PersonAffStatusCode))
    affs = tuple(af for af in affiliations 
                 if isinstance(af, Constants._PersonAffiliationCode))

    if statuses:
        for row in pe.list_affiliations(status=statuses):
            if row['person_id'] in has_account:
                continue
            pe.clear()
            pe.find(row['person_id'])
            create_account(pe, ac, creator_id)
            has_account.add(row['person_id'])
    if affs:
        peaffs = pe.list_affiliations(affiliation=affs)
        logger.debug("%d affiliations to process" % len(peaffs))
        for row in peaffs:
            if row['person_id'] in has_account:
                continue
            pe.clear()
            pe.find(row['person_id'])
            create_account(pe, ac, creator_id)
            has_account.add(row['person_id'])

    if commit:
        db.commit()
        logger.info("Changes commited")
    else:
        db.rollback()
        logger.info("Rolled back changes")
    logger.info("generate_accounts done")

def main():
    opts, junk = getopt.getopt(sys.argv[1:], "h",
                               ("help",
                                "aff=",
                                "commit"))
    affiliations = list()
    commit = False

    for opt, val in opts:
        if opt in ("-h", "--help",):
            usage()
        elif opt in ("--aff",):
            affiliations.extend((str2aff(a) for a in val.split(',')))
        elif opt in ("--commit"):
            commit = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    if not affiliations:
        print "No affiliations given"
        usage(1)
    process(affiliations, commit)

if __name__ == '__main__':
    main()
