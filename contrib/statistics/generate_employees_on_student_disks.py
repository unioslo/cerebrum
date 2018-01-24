#! /usr/bin/env python
# -*- coding: utf-8 -*-
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

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors

"""This program reports employees that are placed on student disks.
Quarantines shown are active.

    The following functions are defined:
        main():
            Initializes database connections, parses command line parameters
            and starts other functions to collect data and generate a report.
        get_empl_on_student_disks():
            This function searches the database for accounts residing on disks
            that have the 'student_disk' trait set, while the accounts are owned
            by a person with an ansatt-affiliation, but without a student-
            affiliation.
        gen_employees_on_student_disk_report():
            Generate HTML report with the accounts found. This function can sort
            the result by SKO-code or by disk. Disk is the default.
        usage():
            Prints usage information.
        preamble():
            Print HTML preamble, for the report.

Overall flow of execution looks like:
    main():
        - Initializes database connections
        - Parses command line options
        - Starts 'get_empl_on_student_disks()'
        - Starts 'gen_employees_on_student_disk_report()'
        - Closes filehandle, then exits

    get_empl_on_student_disks():
        - Fetch spread from constants, and check that it is valid.
        - Collect a list of the disks from the database.
        - Iterate over disks in database:
            - If disk has the correct spread and has the 'student_disk' trait
                set, acquire a list of the users on the disk.
                - For each of the users on the disk:
                    - Lookup owner and check if it is a person
                    - Get affiliations and check if the person is ansatt and not
                        student. If so, add information (account name,
                        full name, disk path, affiliations and quarantines)
                        to our data structure.

    gen_affles_users_report():
        - Prints out the HTML preamble via the preamble() function
        - For each disk (or SKO) in our data structure:
            - Generate a table header
            - Loop over the accounts associated with the SKO or disk, and print
                rows of information.

"""

def usage(exitcode=0):
    print """Usage:
    %s [Options]

    Generate an html formatted report of accounts of employees that are
    residing on a student disk, although lacking student affiliation.

    Options:
    -o, --output      <file>     The file to print the report to. Defaults to stdout.
    -a, --arrange-by  [disk|sko] Arrange report by diskname or sko. Defaults to sko.
    -s, --spread      <spread>   Spread to filter users by. Defaults to NIS_user@uio.
    """ % sys.argv[0] 
    sys.exit(exitcode)


# This function searches each student-disk for accounts that
# are owned by persons that are not students, only employees.
def get_empl_on_student_disks(logger, filter_by_spread, ac, pe, di, en, co, ou, ou2sko):
   
    # We fetch the spread from constants, and check if it exists by comparing it
    # to itself.
    try:
        spread = co.Spread(filter_by_spread)
        spread == co.Spread(filter_by_spread)
    except Errors.NotFoundError:
        logger.error('The spread %s is invalid' % filter_by_spread)
        sys.exit(1)

    # Variables to store results from "search"
    # 'empl_on_stud_disk' are employees (only employee affilation) that are
    # located on a student disk.
    #
    # The variable uses the SKO-code as a key, and the corresponding value
    # is a list of dict's containing info about each user.
    report = {}

    # Stats
    no_disks = 0
    no_accounts = 0

    # Getting a list of all disks, and iterating over it
    disks = di.list()
    for d in disks:
            # We collect the entity of the disk, need this to check the
            # disk traits (if it is a student disk). We also check the
            # spread of the disk, we'll only want NIS_user@uio.
            en.clear()
            en.find(d['disk_id'])
            
            if d['spread'] == spread and \
                    co.trait_student_disk in en.get_traits():
                no_disks += 1
                en.clear()
                
                # For each of the users on the disk (filtered on spread,
                # we don't want duplicates (i.e., if a user has NIS_user@uio
                # and NIS_user@ifi, it would show up two times (or four,
                # if we don't filter the stuff from di.list))).
                users = ac.list_account_home(disk_id=d['disk_id'], \
                        home_spread=spread)
                no_accounts = no_accounts + len(users)
                
                # Look up each of the accounts on the disk, and determine if it
                # is owned by a person or a group (we only process accounts
                # owned by persons). Add them to report if appropriate.
                for u in users:
                    ac.clear()
                    pe.clear()
                    
                    # Lookup user and person
                    try:
                        ac.find(u['account_id'])
                    except Errors.NotFoundError:
                        logger.error('Can\'t find account_id = %d' % \
                                u['account_id'])
                        continue

                    # Some accounts are not personal (i.e, owned by group),
                    # we'll exclude these. We'll lookup the entity of the
                    # accounts owner, and check to see if this entity is a
                    # person.
                    en.clear()
                    en.find(ac.owner_id)
                    if en.entity_type == co.entity_person:
                        try:
                            pe.find(ac.owner_id)
                        except Errors.NotFoundError:
                            logger.error('Can\'t find person_id = %d' % \
                                    ac.owner_id)
                            continue

                        # Checking if this person is ansatt, and not student
                        affs = pe.get_affiliations()
                        if len(affs):
                            onl_emp = True
                            for a in affs:
                                if a['affiliation'] != co.affiliation_ansatt:
                                    onl_emp = False
                        else:
                            onl_emp = False


                        # If the person has ansatt affiliations and no student
                        # affiliations, add the username to the report-list.
                        # We also add some info about quarantines and
                        # affiliations. We only report this if the account
                        # hasn't been added earlier.
                        if onl_emp:
                            ou = affs[0]['ou_id']
                            aff_type = affs[0]['affiliation']

                            quar = ac.get_entity_quarantine(only_active=True)
                            quar_subset = {}
                            if len(quar):
                                quar_subset = {
                                        'type': str(co.Quarantine( \
                                                quar[0]['quarantine_type'])),
                                        'description': quar[0]['description'],
                                        'date_set': \
                                            str(quar[0]['start_date']) \
                                            .split()[0]
                                        }

                            tmp = {
                                    'username': ac.account_name,
                                    'full_name': ac.get_fullname(),
                                    'disk_path': d['path'],
                                    'quarantine': quar_subset,
                                    'affiliation': str(co.PersonAffStatus( \
                                            affs[0]['status']))
                                    }

                            report.setdefault(ou2sko[ou], []).append(tmp)

    logger.debug('%d disks and %d accounts checked' % (no_disks, no_accounts))

    r = len(reduce(lambda x, y: x+y, report.values())) if len(report) else 0
    logger.debug('%d employees on student disks' % r)

    return report

# Own function to print out the HTML-preamble.
def preamble(output, title):
    output.write("""<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
        <title>%s</title>
        <style type="text/css">
            h1 {
                margin: 1em .8em 1em .8em;
                font-size: 1.4em;
            }
            h2 {
                margin: 1.5em 1em 1em 1em;
                font-size: 1em;
            }
            table + h1 {
                margin-top: 3em;
            }
            table {
                border-collapse: collapse;
                width: 100%%;
                text-align: left;
            }
            table thead {
                border-bottom: solid gray 1px;
            }
            table th, table td {
                padding: .5em 1em;
                width: 10%%;
            }
            .meta {
                color: gray;
                text-align: right;
            }
        </style>
    </head>
    <body>
    """ % title)

# Function to produce HTML-output from the results
def gen_employees_on_student_disk_report(output, empl_on_stud_disk, sort_by, sko2name):

    # We reduce the lists contained in the dict, and the length of this list is
    # the amount of users we found.
    number_of_users = len(reduce(lambda x, y: x+y, \
            empl_on_stud_disk.values())) if len(empl_on_stud_disk) else 0

    # Print the HTML preamble. Output is the output fileobject, while the string is the title.
    preamble(output, "Pure employees on student disks")
    # Print some metainfo
    output.write('<p class="meta">' + \
            '%d users with ansatt affiliation on student disks.</p>\n' % \
            number_of_users)

    # Sort function used to sort the different sections of users (on a per-disk
    # or a per-SKO basis), by whether a quarantine is set or not.
    sort_by_quar = lambda o1,o2: -1 if len(o1['quarantine']) < \
            len(o2['quarantine']) else 0 if len(o1['quarantine']) == \
            len(o2['quarantine']) else 1

    # We might want to sort the report per-disk..
    if sort_by == 'disk':
        # Unpack the vars
        empls = {}

        # The dict we get is sorted on SKOs. We re-sort it on disknames:
        # try/except to keep stuff happy if no users is found..
        try:
            for u in reduce(lambda x,y: x+y, empl_on_stud_disk.values()):
                empls.setdefault(u['disk_path'], []).append(u)
        except TypeError:
            pass
            
        # For each disk, we print out a table header:
        for k in sorted(empls.keys()):
            output.write('<h2>%s</h2>\n' % k)
            output.write('<table><thead><tr>\n')
            output.write('<th>Username</th>\n')
            output.write('<th>Full Name</th>\n')
            output.write('<th>Affiliation</th>')
            output.write('<th>Quarantine type</th>\n')
            output.write('<th>Quarantine description</th>\n')
            output.write('<th>Quarantine start date</th>\n')
            output.write('</thead></tr>\n<tr>\n')
            
            # For each user on disk (sorted by quarantine), print account name,
            # full name, affiliation and quarantine information.
            for user in sorted(empls[k], cmp=sort_by_quar):
                output.write('<tr><td>%s</td>\n' % user['username'])
                output.write('<td>%s</td>\n' % user['full_name'])
                output.write('<td>%s</td>\n' % user['affiliation'])

                # If quarantined, print out quarantine info, else,
                # print "placeholder"
                try:
                    output.write('<td>%s</td>\n' % user['quarantine']['type'])
                    output.write('<td>%s</td>\n' % \
                            user['quarantine']['description'])
                    output.write('<td>%s</td>\n' % \
                            user['quarantine']['date_set'])
                except KeyError:
                    output.write('<td></td>\n' * 3)
                output.write('</tr>\n')
            output.write('</table>\n')
    # accounts sorted by SKO
    elif sort_by == 'sko':
        faculties = []
        # For each SKO
        for sko in sorted(empl_on_stud_disk.keys()):

            # Print a header with faculty/institute name..
            fak = sko2name['%02s0000' % sko[:2]]
            if fak not in faculties:
                output.write('<h1>%s</h1>\n' % fak)
                faculties.append(fak)

            # Print out a heading for this SKO-code, and a table header for the
            # accounts:
            output.write('<h2>%s - %s </h2>\n' % (sko, sko2name[sko]))
            output.write('<table><thead><tr>\n')
            output.write('<th>Username</th>\n')
            output.write('<th>Full name</th>\n')
            output.write('<th>Affiliation</th>\n')
            output.write('<th>Disk path</th>\n')
            output.write('<th>Quarantine type</th>\n')
            output.write('<th>Quarantine description</th>\n')
            output.write('<th>Quarantine date set</th>\n')
            output.write('</thead></tr>\n')

            # Print one row for each account. Rows are sorted by the existence
            # of quarantines.
            for user in sorted(empl_on_stud_disk[sko], cmp=sort_by_quar):
                output.write('<tr><td>%s</td>\n' % user['username'])
                output.write('<td>%s</td>\n' % user['full_name'])
                output.write('<td>%s</td>\n' % user['affiliation'])
                output.write('<td>%s</td>\n' % user['disk_path'])
                # We'll try to print out the quarantine. If there is no
                # quarantine associated, we print out blank fields.
                try:
                    output.write('<td>%s</td>\n' % user['quarantine']['type'])
                    output.write('<td>%s</td>\n' % \
                            user['quarantine']['description'])
                    output.write('<td>%s</td>\n' % \
                            user['quarantine']['date_set'])
                except KeyError:
                    output.write('<td></td>\n' * 3)
                output.write('</tr>\n')
            output.write('</table>\n')

    output.write('</body></html>\n')

# Main function, initializes database connections, the logger, sets default
# variables and calls functions to produce an HTML-report.
def main():
    # Initialize database connections
    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    di = Factory.get('Disk')(db)
    en = Factory.get('Entity')(db)
    co = Factory.get('Constants')(db)
    ou = Factory.get('OU')(db)

    # Initialize logger
    logger = Factory.get_logger('cronjob')

    # Default output channel, spread to sort by and what to arrange the final
    # report by (SKO vs. disk)
    output = sys.stdout
    sort_by = 'sko'
    spread = 'NIS_user@uio'
    
    # Helpers from generate_quarantine_report.py. Use this to get
    # names from SKOs and SKOs from OUs.
    ou2sko = dict((row['ou_id'], ("%02d%02d%02d" % (row['fakultet'],
                                                    row['institutt'],
                                                    row['avdeling'])))
                                                    for row in \
                                                            ou.get_stedkoder())

    sko2name = dict((ou2sko[row['entity_id']], row['name']) for row in
                    ou.search_name_with_language(name_variant=
                                                        co.ou_name_display,
                                                        name_language=
                                                        co.language_nb))

    # Parse the options
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:s:a:', ['output=', 'spread=', 'arrange-by='])
    except getopt.GetoptError, e:
        logger.error(e)
        usage(1)
    
    for opt,val in opts:
        if opt in ('-o', '--output'):
            try:
                output = open(val, 'w')
            except IOError, e:
                logger.error(e)
                usage(2)
        elif opt in ('-s', '--spread'):
            spread = val
        elif opt in ('-a', '--arrange-by'):
            sort_by = val
    
    logger.info('Start of employee on student disk report')
    
    # Collect the data
    empl_on_stud_disk = get_empl_on_student_disks(logger, spread, ac, pe, di, en, co, ou, ou2sko)
    # Print the HTML-report
    gen_employees_on_student_disk_report(output, empl_on_stud_disk, sort_by, sko2name)

    # Close the fileobject.
    if not output is sys.stdout:
        output.close()

    logger.info('End of employee on student disk report')

# Start main. This allows import of the file without firing of a report..
if __name__ == '__main__':
    sys.exit(main())
