#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
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
Report accounts in quarantine. Show accounts that belong to employees.
Output:
   Navn	| Tilknytning | Brukernavn | Karantene starter | Karantenens type
Sort rows by faculties and sort the resulting lists by  institutes.
"""

import sys
import getopt
import time

from mx.DateTime import now, ISO, RelativeDateTime

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.no.uio import AutoStud

def usage(exitcode=0):
    print """Usage:
    generate_quarantine_report.py [Options]

    Generate an html formatted report of accounts with active quaranitnes.

    Options:
    -s, --start_date      Show quarantines that startet before this ISO date.
                          Defaults to now.
    -a, --age <int>       Show quaranintines older than this age.      
    -o, --output <file>   The file to print the report to. Defaults to stdout.
        --source_systems  Not implemented. Source systems used by default
                          are SAP and FS. 
    """ 
    sys.exit(exitcode)


def generate_report(output, source_systems, start_date):
    """Generate html formatted report of accounts in quarantine.
    sort by faculites and sort results by institutes.
    @param output: filename to write output to
    @type output: file object, returned by open or sys.stdout
    @param source_systems: not used for now,
    @type source_systems: string with comma separated systems.
    @param start_date: 
    @type start_date: ISO date, i.e YYYY-MM-DD
    """
    t0 = time.clock()
    logger = Factory.get_logger("cronjob")
    database = Factory.get('Database')()
    constants = Factory.get('Constants')(database)
    person = Factory.get('Person')(database)
    account = Factory.get('Account')(database)
    ou = Factory.get('OU')(database)
    
    logger.info('Start Quarantine Report.')
    ou2sko = dict((row['ou_id'], ("%02d%02d%02d" % (row['fakultet'],
                                                    row['institutt'],
                                                    row['avdeling'])))
                                                    for row in ou.get_stedkoder())

    sko2name = dict((ou2sko[row['entity_id']], row['name']) for row in
                    ou.search_name_with_language(name_variant=
                                                        constants.ou_name_display,
                                                        name_language=
                                                        constants.language_nb))
    perspective = constants.OUPerspective('FS')
    autostud = AutoStud.AutoStud(database, logger, debug=0,
    cfg_file='/cerebrum/uio/etc/cerebrum/studconfig.xml',
    studieprogs_file='/cerebrum/uio/dumps/FS/studieprogrammer.xml',
    emne_info_file='/cerebrum/uio/dumps/FS/emner.xml',
    ou_perspective=int(perspective))

    t1 = time.clock()

    logger.debug('Initialization in %.2g seconds' %(t1-t0))
    
    quarantine_list = account.list_entity_quarantines(entity_types=constants.entity_account,
                                                      only_active=True)
    logger.debug('whole list length is %10d' %len(quarantine_list))
    
    quarantines_by_sko = {}
    num_quarantines = 0
    debug_counter = 0

    #diagnose if-tests
    time_if = 0
    deleted_if = 0
    owner_type_if = 0
    disk_if = 0

    t11 = time.clock()
    logger.debug('time used: %.2f' %(t11-t1))
    
    for row_qua in quarantine_list:
        
        debug_counter += 1
        if debug_counter % 10000 == 0:
            logger.debug('row nr %10d , passed %.2f seconds'
                    %(debug_counter,time.clock()-t11))
        
        if row_qua['start_date'] > start_date:
            time_if += 1
            continue # quarantine is not old enough, skip

        account.clear()
        try:
            account.find(row_qua['entity_id'])
        except NotFoundError, nfe:
            logger.error('%s' %nfe)
            continue

        
        if account.owner_type != constants.entity_person:
            owner_type_if += 1
            continue # Filter out non-personal accounts.

        if account.is_deleted() or account.is_reserved():
            deleted_if += 1
            continue # Skip deleted  and reserved accounts.

        try:
            disk_id = account.get_home(int(constants.spread_uio_nis_user))['disk_id']
        except NotFoundError:
            # no homedir exists
            continue

        if (disk_id and autostud.disk_tool.get_diskdef_by_diskid(disk_id)):
            disk_if += 1
            continue # disk_id refers to a student disk, skip.
        
        account_name = account.get_account_name()
        name = account.get_fullname()
        person.clear()
        person.find(account.owner_id)
        affiliations = person.get_affiliations()

        for row in affiliations:
            status = str(constants.PersonAffStatus(row['status']))

            quarantines_by_sko.setdefault(ou2sko[row['ou_id']], []).append({
                'name': name,
                'status': status,
                'account': account_name,
                'quarantine':row_qua
                })
        
        if not affiliations:
            quarantines_by_sko.setdefault('Uregistrert', []).append({
                'name': name,
                'status': 'ikke satt',
                'account': account_name,
                'quarantine':row_qua
                })

        num_quarantines += 1
        
        if num_quarantines % 1000 == 0:
            logger.debug( 'Found %10d quarantines after %.2f seconds' %(
                                    num_quarantines,(time.clock()-t11)))
        
    t2 = time.clock()
    logger.info('Retrieved %10d quarantines to show in %.2f seconds.'
            %(num_quarantines,t2-t11))

    #Write html.
    output.write("""<html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
            <title>Quarantines</title>
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
                    width: 100%;
                    text-align: left;
                }
                table thead {
                    border-bottom: solid gray 1px;
                }
                table th, table td {
                    padding: .5em 1em;
                    width: 20%;
                }
                .meta {
                    color: gray;
                    text-align: right;
                }
            </style>
        </head>
        <body>
    """)
    
    output.write('<p class="meta">Karantener som startet før %s.</p>'  %(start_date.strftime('%Y-%m-%d')))
    
    output.write("\n<h2>Viser %s karantener</h2>\n" %num_quarantines)
    faculties = []
    t3 = time.clock()
    logger.debug('After %4.2f seconds, output loop starts' % (t3-t2))

    logger.debug('Skipped %10d quaranintes started after %s.' %
                                                            (time_if,start_date))
    logger.debug('Skipped %10d deleted and reserved accounts.' % deleted_if)
    logger.debug('Skipped %10d non-personal accounts.' % owner_type_if)
    logger.debug('Skipped %10d accounts on students disks.' % disk_if)

    for sko in sorted(quarantines_by_sko):
        if sko is 'Uregistrert':
            faculty_name = sko
            faculty = sko
            unit_name = ''
        else:
            faculty = "%02s0000" % sko[:2]
            faculty_name = sko2name[faculty]
            unit_name = sko2name[sko]
        if faculty not in faculties:
            output.write("\n<h1>%s</h1>\n" % faculty_name)
            faculties.append(faculty)

        output.write("\n<h2>%s - %s</h2>\n" % (sko, unit_name))
        output.write("<table><thead><tr>")
        output.write("<th>Navn</th>")
        output.write("<th>Tilknytning</th>")
        output.write("<th>Brukernavn</th>")
        output.write("<th>Karantene starter</th>")
        output.write("<th>Karantenens type</th>")
        output.write("</tr></thead>\n")

        for report_line in quarantines_by_sko[sko]:
            output.write("\n<tr>\n")
            output.write("<td>%s</td>\n" % report_line['name'])
            output.write("<td>%s</td>\n" % report_line['status'])
            output.write("<td>%s</td>\n" % report_line['account'])
            output.write("<td>%s</td>\n" % report_line['quarantine']['start_date']\
                         .strftime('%Y-%m-%d kl %H:%M'))
            output.write("<td>%s</td>\n"
                         % constants.Quarantine(report_line['quarantine']
                                                ['quarantine_type']))
            output.write("</tr>\n")

        output.write("</table>\n")

    output.write("""
        <p class="meta">Generert: %s</p>\n</body>
        \n</html>\n""" % now().strftime('%Y-%m-%d kl %H:%M'))

    t4 = time.clock()
    logger.info('Quarantine Report written to output in %4.2f seconds.' %(t4-t3))
    logger.info('Total CPU time used: %4.2f seconds.' % (t4-t0))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hs:o:a:',
                ['start_date=', 'source_systems=', 'output=', 'age='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    start_date = now()
    source_systems = 'SAP,FS'
    output = sys.stdout

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-s', '--start_date', ):
            start_date = ISO.ParseDate(val)
        elif opt in ('-a', '--age'):
            age = int(val)
            if age < 0:
                print 'Enter a positive age in days.'
                usage(2)

            start_date = now() + RelativeDateTime(days=-age)
        elif opt in ('--source_systems', ):
            source_systems = val
        elif opt in ('-o', '--output'):
            output = open(val, 'w')
    generate_report(output=output, source_systems=source_systems,
                                            start_date=start_date)
    if not output is sys.stdout:
        output.close()

if __name__ == '__main__':
    main()
