#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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
This script should be used for reorganisations of the OUs.

It will look up all users with a given (faculty, institute,
affiliation), and add any affiliations the user's owner has which
matches the same criteria, with the same priority as the old
affiliation, thereby pushing it one notch down.

ie., if 130105 is reorganised into 131008, the person will hopefully
have _both_ affiliations in a transition period (this script
requires this to be true).  we add affiliations to persons
automatically, but not to users.  so this script will look up every
user with affiliation 130105, and then add the affiliation 131008
_iff_ its owner (the person) has that affiliation.
"""


import cerebrum_path
import cereconf

import getopt
import sys

from Cerebrum import Errors
from Cerebrum.Utils import Factory

def usage():
    print """Bruk: nye_sko.py [flagg]
    -f fakultet      tosifra talkode for fakultet
    -i institutt     tosifra talkode for institutt
    -a affiliation   namn på affiliation til brukar ("STUDENT", "ANSATT" osv.)
    -p affiliation   namn på affiliation til person (default: same som -a)

    fakultet er obligatorisk."""
    sys.exit(64)

def reorganise_users(fac, inst=None, aff=None, persaff=None):
    done = {}
    for ou_id in list_ous(fac, inst):
        ou.clear()
        ou.find(ou_id)
        logger.debug("Doing OU %02d%02d%02d" % (ou.fakultet, ou.institutt,
                                                ou.avdeling))
        for r in acc.list_accounts_by_type(ou_id=ou_id,
                                           affiliation=aff):
            if r.account_id in done:
                continue
            done[r.account_id] = 1
            user.clear()
            user.find(r.account_id)
            got_aff = {}
            for r2 in user.get_account_types():
                if persaff and r2.affiliation <> persaff:
                    continue
                got_aff[(r2.ou_id,r2.affiliation)] = 1
            for r2 in person.list_affiliations(person_id=r.person_id,
                                               affiliation=persaff):
                assert r2.affiliation == persaff
                if (int(r2.ou_id), int(r2.affiliation)) in got_aff:
                    continue
                ou.clear()
                ou.find(r2.ou_id)
                # perhaps we should allow this fac to be different from
                # the source fac.  (likewise for inst below)
                if ou.fakultet <> fac:
                    continue
                if inst and ou.institutt <> inst:
                    continue
                logger.info("...... %-8s adding %02d%02d%02d %d %d" %
                            (user.account_name, ou.fakultet, ou.institutt,
                             ou.avdeling, r2.affiliation, r.priority))
                user.set_account_type(r2.ou_id, r2.affiliation, r.priority)
            db.commit()

def list_ous(fac, inst=None):
    ret = []
    for r in ou.get_stedkoder(fakultet=fac, institutt=inst):
        ret.append(r.ou_id)
    return ret

db = Factory.get('Database')()
db.cl_init(change_program='nye_sko')
co = Factory.get('Constants')(db)
ou = Factory.get("OU")(db)
acc = Factory.get("Account")(db)
user = Factory.get("Account")(db)
person = Factory.get("Person")(db)
logger = Factory.get_logger("cronjob")

try:
    opts, args = getopt.getopt(sys.argv[1:], "f:i:a:p:",
                               ["fakultet=", "institutt=", "affiliation=",
                                "person-affiliation="])
except getopt.GetoptError:
    usage()

fac = None
inst = None
aff = None
persaff = None
for o, val in opts:
    if o in ('-f', '--fakultet'):
        fac = int(val)
    elif o in ('-i', '--institutt'):
        inst = int(val)
    elif o in ('-a', '--affiliation'):
        aff = int(co.PersonAffiliation(val))
    elif o in ('-p', '--person-affiliation'):
        persaff = int(co.PersonAffiliation(val))
    else:
        usage()

if not persaff:
    persaff = aff

if not fac:
    usage()

reorganise_users(fac, inst, aff, persaff)

# arch-tag: a906182f-560e-446e-b4c4-61dfbcdacca8
