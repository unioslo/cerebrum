#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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
Generer to csv-filer for å eksporteres til adgangskontrollsystemet Bewator:

    1. Personer:

        <adgangskort-id>;<studentnr|ansattnr>;<etternavn>;<fornavn>;<fullt navn>;<fødselsdato>;<brukernavn>;<tittel|''>;<avdeling|''>;<mobil>

        - 1: <adgangskort-id>: en external_id som alle personer skal ha fått
          generert (se contrib/no/hih/generate_bewator_spreads_and_ids.py).
          Skal vere unike.

        - 2: <studentnr|ansattnr>: student- eller ansattnummer slik denne er
          registrert i Cerebrum. For personer som både er student og ansatt
          eksporteres ansattnummer.

        - 3: <etternavn>

        - 4: <fornavn>

        - 5: <fullt navn>

        - 6: <fødselsdato>: TBD: kva format? Er YYYY-MM-DD ok?

        - 7: <brukernavn>: TBD: Primærbrukar? Ein av brukarane? Alle
          brukarane?

        - 8: <tittel|''>: For ansatte er dette stillingstittel fra SAP. For
          studenter skal feltet være blankt.

        - 9: <avdeling|''>: akronym for tilsettingsenheten (f.eks. STUDADM for
          Studieadministrasjonen, Tjeneste for Tjenesteyting osv.). For
          studenter skal feltet være blankt.

        - 10: <mobil>: Mobiltelefonnummer fra SAP eller FS dersom det er
          tilgjengelig. Det skal sjekkes at nummeret består av 8 siffer, andre
          kombinasjoner skal forkastes.

    2. Tilgangsgrupper:

        <gruppenavn>;<medlem1, medlem2,...>

        - <gruppenavn>: navnet på adgangsgruppa slik det er registrert i
          Cerebrum.

        - <medlem>: adgangskort-id'en til medlemmet.

            TODO: skal alle medlem av adgangsgrupper vere med, eller hentar vi
            berre ut personar? Eg gjetter på personar i første omgang.
"""

import sys, getopt

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
pe = Factory.get('Person')(db)
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)
ou = Factory.get('OU')(db)
co = Factory.get('Constants')(db)
logger = Factory.get_logger('cronjob')

def usage(exitcode=0):
    print """Usage: %s --userfile <path> --groupfile <path>

    Generate two csv files with data for the access system Bewator.
    
    --userfile      The csv file with user data for bewator

    --groupfile     The csv file with access data for bewator
    """ % sys.argv[0]
    sys.exit(exitcode)

def process(userout, groupout):
    logger.debug('Start caching data')
    # cache all relevant data
    ent2adgid = dict((row['entity_id'], row['external_id']) for row in
                     pe.list_external_ids(id_type=co.externalid_bewatorid))
    logger.debug('Found %d entities with bewator id', len(ent2adgid))

    ent2ansno = dict((row['entity_id'], row['external_id']) for row in
                     pe.list_external_ids(id_type=co.externalid_sap_ansattnr))
    ent2studno = dict((row['entity_id'], row['external_id']) for row in
                     pe.list_external_ids(id_type=co.externalid_studentnr))
    ent2firstname = dict((row['person_id'], row['name']) for row in
                     pe.list_persons_name(source_system=co.system_cached,
                                          name_type=co.name_first))
    ent2lastname  = dict((row['person_id'], row['name']) for row in
                     pe.list_persons_name(source_system=co.system_cached,
                                          name_type=co.name_last))
    ent2fullname = dict((row['person_id'], row['name']) for row in
                     pe.list_persons_name(source_system=co.system_cached,
                                          name_type=co.name_full))
    ent2title = dict((row['person_id'], row['name']) for row in
                     pe.list_persons_name(source_system=co.system_sap,
                                          name_type=co.name_work_title))
    ent2phone = dict((row['entity_id'], row['contact_value']) for row in 
                     pe.list_contact_info(source_system=(co.system_sap, co.system_fs)))
    employees = set(row['person_id'] for row in 
                     pe.list_affiliations(source_system=co.system_sap))
    students = set(row['person_id'] for row in 
                     pe.list_affiliations(source_system=co.system_fs,
                                          affiliation=co.affiliation_student))
    ou2acr = dict((row['ou_id'], row['acronym']) for row in ou.search())
    ent2avdeling = dict()
    for row in pe.list_affiliations(source_system=co.system_sap):
        ent2avdeling.setdefault(row['person_id'], []).append(ou2acr[row['ou_id']])

    # TODO: this does not guarantee primary accounts - is that ok?
    ent2account = dict((row['owner_id'], row['name']) for row in 
                     ac.search(owner_type=co.entity_person))
    published = set()

    logger.debug('Starting on users')
    for row in pe.search(spread=co.spread_adgang_person, exclude_deceased=True):
        ent = row['person_id']
        if ent in published: # TODO: this is not necessary if pe.search only
                            # returns same person once
            continue

        # adgangskort-id
        if not ent2adgid.has_key(ent):
            logger.warning("Person %d doesn't have a bewator id", ent)
            continue
        line = [ent2adgid[ent]]

        # studentnummer|ansattnummer
        if ent in employees and ent2ansno.has_key(ent):
            line.append(ent2ansno[ent])
        elif ent in students and ent2studno.has_key(ent):
            line.append(ent2studno[ent])
        else:
            logger.debug("Person %d not employee/student (or hasn't studno/ansno), " % ent)
            line.append('')

        # etternavn
        line.append(ent2lastname.get(ent, ''))
        # fornavn
        line.append(ent2firstname.get(ent, ''))
        # fullt navn
        line.append(ent2fullname.get(ent, ''))
        # fødselsdato        
        # TODO: not sure about the format
        line.append(row['birth_date'].strftime('%Y-%m-%d'))

        # brukernavn
        line.append(ent2account.get(ent, ''))

        if ent in employees:
            # tittel
            line.append(ent2title.get(ent, ''))
            # avdeling
            # TODO: usikker på korleis personar med fleire avdelingar skal
            # presenterast - tolka spesifikasjonen sin <avdeling|''> som
            # konkatenering med |
            line.append('|'.join(ent2avdeling.get(ent, '')))
        elif ent in students:
            # tittel
            line.append('')
            # avdeling
            line.append('')
        else:
            line.append('')
            line.append('')

        # mobil
        phone = ent2phone.get(ent, '')
        if not phone or len(phone) != 8 or not phone.isdigit():
            phone = ''
        line.append(phone)
        
        # TODO: loop over the items in line and substitute '; with something
        # else? E.g. ':'
        userout.write(';'.join(line))
        userout.write("\n")
        published.add(ent)

    logger.debug("Users finished")

    logger.debug("Starting on groups")
    for g in gr.search(spread=co.spread_adgang_group):
        try:
            members = set(ent4adgid[row['member_id']] for row in
                          gr.search_members(group_id=g['group_id'],
                                            member_type=co.entity_person)
                           if row['member_id'] in published)
        except KeyError, e:
            logger.warning("%s - person missing bewator id. Skipping group %s.", e, g['name'])
            continue
        groupout.write("%s;%s\n" % (g['name'], ','.join(members)))
    logger.debug("Groups finished")
    
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'h',
                                   ['userfile=',
                                    'groupfile=',
                                    'help'])
    except getopt.GetoptError, e:
        print e
        sys.exit(1)
    
    userout = groupout = sys.stdout

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--userfile',):
            userout = file(val, 'w')
        elif opt in ('--groupfile',):
            groupout = file(val, 'w')
    process(userout, groupout)

if __name__ == '__main__':
    main()
