#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

#            Gruppene angitt på øverste linje i tabellen har rettighet
#            til entitetene angitt i kolonnen ytterst til venstre.
#
# ---------+---------+---------+---------+---------+----------+------------
#   Gruppe:|  EnhAns | Akt1Ans | Akt2Ans | EnhStud | Akt1Stud | Akt2Stud
# =========================================================================
# Rom:     |*********|*********|*********|*********|**********|************
# ---------+---------+---------+---------+---------+----------+------------
# Felles   |  Change |  Change |  Change |   Read  |          |
# ---------+---------+---------+---------+---------+----------+------------
# Lærer    |  Change |  Change |  Change |         |          |
# ---------+---------+---------+---------+---------+----------+------------
# Akt. 1   |         |  Change |         |         |   Write  |
# ---------+---------+---------+---------+---------+----------+------------
# Akt. 2   |         |         |  Change |         |          |   Write
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
import cf_lib

from Cerebrum.Utils import Factory
from Cerebrum import Database

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host='])
    except getopt.GetoptError:
        usage(1)
    host = 'kladdebok.uio.no'
    db_user = 'ureg2000'
    db_service = 'FSPROD.uio.no'
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
    fs_db = Database.connect(user=db_user, service=db_service,
                             DB_driver='Oracle')
    gen_export(host, fs_db)
    
def gen_export(fronterHost, fs_db):
    global fronter
    db = Factory.get('Database')()
    const = Factory.get('Constants')(db)

    fronter = cf_lib.Fronter(fronterHost, db, const, fs_db)

    if 'FS' in [x[0:2] for x in fronter.export]:
        # Fyller %kurs, %emne_versjon, %emne_termnr, %enhet2sko,
        # %kurs2navn, %enhet2akt
        fronter.read_kurs_data()

    global xml
    xml = cf_lib.FronterXML()
    xml.start_xml_file(kurs2enhet)

    users = fronter.get_fronter_users()
    new_users = get_new_users()

    old_group = get_fronter_group()
    new_group = {}
    group_updates = {}

    old_rooms = get_fronter_rooms()
    new_rooms = {}
    room_updates = {}

    # 608-650: legger inn brukermedlemer i %new_groupmembers på
    # cf-gruppenivå 3
    reg_supergroups()

    # 651-694:  Lag xml for insert/update/delete basert på %user_updates
    gen_user_xml()

    # 737-1050:
    # - itererer over kurs2enhet, gjør litt forskjellige ting avhengig av
    #   om det er en EVU kurs eller et vanlig emne
    # - evu og "vanlig kurs" delen kan trolig gjenbruke kode
    # - lager noen rom for det aktuelle kurset
    # - setter acl'er
    process_kurs2enhet()

    # 1242-1348:
    # - div kall til register_group_update, register_room_update,
    #   group_to_XML og room_to_XML
    process_room_group_updates()

    old_groupmembers = fronter.get_fronter_groupmembers()
    groupmember_updates = {}

    # 1435-1462:
    # - div. kall til register_groupmember_update og personmembers_to_XML
    process_groupmembers()

    old_acl = fronter.get_fronter_acl()
    acl_updates = {}

    # 1677-1723:
    # - div kall til acl_to_XML og register_acl_update
    process_acls()
    xml.end()
    
def get_new_users():  # ca 345-374
    # Hent info om brukere i cerebrum
    fix_email = r'\@UIO_HOST$'
    # $u2k->list_users_for_fronter_export
    new_users = {}
    for user in xxx:
        email = fix_email.sub('@ulrik.uio.no', email)
        names = re.split('\s+', fullname)
        new_users[uname] = {'FAMILY': names.pop(0),
                            'GIVEN': " ".join(names),
                            'EMAIL': email,
                            'USERACCESS': 0
                            }

        if 'All_users' in fronter.export:
            new_groupmembers['All_users'][uname] = 1
            new_users[uname]['USERACCESS'] = 'allowlogin'

        if uname in fronter.admins:
            new_users[uname]['USERACCESS'] = 'administrator'

        new_users[uname]['PASSWORD'] = 'unix:'
        if uname in fronter.plain_users:
            new_users[uname]['PASSWORD'] = "plain:%s" % uname
    return new_users

def register_user_update(operation, uname):
    """Update user_updates with info about changes that should be done
    in Fronter.  Also modifies old_users and new_users"""
    update = False
    if operation == fronter.STATUS_UPDATE:
        if (old_users[uname]['PASSWORD'] != new_users[uname]['PASSWORD'] or
	    old_users[uname]['GIVEN'] != new_users[uname]['GIVEN'] or
	    old_users[uname]['FAMILY'] != new_users[uname]['FAMILY'] or
	    old_users[uname]['EMAIL'] != new_users[uname]['EMAIL'] or
            old_users[uname]['USERACCESS'] != new_users[uname]['USERACCESS']):
            update = True

    if update or operation == fronter.STATUS_ADD:
        if (not new_users.has_key(uname)) and (not old_users.has_key(uname)):
            return
	user_updates[operation][uname] = {
            'PASSWORD': fronter_pwd(new_users[uname]['PASSWORD']),
            'GIVEN': new_users[uname]['GIVEN'],
            'FAMILY': new_users[uname]['FAMILY'],
            'EMAIL': new_users[uname]['EMAIL'],
            'EMAILCLIENT': 1,
            'USERACCESS': fronter.useraccess(new_users[uname]['USERACCESS'])
	    }
	del(new_users[uname])
        if update:
            del(old_users[uname])
    elif operation == fronter.STATUS_DELETE:
        if (not new_users.has_key(uname)) and (old_users.has_key(uname)):
            return
	user_updates[operation][uname] = 1
	deleted_users[uname] = 1
	del(old_users[uname])

def register_group(title, id, parentid, allow_room=0, allow_contact=0):
    """Adds info in new_group about group"""

    CFid = id
    if re.search(r'^STRUCTURE/(Enhet|Studentkorridor):', id):
        rest = id.split(":")
        corr_type = rest.pop(0)

        if not rest[0] in (EMNE_PREFIX, EVU_PREFIX):
            rest.insert(0, EMNE_PREFIX)
        id = "%s:%s" % (corr_type, UE2KursID(rest))
    new_group[id] = { 'title': title,
                      'parent': parentid,
                      'allow_room': allow_room,
                      'allow_contact': allow_contact,
                      'CFid': CFid,
		      }

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

    new_acl = {}
    for sgname in fronter.supergroups:
        # $sgname er på nivå 2 == Kurs-ID-gruppe.  Det er på dette nivået
        # eksport til ClassFronter er definert i Ureg2000.
        try:
            group = get_group(sgname)
        except Errors.NotFoundError:
            continue
        for group_id in group.list_members(mtype=co.entity_group):
	    # $gname er på nivå 3 == gruppe med brukere som medlemmer.
	    # Det er disse gruppene som blir opprettet i ClassFronter
	    # som følge av eksporten.
            group = get_group(group_id)
            register_group(group.description, group.group_name,
                           group_struct_id, 0, 1)
            #
            # All groups should have "View Contacts"-rights on
            # themselves.
            new_acl[group.group_name][group.group_name] = {
                'gacc': '100',   # View Contacts
                'racc': '0'} 	 # None
            #
            # Groups populated from FS aren't expanded recursively
            # prior to export.
            for uname in group.list_members(mtype=co.entity_account):
                if new_users.has_key[uname]:
                    if new_users[uname]['USERACCESS'] != 'administrator':
                        new_users[uname]['USERACCESS'] = 'allowlogin'
                    new_groupmembers[group.group_name][uname] = 1

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
        del(user_updates[status])

def get_sted(stedkode=None, entity_id=None):
    sted = Stedkode.Stedkode(db)
    if stedkode is not None:
        sted.find_stedkode(int(sko[0:2]), int(sko[2:4]), int(sko[4:6]))
    else:
        sted.find(entity_id)
    return sted

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
	parent_sted = get_sted(entity_id=sted.get_parent(co.system_fs))
	parent = build_structure("%02d%02d%02d" % (
            parent_sted.fakultet, parent_sted.institutt, parent_sted.avdeling))
            
        if not parent:
	    print "Stedkode <%s> er uten foreldre; bruker %s" % (sko, root_sko)
	    parent = build_structure(root_sko)

	register_group(sted.name, id, parent, allow_room, allow_contact)
    return id

def process_single_enhet_id(enhet_id):
    # I tillegg kommer så evt. rom knyttet til de
    # undervisningsaktivitetene studenter kan melde seg på.
    for akt in enhet2akt[enhet_id]:
        aktkode, aktnavn = akt

        aktans = "uio.no:fs:%s:aktivitetsansvar:%s" % (
            enhet_id.lower(), aktkode.lower())
        groups['aktansv'].append(aktans)
        aktstud = "uio.no:fs:%s:student:%s" % (
            enhet_id.lower(), aktkode.lower())
        groups['aktstud'].append(aktstud)

        # Aktivitetsansvarlig skal ha View Contacts på studentene i
        # sin aktivitet.
        new_acl[aktstud][aktans] = {'gacc': '100', 'racc': '0'}
        # ... og omvendt.
        new_acl[aktans][aktstud] = {'gacc': '100', 'racc': '0'}

        # Alle med ansvar for (minst) en aktivitet tilknyttet
        # en undv.enhet som hører inn under kurset skal ha
        # tilgang til kursets undervisningsrom-korridor samt
        # lærer- og fellesrom.
        new_acl[undervisning_node][aktans] = {
            'gacc': '250',		# Admin Lite
            'racc': '100'}		# Room Creator
        new_acl["ROOM/Felles:%s" % struct_id][aktans] = {
            'role': fronter.ROLE_CHANGE}
        new_acl["ROOM/Larer:%s" % struct_id][aktans] = {
            'role': fronter.ROLE_CHANGE}

        # Alle aktivitetsansvarlige skal ha "View Contacts" på
        # gruppen All_users dersom det eksporteres en slik.
        if export_all_users:
            new_acl['All_users'][aktans] = {'gacc': '100',
                                            'racc': '0'}

        aktid = "%s:%s" % (struct_id, aktkode)
        new_rooms["ROOM/Aktivitet:%s:%s" % (kurs_id, aktkode)] = {
            'title': "%s - %s" % (emnekode, aktnavn),
             'parent': enhet_node,
             'CFid': "ROOM/Aktivitet:%s" % aktid}
        new_acl["ROOM/Aktivitet:%s" % aktid][aktans] = {
            'role': fronter.ROLE_CHANGE}
        new_acl["ROOM/Aktivitet:%s" % aktid][aktstud] = {
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
            new_acl[g][g] = {'gacc': '100', 'racc': '0'}
            #
            # Alle grupper med gruppetype $gt skal ha View
            # Contacts på alle grupper med gruppetype i
            # $other_gt{$gt}.
            for o_gt in other_gt[gt]:
                for og in groups[o_gt]:
                    new_acl[og][g] = {'gacc': '100',
                                      'racc': '0'}
    
def process_kurs2enhet():
    # TODO: some code-duplication has been reduced by adding
    # process_single_enhet_id.  Recheck that the reduction is correct.
    # It should be possible to move more code to that subroutine.
    for kurs_id in kurs2enhet.keys():
        type = kurs_id.split(":")[0].lower()
    if type == EMNE_PREFIX:
        enhet_sorted = kurs2enhet[kurs_id][:].sort(fronter._date_sort)
	# Bruk eldste enhet som $enh_id
	enh_id = enhet_sorted[0]
	enhet = enh_id.split(":")[1]
	struct_id = enh_id.upper()	# Default, for korridorer som
                                        # ikke finnes i CF.
	if old_group.has-key("STRUCTURE/Enhet:%s" % kurs_id):
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
	    struct_id = CFid.split(":")[1]

        Instnr, emnekode, versjon, termk, aar, termnr = enhet.split(":")
	# Opprett strukturnoder som tillater å ha rom direkte under
	# seg.
	sko_node = build_structure(enhet2sko[enh_id])
	enhet_node = "STRUCTURE/Enhet:%s" % struct_id
	undervisning_node = "STRUCTURE/Studentkorridor:%s" % struct_id

	tittel = "%s - %s, %s %s" % (emnekode, kurs2navn[kurs_id], termk, aar)
	multi_enhet = ()
	multi_id = ":".join((Instnr, emnekode, termk, aar))
        if len(emne_termnr[multi_id]) > 1:
            multi_enhet.append("%s. termin" % termnr)
        if len(emne_versjon[multi_id]) > 1:
            multi_enhet.append("v%s" % versjon)
        if multi_enhet:
            tittel += ", %s" % ", ".join(multi_enhet)

	register_group(tittel, enhet_node, sko_node, 1)
	register_group("%s - Undervisningsrom" % emnekode,
		       undervisning_node, enhet_node, 1);

	# Alle eksporterte kurs skal i alle fall ha ett fellesrom og
	# ett lærerrom.
	new_rooms["ROOM/Felles:%s" % kurs_id] = {
            'title': "%s - Fellesrom" % emnekode,
            'parent': enhet_node,
            'CFid': "ROOM/Felles:%s" % struct_id}
	new_rooms["ROOM/Larer:%s" % kurs_id] = {
            'title': "%s - Lærerrom" % emnekode,
            'parent': enhet_node,
            'CFid': "ROOM/Larer:%s" % struct_id}

        for enhet_id in kurs2enhet[kurs_id]:
	    enhans = "uio.no:fs:%s:enhetsansvar" % enhet_id.lower()
	    enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
	    # De ansvarlige for undervisningsenhetene som hører til et
	    # kurs skal ha tilgang til kursets undv.rom-korridor.
	    new_acl[undervisning_node][enhans] = {
                'gacc': '250',		# Admin Lite
                'racc': '100'}		# Room Creator

	    # Alle enhetsansvarlige skal ha "View Contacts" på gruppen
	    # All_users dersom det eksporteres en slik.
            if 'All_users' in fronter.export:
                new_acl['All_users'][enhans] = {'gacc': '100',
                                                'racc': '0'}

	    # Gi studenter+lærere i alle undervisningsenhetene som
	    # hører til kurset passende rettigheter i felles- og
	    # lærerrom.
	    new_acl["ROOM/Felles:%s" % struct_id][enhans] = {
                'role': fronter.ROLE_CHANGE}
	    new_acl["ROOM/Felles:%s" % struct_id][enhstud] = {
                'role': fronter.ROLE_WRITE}
	    new_acl["ROOM/Larer:%s" % struct_id][enhans] = {
                'role': fronter.ROLE_CHANGE}

	    groups = {'enhansv': enhans,
                      'enhstud': enhstud,
                      'aktansv': [],
                      'aktstud': [],
		     }
            process_single_enhet_id(enhet_id)
    elif type == EVU_PREFIX:
	# EVU-kurs er modellert helt uavhengig av semester-inndeling i
	# FS, slik at det alltid vil være nøyaktig en enhet-ID for
	# hver EVU-kurs-ID.  Det gjør en del ting nokså mye greiere...
        for enhet_id in kurs2enhet[kurs_id]:
	    kurskode, tidskode = enhet_id.split(":")[1,2]
	    # Opprett strukturnoder som tillater å ha rom direkte under
	    # seg.
	    sko_node = build_structure(enhet2sko[enhet_id])
	    enhet_node = "STRUCTURE/Enhet:%s" % enhet_id
	    undervisning_node = "STRUCTURE/Studentkorridor:%s" % enhet_id
	    tittel = "%s - %s, %s" % (kurskode, kurs2navn[kurs_id], tidskode)
	    register_group(tittel, enhet_node, sko_node, 1)
	    register_group("%s  - Undervisningsrom" % kurskode,
			   undervisning_node, enhet_node, 1)
	    enhans = "uio.no:fs:%s:enhetsansvar" % enhet_id.lower()
	    enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
	    new_acl[undervisning_node][enhans] = {
                'gacc': '250',		# Admin Lite
                'racc': '100'}		# Room Creator

	    # Alle enhetsansvarlige skal ha "View Contacts" på gruppen
	    # All_users dersom det eksporteres en slik.
            if 'All_users' in fronter.export:
                new_acl['All_users'][enhans] = {'gacc': '100',
                                                'racc': '0'}

	    # Alle eksporterte emner skal i alle fall ha ett
	    # fellesrom og ett lærerrom.
	    new_rooms["ROOM/Felles:%s" % kurs_id] = {
                'title': "%s - Fellesrom" % kurskode,
                'parent': enhet_node,
                'CFid': "ROOM/Felles:%s" % enhet_id}
	    new_acl["ROOM/Felles:%s" % enhet_id][enhans] = {
                'role': fronter.ROLE_CHANGE}
	    new_acl["ROOM/Felles:%s" % enhet_id][enhstud] = {
                'role': fronter.ROLE_WRITE}
	    new_rooms["ROOM/Larer:%s" % kurs_id] = {
                'title': "%s - Lærerrom" % kurskode,
                'parent': enhet_node,
                'CFid': "ROOM/Larer:%s" % enhet_id}
	    new_acl["ROOM/Larer:%s" % enhet_id][enhans] = {
                'role': fronter.ROLE_CHANGE}
	    groups = {'enhansv': enhans,
                      'enhstud': enhstud,
                      'aktansv': [],
                      'aktstud': [],
                      }
            process_single_enhet_id(enhet_id)
    else:
        raise ValueError, "Unknown type <%s> for course <%s>" % (type, kurs_id)

def register_group_update(operation, id):
    """populerer %group_updates"""
    parent = new_group[id]['parent']
    title = new_group[id]['title']

    # This isn't called with $operation = STATUS_UPDATE until all
    # $operation = STATUS_ADD calls are done, and simlarly for
    # STATUS_DELETE after STATUS_UPDATE.
    if (id != root_struct_id and parent and new_group.has_key(parent)):
	register_group_update(operation, parent)

    if operation == fronter.STATUS_ADD:
        if not (new_group.has_key(id) and (not old_group.has_key(id))):
            return
	group_updates[operation][id] = new_group[id]
	del(new_group[id])
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
	del(old_group[id])
	del(new_group[id])
    elif operation == fronter.STATUS_DELETE:
        if not (old_group.has_key(id) and (not new_group.has_key(id))):
            return
	group_updates[operation][id] = old_group[id]
	del(old_group[id])

def register_room_update(operation, id):
    # populerer %room_updates
    if operation == fronter.STATUS_ADD:
        if not (new_rooms.has_key(roomid) and (not old_rooms.has_key(roomid))):
            return
	room_updates[operation][roomid] = new_rooms[roomid]
	del(new_rooms[roomid])
    elif operation == fronter.STATUS_UPDATE:
        if not unless (old_rooms.has_key(roomid) and new_rooms.has_key(roomid)):
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
	del(old_rooms[roomid])
	del(new_rooms[roomid])
    elif operation == fronter.STATUS_DELETE:
        if not (old_rooms.has_key(roomid) and (not new_rooms.has_key(roomid))):
            return
	room_updates[operation][roomid] = old_rooms[roomid]
	del(old_rooms[roomid])

def process_room_group_updates():
    # Vi kan ikke oppdatere medlemskap på grupper vi ikke lenger får data
    # om, så vi må holde orden på hvilke Fronter-grupper som er 'current'.
    current_groups = {}

    for (status, group_dict, room_dict) in (
        (fronter.STATUS_ADD, new_group, new_rooms),
        (fronter.STATUS_UPDATE, new_group, new_rooms),
        (fronter.STATUS_DELETE, old_group, old_rooms)):

        for id in group_dict.keys():
            if status == fronter.STATUS_ADD:
                current_groups[id] = 1
            register_group_update(status, id) 

        for id in group_updates.get(fronter.STATUS_ADD, {}).keys():
            data = group_updates[status][id]
            xml.group_to_XML(data['CFid'], status, data)

        del(group_updates[status])

        # Det skal ikke gjøres endringer i rettighetstildeling til rom vi ikke
        # lenger henter data om (rom fra tidligere semestre).
        current_rooms = {}

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

        del(room_updates[status])

def register_groupmember_update(operation, gname):
    # populererer %groupmember_updates
    if operation == fronter.STATUS_ADD:
        for uname in new_groupmembers[gname].keys():
            if old_groupmembers[gname].has_key(uname):
                continue
	    groupmember_updates[operation][gname].append(uname)
	    del(new_groupmembers[gname][uname])
    elif operation == fronter.STATUS_UPDATE:
	# Vi skiller ikke på rolletype for personmedlemmer i grupper;
	# "oppdateringer" av medlemskap er derfor alltid enten
	# innlegging av nye medlemmer eller fjerning av gamle
	# medlemmer.
        pass
    elif operation == fronter.STATUS_DELETE:
        for uname in old_groupmembers[gname].keys():
	    if (new_groupmembers[gname].has_key(uname) or
                deleted_users.has_key(uname)):
                continue
	    groupmember_updates[operation][gname].append(uname)
	    del(old_groupmembers[gname][uname])

def process_groupmembers():
    for (status, tmp_dict) in ((fronter.STATUS_ADD, new_groupmembers),
                               (fronter.STATUS_DELETE, old_groupmembers)):
        for gname in tmp_dict.keys():
            register_groupmember_update(status, gname)
        for gname in groupmember_updates.get(status, {}).keys():
            xml.personmembers_to_XML(gname, status,
                                     groupmember_updates[status][gname])
        del(groupmember_updates[status])

def register_acl_update(operation, node):
    if operation == fronter.STATUS_ADD:
        for gname in new_acl[node].keys():
            if old_acl[node].has_key(gname):
                continue
	    acl_updates[operation][node][gname] = new_acl[node][gname]
	    del(new_acl[node][gname])
    elif operation == fronter.STATUS_UPDATE:
        for gname in new_acl[node].keys():
            if not (old_acl[node].has_key(gname) and
                    new_acl[node].has_key(gname)):
                continue
	    old = old_acl[node][gname]
	    new = new_acl[node][gname]
            if not ((old.has_key['role'] and
		     # Room ACL.
		     old['role'] == new['role']) or
		    (old.has_key('gacc') and
		     # Structure ACL
		     old['gacc'] == new['gacc'] and
                     old['racc'] == new['racc'])):
		acl_updates[operation][node][gname] = new
	    del(new_acl[node][gname])
	    del(old_acl[node][gname])
    elif operation == fronter.STATUS_DELETE:
        for gname in old_acl[node].keys():
            if new_acl[node].has_key(gname):
                continue
	    acl_updates[operation][node][gname] = old_acl[node][gname]
	    del(old_acl[node][gname])

def process_acls():
    for (status, tmp_acl) in ((fronter.STATUS_ADD, new_acl),
                               (fronter.STATUS_UPDATE, new_acl),
                               (fronter.STATUS_DELETE, old_acl)):
        for id in tmp_acl.keys():
            register_acl_update(status, id)
        for id in acl_updates.get(status, {}).keys():
            data = acl_updates[status][id]
            xml.acl_to_XML(id, status, data)
        del(acl_updates[status])

if __name__ == '__main__':
    main()
