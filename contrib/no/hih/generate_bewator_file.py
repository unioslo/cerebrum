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

        - <adgangskort-id>: en external_id som alle personer skal ha fått
          generert (se contrib/no/hih/generate_bewator_spreads_and_ids.py).
          Skal vere unike.

        - <studentnr|ansattnr>: student- eller ansattnummer slik denne er
          registrert i Cerebrum. For personer som både er student og ansatt
          eksporteres ansattnummer.

        - <tittel|''>: For ansatte er dette stillingstittel fra SAP. For
          studenter skal feltet være blankt.

        - <avdeling|''>: akronym for tilsettingsenheten (f.eks. STUDADM for
          Studieadministrasjonen, Tjeneste for Tjenesteyting osv.). For
          studenter skal feltet være blankt.

        - <mobil>: Mobiltelefonnummer fra SAP dersom det er tilgjengelig. For
          studenter skal feltet være blankt. Det skal sjekkes at nummeret består
          av 8 siffer, andre kombinasjoner skal forkastes.

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
co = Factory.get('Constants')(db)
logger = Factory.get_logger('console')

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
    #ent2phone = dict((row['entity_id'], row['contact_value']) for row in 
    #                 pe.list_contact_info(source_system=co.system_sap))
    employees = set(row['person_id'] for row in 
                     pe.list_affiliations(source_system=co.system_sap))
    students = set(row['person_id'] for row in 
                     pe.list_affiliations(source_system=co.system_fs,
                                          affiliation=co.affiliation_student))
    # TODO: this does not guarantee primary accounts - is that ok?
    ent2account = dict((row['owner_id'], row['name']) for row in 
                     ac.search(owner_type=co.entity_person))
    finished = []

    logger.debug('Starting on users')
    for row in pe.search(spread=co.spread_adgang_person, exclude_deceased=True):
        ent = row['person_id']
        if ent in finished: # TODO: this is not necessary if pe.search only
                            # returns same person once
            continue
        finished.append(ent)

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
            logger.warning("Person %d not employee/student (or hasn't studno/ansno)" % ent)
            continue

        # TODO: handle undefined names and other cached data

        # etternavn
        line.append(ent2lastname[ent])
        # fornavn
        line.append(ent2firstname[ent])
        # fullt navn
        line.append(ent2fullname[ent])
        # fødselsdato        
        # TODO: not sure about the format
        line.append(row['birth_date'].strftime('%Y-%m-%d'))

        # brukernavn
        line.append(ent2account[ent])

        # tittel...
        # avdeling...
        # mobil
        if ent not in employees:
            line.append('')
            line.append('')
            line.append('')
        else:
            line.append('tittel')
            line.append('avdeling')
            # Jazz, 2011-08-12
            # we need to think about the phone numbers, we need to use
            # both system_sap, system_fs and system_manual here
            #phone = ent2phone[ent]
            #if len(phone) == 8 and phone.is_digit():
            #    line.append('mobil')
            else:
                line.append('')
        
        # TODO: loop over the items in line and substitute '; with something
        # else? E.g. ':'
        userout.write(';'.join(line))
        userout.write("\n")
    logger.debug("Users finished")

    logger.debug("Starting on groups")
    for g in gr.search(spread=co.spread_adgang_group):
        try:
            members = set(ent4adgid[row['member_id']] for row in
                          gr.search_members(group_id=g['group_id'],
                                            member_type=co.entity_person))
        except KeyError, e:
            logger.warning("Some person is missing bewator id group %d. Group is skipped.", g['name'])
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
            print "not implemented yet"
            sys.exit(0)
        elif opt in ('--userfile',):
            userout = file(val, 'w')
        elif opt in ('--groupfile',):
            groupout = file(val, 'w')
    process(userout, groupout)

if __name__ == '__main__':
    main()
