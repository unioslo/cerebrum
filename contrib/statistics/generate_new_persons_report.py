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
Script for generating a report about new persons within Cerebrum.

Created to give LITA overview of newly arrived persons from SAPUiO.
"""
import sys, getopt

from mx.DateTime import now, ISO, RelativeDateTime

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError

def usage(exitcode=0):
    print """Usage: generate_new_persons.report.py [--from YYYY-MM-DD] --output FILE

    Generate a html formatted report of all new persons in the given period.

    --from            Date to start searching for new persons from. Defaults
                      to 7 days ago.
    
    --to              Date to start searching for new persons until. Defaults
                      to now.

    --source_systems  Comma separated list of source systems to search
                      through. Defaults to 'SAP,FS'.

    --output          The file to print the report to. Defaults to stdout.
    """
    sys.exit(exitcode)

def process(output, source_systems, start_date, end_date):
    """Get all persons from db created in a given period and send a html
    formatted report to output. The persons are sorted by their person
    affiliations' OUs."""

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    ou = Factory.get('OU')(db)

    source_systems = [int(co.AuthoritativeSystem(sys)) for sys in
                                                    source_systems.split(',')]
    ou2sko = dict((row['ou_id'], ("%02d%02d%02d" % (row['fakultet'], 
                                                    row['institutt'],
                                                    row['avdeling'])))
                                                for row in ou.get_stedkoder())
    sko2name = dict((ou2sko[row['entity_id']], row['name']) for row in
                ou.search_name_with_language(name_variant = co.ou_name_display,
                                             name_language=co.language_nb))

    person_ids = (row['subject_entity'] for row in
                                db.get_log_events_date(sdate=start_date,
                                                       edate=end_date,
                                                       type=int(co.person_create)))
    persons_by_sko = {}
    for p_id in person_ids:
        pe.clear()
        try:
            pe.find(p_id)
        except NotFoundError, nfe:
            # Typically happens when a person-object has been joined
            # with another one since its creation
            continue

        name = pe.search_person_names(person_id=p_id, name_variant=co.name_full)[0]['name']
        try:
            sapid = pe.get_external_id(source_system=co.system_sap,
                                       id_type=co.externalid_sap_ansattnr)[0]['external_id']
        except IndexError:
            sapid = ''
        accounts = []
        for row in ac.search(owner_id=p_id):
            ac.clear()
            ac.find(row['account_id'])
            if ac.is_reserved() or ac.is_deleted() or ac.is_expired():
                status = '(inaktiv)'
            elif ac.get_entity_quarantine():
                status = '(karantene)'
            else:
                status = ''
            accounts.append('%s %s' % (row['name'], status))
        for row in pe.list_affiliations(person_id=p_id, source_system=source_systems):
            persons_by_sko.setdefault(ou2sko[row['ou_id']], []).append({
                'pid': p_id,
                'name': name,
                'status': str(co.PersonAffStatus(row['status'])),
                'birth': pe.birth_date.strftime('%Y-%m-%d'),
                'sapid': sapid,
                'accounts': ', '.join(accounts),
                })

    output.write("""<html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
            <title>New persons</title>
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
                    width: 10%;
                }
                .meta {
                    color: gray;
                    text-align: right;
                }
            </style>
        </head>
        <body>
    """)

    output.write('<p class="meta">Nye personer fra %s til %s</p>' % (start_date.strftime('%Y-%m-%d'),
                                                                     end_date.strftime('%Y-%m-%d')))
    fakults = []
    for sko in sorted(persons_by_sko):
        fak = "%02s0000" % sko[:2]
        if fak not in fakults:
            output.write("\n<h1>%s</h1>\n" % sko2name[fak])
            fakults.append(fak)

        output.write("\n<h2>%s - %s</h2>\n" % (sko, sko2name[sko]))
        output.write("<table><thead><tr>")
        output.write("<th>Navn</th>")
        output.write("<th>Tilknytning</th>")
        output.write("<th>entity_id</th>")
        output.write("<th>Ansattnr</th>")
        output.write("<th>Fødselsdato</th>")
        output.write("<th>Brukere</th>")
        output.write("</tr></thead>\n")

        for p in persons_by_sko[sko]:
            output.write("\n<tr>\n")
            output.write("<td>%s</td>\n" % p['name'])
            output.write("<td>%s</td>\n" % p['status'])
            output.write("<td>%s</td>\n" % p['pid'])
            output.write("<td>%s</td>\n" % p['sapid'])
            output.write("<td>%s</td>\n" % p['birth'])
            output.write("<td>%s</td>\n" % p['accounts'])
            output.write("</tr>\n")

        output.write("</table>\n")

    output.write("""
        <p class="meta">Generert: %s</p>\n</body>
        \n</html>\n""" % now().strftime('%Y-%m-%d kl %H:%M'))


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

    process(output=output, source_systems=source_systems,
            start_date=start_date, end_date=end_date)
    if not output is sys.stdout:
        output.close()

if __name__ == '__main__':
    main()
