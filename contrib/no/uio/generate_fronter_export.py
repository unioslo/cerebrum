#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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


#            Gruppene angitt på øverste linje i tabellen har rettighet
#            til entitetene angitt i kolonnen ytterst til venstre.
#
# ---------+---------+---------+---------+---------+----------+------------
#   Gruppe:|  EnhAns | Akt1Ans | Akt2Ans | EnhStud | Akt1Stud | Akt2Stud
# =========================================================================
# Rom:     |*********|*********|*********|*********|**********|************
# ---------+---------+---------+---------+---------+----------+------------
# Felles   |  Owner  |  Owner  |  Owner  |  Write  |          |
# ---------+---------+---------+---------+---------+----------+------------
# Lærer    |  Owner  |  Owner  |  Owner  |         |          |
# ---------+---------+---------+---------+---------+----------+------------
# Akt. 1   |         |  Owner  |         |         |   Write  |
# ---------+---------+---------+---------+---------+----------+------------
# Akt. 2   |         |         |  Owner  |         |          |   Write
# =========================================================================
# Korridor:|*********|*********|*********|*********|**********|************
# ---------+---------+---------+---------+---------+----------+------------
# Emnets   |         |         |         |         |          |
# hovedkorr|         |         |         |         |          |
# ---------+---------+---------+---------+---------+----------+------------
# Undervisn|AdminLite|AdminLite|AdminLite|         |          |
# rom-korr.| Room Cr.| Room Cr.| Room Cr.|         |          |
# =========================================================================
# Gruppe:  |*********|*********|*********|*********|**********|************
# ---------+---------+---------+---------+---------+----------+------------
# EnhAns   | View C. | View C. | View C. | View C. |  View C. |  View C.
# ---------+---------+---------+---------+---------+----------+------------
# Akt1Ans  | View C. | View C. | View C. | View C. |  View C. |
# ---------+---------+---------+---------+---------+----------+------------
# Akt2Ans  | View C. | View C. | View C. | View C. |          |  View C.
# ---------+---------+---------+---------+---------+----------+------------
# EnhStud  | View C. | View C. | View C. | View C. |          |
# ---------+---------+---------+---------+---------+----------+------------
# Akt1Stud | View C. | View C. |         |         |  View C. |
# ---------+---------+---------+---------+---------+----------+------------
# Akt2Stud | View C. |         | View C. |         |          |  View C.
# ---------+---------+---------+---------+---------+----------+------------

# Navngiving:
#   Grupper (med personmedlemmer):
#     Ansvar und.enh:     uio.no:fs:<enhetid>:enhetsansvar
#     Ansvar und.akt:     uio.no:fs:<enhetid>:aktivitetsansvar:<aktkode>
#     Alle stud. v/enh:   uio.no:fs:<enhetid>:student
#     Alle stud. v/akt:   uio.no:fs:<enhetid>:student:<aktkode>
#
#   Strukturnoder/rom:
#     UiO-enhet-korr.:    STRUCTURE/Sko:<institusjonsnr>:<stedkode>
#     Hovedkorr. enh:     STRUCTURE/Enhet:<ENHETID>
#     Undv.korr. enh:     STRUCTURE/Studentkorridor:<ENHETID>
#     Fellesrom enh:      ROOM/Felles:<ENHETID>
#     Lærerrom enh:       ROOM/Larer:<ENHETID>
#     Aktivitetsrom:      ROOM/Aktivitet:<ENHETID>:<AKTKODE>
#
# <enhetid> :=
#   kurs:<institusjonsnr>:<emnekode>:<versjon>:<terminkode>:<år>:<terminnr>
#  eller
#   evu:<etterutdkurskode>:<kurstidsangivelsekode>

import getopt
import sys
import re
import locale

import cerebrum_path
import cereconf
from Cerebrum.modules.no.uio import fronter_lib
from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum.modules import PosixUser
from Cerebrum import Errors

cf_dir = '/cerebrum/dumps/Fronter'
root_sko = '900199'
root_struct_id = 'UiO root node'
group_struct_id = "UREG2000@uio.no imported groups"
group_struct_title = 'Automatisk importerte grupper'

# Module globals, properly initialized in main().
db = const = logger = fronter = xml = None
new_group = old_group = group_updates = None
new_users = old_users = deleted_users = user_updates = None
new_rooms = old_rooms = room_updates = None
new_groupmembers = old_groupmembers = groupmember_updates = None
new_acl = old_acl = acl_updates = None

def usage(exitcode=0):
    print """Usage: [options] outfile
    -h  --host name : fronter host to use
    --fs-db-user uname : uname when connecting to FS
    --fs-db-service sid: SID to FS instance
    --debug-file name: name of debug file (used by fronter)
    --debug-level level: number of debug level (used by fronter)

    Will connect to the specified fronter host and compare the groups,
    rooms, users and usermemberships therein with settings in Cerebrum
    and FS.  Builds and XML file in outfile that can be imported into
    Fronter to sync the databases.
    """
    sys.exit(exitcode)

def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'fs-db-user=', 'fs-db-service=',
                                    'debug-file=', 'debug-level='])
    except getopt.GetoptError:
        usage(1)
    host = 'kladdebok.uio.no'
    fs_db_user = 'ureg2000'
    fs_db_service = 'FSPROD.uio.no'
    debug_file = "%s/x-import.log" % cf_dir
    debug_level = 4
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--fs-db-user':
            fs_db_user = val
        elif opt == '--fs-db-service':
            fs_db_service = val
        elif opt == '--debug-file':
            debug_file  = val
        elif opt == '--debug-level':
            debug_level = val

    if len(args) != 1:
        usage(1)

    fs_db = Database.connect(user=fs_db_user, service=fs_db_service,
                             DB_driver='Oracle')
    global db, const, logger, fronter, xml
    db = Factory.get('Database')()
    const = Factory.get('Constants')(db)
    logger = Factory.get_logger("cronjob")
    fronter = fronter_lib.Fronter(host, db, const, fs_db,
                                  logger=logger)
    xml = fronter_lib.FronterXML(args[0],
                                 cf_dir = cf_dir,
                                 debug_file = debug_file,
                                 debug_level = debug_level,
                                 fronter = fronter)
    gen_export(fs_db)
    
def gen_export(fs_db):
    # TODO: grisete med disse globale variablene, fjern dem
    global new_group, old_group, group_updates, new_users, old_users, \
           deleted_users, user_updates, new_rooms, old_rooms, room_updates, \
           new_groupmembers, old_groupmembers, groupmember_updates, \
           new_acl, old_acl, acl_updates

    if 'FS' in [x[0:2] for x in fronter.export]:
        # Fyller %kurs, %emne_versjon, %emne_termnr, %enhet2sko,
        # %kurs2navn, %enhet2akt
        fronter.read_kurs_data()

    xml.start_xml_file(fronter.kurs2enhet)

    logger.info("get_fronter_users()")
    old_users = fronter.get_fronter_users()
    logger.info("get_new_users()")
    new_users = {}
    deleted_users = {}
    new_groupmembers =  {'All_users': {}}
    #new_groupmembers = {'admins':{}}
    #new_groupmembers = {'plain_users':{}}

    user_updates = {fronter.STATUS_ADD: {},
                    fronter.STATUS_UPDATE: {},
                    fronter.STATUS_DELETE: {}}
    get_new_users()

    logger.info("get_fronter_groups()")
    old_group = fronter.get_fronter_groups()
    new_group = {}
    group_updates = {fronter.STATUS_ADD: {},
                     fronter.STATUS_UPDATE: {},
                     fronter.STATUS_DELETE: {}}

    logger.info("get_fronter_rooms()")
    old_rooms = fronter.get_fronter_rooms()
    new_rooms = {}
    room_updates = {fronter.STATUS_ADD: {},
                    fronter.STATUS_UPDATE: {},
                    fronter.STATUS_DELETE: {}}

    new_acl = {}

    # 608-650: legger inn brukermedlemer i %new_groupmembers på
    # cf-gruppenivå 3
    logger.info("reg_supergroups()")
    reg_supergroups()

    # 651-694:  Lag xml for insert/update/delete basert på %user_updates
    logger.info("gen_user_xml()")
    gen_user_xml()

    # 737-1050:
    # - itererer over kurs2enhet, gjør litt forskjellige ting avhengig av
    #   om det er en EVU kurs eller et vanlig emne
    # - evu og "vanlig kurs" delen kan trolig gjenbruke kode
    # - lager noen rom for det aktuelle kurset
    # - setter acl'er
    logger.info("process_kurs2enhet()")
    process_kurs2enhet()

    # 1242-1348:
    # - div kall til register_group_update, register_room_update,
    #   group_to_XML og room_to_XML
    logger.info("process_room_group_updates()")
    current_groups = {}
    current_rooms = {}
    process_room_group_updates(current_groups, current_rooms)

    logger.info("get_fronter_groupmembers()")
#    new_groupmembers = {}
    old_groupmembers = fronter.get_fronter_groupmembers(current_groups)
    groupmember_updates = {fronter.STATUS_ADD: {},
                           fronter.STATUS_UPDATE: {},
                           fronter.STATUS_DELETE: {}}

    # 1435-1462:
    # - div. kall til register_groupmember_update og personmembers_to_XML
    logger.info("process_groupmembers()")
    process_groupmembers()

    logger.info("get_fronter_acl()")
    old_acl = fronter.get_fronter_acl(current_groups, current_rooms)
    acl_updates = {fronter.STATUS_ADD: {},
                   fronter.STATUS_UPDATE: {},
                   fronter.STATUS_DELETE: {}}

    # 1677-1723:
    # - div kall til acl_to_XML og register_acl_update
    logger.info("process_acls()")
    process_acls()
    logger.info("end")
    xml.end()

def list_users_for_fronter_export():  # TODO: rewrite this
    ret = []
    posix_user = PosixUser.PosixUser(db)
    email_addrs = posix_user.getdict_uname2mailaddr()
    logger.debug("list_users_for_fronter_export got %d emailaddrs" %
                 len(email_addrs))
    for row in posix_user.list_extended_posix_users(
        const.auth_type_md5_crypt):
        tmp = {'email': email_addrs.get(row['entity_name'],
                                        '@'.join((row['entity_name'],
                                                  'ulrik.uio.no'))),
               'uname': row['entity_name']}
        if row['gecos'] is None:
            tmp['fullname'] = row['name']
        else:
            tmp['fullname'] = row['gecos']            
        ret.append(tmp)
    return ret

def get_new_users():  # ca 345-374
    # Hent info om brukere i cerebrum
    
    fix_email = re.compile(r'\@UIO_HOST$')
    for user in list_users_for_fronter_export():
        email = fix_email.sub('@ulrik.uio.no', user['email'])
#	print user['fullname']
        # lagt inn denne testen fordi scriptet feilet uten, har en liten
        # følelse av det burde løses på en annen måte
        if user['fullname'] is None:
            continue
        names = re.split('\s+', user['fullname'].strip())
        user_params = {'FAMILY': names.pop(),
                       'GIVEN': " ".join(names),
                       'EMAIL': email,
                       'USERACCESS': 0,
                       'PASSWORD': 'unix:',
                       }

	if 'All_users' in fronter.export:
	    new_groupmembers.setdefault('All_users',
                                        {})[user['uname']] = 1
	    user_params['USERACCESS'] = 'allowlogin'

	if user['uname'] in fronter.admins:
	    user_params['USERACCESS'] = 'administrator'

        # The 'plain_users' setting can be useful for debugging.
	if user['uname'] in fronter.plain_users:
	    user_params['PASSWORD'] = "plain:%s" % user['uname']
        new_users[user['uname']] = user_params
		
    logger.debug("get_new_users returns %i users" % len(new_users))

def register_user_update(operation, uname):
    """Update user_updates with info about changes that should be done
    in Fronter.  Also modifies old_users and new_users"""
    if operation == fronter.STATUS_ADD:
        if not (new_users.has_key(uname) and not old_users.has_key(uname)):
            return
	user_updates[operation][uname] = {
            'PASSWORD': fronter.pwd(new_users[uname]['PASSWORD']),
            'GIVEN': new_users[uname]['GIVEN'],
            'FAMILY': new_users[uname]['FAMILY'],
            'EMAIL': new_users[uname]['EMAIL'],
            'EMAILCLIENT': 1,
            'USERACCESS': fronter.useraccess(new_users[uname]['USERACCESS'])
	    }
	del new_users[uname]
    elif operation == fronter.STATUS_UPDATE:
        if not (new_users.has_key(uname) and old_users.has_key(uname)):
            return
        old = old_users[uname]
        new = new_users[uname]
        if (old['PASSWORD'] != new['PASSWORD'] or
	    old['GIVEN'] != new['GIVEN'] or
	    old['FAMILY'] != new['FAMILY'] or
	    old['EMAIL'] != new['EMAIL'] or
            old['USERACCESS'] != new['USERACCESS']):
            user_updates[operation][uname] = {
                'PASSWORD': fronter.pwd(new['PASSWORD']),
                'GIVEN': new['GIVEN'],
                'FAMILY': new['FAMILY'],
                'EMAIL': new['EMAIL'],
                'EMAILCLIENT': 1,
                'USERACCESS': fronter.useraccess(new['USERACCESS'])
                }
        del new_users[uname]
        del old_users[uname]
    elif operation == fronter.STATUS_DELETE:
        if not (old_users.has_key(uname) and not new_users.has_key(uname)):
            return
	user_updates[operation][uname] = 1
	deleted_users[uname] = 1
	del old_users[uname]

def register_group(title, id, parentid, allow_room=0, allow_contact=0):
    """Adds info in new_group about group."""
    CFid = id
    if re.search(r'^STRUCTURE/(Enhet|Studentkorridor):', id):
        rest = id.split(":")
        corr_type = rest.pop(0)

        if not rest[0] in (fronter.EMNE_PREFIX, fronter.EVU_PREFIX):
            rest.insert(0, fronter.EMNE_PREFIX)
        id = "%s:%s" % (corr_type, fronter_lib.FronterUtils.UE2KursID(*rest))
    new_group[id] = { 'title': title,
                      'parent': parentid,
                      'allow_room': allow_room,
                      'allow_contact': allow_contact,
                      'CFid': CFid,
		      }

def get_group(id):
    group = Factory.get('Group')(db)
    if isinstance(id, str):
        group.find_by_name(id)
    else:
        group.find(id)
    return group

def reg_supergroups():
    register_group("Universitetet i Oslo", root_struct_id, root_struct_id)
    register_group(group_struct_title, group_struct_id, root_struct_id)
    if 'All_users' in fronter.export:
        # Webinterfacet mister litt pusten når man klikker på gruppa
        # All_users (dersom man f.eks. ønsker å gi alle brukere rettighet
        # til noe); oppretter derfor en dummy-gruppe som kun har den
        # /egentlige/ All_users-gruppa som medlem.
        sg_id = "All_users_supergroup"
        register_group("Alle brukere", sg_id, root_struct_id, 0, 0)
        register_group("Alle brukere (STOR)", 'All_users', sg_id, 0, 1)

    for sgname in fronter.supergroups:
        # $sgname er på nivå 2 == Kurs-ID-gruppe.  Det er på dette nivået
        # eksport til ClassFronter er definert i Ureg2000.
        try:
            group = get_group(sgname)
        except Errors.NotFoundError:
            continue
        for member_type, group_id in \
            group.list_members(member_type = const.entity_group)[0]:
	    # $gname er på nivå 3 == gruppe med brukere som medlemmer.
	    # Det er disse gruppene som blir opprettet i ClassFronter
	    # som følge av eksporten.
            group = get_group(group_id)
            register_group(group.description, group.group_name,
                           group_struct_id, 0, 1)
            #
            # All groups should have "View Contacts"-rights on
            # themselves.
            new_acl.setdefault(group.group_name, {})[group.group_name] = {
                'gacc': '100',   # View Contacts
                'racc': '0'} 	 # None
            #
            # Groups populated from FS aren't expanded recursively
            # prior to export.
            for row in \
                group.list_members(member_type = const.entity_account,
                                   get_entity_name = True)[0]:
                uname = row[2]
                if new_users.has_key(uname):
                    if new_users[uname]['USERACCESS'] != 'administrator':
                        new_users[uname]['USERACCESS'] = 'allowlogin'
                    new_groupmembers.setdefault(group.group_name,
                                                {})[uname] = 1

def gen_user_xml():
    # Nå har vi fått oversikt over hvilke brukere som er medlem i de
    # eksporterte gruppene, og kan foreta XML-output for brukerelementene.

    for (status, tmp_dict) in ((fronter.STATUS_ADD, new_users),
                               (fronter.STATUS_UPDATE, new_users),
                               (fronter.STATUS_DELETE, old_users)):
        for id in tmp_dict.keys():
            register_user_update(status, id)

        for id in user_updates.get(status, {}).keys():
            xml.user_to_XML(id, status,
                            user_updates[status][id])
        del user_updates[status]

def get_sted(stedkode=None, entity_id=None):
    sted = Factory.get('OU')(db)
    if stedkode is not None:
        sted.find_stedkode(int(stedkode[0:2]),
                           int(stedkode[2:4]),
                           int(stedkode[4:6]),
                           cereconf.DEFAULT_INSTITUSJONSNR)
    else:
        sted.find(entity_id)
    # Only OUs where katalog_merke is set should be returned; if no
    # such OU can be found by moving towards the root of the OU tree,
    # return None.
    if sted.katalog_merke == 'T':
        return sted
    elif (sted.fakultet, sted.institutt, sted.avdeling) == (15, 0, 30):
        # Special treatment of UNIK; even though katalog_merke isn't
        # set for this OU, return it, so that they get their own
        # corridor.
        return sted
    parent_id = sted.get_parent(const.perspective_lt)
    if parent_id is not None and parent_id <> sted.entity_id:
        return get_sted(entity_id = parent_id)
    return None

def build_structure(sko, allow_room=0, allow_contact=0):
    # rekursiv bygging av sted som en gruppe
    if sko == root_sko:
        return root_struct_id
    if not sko:
        return None

    id = "STRUCTURE/Sko:185:%s" % sko
    if ((not new_group.has_key(id)) or
        (allow_room and
	 new_group[id]['allow_room'] != allow_room) or
	(allow_contact and
         new_group[id]['allow_contact'] != allow_contact)):
	# Insert ancestors first; by not passing $allow_* on up the
	# tree, we're causing nodes that are created purely as
	# ancestors to allow neither rooms nor contacts.
        sted = get_sted(stedkode=sko)
        if sted is None:
            # This shouldn't happen, but if it does, there's not much
            # we can do to salvage the situation.  Bail out by
            # returning None.
            return None
        try:
            parent_sted = get_sted(entity_id=sted.get_parent(const.perspective_lt))
        except Errors.NotFoundError:
	    logger.warn("Stedkode <%s> er uten foreldre; bruker %s" %
                        (sko, root_sko))
	    parent = build_structure(root_sko)
        else:
            parent = build_structure("%02d%02d%02d" % (
                parent_sted.fakultet,
                parent_sted.institutt,
                parent_sted.avdeling))
	register_group(sted.name, id, parent, allow_room, allow_contact)
    return id

def process_single_enhet_id(kurs_id, enhet_id, struct_id, emnekode,
                            groups, enhet_node, undervisning_node,
                            termin_suffix=""):
    # I tillegg kommer så evt. rom knyttet til de
    # undervisningsaktivitetene studenter kan melde seg på.
    for akt in fronter.enhet2akt.get(enhet_id, []):
        aktkode, aktnavn = akt

        aktans = "uio.no:fs:%s:aktivitetsansvar:%s" % (
            enhet_id.lower(), aktkode.lower())
        groups['aktansv'].append(aktans)
        aktstud = "uio.no:fs:%s:student:%s" % (
            enhet_id.lower(), aktkode.lower())
        groups['aktstud'].append(aktstud)

        # Aktivitetsansvarlig skal ha View Contacts på studentene i
        # sin aktivitet.
        new_acl.setdefault(aktstud, {})[aktans] = {'gacc': '100',
                                                   'racc': '0'}
        # ... og omvendt.
        new_acl.setdefault(aktans, {})[aktstud] = {'gacc': '100',
                                                   'racc': '0'}

        # Alle med ansvar for (minst) en aktivitet tilknyttet
        # en undv.enhet som hører inn under kurset skal ha
        # tilgang til kursets undervisningsrom-korridor samt
        # lærer- og fellesrom.
        new_acl.setdefault(undervisning_node, {})[aktans] = {
            'gacc': '250',		# Admin Lite
            'racc': '100'}		# Room Creator
        new_acl.setdefault("ROOM/Felles:%s" % struct_id, {})[aktans] = {
            'role': fronter.ROLE_CHANGE}
        new_acl.setdefault("ROOM/Larer:%s" % struct_id, {})[aktans] = {
            'role': fronter.ROLE_CHANGE}

        # Alle aktivitetsansvarlige skal ha "View Contacts" på
        # gruppen All_users dersom det eksporteres en slik.
        if 'All_users' in fronter.export:
            new_acl.setdefault('All_users', {})[aktans] = {'gacc': '100',
                                                           'racc': '0'}

        akt_rom_id = "ROOM/Aktivitet:%s:%s" % (enhet_id.upper(),
                                               aktkode.upper())
        akt_tittel = "%s - %s%s" % (emnekode.upper(), aktnavn, termin_suffix)
        new_rooms[akt_rom_id] = {'title': akt_tittel,
                                 'parent': enhet_node,
                                 'CFid': akt_rom_id}
        new_acl.setdefault(akt_rom_id, {})[aktans] = {
            'role': fronter.ROLE_CHANGE}
        new_acl.setdefault(akt_rom_id, {})[aktstud] = {
            'role': fronter.ROLE_WRITE}

    # Til slutt deler vi ut "View Contacts"-rettigheter på kryss og
    # tvers.
    for gt in groups.keys():
        other_gt = {'enhansv': ['enhstud', 'aktansv', 'aktstud'],
                    'enhstud': ['enhansv', 'aktansv'],
                    'aktansv': ['enhansv', 'aktansv', 'enhstud'],
                    'aktstud': ['enhansv'],
                   }
        for g in groups[gt]:
            # Alle grupper skal ha View Contacts på seg selv.
            new_acl.setdefault(g, {})[g] = {'gacc': '100',
                                            'racc': '0'}
            #
            # Alle grupper med gruppetype $gt skal ha View
            # Contacts på alle grupper med gruppetype i
            # $other_gt{$gt}.
            for o_gt in other_gt[gt]:
                for og in groups[o_gt]:
                    new_acl.setdefault(og, {})[g] = {'gacc': '100',
                                                     'racc': '0'}
    
def process_kurs2enhet():
    # TODO: some code-duplication has been reduced by adding
    # process_single_enhet_id.  Recheck that the reduction is correct.
    # It should be possible to move more code to that subroutine.
    for kurs_id in fronter.kurs2enhet.keys():
        type = kurs_id.split(":")[0].lower()
        if type == fronter.EMNE_PREFIX.lower():
            enhet_sorted = fronter.kurs2enhet[kurs_id][:]
            enhet_sorted.sort(fronter._date_sort)
            # Bruk eldste enhet som $enh_id
            enh_id = enhet_sorted[0]
            enhet = enh_id.split(":", 1)[1]
            struct_id = enh_id.upper()	# Default, for korridorer som
                                        # ikke finnes i CF.
            if old_group.has_key("STRUCTURE/Enhet:%s" % kurs_id):
                # Struktur-ID må forbli uforandret i hele kursets levetid,
                # slik at innhold lagt inn i eksisterende rom blir værende
                # der.
                #
                # Så, dersom det allerede finnes en
                # "STRUCTURE/Enhet"-korridor for denne kurs-IDen i
                # ClassFronter, kan vi plukke eksisterende $struct_id
                # derfra.
                CFid = old_group["STRUCTURE/Enhet:%s" % kurs_id]['CFid']
                # Stripp vekk "STRUCTURE/Enhet:" fra starten for å få
                # eksisterende $struct_id.
                struct_id = CFid.split(":", 1)[1]

            Instnr, emnekode, versjon, termk, aar, termnr = enhet.split(":")
            # Opprett strukturnoder som tillater å ha rom direkte under
            # seg.
            sko_node = build_structure(fronter.enhet2sko[enh_id])
            enhet_node = "STRUCTURE/Enhet:%s" % struct_id
            undervisning_node = "STRUCTURE/Studentkorridor:%s" % struct_id

            tittel = "%s - %s, %s %s" % (emnekode.upper(),
                                         fronter.kurs2navn[kurs_id],
                                         termk.upper(), aar)
            multi_enhet = []
            termin_suffix = ""
            multi_id = ":".join((Instnr, emnekode, termk, aar))
            if (# Det finnes flere und.enh. i semesteret angitt av
                # 'terminkode' og 'arstall' hvor både 'institusjonsnr'
                # og 'emnekode' er like, men 'terminnr' varierer.
                len(fronter.emne_termnr[multi_id]) > 1
                # Det finnes mer enn en und.enh. som svarer til samme
                # "kurs", e.g. både 'høst 2004, terminnr=1' og 'vår
                # 2005, terminnr=2' finnes.
                or len(enhet_sorted) > 1
                # Denne und.enh. har terminnr større enn 1, slik at
                # det er sannsynlig at det finnes und.enh. fra
                # tidligere semester som hører til samme "kurs".
                or int(termnr) > 1):
                #
                # Dersom minst en av testene over slår til, er det her
                # snakk om et "flersemesteremne" (eller i alle fall et
                # emne som i noen varianter undervises over flere
                # semestere).  Ta med terminnr-angivelse i tittelen på
                # kursets hovedkorridor, og semester-angivelse i
                # aktivitetsrommenes titler.
                multi_enhet.append("%s. termin" % termnr)
                termin_suffix = " %s %s" % (termk.upper(), aar)
            if len(fronter.emne_versjon[multi_id]) > 1:
                multi_enhet.append("v%s" % versjon)
            if multi_enhet:
                tittel += ", " + ", ".join(multi_enhet)

            register_group(tittel, enhet_node, sko_node, 1)
            register_group("%s - Undervisningsrom" % emnekode.upper(),
                           undervisning_node, enhet_node, 1);

            # Alle eksporterte kurs skal i alle fall ha ett fellesrom og
            # ett lærerrom.
            new_rooms["ROOM/Felles:%s" % struct_id] = {
                'title': "%s - Fellesrom" % emnekode.upper(),
                'parent': enhet_node,
                'CFid': "ROOM/Felles:%s" % struct_id}
            new_rooms["ROOM/Larer:%s" % struct_id] = {
                'title': "%s - Lærerrom" % emnekode.upper(),
                'parent': enhet_node,
                'CFid': "ROOM/Larer:%s" % struct_id}

            for enhet_id in fronter.kurs2enhet[kurs_id]:
                enhans = "uio.no:fs:%s:enhetsansvar" % enhet_id.lower()
                enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
                # De ansvarlige for undervisningsenhetene som hører til et
                # kurs skal ha tilgang til kursets undv.rom-korridor.
                new_acl.setdefault(undervisning_node, {})[enhans] = {
                    'gacc': '250',		# Admin Lite
                    'racc': '100'}		# Room Creator

                # Alle enhetsansvarlige skal ha "View Contacts" på gruppen
                # All_users dersom det eksporteres en slik.
                if 'All_users' in fronter.export:
                    new_acl.setdefault('All_users', {})[enhans] = {
                        'gacc': '100',
                        'racc': '0'}

                # Gi studenter+lærere i alle undervisningsenhetene som
                # hører til kurset passende rettigheter i felles- og
                # lærerrom.
                new_acl.setdefault("ROOM/Felles:%s" % struct_id,
                                   {}).update({
                    enhans: {'role': fronter.ROLE_CHANGE},
                    enhstud: {'role': fronter.ROLE_WRITE}
                    })
                new_acl.setdefault("ROOM/Larer:%s" % struct_id,
                                   {})[enhans] = {
                    'role': fronter.ROLE_CHANGE}

                groups = {'enhansv': [enhans],
                          'enhstud': [enhstud],
                          'aktansv': [],
                          'aktstud': [],
                         }
                process_single_enhet_id(kurs_id, enhet_id, struct_id,
                                        emnekode, groups,
                                        enhet_node, undervisning_node,
                                        termin_suffix)
        elif type == fronter.EVU_PREFIX.lower():
            # EVU-kurs er modellert helt uavhengig av semester-inndeling i
            # FS, slik at det alltid vil være nøyaktig en enhet-ID for
            # hver EVU-kurs-ID.  Det gjør en del ting nokså mye greiere...
            for enhet_id in fronter.kurs2enhet[kurs_id]:
                kurskode, tidskode = enhet_id.split(":")[1:3]
                # Opprett strukturnoder som tillater å ha rom direkte under
                # seg.
                sko_node = build_structure(fronter.enhet2sko[enhet_id])
                struct_id = enhet_id.upper()
                enhet_node = "STRUCTURE/Enhet:%s" % struct_id
                undervisning_node = "STRUCTURE/Studentkorridor:%s" % struct_id
                tittel = "%s - %s, %s" % (kurskode.upper(),
                                          fronter.kurs2navn[kurs_id],
                                          tidskode.upper())
                register_group(tittel, enhet_node, sko_node, 1)
                register_group("%s  - Undervisningsrom" % kurskode.upper(),
                               undervisning_node, enhet_node, 1)
                enhans = "uio.no:fs:%s:enhetsansvar" % enhet_id.lower()
                enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
                new_acl.setdefault(undervisning_node, {})[enhans] = {
                    'gacc': '250',		# Admin Lite
                    'racc': '100'}		# Room Creator

                # Alle enhetsansvarlige skal ha "View Contacts" på gruppen
                # All_users dersom det eksporteres en slik.
                if 'All_users' in fronter.export:
                    new_acl.setdefault('All_users', {})[enhans] = {
                        'gacc': '100',
                        'racc': '0'}

                # Alle eksporterte emner skal i alle fall ha ett
                # fellesrom og ett lærerrom.
                new_rooms["ROOM/Felles:%s" % struct_id] = {
                    'title': "%s - Fellesrom" % kurskode.upper(),
                    'parent': enhet_node,
                    'CFid': "ROOM/Felles:%s" % struct_id}
                new_acl.setdefault("ROOM/Felles:%s" % struct_id,
                                   {})[enhans] = {
                    'role': fronter.ROLE_CHANGE}
                new_acl.setdefault("ROOM/Felles:%s" % struct_id,
                                   {})[enhstud] = {
                    'role': fronter.ROLE_WRITE}
                new_rooms["ROOM/Larer:%s" % struct_id] = {
                    'title': "%s - Lærerrom" % kurskode.upper(),
                    'parent': enhet_node,
                    'CFid': "ROOM/Larer:%s" % struct_id}
                new_acl.setdefault("ROOM/Larer:%s" % struct_id,
                                   {})[enhans] = {
                    'role': fronter.ROLE_CHANGE}
                groups = {'enhansv': [enhans],
                          'enhstud': [enhstud],
                          'aktansv': [],
                          'aktstud': [],
                          }
                process_single_enhet_id(kurs_id, enhet_id, struct_id,
                                        kurskode, groups,
                                        enhet_node, undervisning_node)
        else:
            raise ValueError, "Unknown type <%s> for course <%s>" % (type, kurs_id)

def register_group_update(operation, id):
    """populerer %group_updates"""

    if operation != fronter.STATUS_DELETE:
        parent = new_group.get(id, {}).get('parent')
        # title = new_group[id]['title']

        # This isn't called with $operation = STATUS_UPDATE until all
        # $operation = STATUS_ADD calls are done, and simlarly for
        # STATUS_DELETE after STATUS_UPDATE.
        if (id != root_struct_id and parent and new_group.has_key(parent)):
            register_group_update(operation, parent)

    if operation == fronter.STATUS_ADD:
        if not (new_group.has_key(id) and (not old_group.has_key(id))):
            return
	group_updates[operation][id] = new_group[id]
	del new_group[id]
    elif operation == fronter.STATUS_UPDATE:
        if not(old_group.has_key(id) and new_group.has_key(id)):
            return
	if (old_group[id]['parent'] != new_group[id]['parent'] or
	    old_group[id]['title'] != new_group[id]['title'] or
	    (old_group[id]['allow_room'] ^ # xor
	     new_group[id]['allow_room']) or
	    (old_group[id]['allow_contact'] ^ # xor
             new_group[id]['allow_contact'])):
	    group_updates[operation][id] = new_group[id]
	    # Siden gruppen/korridoren allerede finnes i CF, skal alle
	    # updates på denne gjøres med den import-IDen som allerede
	    # finnes i CF.
	    #
	    # Merk at dette ikke vil ha effekt for noe annet enn
	    # korridorer, da det for grupper ikke skal være noen
	    # forskjell på id og CFid.
	    group_updates[operation][id]['CFid'] = old_group[id]['CFid']
	del old_group[id]
	del new_group[id]
    elif operation == fronter.STATUS_DELETE:
        if not (old_group.has_key(id) and (not new_group.has_key(id))):
            return
	group_updates[operation][id] = old_group[id]
	del old_group[id]

def register_room_update(operation, roomid):
    # populerer %room_updates
    if operation == fronter.STATUS_ADD:
        if not (new_rooms.has_key(roomid) and (not old_rooms.has_key(roomid))):
            return
	room_updates[operation][roomid] = new_rooms[roomid]
	del new_rooms[roomid]
    elif operation == fronter.STATUS_UPDATE:
        if not (old_rooms.has_key(roomid) and new_rooms.has_key(roomid)):
            return
        if new_rooms[roomid].has_key('profile'):
            new_profile = new_rooms[roomid]['profile']
        else:
            new_profile = fronter._accessFronter.GetProfileId('UiOstdrom2003')
            
	if (old_rooms[roomid]['title'] != new_rooms[roomid]['title'] or
	    old_rooms[roomid]['parent'] != new_rooms[roomid]['parent'] or
            old_rooms[roomid]['profile'] != new_profile):
	    room_updates[operation][roomid] = new_rooms[roomid]
	    # Ettersom rommet allerede finnes i CF, ønsker vi å bruke
	    # samme import-ID som før; endringer i rom-attributter
	    # skal ikke føre til opprettelse av noe nytt rom.
	    room_updates[operation][roomid]['CFid'] = old_rooms[roomid]['CFid']
	del old_rooms[roomid]
	del new_rooms[roomid]
    elif operation == fronter.STATUS_DELETE:
        if not (old_rooms.has_key(roomid) and (not new_rooms.has_key(roomid))):
            return
	room_updates[operation][roomid] = old_rooms[roomid]
	del old_rooms[roomid]

def process_room_group_updates(current_groups, current_rooms):
    # Vi kan ikke oppdatere medlemskap på grupper vi ikke lenger får data
    # om, så vi må holde orden på hvilke Fronter-grupper som er 'current'.

    for (status, group_dict, room_dict) in (
        (fronter.STATUS_ADD, new_group, new_rooms),
        (fronter.STATUS_UPDATE, new_group, new_rooms),
        (fronter.STATUS_DELETE, old_group, old_rooms)):

        for id in group_dict.keys():
            if status == fronter.STATUS_ADD:
                current_groups[id] = 1
            register_group_update(status, id) 

        for id in group_updates.get(status, {}).keys():
            data = group_updates[status][id]
            xml.group_to_XML(data['CFid'], status, data)

        del group_updates[status]

        # Det skal ikke gjøres endringer i rettighetstildeling til rom vi ikke
        # lenger henter data om (rom fra tidligere semestre).

        for id in room_dict.keys():
            if status == fronter.STATUS_ADD:
                if old_rooms.has_key(id):
                    current_rooms[old_rooms[id]['CFid']] = 1
                else:
                    current_rooms[id] = 1
            register_room_update(status, id)
        for id in room_updates.get(status, {}).keys():
            data = room_updates[status][id]
            xml.room_to_XML(data['CFid'], status, data)

        del room_updates[status]

def register_groupmember_update(operation, gname):
    # populererer %groupmember_updates
    if operation == fronter.STATUS_ADD:
        for uname in new_groupmembers.get(gname, {}).keys():
            if old_groupmembers.get(gname, {}).has_key(uname):
                continue
	    groupmember_updates[operation].setdefault(gname, []).append(uname)
	    del new_groupmembers[gname][uname]
    elif operation == fronter.STATUS_UPDATE:
	# Vi skiller ikke på rolletype for personmedlemmer i grupper;
	# "oppdateringer" av medlemskap er derfor alltid enten
	# innlegging av nye medlemmer eller fjerning av gamle
	# medlemmer.
        pass
    elif operation == fronter.STATUS_DELETE:
        for uname in old_groupmembers.get(gname, {}).keys():
            if (new_groupmembers.get(gname, {}).has_key(uname) or
                deleted_users.has_key(uname)):
                continue
            groupmember_updates[operation].setdefault(gname, []).append(uname)
            del old_groupmembers[gname][uname]

def process_groupmembers():
    for (status, tmp_dict) in ((fronter.STATUS_ADD, new_groupmembers),
                               (fronter.STATUS_DELETE, old_groupmembers)):
        for gname in tmp_dict.keys():
            register_groupmember_update(status, gname)
        for gname in groupmember_updates.get(status, {}).keys():
            xml.personmembers_to_XML(gname, status,
                                     groupmember_updates[status][gname])
        del groupmember_updates[status]

def register_acl_update(operation, node):
    if operation == fronter.STATUS_ADD:
        for gname, gdata in new_acl[node].items():
            if old_acl.get(node, {}).has_key(gname):
                continue
	    acl_updates[operation].setdefault(
                node, {})[gname] = gdata
	    del new_acl[node][gname]
    elif operation == fronter.STATUS_UPDATE:
        for gname in new_acl[node].keys():
            if not (old_acl.get(node, {}).has_key(gname) and
                    new_acl[node].has_key(gname)):
                continue
	    old = old_acl[node][gname]
	    new = new_acl[node][gname]
            if not ((old.has_key('role') and
		     # Room ACL.
		     old['role'] == new['role']) or
		    (old.has_key('gacc') and
		     # Structure ACL
		     old['gacc'] == new['gacc'] and
                     old['racc'] == new['racc'])):
		acl_updates[operation].setdefault(
                    node, {})[gname] = new
	    del new_acl[node][gname]
	    del old_acl[node][gname]
    elif operation == fronter.STATUS_DELETE:
        for gname in old_acl[node].keys():
            if new_acl.get(node, {}).has_key(gname):
                continue
	    acl_updates[operation].setdefault(
                node, {})[gname] = old_acl[node][gname]
	    del old_acl[node][gname]

def process_acls():
    for (status, tmp_acl) in ((fronter.STATUS_ADD, new_acl),
                               (fronter.STATUS_UPDATE, new_acl),
                               (fronter.STATUS_DELETE, old_acl)):
        for id in tmp_acl.keys():
            register_acl_update(status, id)
        for id in acl_updates.get(status, {}).keys():
            data = acl_updates[status][id]
            xml.acl_to_XML(id, status, data)
        del acl_updates[status]

if __name__ == '__main__':
    main()

# arch-tag: 20830ccd-e841-422d-87d2-65f6ebd2c8f0
