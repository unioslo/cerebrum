#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012, 2014 University of Oslo, Norway
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
"""This program reports users on disk without affiliations, and any quarantines
that are ACTIVE for that user.

    The following functions are defined:
        main():
            This function initializes database-connections, parses command line
            parameters and starts other functions used to collect data and
            generate a report.
        get_accs_wo_affs():
            This function searches the database for accounts that are owned by
            a person which is not affiliated with anything, or accounts that have
            no affiliations but are owned by a person who is affiliated with
            something (depending on script options).
        gen_affles_users_report():
            This function generates an HTML-report.
        usage():
            - Prints usage information
        preamble():
            - Print HTML preable, for the report.
        usage():
            - Prints a help text about options.

Overall flow of execution looks like:
    main():
        - Initializes database connections
        - Parses command line options
        - Starts 'get_accs_wo_affs()'
        - Starts 'gen_affles_users_report()'
        - Closes filehandle, then exits

    get_accs_wo_affs():
        - Starts by checking if the spread we are going to use is valid.
        - Loops over all disks
            - If the disk has a NIS_user@uio spread, list all accounts (but only
                those with the NIS_user@uio spread) in a var.
                - For each of these accounts, find the owners entity. The owners
                    entity must be checked to makes sure it is a person, and if
                    so, the person is fetched. Then one of the following, depending
                    on script options:
                    - Get the person's affiliations, if there are none, we add the
                        account to our report-dict.
                    - Get the account's affiliations, if there are none but there
                        are person affiliations, we add the account to our
                        report-dict.

    gen_affles_users_report():
        - Prints out the HTML preamble via the preamble() function
        - For each disk in our result-dictionary:
            - Generate a table header
            - Loop over the accounts on the disk in question
                - Print a row of info.

"""

import sys
import getopt
import csv
from mx.DateTime import now

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors

class CSVDialect(csv.excel):
    """Specifying the CSV output dialect the script uses.

    See the module `csv` for a description of the settings.

    """
    delimiter = ';'    
    lineterminator = '\n'

def usage(exitcode=0):
    print """Usage:
    %s [Options]

    Generate an HTML formatted report of accounts on disk, belonging to persons
    without affiliations (or, if -a is used, accounts without affiliations
    belonging to persons with affiliations).

    Options:
    -o, --output FILE       The file to print the report to. Defaults to stdout.

    -s, --spread SPREAD     Spread to filter users by. Defaults to NIS_user@uio.

    -a, --check-accounts    Find the accounts lacking affiliations, belonging to
                            persons who have affiliations.
                            If this option is not set, the default behavior is
                            instead to find the accounts of persons who lack
                            affiliations, regardless of whether the accounts
                            have affiliations or not.

    -f, --output-format FMT The type of format. Defaults to 'html'. Available
                            options: html and csv.

    -h, --help              Show this and quit.

    """ % sys.argv[0] 
    sys.exit(exitcode)

def get_accs_wo_affs(logger, filter_by_spread, ac, pe, di, co, check_accounts=False):
    """Search disks for users owned by persons without affiliations.

    :rtype: dict
    :return:
        All targeted users, sorted by disk name. The dict's values are dicts
        with information about each users:

        - account_name: account name
        - full_name:    full name
        - quarantine:   {
                         type:           the type of the quarantine
                         description:    general description
                         date_set:       The date the quarantine was set
                        }

    """
    logger.debug("Start fetching accounts...")

    # We fetch the spread from constants, and check if it exists by comparing it
    # to itself. This is a bit ugly. 
    try:
        target_spread = co.Spread(filter_by_spread)
        int(target_spread)
    except Errors.NotFoundError:
        logger.error('The spread %s is invalid', filter_by_spread)
        sys.exit(1)

    no_aff = {}

    # Cache the person affiliations
    target_person_affs = {}
    # Might want to be able to set the affiliation type, for later being able to
    # include e.g. manual affiliations in the person list.
    for row in pe.list_affiliations():
        target_person_affs.setdefault(row['person_id'], []).append(row)

    # Counter values, number of disks checked and number of accounts checked.
    no_disks = 0
    no_accounts = 0

    # We iterate over the disks:
    for d in di.list():
        # We only want disks with target spread
        if d['spread'] != target_spread:
            continue

        logger.debug2("Targeting disk: %s", d['path'])
        no_disks += 1

        # We only pull users from NIS_user@uio..
        users = ac.list_account_home(disk_id=d['disk_id'],
                                     home_spread=target_spread)
        logger.debug2("Users found on disk: %s", len(users))

        for u in users:
            ac.clear()
            try:
                ac.find(u['account_id'])
            except Errors.NotFoundError:
                logger.warn("Can't find account_id = %d", u['account_id'])
                continue
            # Exclude non personal accounts:
            if ac.owner_type != co.entity_person:
                continue
            # If we're focusing on person affiliations,
            # ignore persons with an affiliation:
            if not check_accounts and ac.owner_id in target_person_affs:
                continue
            # If we're focusing on account affiliations,
            # ignore persons without an affiliation and
            # accounts with an affiliation
            if check_accounts and (ac.get_account_types() != [] or
                                   ac.owner_id not in target_person_affs):
                continue

            # We pull out the first entry from the quarantine list,
            # and put parts of it in a dict for easier handling.
            quar = ac.get_entity_quarantine(only_active=True)
            quar_subset = {}
            if len(quar):
                quar_subset = {
                        'type': str(co.Quarantine(quar[0]['quarantine_type'])),
                        'description': quar[0]['description'],
                        'date_set': str(quar[0]['start_date']).split()[0],
                        }
            report_item = {'account_name': ac.account_name,
                           'full_name': ac.get_fullname(),
                           'quarantine': quar_subset,
                           }
            no_aff.setdefault(d['path'], []).append(report_item)
            no_accounts += 1

    # Log the counts of disks and accounts checked.
    logger.debug('%d disks and %d accounts checked', no_disks, no_accounts)
    
    # We count the number of accounts on disk whithout affiliations, and report
    # via logger.
    r = len(reduce(lambda x, y: x+y, no_aff.values())) if len(no_aff) else 0
    logger.debug('%d users on disk without affiliations', r)

    # Function end, we return the dict.
    return no_aff

# Own function to print out the HTML-preamble. 'title' is the title of the
# HTML-page, while 'output' is the file-object used for output.
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

def gen_affles_users_report(output, no_aff, output_format, check_accounts=False):
    """Produce the output for the report, based on the given input.

    :param file output: The stream the report is written to.

    :param dict no_aff:
        The list of users without affiliations, grouped per disk. This is the
        data that is written out in the report.

    :param str output_format:
        Sets the format of the report. Available formats:

        - `html` - With focus on being more human readable. The output is sorted
          per disk, grouped in HTML `<table>` elements.

        - `csv` - For easier parsing and post processing. All data is written
          per line.

    """
    assert output_format in ('html', 'csv')

    # Counting the total number of users
    number_of_users = len(reduce(lambda x, y: x+y, no_aff.values())) \
                       if len(no_aff) else 0

    # Sort function used to sort entries depending on whether they have
    # a quarantine or not (to be used on list of users, not the disks).
    sa = lambda x,y: -1 if len(x['quarantine']) < len(y['quarantine']) else \
            0 if len(x['quarantine']) == len(y['quarantine']) else 1

    if output_format == 'csv':
        # Print out status first:
        output.write('# Generated: %s\n' % now())
        output.write('# Number of users found: %d\n' % number_of_users)
        writer = csv.writer(output, dialect=CSVDialect)
        for disk in sorted(no_aff):
            for user in sorted(no_aff[disk], cmp=sa):
                q = user.get('quarantine', '')
                if q:
                    q = ','.join((q['type'], q['description'], q['date_set']))
                writer.writerow((disk,
                                 user['account_name'],
                                 user['full_name'],
                                 q,
                                ))
        return

    # Print the header. Then some info
    preamble(output, 'Users on disk without affiliations')
    if check_accounts:
        output.write('<p class="meta">%d users on disk without affiliations, '
                     'owned by persons with affiliations.</p>\n' % number_of_users)
    else:
        output.write('<p class="meta">%d users without person affiliations on '
                     'disk.</p>\n' % number_of_users)

    # Print tables of disks with users:
    # For each disk
    for key in sorted(no_aff):
        output.write('<h2>%s</h2>\n' % key)
        output.write('<table>\n<thead><tr>')
        output.write('<th>Username</th>')
        output.write('<th>Full Name</th>')
        output.write('<th>Quarantine type</th>')
        output.write('<th>Quarantine description</th>')
        output.write('<th>Quarantine start date</th>')
        output.write('</thead></tr>\n')

        # For each user on disk (sorted by sa-function)
        for i in sorted(no_aff[key], cmp=sa):
            output.write('<tr>\n')
            output.write('<td>%s</td>' % i['account_name'])
            output.write('<td>%s</td>' % i['full_name'])

            # Try to print out quarantine-information. If the account isn't
            # quarantined, print out a placeholder.
            try:
                output.write('<td>%s</td>' % i['quarantine']['type'])
                output.write('<td>%s</td>' % i['quarantine']['description'])
                output.write('<td>%s</td>' % i['quarantine']['date_set'])
            except KeyError:
                output.write('<td></td>' * 3)
            output.write('\n</tr>\n')
        output.write('</table>\n')

    output.write('<p class="meta">Generert: %s</p>\n' % 
                                     now().strftime('%Y-%m-%d kl %H:%M'))
    output.write('</body></html>\n')

# The main function. This is where the database connection, logger and various
# variables (spreadname and output-channel) is initialized, before options from
# the command line are parsed, and the report generation starts.
def main():
    # Initialization of database connections
    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    di = Factory.get('Disk')(db)
    co = Factory.get('Constants')(db)

    # Initialization of logger
    logger = Factory.get_logger('cronjob')

    # Default output channel and spread to search by
    output = sys.stdout
    output_format = 'html'
    spread = 'NIS_user@uio'
    check_accounts = False

    # Parsing opts
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:s:f:a',
                                   ['output=', 
                                    'output-format=',
                                    'spread='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    for opt, val in opts:
        if opt in ('-o', '--output'):
            try:
                output = open(val, 'w')
            except IOError, e:
                logger.error(e)
                sys.exit(2)
        elif opt in ('-f', '--output-format'):
            if val not in ('html', 'csv'):
                print "Invalid output-format: %s" % val
                usage(1)
            output_format = val
        elif opt in ('-s', '--spread'):
            spread = val
        elif opt in ('-a', '--check-accounts'):
            check_accounts = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    logger.info('Start of accounts without affiliation report')

    # Search for accounts without affiliations
    no_aff = get_accs_wo_affs(logger, spread, ac, pe, di, co, check_accounts)
   
   # Generate HTML report of results
    gen_affles_users_report(output, no_aff, output_format, check_accounts)

    # If the output is being written to file, close the filehandle
    if not output is sys.stdout:
        output.close()

    logger.info('End of accounts without affiliation report')

# If we run as a program, execute main(), then exit
if __name__ == '__main__':
        sys.exit(main())
