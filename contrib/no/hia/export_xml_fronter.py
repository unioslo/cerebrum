#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from __future__ import unicode_literals
import sys
import os
import getopt
import time

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import access_FS
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.hia import fronter_lib


db = const = logger = None
fxml = None
romprofil_id = {}
include_this_sem = True


def init_globals():
    global db, const, logger
    logger = Factory.get_logger("cronjob")
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    cf_dir = '/cerebrum/var/cache/Fronter'
    global fs_dir
    fs_dir = '/cerebrum/var/cache/FS'

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'uten-dette-semester',
                                    'uten-passord',
                                    'debug-file=', 'debug-level=',
                                    'cf-dir=', 'fs-dir='])
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
        elif opt == '--cf-dir':
            cf_dir = val
        elif opt == '--fs-dir':
            fs_dir = val
        else:
            raise ValueError("Invalid argument: %r" % opt)

    host_profiles = {'hia': {'emnerom': 2696,
                             'evukursrom': 2696,
                             'studieprogram': 1521},
                     'hia2': {'emnerom': 42,
                              'evukursrom': 42,
                              'studieprogram': 42},
                     'hia3': {'emnerom': 1520,
                              'evukursrom': 1520,
                              'studieprogram': 1521}
                     }
    if host in host_profiles:
        romprofil_id.update(host_profiles[host])

    filename = os.path.join(cf_dir, 'test.xml')
    if len(args) == 1:
        filename = args[0]
    elif len(args) != 0:
        usage(2)

    global fxml
    fxml = fronter_lib.FronterXML(filename,
                                  cf_dir=cf_dir,
                                  debug_file=debug_file,
                                  debug_level=debug_level,
                                  fronter=None,
                                  include_password=set_pwd)


def get_semester():
    t = time.localtime()[0:2]
    this_year = t[0]
    # the normal state:
    # if t[1] <= 6

    # Need to make the spring term last at least untill 2005-08-1:
    if t[1] <= 7:
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


def load_phone_numbers(person):
    """Fish out cell phone numbers for Fronter export.

    At UiA's request (2010-04-20), we export mobile phone numbers to
    Fronter. It is not an error, if a person misses a number.
    """

    person2phone = dict()
    last = None
    logger.debug("Preloading phone numbers")
    for row in person.list_contact_info(
            source_system=const.system_fs,
            contact_type=const.contact_mobile_phone,
            entity_type=const.entity_person):
        person_id = int(row["entity_id"])
        # We grab the first matching cell phone
        # The best priority takes precedence, when there are multiple rows
        # satisfying all of the filters above.
        if person_id == last:
            continue
        person2phone[person_id] = row["contact_value"]

    logger.debug("Collected numbers for %s people", len(person2phone))
    return person2phone
# end load_phone_numbers


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
        name_types=[const.name_first, const.name_last, const.name_full])

    ext2puname = person.getdict_external_id2primary_account(
        const.externalid_fodselsnr)

    person2phone = load_phone_numbers(person)
    ret = {}
    for pers in person.list_persons_atype_extid():
        # logger.debug("Loading person: %s" % pers['name'])
        if pers['external_id'] in ext2puname:
            ent_name = ext2puname[pers['external_id']]
        else:
            continue
        if int(pers['person_id']) in person_name:
            if len(person_name[int(pers['person_id'])]) != 3:
                continue
            else:
                names = person_name[int(pers['person_id'])]
        else:
            # logger.debug("Person name fault, person_id: %s" % ent_name)
            continue
        if ent_name in uname2mail:
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
            # HiA har bedt om denne eksplisitt
            'PASSWORD': 'ldap1',
            'EMAILCLIENT': 1,
            'MOBILE': person2phone.get(pers["person_id"])}
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
                    logger.debug("Person pers_id: %d , no valid account!",
                                 person.entity_id)
                    break
                if acc_id and acc_id in ent2uname:
                    uname = ent2uname[acc_id]['NAME']
                    if uname not in ans_list:
                        ans_list.append(uname)
                else:
                    logger.debug("Person pers_id: %d have no account!",
                                 person.entity_id)
        fak_res[int(fak)] = ans_list
    return fak_res


def register_spread_groups_evu(row, group, evukurs_info, entity2name):
    """
    Registrer alle rom/grupper knyttet til en intern gruppe representert av
    row.
    """

    gname = row["name"]
    gname_el = gname.split(":")

    assert gname_el[4] == 'evu', \
        "Registerer en ikke-evu gruppe %s som om den var EVU" % gname

    logger.debug("bygger grupper knyttet til %s", gname)

    #
    # Oppgaven foran oss er slik: CF-strukturen til EVU-delen er
    # egentlig ikke så veldig fancy. Vi har:
    #
    # * Et evukursrom for hvert EVU-kurs (KR)
    # * En gruppe for studenter for det tilsvarende kurset som får
    #   rettigheter i KR.
    # * En gruppe for forelesere for det tilsvarende kurset som får
    #   rettigheter i KR.

    # eukk == etterutdkurskode, tak == kurstidsangivelsekode
    junk, domain, fs_part, domain_nr, evu_part, eukk, ktak = gname_el

    # Denne skal allerede finnes (den er statisk)
    kursrom_parent = 'STRUCTURE:%s:fs:%s:evu:kursrom' % (domain, domain_nr)
    # Rom for EVU-kurset
    evukursrom_id = 'ROOM:%s:fs:%s:evu:%s:%s' % (domain, domain_nr,
                                                 eukk, ktak)
    try:
        register_room(evukurs_info[eukk, ktak],
                      evukursrom_id,
                      kursrom_parent,
                      profile=romprofil_id["evukursrom"])
    except KeyError:
        logger.error("Could not find room %s", evukursrom_id)

    #
    # Grupper for studenter og forelesere på EVU-kurset
    group.clear()
    group.find(row["group_id"])
    for member_row in group.search_members(group_id=group.entity_id,
                                           member_type=const.entity_group):
        subg_id = int(member_row["member_id"])
        subg_name = entity2name.get(subg_id)
        if subg_id not in entity2name:
            logger.warn("Group member id=%s of group id=%s has no name!",
                        subg_id, group.entity_id)
            continue

        #
        # Gruppenavn er her på formen:
        #     internal:DOMAIN:fs:INSTITUSJONSNR:evu:EUKK:KTAK:KATEGORI
        # Tilsvarende CF-navn blir derimot
        #     DOMAIN:fs:INSTITUSJONSNR:evu:KATEGORI:EUKK:KTAK
        subg_name_el = subg_name.split(':')
        if subg_name_el[0] == 'internal':
            subg_name_el.pop(0)
        else:
            raise ValueError("intern gruppe uten 'internal':%s" %
                             subg_name)
        # fi

        category = subg_name_el[6]
        parent_id = "STRUCTURE:%s:fs:%s:evu" % (subg_name_el[0],
                                                subg_name_el[2])
        if category == "kursdeltaker":
            title = "Kursdeltakere"
            permission = fronter_lib.Fronter.ROLE_WRITE
            parent_suffix = "kursdeltaker"
        elif category == "foreleser":
            title = "Forelesere"
            permission = fronter_lib.Fronter.ROLE_CHANGE
            parent_suffix = "foreleser"
        else:
            raise ValueError("ukjent kategori '%s' for %s" % (category,
                                                              subg_name))
        # fi

        parent_id = parent_id + ":" + parent_suffix
        title = "%s %s %s" % (title, eukk, ktak)
        fronter_gname = ':'.join(subg_name_el[0:4] + [category, ] +
                                 subg_name_el[4:6])
        # FIXME: allow_contact?
        register_group(title, fronter_gname, parent_id, allow_contact=True)

        group.clear()
        group.find(subg_id)
        user_members = [
            entity2name.get(int(r["member_id"])) for r in
            group.search_members(group_id=group.entity_id,
                                 member_type=const.entity_account)
            if int(row["member_id"]) in entity2name]
        if user_members:
            register_members(fronter_gname, user_members, const.entity_account)
        # fi

        register_room_acl(evukursrom_id, fronter_gname, permission)
    # od


def _load_entity_names():
    """Cache entity_id -> name mapping for later.

    @rtype: dict (of int to basestring)
    @return:
      A dictionary mapping entity ids (of groups and accounts) to the
      respective names from entity_name. Naturally, if one entity has several
      names in different name domains, we'll have interesting results.
    """

    # any entity with access to names would do nicely
    en = Factory.get("Group")(db)
    entity2name = dict((x["entity_id"], x["entity_name"]) for x in
                       en.list_names(const.account_namespace))
    entity2name.update((x["entity_id"], x["entity_name"]) for x in
                       en.list_names(const.group_namespace))
    return entity2name
# end _load_entity_names


def register_spread_groups(emne_info, stprog_info, evukurs_info):
    group = Factory.get('Group')(db)
    this_sem, next_sem = get_semester()
    entity2name = _load_entity_names()
    for r in group.search(spread=const.spread_hia_fronter):
        gname = r['name']
        gname_el = gname.split(':')

        if gname_el[4] == 'evu':
            register_spread_groups_evu(r, group, evukurs_info, entity2name)
        elif gname_el[4] == 'undenh':
            # Nivå 3: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
            #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
            #
            # De interessante gruppene (som har brukermedlemmer) er på
            # nivå 4.
            instnr = gname_el[3]
            ar, term, emnekode, versjon, terminnr = gname_el[5:10]
            if (ar, term) not in (this_sem, next_sem):
                continue

            if emnekode not in emne_info:
                logger.warn("Emne %s er ikke i emne_info/underv_enhet.xml, " +
                            "men det finnes en gruppe %s med fronter spread",
                            emnekode, gname)
                continue
            # fi

            fak_sko = "%02d0000" % emne_info[emnekode]['fak']

            # Rom for undervisningsenheten.
            emne_id_prefix = ':'.join((cereconf.INSTITUTION_DOMAIN_NAME_LMS,
                                       'fs', 'emner'))
            emne_rom_id = fronter_lib.FronterUtils.UE2RomID(
                'ROOM:%s' % emne_id_prefix,
                ar, term, instnr, fak_sko, 'undenh',
                emnekode, versjon, terminnr)
            emne_id_term_prefix = ':'.join((emne_id_prefix, ar, term,
                                            instnr, fak_sko))
            emne_sted_id = 'STRUCTURE:%s' % emne_id_term_prefix
            if int(terminnr) == 1 or (ar, term) == this_sem:
                # Registrer rom for alle undervisningsenheter som
                # danner starten på et kurs (terminnr == 1).
                #
                # For senere semestere av flersemesterkurs skal rommet
                # registreres i korridoren som svarer til inneværende
                # semester.  Dette betyr at rom for flersemesterkurs
                # vil bli flyttet til nytt semester først etter at det
                # nye semesteret har startet.
                #
                # Merk dog at så snart det blir registrert studenter
                # på neste semesters undervisningsenhet, vil disse få
                # rettigheter til flersemesterkursets rom, selv om
                # dette på det tidspunktet fortsatt ligger i
                # korridoren for inneværende semester.
                register_room('%s (ver %s, %d. termin, %s %s)' % (
                    emnekode.upper(), versjon, int(terminnr), ar, term),
                    emne_rom_id, emne_sted_id, profile=romprofil_id['emnerom'])

            # Grupper for studenter, forelesere og studieveileder på
            # undervisningsenheten.
            group.clear()
            group.find(r['group_id'])
            for member_row in group.search_members(
                    group_id=group.entity_id,
                    member_type=const.entity_group):
                subg_id = int(member_row["member_id"])
                subg_name = entity2name.get(subg_id)
                if subg_id not in entity2name:
                    logger.warn(
                        "Group member id=%s of group id=%s has no name!",
                        subg_id, group.entity_id)
                    continue

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
                    rettighet = fronter_lib.Fronter.ROLE_CHANGE
                elif kategori == 'studieleder':
                    title = 'Studieledere for '
                    rettighet = fronter_lib.Fronter.ROLE_CHANGE
                else:
                    raise RuntimeError("Ukjent kategori: %r" % (kategori,))
                title += '%s (ver %s, %d. termin, %s %s)' % (
                    subg_name_el[6].upper(),  # EMNEKODE
                    subg_name_el[7],    # VERSJONSKODE
                    int(subg_name_el[8]),  # TERMINNR
                    subg_name_el[4],  # ARSTALL
                    subg_name_el[5])  # TERMINKODE
                fronter_gname = ':'.join(subg_name_el)
                register_group(title, fronter_gname, parent_id,
                               allow_contact=True)
                group.clear()
                group.find(subg_id)
                user_members = [
                    entity2name.get(int(row["member_id"])) for row in
                    group.search_members(group_id=group.entity_id,
                                         member_type=const.entity_account)
                    if int(row["member_id"]) in entity2name]

                if user_members:
                    register_members(fronter_gname, user_members,
                                     const.entity_account)
                # some groups have special permissions wrt "...:student"
                if kategori == "student":
                    foreleser_id = ':'.join(subg_name_el[:9] + ["foreleser", ])
                    studieleder_id = ':'.join(subg_name_el[:9] +
                                              ["studieleder", ])
                    register_members(fronter_gname,
                                     (foreleser_id, studieleder_id),
                                     const.entity_group)

                register_room_acl(emne_rom_id, fronter_gname, rettighet)

        elif gname_el[4] == 'studieprogram':
            # En av studieprogram-grenene på nivå 3.  Vil eksportere
            # gruppene på nivå 4.
            group.clear()
            group.find(r['group_id'])
            # Legges inn new group hvis den ikke er opprettet
            for member_row in group.search_members(
                    group_id=group.entity_id,
                    member_type=const.entity_group):
                subg_id = int(member_row["member_id"])
                subg_name = entity2name.get(subg_id)
                if subg_id not in entity2name:
                    logger.warn(
                        "Group member id=%s of group id=%s has no name!",
                        subg_id, group.entity_id)
                    continue

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
                    'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME_LMS,
                    'fs', 'fellesrom', institusjonsnr, fak_sko))
                fellesrom_stprog_rom_id = ':'.join((
                    'ROOM', cereconf.INSTITUTION_DOMAIN_NAME_LMS, 'fs',
                    'fellesrom', 'studieprogram', stprog))
                register_room(stprog.upper(), fellesrom_stprog_rom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])
                if subg_name_el[-1] == 'student':
                    brukere_studenter_id = ':'.join((
                        'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME_LMS,
                        'fs', 'brukere', institusjonsnr, fak_sko, 'student'))
                    brukere_stprog_id = brukere_studenter_id + \
                        ':%s' % stprog
                    register_group(stprog.upper(), brukere_stprog_id,
                                   brukere_studenter_id)
                    register_group(
                        # "Studenter på <STUDIEPROGRAMKODE>
                        #  <arstall_kull> <terminkode_kull>"
                        'Studenter på %s %s %s' % (stprog.upper(),
                                                    subg_name_el[6],
                                                    subg_name_el[7]),
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
                    raise RuntimeError("Ukjent studieprogram-gruppe: %r" %
                                       (gname,))

                # Synkroniser medlemmer i Cerebrum-gruppa til CF.
                group.clear()
                group.find(subg_id)
                user_members = [
                    entity2name.get(int(row["member_id"])) for row in
                    group.search_members(group_id=group.entity_id,
                                         member_type=const.entity_account)
                    if int(row["member_id"]) in entity2name ]

                if user_members:
                    register_members(fronter_gname,
                                     user_members, const.entity_account)
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
def register_members(gname, members, member_type):
    """Register members for a group.

    Register members for group 'gname'. We can register either account members
    (typically a member of ':foreleser' group) or group members (group members
    of a group).

    @type gname: basestring
    @param gname:
      Group name for which we supply the member list

    @type members: sequence of names (basestrings)
    @param members:
      Sequence of group members of a certain type that are all the the members
      of the said type for group L{gname}.

    @type member_type: instance of EntityTypeCode
    @param member_type:
      Specifies the member type for L{members}. Each group may have many
      members split into different types. entity_account and entity_group are
      the only two types accepted.
    """
    assert member_type in (const.entity_account, const.entity_group)
    new_groupmembers.setdefault(gname, {})[int(member_type)] = members
# end register_members

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
        if parent != id:
            output(parent)
        fxml.group_to_XML(data['CFid'], fronter_lib.Fronter.STATUS_ADD,
                          data)
        done[id] = True
    for group in new_group.iterkeys():
        output(group)

def usage(exitcode):
    print "Usage: export_xml_fronter.py OUTPUT_FILENAME"
    sys.exit(exitcode)

def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    init_globals()

    fxml.start_xml_head()

    # Finn `account_id` -> account-data for alle brukere.
    acc2names = load_acc2name()
    # Spytt ut PERSON-elementene.
    for user in acc2names.itervalues():
        fxml.user_to_XML(user['NAME'],
                         # Som påpekt av HiA i en e-post til cerebrum-hia
                         # (<messsage-id:430C4970.2030709@fronter.com), skal
                         # vi bruke STATUS_ADD (autentiseringsrutinene har
                         # endret seg og nå *skal* man levere dumpen med
                         # recstatus=1).
                         fronter_lib.Fronter.STATUS_ADD,
                         user)

    # Registrer en del semi-statiske strukturnoder.
    root_node_id = "STRUCTURE:ClassFronter structure root node"
    register_group('Universitetet i Agder', root_node_id, root_node_id)

    manuell_node_id = 'STRUCTURE:%s:manuell' % \
                      cereconf.INSTITUTION_DOMAIN_NAME_LMS
    register_group('Manuell', manuell_node_id, root_node_id,
                   allow_room=True)

    auto_node_id = "STRUCTURE:%s:automatisk" % \
                   cereconf.INSTITUTION_DOMAIN_NAME_LMS
    register_group("Automatisk", auto_node_id, root_node_id)

    emner_id = 'STRUCTURE:%s:fs:emner' % cereconf.INSTITUTION_DOMAIN_NAME_LMS
    register_group('Emner', emner_id, auto_node_id)

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

    brukere_id= 'STRUCTURE:%s:fs:brukere' % cereconf.INSTITUTION_DOMAIN_NAME_LMS
    register_group('Brukere', brukere_id, auto_node_id)

    fellesrom_id = 'STRUCTURE:%s:fs:fellesrom' % \
                   cereconf.INSTITUTION_DOMAIN_NAME_LMS
    register_group('Fellesrom', fellesrom_id, auto_node_id)

    # Registrer statiske EVU-strukturnoder.
    # Ting blir litt enklere, hvis vi drar med oss institusjonsnummeret
    evu_node_id = 'STRUCTURE:%s:fs:%s:evu' % (cereconf.INSTITUTION_DOMAIN_NAME_LMS,
                                              cereconf.DEFAULT_INSTITUSJONSNR)
    register_group('EVU', evu_node_id, auto_node_id)
    for (suffix,
         title,
         allow_room) in (("kursrom", "EVU kursrom", True),
                         ("kursdeltaker", "EVU kursdeltaker", False),
                         ("foreleser", "EVU foreleser", False)):
        node_id = evu_node_id + ":" + suffix
        register_group(title, node_id, evu_node_id, allow_room)
    # od

    # Populer dicter for "emnekode -> emnenavn", "fakultet ->
    # [emnekode ...]" og "<evukurs> -> evukursnavn".
    emne_info = {}
    fakulteter = []
    def finn_emne_info(element, attrs):
        if element != 'undenhet':
            return
        emnekode = attrs['emnekode'].lower()
        faknr = int(attrs['faknr_kontroll'])
        emne_info[emnekode] = {'navn': attrs['emnenavn_bokmal'],
                               'fak': faknr}
        if faknr not in fakulteter:
            fakulteter.append(faknr)
    access_FS.underv_enhet_xml_parser(os.path.join(fs_dir, 'underv_enhet.xml'),
                                      finn_emne_info)

    stprog_info = {}
    def finn_stprog_info(element, attrs):
        if element != 'studprog':
            return
        stprog = attrs['studieprogramkode'].lower()
        faknr = int(attrs['faknr_studieansv'])
        stprog_info[stprog] = {'fak': faknr}
        if faknr not in fakulteter:
            fakulteter.append(faknr)
    access_FS.studieprog_xml_parser(os.path.join(fs_dir, 'studieprog.xml'),
                                    finn_stprog_info) 
    
    evukurs_info = {}
    def finn_evukurs_info(element, attrs):
        if element != "evukurs":
            return

        name = "%s (%s)" % (attrs.get("etterutdkursnavnkort", ""),
                            ", ".join(filter(None,
                                        (attrs.get("etterutdkurskode"),
                                         attrs.get("kurstidsangivelsekode"),
                                         attrs.get("emnekode")))))

        eukk, ktak = (attrs["etterutdkurskode"].lower(),
                      attrs["kurstidsangivelsekode"].lower())
        evukurs_info[eukk, ktak] = name
    # end finn_evukurs_info
    access_FS.evukurs_xml_parser(os.path.join(fs_dir, 'evu_kursinfo.xml'),
                                 finn_evukurs_info)
    
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
            acronym = ou.get_name_with_language(name_variant=const.ou_name_acronym,
                                                name_language=const.language_nb,
                                                default="")
            short_name = ou.get_name_with_language(name_variant=const.ou_name_short,
                                                   name_language=const.language_nb,
                                                   default="")
            if acronym:
                faknavn = acronym
            else:
                faknavn = short_name
        fak_ans_id = "%s:sap:gruppe:%s:%s:ansatte" % \
                     (cereconf.INSTITUTION_DOMAIN_NAME_LMS,
                      cereconf.DEFAULT_INSTITUSJONSNR,
                      fak_sko)
        ans_title = "Ansatte ved %s" % faknavn
        register_group(ans_title, fak_ans_id, brukere_id,
                       allow_contact=True)
        ans_memb = ans_dict[int(faknr)]
        register_members(fak_ans_id, ans_memb, const.entity_account)
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

    register_spread_groups(emne_info, stprog_info, evukurs_info)

    output_group_xml()
    for room, data in new_rooms.iteritems():
        fxml.room_to_XML(data['CFid'], fronter_lib.Fronter.STATUS_ADD, data)

    for node, data in new_acl.iteritems():
        fxml.acl_to_XML(node, fronter_lib.Fronter.STATUS_ADD, data)

    for gname, members in new_groupmembers.iteritems():
        person_members = members.get(int(const.entity_account), ())
        group_members = members.get(int(const.entity_group), ())
        fxml.personmembers_to_XML(gname, fronter_lib.Fronter.STATUS_ADD,
                                  person_members)
        if group_members:
            # IVR 2008-01-29 Just to be sure...
            assert gname.split(':')[-1] == "student"
            fxml.groupmembers_to_XML(gname, fronter_lib.Fronter.STATUS_ADD,
                                     group_members)
    fxml.end()


if __name__ == '__main__':
    main()
