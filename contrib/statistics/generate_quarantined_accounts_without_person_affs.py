#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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

"""This program looks for accounts that have been quarantined for over 1 year,
not expired and owned by a person with no affiliations.

Note that only one quarantine per account is included in the HTML report.

    The following functions are defined:
        main():
            This function initializes database connections, parses command line
            parameters and starts other functions used to collect data and
            generate a report.
        get_matching_accs():
            This function searches the database for accounts where:
                - account is owned by a person with no affiliations
                - account has been quarantined for > 1 year
                - account is not expired
        create_html_report():
            This function generates an HTML report.
        usage():
            - Prints usage information
        preamble():
            - Prints HTML preamble for the report.
        usage():
            - Prints a help text about options.
"""

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors

from mx import DateTime

def usage(exitcode=0):
    print """Usage:
    %s [Options]

    Generate an HTML formatted report of accounts where:
        - account owner is no longer affiliated
        - account has been quarantined for > 1 year
        - account is not expired

    Options:
    -o, --output <file>    The file to print the report to. Defaults to stdout.
    """ % sys.argv[0] 
    sys.exit(exitcode)

def get_matching_accs(logger, ac, pe, co):
    """For each account:
        - checks if the owner of the account (person) is still affiliated
            - if not, go to next account
        - checks if the account is quarantined
            - if not, go to next account
        - for each quarantine, checks if 1 year has passed
            - if not, go to next account
        - saves account name, full name and quarantine information

    @param logger: logger object
    @type logger: logger

    @param ac: Account object
    @type ac: Account

    @param pe: Person object
    @type pe: Person

    @param co: Constants object
    @type co: Constants

    @return a dictionary indexed by disk, each containing a list of dictionaries with
    account information
    """

    # Get all non-expired accounts
    accounts = ac.search(owner_type=co.entity_person)
    logger.info("Found %d accounts with owner_type = 'person'" % len(accounts))

    # Map account_id to disk
    acc2disk = {}
    for i in ac.list_account_home():
        acc2disk[i['account_id']] = i['path']
    logger.info("Found %d accounts assigned to a disk" % len(acc2disk))

    # Map account_id to quarantines
    acc2quar = {}
    for q in ac.list_entity_quarantines(only_active=True, entity_types=co.entity_account):
        acc2quar.setdefault(q['entity_id'], [])
        acc2quar[q['entity_id']].append(q)
    logger.info("Found quarantines for %d accounts" % len(acc2quar))

    # Map person_id to full name
    person2name = {}
    for n in pe.search_person_names(name_variant=co.name_full, source_system=co.system_cached):
        person2name[n['person_id']] = n['name']
    logger.info("Found full names for %d persons" % len(person2name))

    # Add person_id to the list if the person has an affiliation
    person_has_affs = set()
    for aff in pe.list_affiliations():
        person_has_affs.add(aff['person_id'])
    logger.info("Found %d persons with affiliations" % len(person_has_affs))

    matches = {}

    for acc in accounts:
        # Is the account owner still affiliated?
        if acc['owner_id'] not in person_has_affs:
            # Is the account quarantined?
            if acc['account_id'] not in acc2quar:
                continue

            quar = {}

            for q in acc2quar[acc['account_id']]:
                # Has this quarantine been in place for > 1 year?
                if (q['start_date'] + DateTime.DateTimeDelta(365)) < DateTime.now():
                    quar = {
                        'type': str(co.Quarantine(q['quarantine_type'])),
                        'description': q['description'],
                        'start_date': str(q['start_date']).split()[0],
                    }
            
            # Include this account in the result set if quarantined for > 1 year
            if len(quar):
                disk = acc2disk.setdefault(acc['account_id'], None)
                matches.setdefault(disk, [])

                matches[disk].append({
                    'account_name': acc['name'],
                    'full_name': person2name.get(acc['owner_id'], '(not set)'),
                    'quarantine': quar,
                })

    return matches

def preamble(output, title):
    """Prints the HTML preamble.

    @param title: Title of the HTML report
    @type title: String

    @param output: File object used for output
    @type output: File
    """

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
                padding: .3em 1em;
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

def create_html_report(output, matches):
    """Formats the HTML report and writes to 'output'.

    Each key in 'matches' is a disk path. The value is a list with a dictionary
    for each account. A separate table is printed for each disk.

    @param output: Output file handle
    @type output: file

    @param matches: Dictionary of matches from get_matching_accs()
    @type matches: Dictionary
    """

    # Count the total number of users
    number_of_accounts = len(reduce(lambda x, y: x+y, matches.values())) if \
            len(matches) else 0

    preamble(output, 'Quarantined users without person affiliations')

    output.write('<p class="meta">')
    output.write('%d accounts without person affiliations + not expired + quarantined for minimum 1 year' % number_of_accounts)
    output.write('\n<br/>Generated %s</p>' % DateTime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # Print a table showing number of accounts per disk, with anchors
    output.write('<table><thead><tr><th>Disk</th><th>Accounts</th></thead><tbody>')
    for disk in sorted(matches.keys()):
        output.write('<tr><td><a href="#%s">%s</a></td><td>%s</td></tr>\n' % (disk, disk, len(matches[disk])))
    output.write('</tbody></table>')

    # For each disk, sorted by disk path
    for disk in sorted(matches.keys()):
        output.write('<a name="%s"><h2>%s</h2></a>\n' % (disk, disk))
        output.write('<table><thead><tr>\n')
        output.write('<th>Username</th>\n')
        output.write('<th>Full Name</th>\n')
        output.write('<th>Quarantine type</th>\n')
        output.write('<th>Quarantine description</th>\n')
        output.write('<th>Quarantine start date</th>\n')
        output.write('</thead></tr>\n')
        output.write('<tbody>\n')

        # For each account, sorted by quarantine start date
        for i in sorted(matches[disk], key=lambda x: x['quarantine']['start_date']):
            output.write('<tr><td>%s</td>' % i['account_name'])
            output.write('<td>%s</td>' % i['full_name'])
            output.write('<td>%s</td>' % i['quarantine'].get('type', '(not set)'))
            output.write('<td>%s</td>' % i['quarantine'].get('description', '(not set)'))
            output.write('<td>%s</td>' % i['quarantine'].get('start_date', '(not set)'))
            output.write('</tr>\n')

        output.write('</tbody></table>\n')
    output.write('</body></html>\n')

def main():
    """Initializes database connections, reads options, starts report generation."""

    # Initialization of database connections
    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    # Initialization of logger
    logger = Factory.get_logger('cronjob')

    # Default output channel
    output = sys.stdout

    # Parsing opts
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:', ['output='])
    except getopt.GetoptError, e:
        logger.error(e)
        usage(1)
    
    for opt,val in opts:
        if opt in ('-o', '--output'):
            try:
                output = open(val, 'w')
            except IOError, e:
                logger.error(e)
                sys.exit(2)

    logger.info('Start of quarantined accounts without person affiliations report')

    # Search for accounts
    matches = get_matching_accs(logger, ac, pe, co)

    # Generate HTML report
    create_html_report(output, matches)

    # Count number of accounts
    number_of_accounts = len(reduce(lambda x, y: x+y, matches.values())) if \
            len(matches) else 0

    logger.info('Found %d matching accounts' % number_of_accounts)

    # If the output is being written to file, close the file handle
    if not output is sys.stdout:
        output.close()

    logger.info('End of quarantined accounts without person affiliations report')

# If we run as a program, execute main(), then exit
if __name__ == '__main__':
        sys.exit(main())
