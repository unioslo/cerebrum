#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 University of Oslo, Norway
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

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

"""This program generates a report of persons that are not registered in an
authoritative system (e.g. SAP or FS), but still has an active account.  An
active account is simply an account that is not expired, regardless of home is
set.

The script is sorting the persons by OUs. It can work at fakultet, institutt and
avdeling level. Those that does not even have a manual affiliation are sorted as
'unregistered'.

Example of use:

    generate_unregistered_report.py -f /tmp/unregistered_report.txt \
            --ignore-students --ignore-sko 78,79
"""

db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")
constants = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
ou = Factory.get('OU')(db)

# List of the authoritative systems
auth_sources = filter(None, (constants.human2constant(x, constants.AuthoritativeSystem) 
        for x in getattr(cereconf, "BOFHD_AUTH_SYSTEMS", ())))

# Counters:
nr_hasaccounts = 0  # number of people that has at least one account, registered or not
nr_manually = 0     # number of people with manually affiliations only


def usage(exitcode = 0, message = None):

    if message is not None:
        print "\n%s" % message

    print """\nUsage: %s [options]

    -f, --file          The file to send the report to, outputted to the console
                        if no file is given.

    --summary           Only print summary of the number of unregistered
                        persons.
    --faculties         Only the faculty level of OUs are being searched.
    --institutes        Only the faculty and institute OUs are being searched.

                        If neither --faculties nor --institutes is used every ou
                        is searched through.

    --ignore-students   Since a lot of students are unregistered before they're
                        disabled, this option can be used to ignore these
                        persons.
    --ignore-quarantined
    --ignore-sko        If some OUs are to be ignored. Can be a commaseparated 
                        list of stedkoder. Can add sub-OUs by only adding the 
                        first digits in the sko. E.g. '33' gives all OUs at 
                        USIT.

    -h, --help          See this help info and exit.

    """ % sys.argv[0]

    sys.exit(exitcode)


def ou_name(ou):
    return ou.get_name_with_language(name_variant=constants.ou_name,
                                     name_language=constants.language_nb,
                                     default="")
# end ou_name

    

def process_report(stream, ou_level = 0, summary = False, ignore_sko = (),
                        ignore_students = False, ignore_quarantined = False):
    '''
    Generating the report and send it to logger.
    '''

    logger.info("Generating report of persons not registered in auth_source")

    # Dict with the unregistered persons
    # First dimension has stedkode as keys, the deeper key gives the persons 
    # entity_id, which at last points at the persons accountnames. The boolean
    # value for each account is set to False if the account does not have a home 
    # set.
    #
    #   unregistered => sko => person_id => account_id => (bool) Home
    # 
    # The special case ou_id = None lists persons without any affiliation.
    unregistered = {None: {}}

    # OUs
    institutt = None
    avdeling = None
    if ou_level >= 1: institutt = 0
    if ou_level >= 2: avdeling = 0
    # else: every ou

    # Get a list of all OUs we want to search through on the form
    # ((ou_id, stedkode), (ou_id, stedkode), ...)
    all_ous = set((row['ou_id'], "%02d%02d%02d" % (row['fakultet'],
                                                   row['institutt'],
                                                   row['avdeling']))
                          for row in ou.get_stedkoder(institutt=institutt, 
                                                      avdeling=avdeling))
    # Create a dict of the ous and skos, but without those specified in 
    # ignore_sko (if any):
    ous = dict(x for x in all_ous if not any(sko_filter in x[1]
                                          for sko_filter in ignore_sko))
    logger.debug("Found %d OUs to sort by" % len(ous))

    all_persons = person.list_persons()
    logger.debug("%d persons found" % len(all_persons))

    for pid in all_persons:
        process_person(pid=int(pid['person_id']), unregistered=unregistered,
                       ous=ous, ignore_students=ignore_students,
                       ignore_quarantined=ignore_quarantined)


    logger.debug("Search is done, go for report")

    stream.write("===== Summary =====\n")
    stream.write("Persons found:                    %8d\n" % len(all_persons))
    stream.write("Persons with accounts:            %8d\n" % nr_hasaccounts) 
    stream.write(" - With manual affiliations only: %8d\n" % nr_manually)
    stream.write(" - Without any affiliation:       %8d\n" % len(unregistered[None]))
    stream.write("\n")
    if ignore_students: stream.write("Filter: Ignoring students\n")
    if ignore_quarantined: stream.write("Filter: Ignoring quarantined\n")
    if ignore_sko: stream.write("Filter: Ignoring sko(prefix): %s\n" % ignore_sko)
    stream.write("\n")

    if summary:
        stream.write("===== Manually registrations =====\n")
        for sko in sorted(unregistered):
            if sko is not None and len(unregistered[sko]) > 0:
                ou.clear()
                ou.find_stedkode(fakultet=sko[:2], institutt=sko[2:4], avdeling=sko[4:6], 
                        institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
                stream.write(" %8d affiliations on %02d%02d%02d (%s)\n" %
                             (len(unregistered[sko]), ou.fakultet, ou.institutt,
                              ou.avdeling, ou_name(ou)))
    else:
        for sko in sorted(unregistered):

            # Persons without any affiliation
            if sko is None:
                stream.write("\n----- Unregistered persons (no affiliations) -----\n")
            else:
                ou.clear()
                ou.find_stedkode(fakultet=sko[:2], 
                                 institutt=sko[2:4], 
                                 avdeling=sko[4:6], 
                                 institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
                stream.write("\n----- %02d%02d%02d (%s) -----\n" % (ou.fakultet, 
                                                                    ou.institutt,
                                                                    ou.avdeling, 
                                                                    ou_name(ou)))

            for pid in unregistered[sko]:
                person.clear()
                person.find(pid)
                acstrings = ()
                for ac, home in unregistered[sko][pid].items():
                    if home:
                        acstrings += (str(ac),)
                    else:
                        acstrings += ("%s (NOHOME)" % ac,)

                stream.write("%d - %s - accounts: %s\n" % (pid, 
                    person.get_name(constants.system_cached, constants.name_full),
                                ', '.join(acstrings)))

    logger.info("Generating report of persons not registered in auth_source - done")


def process_person(pid, unregistered, ous, ignore_students=False,
                                           ignore_quarantined=False):
    '''
    Checks if a given person validates as an unregistered person, and then adds
    it to the list of unregistered.

    Returns true only if the person qualifies as unregistered and is put into
    the unregistered list.
    '''

    global nr_hasaccounts, nr_manually

    accs = [ac[0] for ac in account.list_accounts_by_owner_id(owner_id=pid)]

    if len(accs) == 0:
        return False

    nr_hasaccounts += 1

    # Check for authoritative systems, skipping person if found
    affs = person.list_affiliations(person_id=pid)
    for aff in affs:
        if aff['source_system'] in auth_sources:
            return False

    # Get the account names
    accounts = {}
    for ac in accs:
        account.clear()
        account.find(ac)
        # Students should only have _one_ account, so if a student
        # has several accounts he/she should still be listed
        if ignore_students and len(accs) == 1:
            # Check for a STUDENT-affiliation on the account
            if constants.affiliation_student in [type['affiliation'] for type in 
                                                   account.get_account_types()]:
                return False
        if ignore_quarantined and account.get_entity_quarantine(only_active=True):
            return False

        accounts[account.account_name] = bool(account.get_homes())

    # Unregistered persons
    if len(affs) == 0:
        unregistered[None][pid] = accounts
        return True

    nr_manually += 1

    # Finding and sorting by OU
    for aff in affs:
        if aff['ou_id'] in ous:
            unregistered.setdefault(ous[aff['ou_id']], {})[pid] = accounts
        # else: skip the person
    return True

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                "hf:s:",
                ["help", 
                 "file=",
                 "summary",
                 "faculties",
                 "ignore-students",
                 "ignore-quarantined",
                 "ignore-sko=",
                 "institutes"])
    except getopt.GetoptError:
        usage(1)

    outputstream = sys.stdout
    ou_level = 0
    summary = False
    ignore_students = ignore_quarantined = False
    ignore_sko = []

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-f', '--file'):
            outputstream = open(val, 'w')
        elif opt == '--summary':
            summary = True
        elif opt == '--faculties':
            ou_level = 2
        elif opt == '--institutes':
            ou_level = 1
        elif opt == '--ignore-students':
            ignore_students = True
        elif opt == '--ignore-quarantined':
            ignore_quarantined = True
        elif opt == '--ignore-sko':
            ignore_sko = val.split(',')
        else:
            usage(1, "Unknown parameter '%s'" % opt)

    process_report(outputstream, ou_level=ou_level, summary=summary, 
                        ignore_students=ignore_students,
                        ignore_quarantined=ignore_quarantined,
                        ignore_sko=ignore_sko)

    if outputstream not in (sys.stdout, sys.stderr):
        outputstream.close()

if __name__ == '__main__':
    main()

