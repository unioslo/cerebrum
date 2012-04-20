#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 University of Oslo, Norway
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
A script for updating the reservations from being made public on www.uio.no.
A person should be considered as reserved when:

    - The person does not have any co.trait_public_reservation
    - The person has co.trait_public_reservation and numval=1

A person should not be considered as reserved when:

    - The person has co.trait_public_reservation and numval=0

This is to prevent publishing reserved people if the script fails to run for
some time. TBD: someone should decide if this is the right behaviour.

For now, person traits are used for tagging reserved persons. In the future,
there should probably exist some reservation table for different kinds of
reservations.
"""
import sys, getopt
from mx.DateTime import now

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="update_publication_reservations")
pe = Factory.get('Person')(db)
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)
co = Factory.get('Constants')(db)
logger = Factory.get_logger('cronjob')
count_resrv_true = count_resrv_false = 0


def usage(exitcode=0):
    print "Usage: %s [--commit]" % sys.argv[0]
    print
    print __doc__
    sys.exit(exitcode)

def process(with_commit=False):
    logger.info("Starting update_publication_reservations")
    logger.info("Harvesting data")

    employees  = get_employees()
    logger.debug('%d employees found', len(employees))
    students   = get_students()
    logger.debug('%d students found', len(students))

    sapmembers = get_members('SAP-elektroniske-reservasjoner')
    logger.debug('%d members from SAP reservations', len(sapmembers))
    fsmembers  = get_members('FS-aktivt-samtykke')
    logger.debug('%d members from FS consent', len(fsmembers))

    global reservations
    logger.debug('%d reservations found in db', len(reservations))

    logger.info("Iterate over all persons")
    already_processed = set()
    for row in pe.search():
        # note that people can be returned several times by search()
        person_id = row['person_id']
        if person_id in already_processed:
            continue
        already_processed.add(person_id)
        
        if person_id in employees:
            set_reservation(person_id, person_id in sapmembers)
        elif person_id in students:
            set_reservation(person_id, person_id not in fsmembers)
        else:
            set_reservation(person_id, True)
    logger.debug("%d persons got reserved", count_resrv_true)
    logger.debug("%d persons got unreserved", count_resrv_false)
    if with_commit:
        db.commit()
        logger.info('Commited changes')
    else:
        db.rollback()
        logger.info('Rolled back changes')
    logger.info("update_publication_reservations done")

def set_reservation(person_id, value=True):
    """Set a reservation on or off for a given person. Checks the already set
    reservations first, to speed up the process."""
    global reservations
    if value and reservations.get(person_id, -1) == 1:
        logger.debug2('person_id=%s already reserved', person_id)
        return True
    if not value and reservations.get(person_id, -1) == 0:
        logger.debug2('person_id=%s already not reserved', person_id)
        return True
    logger.debug2("Setting reservation to %s for person_id=%s" % (bool(value),
                                                                  person_id))
    pe.clear()
    pe.find(person_id)
    pe.populate_trait(code=co.trait_public_reservation, date=now(),
                      numval=int(bool(value)))
    pe.write_db()
    global count_resrv_true, count_resrv_false
    if value:
        count_resrv_true += 1
    else:
        count_resrv_false += 1
    # TODO: commit after each update?

def get_employees():
    """Returns a set with person_id for all that are considered employees in
    context of publication."""
    return set(row['person_id'] for row in
            pe.list_affiliations(affiliation=(co.affiliation_ansatt,
                                              co.affiliation_tilknyttet),
                                 source_system=co.system_sap) 
            if row['status'] != co.affiliation_tilknyttet_fagperson)

def get_students():
    """Returns a set with person_id for all that are considered students in
    context of publication."""
    return set(row['person_id'] for row in
            pe.list_affiliations(status=(co.affiliation_status_student_aktiv,
                                         co.affiliation_status_student_emnestud,
                                         co.affiliation_status_student_drgrad),
                                 source_system=co.system_fs))

def get_members(groupname):
    """Returns a set with person_id of all person members of a given group."""
    rows = gr.search(name=groupname)
    group_id = rows[0]['group_id']
    return set(row['member_id'] for row in gr.search_members(group_id=group_id,
                                                member_type=co.entity_person))

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['help', 'commit'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    with_commit = False

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--commit',):
            with_commit = True

    global reservations
    reservations = dict((row['entity_id'], row['numval']) for row in pe.list_traits(
                                            code = co.trait_public_reservation))

    process(with_commit = with_commit)
