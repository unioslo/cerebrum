#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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
import locale
import os
import getopt
import time

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia import access_FS
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.hia import fronter_lib



db = const = logger = None
fxml = None
romprofil_id = {}
include_this_sem = True

def init_globals():
    global db, const, logger
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger("console")

    cf_dir = '/cerebrum/dumps/Fronter'

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'uten-dette-semester',
                                    'uten-passord',
                                    'debug-file=', 'debug-level='])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(cf_dir, "x-import.log")
    debug_level = 4
    host = 'hia'
    set_pwd = True
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--debug-file':
            debug_file = val
        elif opt == '--debug-level':
            debug_level = val
        elif opt == '--uten-dette-semester':
            global include_this_sem
            include_this_sem = False
        elif opt == '--uten-passord':
            set_pwd = False
        else:
            raise ValueError, "Invalid argument: %r", (opt,)

    host_profiles = {'hia': {'emnerom': 1520,
                             'studieprogram': 1521},
                     'hia2': {'emnerom': 42,
                              'studieprogram': 42},
                     'hia3': {'emnerom': 1520,
                              'studieprogram': 1521}
                     }
    if host_profiles.has_key(host):
        romprofil_id.update(host_profiles[host])

    filename = os.path.join(cf_dir, 'test.xml')
    if len(args) == 1:
        filename = args[0]
    elif len(args) <> 0:
        usage(2)

    global fxml
    fxml = fronter_lib.FronterXML(filename,
                                  cf_dir = cf_dir,
                                  debug_file = debug_file,
                                  debug_level = debug_level,
                                  fronter = None,
                                  include_password = set_pwd)

def get_semester():
    t = time.localtime()[0:2]
    this_year = t[0]
    if t[1] <= 6:
        this_sem = 'vår'
        next_year = this_year
        next_sem = 'høst'
    else:
        this_sem = 'høst'
        next_year = this_year + 1
        next_sem = 'vår'
    if not include_this_sem:
        this_year, this_sem = next_year, next_sem
    return ((str(this_year), this_sem), (str(next_year), next_sem))

def load_acc2name():
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    logger.debug('Loading person/user-to-names table')
    # For the .getdict_uname2mailaddr method to be available, this
    # Cerebrum instance must have enabled the Account mixin class
    # Cerebrum.modules.Email.AccountEmailMixin (by including it in
    # cereconf.CLASS_ACCOUNT).
    uname2mail = account.getdict_uname2mailaddr()

    # Build the person_name_dict based on the automatically updated
    # 'system_cached' name variants in the database.
    person_name = person.getdict_persons_names(
        source_system=const.system_cached,
        name_types = [const.name_first, const.name_last, const.name_full])

    ext2puname = person.getdict_external_id2primary_account(
        const.externalid_fodselsnr)
    ret = {}
    for pers in person.list_persons_atype_extid():
	# logger.debug("Loading person: %s" % pers['name'])
	if ext2puname.has_key(pers['external_id']):
	    ent_name = ext2puname[pers['external_id']]
	else:
	    # logger.debug("Person has no account: %d" % pers['person_id']) 
	    continue
	if person_name.has_key(int(pers['person_id'])):
	    if len(person_name[int(pers['person_id'])]) <> 3:
		# logger.debug("Person name fault, person_id: %s" % ent_name)
		continue
	    else: 
		names = person_name[int(pers['person_id'])]
	else:
	    # logger.debug("Person name fault, person_id: %s" % ent_name)
	    continue
        if uname2mail.has_key(ent_name):
            email = uname2mail[ent_name]
        else:
            email = ""
	ret[int(pers['account_id'])] = {
            'NAME': ent_name,
            'FN': names[int(const.name_full)],
            'GIVEN': names[int(const.name_first)],
            'FAMILY': names[int(const.name_last)],
            'EMAIL': email,
            'USERACCESS': 2,
            'PASSWORD': 5,
            'EMAILCLIENT': 1}
    return ret

def get_ans_fak(fak_list, ent2uname):
    fak_res = {}
    person = Factory.get('Person')(db)
    stdk = Stedkode.Stedkode(db)
    for fak in fak_list:
        ans_list = []
        # Get all stedkoder in one faculty
        for ou in stdk.get_stedkoder(fakultet=int(fak)):
            # get persons in the stedkode
            for pers in person.list_affiliations(
                  source_system=const.system_sap,
                  affiliation=const.affiliation_ansatt,
                  ou_id=int(ou['ou_id'])):
                person.clear()
                try:
		    person.find(int(pers['person_id']))
                    acc_id = person.get_primary_account()
                except Errors.NotFoundError:
                    logger.debug("Person pers_id: %d , no valid account!" % \
                                 person.entity_id)
                    break
		if acc_id and ent2uname.has_key(acc_id):
		    uname = ent2uname[acc_id]['NAME']
		    if uname not in ans_list:
			ans_list.append(uname)
		else:
		    logger.debug("Person pers_id: %d have no account!" % \
							person.entity_id)
        fak_res[int(fak)] = ans_list
    return fak_res


def register_spread_groups(emne_info, stprog_info):
    group = Factory.get('Group')(db)
    this_sem, next_sem = get_semester()
    for r in group.search(filter_spread=const.spread_hia_fronter):
        gname = r['name']
        gname_el = gname.split(':')
        if gname_el[4] == 'undenh':
            # Nivå 3: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
            #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
            #
            # De interessante gruppene (som har brukermedlemmer) er på
            # nivå 4.
            instnr = gname_el[3]
            ar, term, emnekode, versjon, terminnr = gname_el[5:10]
            if (ar, term) not in (this_sem, next_sem):
                continue
            fak_sko = "%02d0000" % emne_info[emnekode]['fak']

            # Rom for undervisningsenheten.
            emne_id_prefix = '%s:fs:emner:%s:%s:%s:%s' % (
                cereconf.INSTITUTION_DOMAIN_NAME,
                ar, term, instnr, fak_sko)
            emne_sted_id = 'STRUCTURE:%s' % emne_id_prefix
            emne_rom_id = 'ROOM:%s:undenh:%s:%s:%s' % (
                emne_id_prefix, emnekode, versjon, terminnr)
            register_room('%s (ver %s, %d. termin)' %
                          (emnekode.upper(), versjon, int(terminnr)),
                          emne_rom_id, emne_sted_id,
                          profile=romprofil_id['emnerom'])

            # Grupper for studenter, forelesere og studieveileder på
            # undervisningsenheten.
            group.clear()
            group.find(r['group_id'])
	    for op, subg_id, subg_name in \
                    group.list_members(None, int(const.entity_group),
                                       get_entity_name=True)[0]:
                # Nivå 4: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
                #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR:KATEGORI
                subg_name_el = subg_name.split(':')
                # Fjern "internal:"-prefiks.
                if subg_name_el[0] == 'internal':
                    subg_name_el.pop(0)
                kategori = subg_name_el[9]
                parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:%s' % (
                    subg_name_el[0],    # DOMAIN
                    subg_name_el[4],    # ARSTALL
                    subg_name_el[5],    # TERMINKODE
                    kategori
                    )
                if kategori == 'student':
                    title = 'Studenter på '
                    rettighet = fronter_lib.Fronter.ROLE_WRITE
                elif kategori == 'foreleser':
                    title = 'Forelesere på '
                    rettighet = fronter_lib.Fronter.ROLE_DELETE
                elif kategori == 'studieleder':
                    title = 'Studieledere for '
                    rettighet = fronter_lib.Fronter.ROLE_DELETE
                else:
                    raise RuntimeError, "Ukjent kategori: %r" % (kategori,)
                title += '%s (ver %s, %d. termin)' % (
                    subg_name_el[6].upper(), # EMNEKODE
                    subg_name_el[7],    # VERSJONSKODE
                    int(subg_name_el[8])) # TERMINNR
                fronter_gname = ':'.join(subg_name_el)
                register_group(title, fronter_gname, parent_id,
                               allow_contact=True)
                group.clear()
                group.find(subg_id)
                user_members = [
                    row[2]  # username
                    for row in group.list_members(None,
                                                  const.entity_account,
                                                  get_entity_name=True)[0]]
                if user_members:
                    register_members(fronter_gname, user_members)
                register_room_acl(emne_rom_id, fronter_gname, rettighet)

	elif gname_el[4] == 'studieprogram':
            # En av studieprogram-grenene på nivå 3.  Vil eksportere
            # gruppene på nivå 4.
            group.clear()
            group.find(r['group_id'])
	    # Legges inn new group hvis den ikke er opprettet
            for op, subg_id, subg_name in \
                    group.list_members(None, int(const.entity_group),
                                       get_entity_name=True)[0]:
                subg_name_el = subg_name.split(':')
                # Fjern "internal:"-prefiks.
                if subg_name_el[0] == 'internal':
                    subg_name_el.pop(0)
                fronter_gname = ':'.join(subg_name_el)
                institusjonsnr = subg_name_el[2]
                stprog = subg_name_el[4]
                fak_sko = '%02d0000' % stprog_info[stprog]['fak']
                # Opprett fellesrom for dette studieprogrammet.
                fellesrom_sted_id = ':'.join((
                    'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                    'fs', 'fellesrom', subg_name_el[2], # institusjonsnr
                    fak_sko))
                fellesrom_stprog_rom_id = ':'.join((
                    'ROOM', cereconf.INSTITUTION_DOMAIN_NAME, 'fs',
                    'fellesrom', 'studieprogram', stprog))
                register_room(stprog.upper(), fellesrom_stprog_rom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])
                if subg_name_el[-1] == 'student':
                    brukere_studenter_id = ':'.join((
                        'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                        'fs', 'brukere', subg_name_el[2], # institusjonsnr
                        fak_sko, 'student'))
                    brukere_stprog_id = brukere_studenter_id + \
                                        ':%s' % stprog
                    register_group(stprog.upper(), brukere_stprog_id,
                                   brukere_studenter_id)
                    register_group(
                        'Studenter på %s' % subg_name_el[6], # kullkode
                        fronter_gname, brukere_stprog_id,
                        allow_contact=True)
                    # Gi denne studiekullgruppen 'skrive'-rettighet i
                    # studieprogrammets fellesrom.
                    register_room_acl(fellesrom_stprog_rom_id, fronter_gname,
                                      fronter_lib.Fronter.ROLE_WRITE)
                elif subg_name_el[-1] == 'studieleder':
                    fellesrom_studieledere_id = fellesrom_sted_id + \
                                                ':studieledere'
                    register_group("Studieledere", fellesrom_studieledere_id,
                                   fellesrom_sted_id)
                    register_group(
                        "Studieledere for program %s" % stprog.upper(),
                        fronter_gname, fellesrom_studieledere_id,
                        allow_contact=True)
                    # Gi studieleder-gruppen 'slette'-rettighet i
                    # studieprogrammets fellesrom.
                    register_room_acl(fellesrom_stprog_rom_id, fronter_gname,
                                       fronter_lib.Fronter.ROLE_DELETE)
                else:
                    raise RuntimeError, \
                          "Ukjent studieprogram-gruppe: %r" % (gname,)

                # Synkroniser medlemmer i Cerebrum-gruppa til CF.
                group.clear()
                group.find(subg_id)
                user_members = [
                    row[2]  # username
                    for row in group.list_members(None,
                                                  const.entity_account,
                                                  get_entity_name=True)[0]]
                if user_members:
                    register_members(fronter_gname, user_members)
        else:
            raise RuntimeError, \
                  "Ukjent type gruppe eksportert: %r" % (gname,)

new_acl = {}
def register_room_acl(room_id, group_id, role):
    new_acl.setdefault(room_id, {})[group_id] = {'role': role}

def register_structure_acl(node_id, group_id, contactAccess, roomAccess):
    new_acl.setdefault(node_id, {})[group_id] = {'gacc': contactAccess,
                                                 'racc': roomAccess}

new_groupmembers = {}
def register_members(gname, members):
    new_groupmembers[gname] = members

new_rooms = {}
def register_room(title, id, parentid, profile):
    new_rooms[id] = {
        'title': title,
        'parent': parentid,
        'CFid': id,
        'profile': profile}

new_group = {}
def register_group(title, id, parentid,
                   allow_room=False, allow_contact=False):
    """Adds info in new_group about group."""
    new_group[id] = { 'title': title,
                      'parent': parentid,
                      'allow_room': allow_room,
                      'allow_contact': allow_contact,
                      'CFid': id,
		      }

def output_group_xml():
    """Generer GROUP-elementer uten forover-referanser."""
    done = {}
    def output(id):
        if id in done:
            return
        data = new_group[id]
        parent = data['parent']
        if parent <> id:
            output(parent)
        fxml.group_to_XML(data['CFid'], fronter_lib.Fronter.STATUS_ADD, data)
        done[id] = True
    for group in new_group.iterkeys():
        output(group)

def usage(exitcode):
    print "Usage: export_xml_fronter.py OUTPUT_FILENAME"
    sys.exit(exitcode)

def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    init_globals()

    fxml.start_xml_head()

    # Finn `account_id` -> account-data for alle brukere.
    acc2names = load_acc2name()
    # Spytt ut PERSON-elementene.
    for user in acc2names.itervalues():
        fxml.user_to_XML(user['NAME'],
                         # Forhåpentligvis gjør "STATUS_UPDATE" at
                         # brukeren ikke får satt passord lik
                         # brukernavn, i motsetning til hva som skjer
                         # med "STATUS_ADD".
                         fronter_lib.Fronter.STATUS_UPDATE,
                         user)

    # Registrer en del semi-statiske strukturnoder.
    root_node_id = "STRUCTURE:ClassFronter structure root node"
    register_group('Høyskolen i Agder', root_node_id, root_node_id)

    manuell_node_id = 'STRUCTURE:%s:manuell' % \
                      cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Manuell', manuell_node_id, root_node_id,
                   allow_room=True)

    emner_id = 'STRUCTURE:%s:fs:emner' % cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Emner', emner_id, root_node_id)

    this_sem, next_sem = get_semester()
    emner_this_sem_id = emner_id + ':%s:%s' % tuple(this_sem)
    emner_next_sem_id = emner_id + ':%s:%s' % tuple(next_sem)
    register_group('Emner %s %s' % (this_sem[1].upper(), this_sem[0]),
                   emner_this_sem_id, emner_id)
    register_group('Emner %s %s' % (next_sem[1].upper(), next_sem[0]),
                   emner_next_sem_id, emner_id)

    emnerom_this_sem_id = emner_this_sem_id + ':emnerom'
    emnerom_next_sem_id = emner_next_sem_id + ':emnerom'
    register_group('Emnerom %s %s' % (this_sem[1].upper(), this_sem[0]),
                   emnerom_this_sem_id, emner_this_sem_id)
    register_group('Emnerom %s %s' % (next_sem[1].upper(), next_sem[0]),
                   emnerom_next_sem_id, emner_next_sem_id)

    for sem, sem_node_id in ((this_sem, emner_this_sem_id),
                             (next_sem, emner_next_sem_id)):
        for suffix, title in (
            ('student', 'Studenter %s %s' % (sem[1].upper(),
                                             sem[0])),
            ('foreleser', 'Forelesere %s %s' % (sem[1].upper(),
                                                sem[0])),
            ('studieleder', 'Studieledere %s %s' % (sem[1].upper(),
                                                    sem[0]))):
            node_id = sem_node_id + ':' + suffix
            register_group(title, node_id, sem_node_id)

    brukere_id= 'STRUCTURE:%s:fs:brukere' % cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Brukere', brukere_id, root_node_id)

    fellesrom_id = 'STRUCTURE:%s:fs:fellesrom' % \
                   cereconf.INSTITUTION_DOMAIN_NAME
    register_group('Fellesrom', fellesrom_id, root_node_id)

    # Populer dicter for "emnekode -> emnenavn" og "fakultet ->
    # [emnekode ...]".
    emne_info = {}
    fakulteter = []
    def finn_emne_info(element, attrs):
        if element <> 'undenhet':
            return
        emnekode = attrs['emnekode'].lower()
        faknr = int(attrs['faknr_kontroll'])
        emne_info[emnekode] = {'navn': attrs['emnenavn_bokmal'],
                               'fak': faknr}
        if faknr not in fakulteter:
            fakulteter.append(faknr)
    access_FS.underv_enhet_xml_parser('/cerebrum/dumps/FS/underv_enhet.xml',
                                      finn_emne_info)

    stprog_info = {}
    def finn_stprog_info(element, attrs):
        if element <> 'studprog':
            return
        stprog = attrs['studieprogramkode'].lower()
        faknr = int(attrs['faknr_studieansv'])
        stprog_info[stprog] = {'fak': faknr}
        if faknr not in fakulteter:
            fakulteter.append(faknr)
    access_FS.studieprog_xml_parser('/cerebrum/dumps/FS/studieprog.xml',
                                    finn_stprog_info)
    # Henter ut ansatte per fakultet
    ans_dict = get_ans_fak(fakulteter, acc2names)
    # Opprett de forskjellige stedkode-korridorene.
    ou = Stedkode.Stedkode(db)
    for faknr in fakulteter:
        fak_sko = "%02d0000" % faknr
        ou.clear()
        try:
	    ou.find_stedkode(faknr, 0, 0,
                             institusjon = cereconf.DEFAULT_INSTITUSJONSNR)
        except Errors.NotFoundError:
            logger.error("Finner ikke stedkode for fakultet %d", faknr)
            faknavn = '*Ikke registrert som fakultet i FS*'
        else:
            if ou.acronym:
                faknavn = ou.acronym
            else:
                faknavn = ou.short_name
        fak_ans_id = "%s:sap:gruppe:%s:%s:ansatte" % \
                     (cereconf.INSTITUTION_DOMAIN_NAME,
                      cereconf.DEFAULT_INSTITUSJONSNR,
                      fak_sko)
        ans_title = "Ansatte ved %s" % faknavn
        register_group(ans_title, fak_ans_id, brukere_id,
                       allow_contact=True)
        ans_memb = ans_dict[int(faknr)]
        register_members(fak_ans_id, ans_memb)
        for id_prefix, parent_id in ((emner_this_sem_id, emnerom_this_sem_id),
                                     (emner_next_sem_id, emnerom_next_sem_id)):
            fak_node_id = id_prefix + \
                          ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                      fak_sko)
            register_group(faknavn, fak_node_id, parent_id,
                           allow_room=True)
        brukere_sted_id = brukere_id + \
                          ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                      fak_sko)
        register_group(faknavn, brukere_sted_id, brukere_id)
        brukere_studenter_id = brukere_sted_id + ':student'
        register_group('Studenter ved %s' % faknavn,
                       brukere_studenter_id, brukere_sted_id)
        fellesrom_sted_id = fellesrom_id + ":%s:%s" % (
            cereconf.DEFAULT_INSTITUSJONSNR, fak_sko)
        register_group(faknavn, fellesrom_sted_id, fellesrom_id,
                       allow_room=True)

    register_spread_groups(emne_info, stprog_info)

    output_group_xml()
    for room, data in new_rooms.iteritems():
        fxml.room_to_XML(data['CFid'], fronter_lib.Fronter.STATUS_ADD, data)

    for node, data in new_acl.iteritems():
        fxml.acl_to_XML(node, fronter_lib.Fronter.STATUS_ADD, data)

    for gname, members in new_groupmembers.iteritems():
        fxml.personmembers_to_XML(gname, fronter_lib.Fronter.STATUS_ADD,
                                  members)
    fxml.end()


if __name__ == '__main__':
    main()
