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
from Cerebrum import Database
from Cerebrum import Person
from Cerebrum import Group
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.hia import fronter_lib



db = const = logger = None
fxml = None
romprofil_id = {}

def init_globals():
    global db, const, logger
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger("console")

    cf_dir = '/cerebrum/dumps/Fronter'

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'debug-file=', 'debug-level='])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(cf_dir, "x-import.log")
    debug_level = 4
    host = 'hia'
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--debug-file':
            debug_file = val
        elif opt == '--debug-level':
            debug_level = val
        elif opt == 'rom-profil':
            profil_navn, profil_id = val.split(':')
            romprofil_id[profil_navn] = profil_id
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
                                  fronter = None)

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
    return ((str(this_year), this_sem), (str(next_year), next_sem))

def load_acc2name():
    logger.debug('Loading person/user-to-names table')
    ret = {}
    front = fronter_lib.hiafronter(db)
    """	Followin field in fronter_lib.hiafronter.list_cf_persons
	person_id, account_id, external_id, name, entity_name,
	fs_l_name, fs_f_name, local_part, domain """
    for pers in front.list_cf_persons():
	#logger.debug("Loading person: %s" % pers['name'])
	if not (pers['fs_f_name'] and pers['fs_l_name']):
	    l_name, f_name = get_names(pers['person_id'])
	else:
	    l_name, f_name = pers['fs_l_name'],pers['fs_f_name']
	ret[pers['account_id']] = {
            'NAME': pers['entity_name'],
            'FN': pers['name'],
            'GIVEN': f_name,
            'FAMILY': l_name,
            'EMAIL': '@'.join((pers['local_part'], pers['domain'])),
            'USERACCESS': 2,
            'PASSWORD': 5,
            'EMAILCLIENT': 1}
    return ret

def get_names(person_id):
    name_tmp = {}
    person = Factory.get('Person')(db)
    person.find(person_id)
    for names in person.get_all_names():
	if int(names['source_system']) <> int(const.system_cached):
	    sys_key = int(names['source_system'])
            sys_names = name_tmp.setdefault(sys_key, [])
	    name_li = "%s:%s" % (names['name_variant'], names['name'])
            sys_names.append(name_li)
    last_n = first_n = None
    for a_sys in cereconf.SYSTEM_LOOKUP_ORDER:
	sys_key = int(getattr(const, a_sys))
        for p_name in name_tmp.get(sys_key, []):
            var_n, nam_n = p_name.split(':')
            if (int(var_n) == int(const.name_last)):
                last_n = nam_n
            elif (int(var_n) == int(const.name_first)):
                first_n = nam_n
            else: pass
            if first_n is not None and last_n is not None:
                return (last_n, first_n)
    return ("*Ukjent etternavn*", "*Ukjent fornavn*")

def get_ans_fak(fak_list, ent2uname):
    fak_res = {}
    person = Factory.get('Person')(db)
    stdk = Stedkode.Stedkode(db)
    for fak in fak_list:
        ans_list = []
        # Get all stedkoder in one faculty
        for ou in stdk.get_stedkoder(fakultet=int(fak)):
            # get persons in the stedkode
            for pers in person.list_affiliations(source_system=const.system_sap,
                                        affiliation=const.affiliation_ansatt,
                                        ou_id=int(ou['ou_id'])):
                person.clear()
                #person.entity_id = int(pers['person_id'])
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
                if subg_name_el[-1] == 'student':
                    stprog = subg_name_el[4]
                    fak_sko = '%02d0000' % stprog_info[stprog]['fak']
                    brukere_studenter_id = ':'.join((
                        'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                        'fs', 'brukere', subg_name_el[2], fak_sko,
                        'student'))
                    brukere_stprog_id = brukere_studenter_id + \
                                        ':%s' % stprog
                    fronter_gname = ':'.join(subg_name_el)
                    register_group(stprog.upper(), brukere_stprog_id,
                                   brukere_studenter_id)
                    register_group(
                        'Studenter på %s' % subg_name_el[6], # kullkode
                        fronter_gname, brukere_stprog_id,
                        allow_contact=1)
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
                elif subg_name_el[-1] == 'studieleder':
                    # TBD: Hvor i CF-strukturen skal disse
                    # "studieleder på studieprogram" forankres?
                    pass
                else:
                    raise RuntimeError, \
                          "Ukjent studieprogram-gruppe: %r" % (gname,)
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
def register_group(title, id, parentid, allow_room=0, allow_contact=0):
    """Adds info in new_group about group."""
    new_group[id] = { 'title': title,
                      'parent': parentid,
                      'allow_room': allow_room,
                      'allow_contact': allow_contact,
                      'CFid': id,
		      }

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
	fxml.user_to_XML(user)

    # Registrer en del semi-statiske strukturnoder.
    root_node_id = "STRUCTURE:ClassFronter structure root node"
    register_group('Høyskolen i Agder', root_node_id, root_node_id)

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
    fak_emner = {}
    def finn_emne_info(element, attrs):
        if element <> 'undenhet':
            return
        emnekode = attrs['emnekode'].lower()
        faknr = int(attrs['faknr_kontroll'])
        emne_info[emnekode] = {'navn': attrs['emnenavn_bokmal'],
                               'fak': faknr}
        fak_emner.setdefault(faknr, []).append(emnekode)
    access_FS.underv_enhet_xml_parser('/cerebrum/dumps/FS/underv_enhet.xml',
                                      finn_emne_info)

    stprog_info = {}
    def finn_stprog_info(element, attrs):
        if element == 'studprog':
            stprog = attrs['studieprogramkode'].lower()
            faknr = int(attrs['faknr_studieansv'])
            stprog_info[stprog] = {'fak': faknr}
    access_FS.studieprog_xml_parser('/cerebrum/dumps/FS/studieprog.xml',
                                    finn_stprog_info)
    # Henter ut ansatte per fakultet
    ans_dict = get_ans_fak(fak_emner.keys(),acc2names) 
    # Opprett de forskjellige stedkode-korridorene.
    ou = Stedkode.Stedkode(db)
    for faknr in fak_emner.iterkeys():
        fak_sko = "%02d0000" % faknr
        ou.clear()
        try:
	    ou.find_stedkode(faknr, 0, 0,
                             institusjon = cereconf.DEFAULT_INSTITUSJONSNR)
	except Errors.NotFoundError:
	    logger.error("Finner ikke stedkode for fakultet %d", faknr)
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
	    print "register group",ans_title, brukere_id, fak_ans_id
	    register_group(ans_title, fak_ans_id, brukere_id, allow_contact=True)
	    ans_memb = ans_dict[int(faknr)]
	    register_members(fak_ans_id, ans_memb)
            for sem_node_id in (emnerom_this_sem_id,
                                emnerom_next_sem_id):
                fak_node_id = sem_node_id + \
                              ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                          fak_sko)
                register_group(faknavn, fak_node_id, sem_node_id,
                               allow_room=1)
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
                           allow_room=1)

    register_spread_groups(emne_info, stprog_info)

    for group, data in new_group.iteritems():
        fxml.group_to_XML(data['CFid'], fronter_lib.Fronter.STATUS_ADD, data)
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
