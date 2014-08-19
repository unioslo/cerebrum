#! /usr/bin/env python
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

import sys
import getopt
from mx.DateTime import now

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors

"""This program reports users on disk without affiliations, and any quarantines
that are ACTIVE for that user.

    The following functions are defined:
        main():
            This function initializes database-connections, parses command line
            parameters and starts other functions used to collect data and
            generate a report.
        get_accs_wo_affs():
            This function searches the database for accounts that are owned by
            a person which is not affiliated with anything.
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
                    so, the person is fetched.
                    - Get the affiliations, if there are none, we add the
                        account to our report-dict.

    gen_affles_users_report():
        - Prints out the HTML preamble via the preamble() function
        - For each disk in our result-dictionary:
            - Generate a table header
            - Loop over the accounts on the disk in question
                - Print a row of info.

"""

def usage(exitcode=0):
    print """Usage:
    %s [Options]

    Generate an HTML formatted report of accounts on disk without affiliations.

    Options:
    -o, --output <file>    The file to print the report to. Defaults to stdout.
    -s, --spread <spread>  Spread to filter users by. Defaults to NIS_user@uio.
    """ % sys.argv[0] 
    sys.exit(exitcode)

# This function searches the disks for users owned by persons that are not
# affiliated with anything. These users (or, accounts), are then placed in a
# dictionary which is indexed by the disknames. The value of each key is a list
# of dicts with information about accounts.
def get_accs_wo_affs(logger, filter_by_spread, ac, pe, di, en, co):

    # We fetch the spread from constants, and check if it exists by comparing it
    # to itself. This is a bit ugly. 
    try:
        spread = co.Spread(filter_by_spread)
        spread == co.Spread(filter_by_spread)
    except Errors.NotFoundError:
        logger.error('The spread %s is invalid' % filter_by_spread)
        sys.exit(1)

    # Variables to store results from "search"
    # 'no_aff' are is a dict where the key is the diskname, and the value is
    # a list of dicts with information about users without any affiliations.
    #
    # The keys and values are:
    # account_name: account name
    # full_name:    full name
    # quarantine:   {
    #                   type:           the type of the quarantine
    #                   description:    general description
    #                   date_set:       The date the quarantine was set
    #               }
    no_aff = {}

    # Getting a list of all disks from the database:
    disks = di.list()

    # Counter values, number of disks checked and number of accounts checked.
    no_disks = 0
    no_accounts = 0

    # We iterate over the disks:
    for d in disks:
        # We only want disks in the NIS_user@uio spread
        if d['spread'] == spread:
            # Increment stat-counter
            no_disks = no_disks + 1

            # We only pull users from NIS_user@uio..
            users = ac.list_account_home(disk_id=d['disk_id'], \
                    home_spread=spread)

            # Update stat-counter
            no_accounts = no_accounts + len(users)

            # For each of the users on the disk
            for u in users:
                ac.clear()
                pe.clear()
                
                # We try to find the user
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
                    # So this is a person, we try to find it.
                    try:
                        pe.find(ac.owner_id)
                    except Errors.NotFoundError:
                        logger.error('Can\'t ' + \
                                'find person_id = %d for account_id = %d' \
                                % (ac.owner_id, ac.entity_id))
                        continue

                    # And then we get the affiliations
                    affs = pe.get_affiliations()

                    # We check if this person does not have any affiliations, if
                    # so, we report, since the user shouldn't be on disk.
                    if not len(affs):
                        # We pull out the first entry from the quarantine list,
                        # and put parts of it in a dict for easier handling.
                        # NOTE: we only fetch ACTIVE quarantines.
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
                        report_item = {'account_name': ac.account_name, \
                                    'full_name': ac.get_fullname(), \
                                    'quarantine': quar_subset}

                        # Put the accounts w/info in a dict, the key is the
                        # path to the disk.
                        if no_aff.has_key(d['path']):
                            no_aff[d['path']] += [report_item]
                        elif not no_aff.has_key(d['path']):
                            no_aff[d['path']] = [report_item]

    # Log the counts of disks and accounts checked.
    logger.debug('%d disks and %d accounts checked' % (no_disks, no_accounts))
    
    # We count the number of accounts on disk whithout affiliations, and report
    # via logger.
    r = len(reduce(lambda x, y: x+y, no_aff.values())) if len(no_aff) else 0
    logger.debug('%d users on disk without affiliations' % r)

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

# Function to produce HTML-output from the results. This function outputs HTML.
# In more detail, a table for each disk, that contains the users without
# affiliations on the disk. Prints one table for each key in 'no_aff'.
def gen_affles_users_report(output, no_aff):
    # Counting the total number of users
    number_of_users = len(reduce(lambda x, y: x+y, no_aff.values())) if \
            len(no_aff) else 0

    # Print the header. Then some info
    preamble(output, 'Users on disk without affiliations')
    output.write('<p class="meta">' + \
            '%d users without person affiliations on disk.</p>\n' % \
            number_of_users)

    # Sort function used to sort entries depending on whether they have
    # a quarantine or not (to be used on list of users, not the disks).
    sa = lambda x,y: -1 if len(x['quarantine']) < len(y['quarantine']) else \
            0 if len(x['quarantine']) == len(y['quarantine']) else 1


    # Print tables of disks with users:
    # For each disk
    for key in sorted(no_aff.keys()):
        output.write('<h2>%s</h2>\n' % key)
        output.write('<table><thead><tr>\n')
        output.write('<th>Username</th>\n')
        output.write('<th>Full Name</th>\n')
        output.write('<th>Quarantine type</th>\n')
        output.write('<th>Quarantine description</th>\n')
        output.write('<th>Quarantine start date</th>\n')
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
    en = Factory.get('Entity')(db)
    co = Factory.get('Constants')(db)

    # Initialization of logger
    logger = Factory.get_logger('cronjob')

    # Default output channel and spread to search by
    output = sys.stdout
    spread = 'NIS_user@uio'

    # Parsing opts
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:s:', ['output=', 'spread='])
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
        if opt in ('-s', '--spread'):
            spread = val

    logger.info('Start of accounts without affiliation report')

    # Search for accounts without affiliations
    no_aff = get_accs_wo_affs(logger, spread, ac, pe, di, en, co)
   
   # Generate HTML report of results
    gen_affles_users_report(output, no_aff)

    # If the output is being written to file, close the filehandle
    if not output is sys.stdout:
        output.close()

    logger.info('End of accounts without affiliation report')

# If we run as a program, execute main(), then exit
if __name__ == '__main__':
        sys.exit(main())
