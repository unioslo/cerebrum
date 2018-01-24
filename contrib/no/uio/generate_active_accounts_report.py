#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

"""This script is a tool used to check active accounts in Cerebrum
and send email as alarm when the number is greater than allowed.
"""
import sys
import getopt
from Cerebrum import Utils
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pr = Factory.get('Person')(db)
ou = Factory.get('OU')(db)

def usage(exit_status = 0):
    print """Usage: %s [options]
    
    --min [Nr1]       The default vaule for Nr1 is 1. Check the persons
                      who have more than Nr1 active accounts in Cerebrum.
                       
    --max [Nr2]       Check the persons who have less than Nr2 active
                      accounts in Cerebrum.

    --source_systems  Comma separated list of source system will search through.
                      Defaults to 'SAP,FS'.
                    
    -o, --output      The file to print the report to. Defaults to screen.

    --mail-from       The email address setted to send the report as an email.

    --mail-to         The email address setted to receive the report.
                       
    -h, --help        See this help infomation and exit.
    
    """ % sys.argv[0]
    
    sys.exit(exit_status)

def accountNr(minimum, maxmum, accs):
    """
    Compare the number of accounts in the 'accs' list for each person
    with the input option number 'minimum' and 'maxmum'.
    """
    
    if len(accs) < minimum:
        return False
    if  maxmum and len(accs) > maxmum:
        return False
    return True

def checkACaccount(source_systems, minimum, maxmum, outputstream):
    """
    Check the accounts for each person and report the results into
    print or file. Return the person_ids whose number of accounts is
    between 'minimum' and 'maxmum'.
    """
    source_systems = [int(co.AuthoritativeSystem(sys)) for sys in
                      source_systems.split(',')]
    ou2sko = dict((row['ou_id'], "%02d%02d%02d" % (row['fakultet'],
                                                    row['institutt'],
                                                    row['avdeling']))
                  for row in ou.get_stedkoder())
    sko2name = dict((ou2sko[row['entity_id']], row['name']) for row in
                    ou.search_name_with_language(name_variant=co.ou_name_display,
                                                 name_language=co.language_nb))

    persons_by_sko = {}
    nr_person = 0
    persons = ''
    for p_id in pr.list_persons():
        pr.clear()
        pr.find(p_id['person_id'])
        accs = pr.get_accounts()
        name = pr.search_person_names(person_id=p_id['person_id'],
                                      name_variant=co.name_full)[0]['name']
        try:
            sapid = pr.get_external_id(source_system=co.system_sap,
                                       id_type=co.externalid_sap_ansattnr)[0]['external_id']
        except IndexError:
            sapid = ''
        if accountNr(minimum, maxmum, accs):
            nr_person += 1
            persons += "\n%s" % str(p_id['person_id'])
            accounts = ''
            for row in accs:
                ac.clear()
                ac.find(row['account_id'])
                accounts += ac.account_name
                accounts += ", "
            for row in pr.list_affiliations(person_id=p_id['person_id'],
                                            source_system=source_systems):
                persons_by_sko.setdefault(ou2sko[row['ou_id']], []).append({
                    'name': name,
                    'sapid': sapid,
                    'accountsnr': len(accs),
                    'accounts': accounts,
                    })
    if maxmum:
        msg = "%s persons have acctive accounts between %s and %s" % (nr_person, minimum, maxmum)
    else:
        msg = "%s persons have more than %s acctive accounts" % (nr_person, minimum)
    outputstream.write('<p class="meta">%s</p>' % msg)
    persons += "\n\n%s" % msg
    fakults = []
    for sko in sorted(persons_by_sko):
        fak = "%02s0000" % sko[:2]
        if fak not in fakults:
             outputstream.write("\n<h1>%s</h1>\n" % sko2name[fak])
             fakults.append(fak)
        outputstream.write("\n<h2>%s - %s</h2>\n" % (sko, sko2name[sko]))
        outputstream.write("<table><thead><tr>")
        outputstream.write("<th>Navn</th>")
        outputstream.write("<th>Ansattnummer</th>")
        outputstream.write("<th>Antall brukere</th>")
        outputstream.write("<th>Brukernavn</th>")
        outputstream.write("</tr></thead>\n")
        for p in persons_by_sko[sko]:
            outputstream.write("\n<tr>\n")
            outputstream.write("<td>%s</td>\n" % p['name'])
            outputstream.write("<td>%s</td>\n" % p['sapid'])
            outputstream.write("<td>%s</td>\n" % p['accountsnr'])
            outputstream.write("<td>%s</td>\n" % p['accounts'])
        outputstream.write("</table>\n")
    outputstream.write("</body>\n</html>\n")
    return persons

    
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ho:',
                                   ['help', 'min=', 'max=',
                                    'mail-to=', 'mail-from=',
                                    'source_systems=', 'output='])
    except getopt.GetoptError:
        usage(1)

    minimum = 1  
    maxmum = None
    outputstream = sys.stdout
    mail_to = None
    mail_from = None
    source_systems = 'SAP,FS'
    
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--min'):
            minimum = int(val)
            if minimum < 0:
                usage(2)
        elif opt in ('--max'):
            maxmum = int(val)
            if maxmum < 0 or maxmum < minimum:
                usage(3)
        elif opt in ('--source_systems'):
            source_systems = val
        elif opt in ('-o', '--output'):
            outputstream = open(val, 'w')
            outputstream.write("""<html>
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
            <title>Active accounts report</title>
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
        elif opt in ('--mail-to'):
            mail_to = val
        elif opt in ('--mail-from'):
            mail_from = val
        else:
            usage(4)
    persons = 'These following persons are found in Cerebrum:\n\nperson_id'
    persons += checkACaccount(source_systems, minimum, maxmum, outputstream)

    if not outputstream is sys.stdout:
        outputstream.close()
          
    if mail_to:
        subject = "Report from check_acctive_account.py"
        Utils.sendmail(mail_to, mail_from, subject, persons)
            

if __name__ == '__main__':
    main()
