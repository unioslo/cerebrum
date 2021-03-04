#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011, 2012 University of Oslo, Norway
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

"""Script for setting person traits for being reserved from publication.

A person should be considered as reserved when:

    - The person does not have any co.trait_public_reservation
    - The person has co.trait_public_reservation and numval is not 0

A person should *not* be considered as reserved *only* when:

    - The person has co.trait_public_reservation and numval=0

This is to prevent publishing reserved people if the script fails to run for
some time. TBD: someone should decide if this is the right behaviour.

TODO: maybe just remove the trait for those marked as reserved, as this makes
the same meaning? This puts less data in Cerebrum, and the list_trait functions
get a bit faster.

For now, person traits are used for tagging reserved persons. In the future,
there should probably exist some reservation tables in Cerebrum for different
kinds of reservations and acceptance.

The script tags people in the following order:

1. If the person is an employee:
   - Gets reserved if a member of SAP-elektroniske-reservasjoner.
   - Otherwise reservation is removed.

2. If the person is not an employee, but is a student:
   - Reservation is removed if a member of FS-aktivt-samtykke.
   - Otherwise gets reserved.

3. Everyone else, i.e. those which are not employees or students, gets reserved.

"""

from __future__ import unicode_literals

import sys
import getopt

from Cerebrum.Utils import Factory
from Cerebrum.utils.date import now

reservations = None

db = Factory.get('Database')()
db.cl_init(change_program="update_publication_reservations")
pe = Factory.get('Person')(db)
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)
co = Factory.get('Constants')(db)
logger = Factory.get_logger('cronjob')
count_resrv_true = count_resrv_false = 0


def usage(exitcode=0):
    print """Usage: %(scriptname)s --employee AFFS --student AFFS [--commit]

    %(doc)s

    Parameters:

    --commit        For actually committing the changes. Dryruns without it.

    --employee AFFS Comma separated list of affiliations persons must have to be
                    considered employees. Employees are not reserved unless they
                    are members of the group 'SAP-elektroniske-reservasjoner'.

                    Example: ANSATT,TILKNYTTET/gjesteforsker

                    Note that one could remove statuses of given affiliations by
                    adding - in front of the status. Useful e.g. for "I want all
                    ANSATT affiliations, but not ANSATT/bilag", which would give
                    you: ANSATT,-ANSATT/bilag. Note that this only works for
                    statuses for the given affiliations, you wouldn't be able to
                    get all ANSATT affiliation, but not STUDENT/aktiv, as that
                    does not belong to the affiliation ANSATT.

    --student AFFS  The affiliations a person must have to be considered a
                    student. All students are reserved, unless they are members
                    of the group 'FS-aktivt-samtykke'.

                    Example: STUDENT/aktiv,STUDENT/opptak,STUDENT/drgrad

                    Note that employees override student settings, so students
                    that also are employees are only considered employees.

                    Note that one could remove statuses of given affiliations by
                    adding '-' in front of the status. Useful e.g. for "I want
                    all STUDENT affiliations, except STUDENT/fagperson", which
                    would give: STUDENT,-STUDENT/fagperson. Note that this only
                    works for statuses for the given affiliations, you wouldn't
                    be able to get all STUDENT affiliation, but not
                    TILKNYTTET/gjesteforsker, as that does not belong to the
                    affiliation STUDENT.

    --help          Show this and quit.

    """ % {'scriptname': sys.argv[0],
           'doc': __doc__}
    sys.exit(exitcode)


def process(emplaffs, studaffs, with_commit=False):
    logger.info("Starting update_publication_reservations")
    logger.info("Harvesting data")

    logger.debug('Employee affiliations: %s', emplaffs)
    employees = get_employees(emplaffs)
    logger.debug('%d employees found', len(employees))

    logger.debug('Student affiliations: %s', studaffs)
    students = get_students(studaffs)
    logger.debug('%d students found', len(students))

    sapmembers = get_members('SAP-elektroniske-reservasjoner')
    logger.debug('%d members from SAP reservations', len(sapmembers))
    fsmembers = get_members('FS-aktivt-samtykke')
    logger.debug('%d members from FS consent', len(fsmembers))

    global reservations
    reservations = dict((row['entity_id'], row['numval']) for row in
                        pe.list_traits(code=co.trait_public_reservation))
    logger.debug('%d reservation traits found in db', len(reservations))
    is_true = is_false = 0
    for r in reservations:
        if reservations[r]:
            is_true += 1
        else:
            is_false += 1
    logger.debug('  numval=0: %7d reservations', is_false)
    logger.debug('  numval>0: %7d reservations', is_true)

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
    pe.populate_trait(code=co.trait_public_reservation,
                      date=now(), numval=int(bool(value)))
    pe.write_db()
    global count_resrv_true, count_resrv_false
    if value:
        count_resrv_true += 1
    else:
        count_resrv_false += 1
    # TODO: commit after each update?


def get_employees(affs):
    """Returns a set with person_id for all that are considered employees in
    context of publication.

    """
    affiliations = affs[0] or None
    statuses = affs[1] or None
    return set(row['person_id'] for row in
               pe.list_affiliations(affiliation=affiliations, status=statuses,
                                    source_system=co.system_sap)
               if row['status'] not in affs[2])


def get_students(affs):
    """Returns a set with person_id for all that are considered students in
    context of publication."""
    affiliations = affs[0] or None
    statuses = affs[1] or None
    return set(row['person_id'] for row in
               pe.list_affiliations(affiliation=affiliations, status=statuses,
                                    source_system=co.system_fs)
               if row['status'] not in affs[2])


def get_members(groupname):
    """Returns a set with person_id of all person members of a given group."""
    rows = gr.search(name=groupname)
    group_id = rows[0]['group_id']
    return set(row['member_id'] for row in gr.search_members(
        group_id=group_id,
        member_type=co.entity_person))


def update_affiliations(affstring, existing):
    """Parse a string with affiliations and statuses and add it to the list of
    L{existing} affs and statuses. The list must contain three elements:

     - A list of affiliation constants.
     - A list of status constants.
     - A list of negative statuses, i.e. those that should be ignored.

    The negative lists are useful e.g. for finding all STUDENT affiliations but
    not the STUDENT/fagperson.

    """
    affs, statuses, notstatuses = existing

    for aff in affstring.split(','):
        negate = False
        if aff[0] == '-':
            negate = True
            aff = aff[1:]
        try:
            aff, status = aff.split('/', 1)
        except ValueError:
            if negate:
                raise Exception(
                    "Negative affiliations isn't logical, only statuses")
            affs.append(int(co.PersonAffiliation(aff)))
        else:
            if negate:
                notstatuses.append(int(co.PersonAffStatus(aff, status)))
            else:
                statuses.append(int(co.PersonAffStatus(aff, status)))

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['help',
                                    'commit',
                                    'student=',
                                    'employee='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    with_commit = False
    studaffs = [[], [], []]
    emplaffs = [[], [], []]

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--commit',):
            with_commit = True
        elif opt in ('--student',):
            update_affiliations(val, studaffs)
        elif opt in ('--employee',):
            update_affiliations(val, emplaffs)
        else:
            print "Unknown arg: %s" % opt
            usage(1)

    if not emplaffs:
        print "No employee affiliations given."
        usage(1)
    if not studaffs:
        print "No student affiliations given."
        usage(1)

    process(with_commit=with_commit, studaffs=studaffs, emplaffs=emplaffs)
