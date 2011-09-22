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

def usage(exitcode=0):
    print """Usage: generate_new_persons.report.py [--from 2011-09-20]

    --from            Date to start searching for new persons from. Defaults
                      to 7 days ago.
    
    --to              Date to start searching for new persons until. Defaults
                      to now.

    --html            If the output file should be formatted with simple html.

    --source_systems  Comma separated list of source systems to search
                      through. Defaults to 'SAP,FS'.
    """
    sys.exit(exitcode)

def process(source_systems, start_date, end_date=now(), html=False):
    """Get all persons from db created in a given period and print them out,
    sorted by their OU."""

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
        name = pe.search_person_names(person_id=p_id, name_variant=co.name_full)[0]['name']
        pe.clear()
        pe.find(p_id)
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

    # print it
    if html:
        print """<html>
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
                    .footer {
                        color: gray;
                        text-align: right;
                    }
                </style>
            </head>
            <body>
        """
    fakults = []
    for sko in sorted(persons_by_sko):
        fak = "%02s0000" % sko[:2]
        if html and fak not in fakults:
            print "\n<h1>%s</h1>\n" % sko2name[fak]
            fakults.append(fak)

        if html:
            print "\n<h2>%s - %s</h2>" % (sko, sko2name[sko])
            print "<table><thead><tr>"
            print "<th>Navn</th>"
            print "<th>Tilknytning</th>"
            print "<th>entity_id</th>"
            print "<th>Ansattnr</th>"
            print "<th>Fødselsdato</th>"
            print "<th>Brukere</th>"
            print "</tr></thead>"
        else:
            print "\n=== %s ===\n" % sko

        for p in persons_by_sko[sko]:
            if html:
                print "<tr>"
                print "<td>%s</td>" % p['name']
                print "<td>%s</td>" % p['status']
                print "<td>%s</td>" % p['pid']
                print "<td>%s</td>" % p['sapid']
                print "<td>%s</td>" % p['birth']
                print "<td>%s</td>" % p['accounts']
                print "</tr>"
            else:
                print "%s;%s;entity_id:%d" % (p['name'], p['status'], p['pid'])

        if html:
            print "</table>"

    if html:
        print """
            <p class="footer">Generert: %s</p>
            </body>
        </html>
        """ % now().strftime('%Y-%m-%d kl %H:%I')

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                ['from=', 'to=', 'source_systems=', 'html'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    end_date = now()
    start_date = now() + RelativeDateTime(days=-7)
    source_systems = 'SAP,FS'
    html = False

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--from', ):
            start_date = ISO.ParseDate(val)
        elif opt in ('--to', ):
            end_date = ISO.ParseDate(val)
        elif opt in ('--html', ):
            html = True
        elif opt in ('--source_systems', ):
            source_systems = val
    process(source_systems=source_systems, start_date=start_date, end_date=end_date, html=html)

if __name__ == '__main__':
    main()
