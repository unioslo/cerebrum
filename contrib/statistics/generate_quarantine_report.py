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
Report accounts in quarantine.
Idea:
   Events like quarantine_add are logged with a timestamp.
   Retreive the events and get account ids,
   process only personal accounts.
   Account object has required attributes for the report, so does
   the accounts owner object Person.
   Output:
   Navn	| Tilknytning | Fødselsdato | Brukernavn | Karantene starter | Karantenens type
   Sort rows by faculties.
   

"""

import sys, getopt

from mx.DateTime import now, ISO, RelativeDateTime

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError

def usage(exitcode=0):
    print """Usage:
    generate_quarantine_report.py [--from YYYY-MM-DD]\
    [--to YYYY-MM-DD] [--source_systems SAP,FS] --output FILE

    Generate an html formatted report of accounts with active quaranitnes
    for the given period.

    --from            Date to start searching for new quarantines from. Defaults
                      to 7 days ago.
    
    --to              Date to start searching for new quarantines until. Defaults
                      to now.

    --source_systems  Comma separated list of source systems to search
                      through. Defaults to 'SAP,FS'.

    --output          The file to print the report to. Defaults to stdout.
    """ 
    sys.exit(exitcode)

def generate_report(output, source_systems, start_date, end_date):
    """Generate html formatted report of accounts in quarantine between start_date
    and end_date, sort by respective persons affiliations.
    @param output: filename to write output to
    @type output: file object, returned by open or sys.stdout
    @param source_systems: not used for now,
    @type source_systems: string with comma separated systems.
    @param start_date: 
    @type start_date: ISO date, i.e YYYY-MM-DD
    @param end_date:
    @type end_date: ISO date, YYY-MM-DD
    """
    
    lg = Factory.get_logger("cronjob")
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    ou = Factory.get('OU')(db)
    
    lg.info('Start report.')
    
    ou2sko = dict((row['ou_id'], ("%02d%02d%02d" % (row['fakultet'], 
                                                    row['institutt'],
                                                    row['avdeling'])))
                                                    for row in ou.get_stedkoder())

    sko2name = dict((ou2sko[row['entity_id']], row['name']) for row in
                    ou.search_name_with_language(name_variant = co.ou_name_display,
                                                 name_language=co.language_nb))
    
    events = db.get_log_events_date(int(co.quarantine_add),
                                    sdate=start_date,
                                    edate=end_date)
    quarantines_by_sko = {}
    num_quarantines = 0

    for row_e in events:
        ac.clear()
        try: 
            ac.find(row_e['subject_entity'])
        except NotFoundError, nfe:
            lg.error('%s' %nfe)
            continue
        
        if ac.owner_type <> co.entity_person:
            #lg.info('Account %s with id %s is non-personal'
            #        %(ac.get_account_name(), row_e['subject_entity']))
            continue # Filter out non-personal accounts.

        account_name = ac.get_account_name()
        name = ac.get_fullname()
        
        pe.clear()
        pe.find(ac.owner_id)
        aff = pe.get_affiliations()
        ac_q = ac.get_entity_quarantine(only_active=True)

        if not ac_q:
            #lg.info('No active quarantines for %s' %ac.get_account_name())
            continue # No active quarantines for that account, skip.

        num_quarantines += 1
        for row in aff:
            quarantines_by_sko.setdefault(ou2sko[row['ou_id']], []).append({
                'name': name,
                'status': str(co.PersonAffStatus(row['status'])),
                'birth': pe.birth_date.strftime('%Y-%m-%d'),
                'account': account_name,
                'quarantines':ac_q
                })

    lg.info('Found %d active quaranines created between %s and %s'
            %(num_quarantines, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

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
                    width: 16%;
                }
                .meta {
                    color: gray;
                    text-align: right;
                }
            </style>
        </head>
        <body>
    """)
    
    output.write('<p class="meta">Karantener fra %s til %s</p>' \
                 %(start_date.strftime('%Y-%m-%d'),
                   end_date.strftime('%Y-%m-%d')))
    
    output.write("\n<h2>Viser %s karantener</h2>\n" %num_quarantines)
    faculties = []
    for sko in sorted(quarantines_by_sko):
        fac = "%02s0000" % sko[:2]
        if fac not in faculties:
            output.write("\n<h1>%s</h1>\n" % sko2name[fac])
            faculties.append(fac)

        output.write("\n<h2>%s - %s</h2>\n" % (sko, sko2name[sko]))
        output.write("<table><thead><tr>")
        output.write("<th>Navn</th>")
        output.write("<th>Tilknytning</th>")
        output.write("<th>Fødselsdato</th>")
        output.write("<th>Brukernavn</th>")
        output.write("<th>Karantene starter</th>")
        output.write("<th>Karantenens type</th>")
        output.write("</tr></thead>\n")

        for qa in quarantines_by_sko[sko]:
            output.write("\n<tr>\n")
            output.write("<td>%s</td>\n" % qa['name'])
            output.write("<td>%s</td>\n" % qa['status'])
            output.write("<td>%s</td>\n" % qa['birth'])
            output.write("<td>%s</td>\n" % qa['account'])
            for entry in qa['quarantines']:
                output.write("<td>%s</td>\n" % entry['start_date']\
                             .strftime('%Y-%m-%d kl %H:%M'))
                output.write("<td>%s</td>\n" % co.Quarantine(entry['quarantine_type']))
                
                if entry <> qa['quarantines'][-1]:
                    output.write("</tr>\n")
                    output.write("<td></td><td></td><td></td><td></td>\n")

            output.write("</tr>\n")

        output.write("</table>\n")

    output.write("""
        <p class="meta">Generert: %s</p>\n</body>
        \n</html>\n""" % now().strftime('%Y-%m-%d kl %H:%M'))

    lg.info('Done. Quarantine Report is generated.')

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ho:',
                ['from=', 'to=', 'source_systems=', 'output='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    end_date = now()
    start_date = now() + RelativeDateTime(days=-7)
    source_systems = 'SAP,FS'
    output = sys.stdout

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--from', ):
            start_date = ISO.ParseDate(val)
        elif opt in ('--to', ):
            end_date = ISO.ParseDate(val)
        elif opt in ('--source_systems', ):
            source_systems = val
        elif opt in ('-o', '--output'):
            output = open(val, 'w')

    generate_report(output=output, source_systems=source_systems,
            start_date=start_date, end_date=end_date)
    if not output is sys.stdout:
        output.close()

if __name__ == '__main__':
    main()
