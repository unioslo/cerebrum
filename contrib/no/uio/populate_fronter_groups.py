#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

"""Populate Cerebrum with FS-derived groups.

These groups are later used when exporting data to ClassFronter.

"""

import sys
import getopt
import re

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio.fronter_lib import FronterUtils
from Cerebrum import Logging

def prefetch_primaryusers():
    # TBD: This code is used to get account_id for both students and
    # fagansv.  Should we look at affiliation here?
    account = Factory.get('Account')(db)
    personid2accountid = {}
    for a in account.list_accounts_by_type():
        # TODO: Also look at account_type.priority
        personid2accountid[int(a['person_id'])] = int(a['account_id'])

    person = Factory.get('Person')(db)
    for row in person.list_external_ids(
        source_system=co.system_fs, id_type=co.externalid_fodselsnr):
        if personid2accountid.has_key(int(row['person_id'])):
            account_id = personid2accountid[int(row['person_id'])]
            account_id2fnr[account_id] = row['external_id']
            fnr2account_id[row['external_id']] = account_id

def fnrs2account_ids(rows):
    ret = []
    for r in rows:
        fnr = "%06d%05d" % (
            int(r['fodselsdato']), int(r['personnr']))
        if fnr2account_id.has_key(fnr):
            ret.append(fnr2account_id[fnr])
    return ret

def process_kursdata():
    logger.debug("Getting all primaryusers")
    prefetch_primaryusers()
    logger.debug(" ... done")
    get_undervisningsenheter()    # Utvider UndervEnhet med mer data
    get_undervisningsaktiviteter()
    get_evukurs_aktiviteter()
    logger.debug(UndervEnhet)

    for k in UndervEnhet.keys():
        # Legger inn brukere i gruppene på nivå 3.
        #
        # $enhet er her enten en undervisningsenhet (starter med "kurs:")
        # eller en EVU-enhet (starter med "evu:"); vi overlater til
        # populate_enhet_groups å behandle forskjellige type enheter på
        # passende vis.
        populate_enhet_groups(k)

    # Oppdaterer gruppene på nivå 2.
    #
    # Må skille mellom EVU-kurs og vanlige kurs da identifikatorene deres
    # har forskjellig antall felter i $kurs_id.
    #
    logger.info("Oppdaterer enhets-supergrupper:")
    for kurs_id in AffiliatedGroups.keys():
        rest = kurs_id.split(":")
        type = rest.pop(0).lower()
        if type == 'kurs':
            instnr, emnekode, versjon, termk, aar = rest
            sync_group("%s:%s" % (type, emnekode), kurs_id,
                       "Ikke-eksporterbar gruppe.  Brukes for å definere hvor"+
                       " data om kurset <%s> skal eksporteres." % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id])
        elif type == 'evu':
            kurskode, tidsrom = rest
            sync_group("%s:%s" % (type, kurskode), kurs_id,
                       "Ikke-eksporterbar gruppe.  Brukes for å definere hvor"+
                       " data om emnet <%s> skal eksporteres. " % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id])
        else:
            logger.warn("Ukjent kurstype <%s> for kurs <%s>" % (type, k))

        # Kallene på sync_group legger inn nye entries i
        # %AffiliatedGroups; ting blir mye greiere å holde rede på om vi
        # fjerner "våre" nøkler derfra så snart vi er ferdige.
        del(AffiliatedGroups[kurs_id])
    logger.info(" ... done")

    # Oppdaterer gruppene på nivå 1.
    #
    # Alle grupper knyttet til en undervisningsenhet skal meldes inn i den
    # u2k-interne emnekode-gruppen.  Man benytter så emnekode-gruppen til
    # å definere eksport-egenskaper for alle grupper tilknyttet en
    # undervisningsenhet.
    logger.info("Oppdaterer emne-supergrupper:")
    for gname in AffiliatedGroups.keys():
        sync_group(fs_supergroup, gname,
                   "Ikke-eksporterbar gruppe.  Brukes for å samle kursene"+
                   " knyttet til %s." % gname,
                   co.entity_group, AffiliatedGroups[gname]);
    logger.info(" ... done")


    #
    # Alle emnekode-supergrupper skal meldes inn i en supergruppe
    # spesifikk for denne importmekanismen.
    #
    # På denne måten holdes det oversikt over hvilke grupper som er
    # automatisk opprettet på bakgrunn av import fra FS.  Uten en slik
    # oversikt vil man ikke kunne foreta automatisk sletting av grupper
    # tilhørende "utgåtte" undervisningsenheter og -aktiviteter.
    logger.info("Oppdaterer supergruppe for alle emnekode-supergrupper")
    sync_group(None, fs_supergroup,
               "Ikke-eksporterbar gruppe.  Definerer hvilke andre grupper "+
               "som er opprettet automatisk som følge av FS-import.",
               co.entity_group,
               AffiliatedGroups[fs_supergroup])
    logger.info(" ... done")



## send_mail("\n$warn_msg",
##        sender => 'ureg2000-core@usit.uio.no',
##        recips => [ split(m/\s+/, $warn_addr) ],
##        subject => 'Bygging av ureg2000-grupper fra FS-data',
##        dryrun => $dryrun,
##        dryrun_output => '>&STDOUT')
##   if $warn_msg;

## $u2k.commit() unless $dryrun;

def get_undervisningsenheter():
    # TODO: Dumpe alle unervisningsenheter til fil
    for enhet in fs.GetUndervEnhetAll()[1]:
        # Prefikser alle nøkler i %UndervEnhet som stammer fra
        # undervisningsenheter med "kurs:".
        enhet_id = "kurs:%s:%s:%s:%s:%s:%s" % (
            enhet['institusjonsnr'], enhet['emnekode'],
            enhet['versjonskode'], enhet['terminkode'],
            enhet['arstall'], enhet['terminnr'])
        if UndervEnhet.has_key(enhet_id):
            raise ValueError, "Duplikat undervisningsenhet: <%s>" % enhet_id
        UndervEnhet[enhet_id] = {'aktivitet': {}}
        multi_id = "%s.%s.%s.%s" % (enhet['institusjonsnr'], enhet['emnekode'],
                                    enhet['terminkode'], enhet['arstall'])
        # Finnes det flere enn en undervisningsenhet tilknyttet denne
        # emnekoden i inneværende semester?
        emne_versjon.setdefault(multi_id, {})[enhet['versjonskode']] = 1
        emne_termnr.setdefault(multi_id, {})[enhet['terminnr']] = 1

def get_undervisningsaktiviteter():
    for akt in fs.GetUndAktivitet()[1]:
        enhet_id = "kurs:%s:%s:%s:%s:%s:%s" % (
            akt['institusjonsnr'], akt['emnekode'],
            akt['versjonskode'], akt['terminkode'],
            akt['arstall'], akt['terminnr'])
        if not UndervEnhet.has_key(enhet_id):
            raise ValueError, "Ikke-eksisterende enhet <%s> har aktiviteter" %\
                  enhet_id
        if UndervEnhet[enhet_id]['aktivitet'].has_key(akt['aktivitetkode']):
            raise ValueError, "Duplikat undervisningsaktivitet <%s:%s>" % (
                enhet_id, akt['aktivitetkode'])
        UndervEnhet[enhet_id][
            'aktivitet'][akt['aktivitetkode']] = akt['aktivitetsnavn']

def get_evukurs_aktiviteter():
    for kurs in fs.GetEvuKurs()[1]:
        kurs_id = "evu:%s:%s" % (kurs['etterutdkurskode'],
                                 kurs['kurstidsangivelsekode'])
        UndervEnhet[kurs_id] = {}
        for aktivitet in fs.GetAktivitetEvuKurs(
            kurs['etterutdkurskode'], kurs['kurstidsangivelsekode'])[1]:
            UndervEnhet[kurs_id].setdefault('aktivitet', {})[
                aktivitet['aktivitetskode']] = aktivitet['aktivitetsnavn']
        tmp = {}
        for evuansv in fs.GetAnsvEvuKurs(kurs['etterutdkurskode'],
                                         kurs['kurstidsangivelsekode'])[1]:
            fnr = "%06d%05d" % (
                int(evuansv['fodselsdato']), int(evuansv['personnr']))
            if fnr2account_id.has_key(fnr):
                tmp[fnr2account_id[fnr]] = 1
        UndervEnhet[kurs_id]['fagansv'] = tmp.copy()
        tmp = {}
        for student in fs.GetStudEvuKurs(kurs['etterutdkurskode'],
                                         kurs['kurstidsangivelsekode'])[1]:
            fnr = "%06d%05d" % (
                int(student['fodselsdato']), int(student['personnr']))
            if fnr2account_id.has_key(fnr):
                tmp[fnr2account_id[fnr]] = 1
        UndervEnhet[kurs_id]['students'] = tmp.copy()

def get_evu_ansv(kurskode, tidsrom):
    kurs_id = "evu:%s:%s" % (kurskode, tidsrom)
    return UndervEnhet[kurs_id]['fagansv']

def get_evu_students(kurskode, tidsrom):
    kurs_id = "evu:%s:%s" % (kurskode, tidsrom)
    return UndervEnhet[kurs_id]['students']

def populate_enhet_groups(enhet_id):
    type_id = enhet_id.split(":")
    type = type_id.pop(0).lower()

    if type == 'kurs':
        Instnr, emnekode, versjon, termk, aar, termnr = type_id

        # Finnes det mer enn en undervisningsenhet knyttet til dette
        # emnet, kun forskjellig på versjonskode og/eller terminnr?  I
        # så fall bør gruppene få beskrivelser som gjør det mulig å
        # knytte dem til riktig undervisningsenhet.
        multi_enhet = []
        multi_id = "%s:%s:%s:%s" % (Instnr, emnekode, termk, aar)
        if emne_termnr.get(multi_id, {}).keys() > 1:
            multi_enhet.append("%s. termin" % termnr)
        if emne_versjon.get(multi_id, {}).keys() > 1:
            multi_enhet.append("v%s" % versjon)
        if multi_enhet:
            enhet_suffix = ", %s" % ", ".join(multi_enhet)
        else:
            enhet_suffix = ""
        logger.debug("Oppdaterer grupper for %s %s %s%s:" % (
            emnekode, termk, aar, enhet_suffix))

        #
        # Ansvarlige for undervisningsenheten.
        logger.debug(" enhetsansvar")
        enhet_ansv = {}
        for account_id in fnrs2account_ids(
            fs.GetAnsvUndervEnhet(Instnr, emnekode, versjon, termk,
                                  aar, termnr)[1]):
            enhet_ansv[account_id] = 1

        # Finnes kurs som går over mer enn et semester, samtidig som
        # at kurset/emnet starter hvert semester.  Utvider strukturen
        # til å ta høyde for at det til enhver tid kan finnes flere
        # kurs av samme type til en hver tid.
        kurs_id = FronterUtils.UE2KursID('kurs', Instnr, emnekode,
                                         versjon, termk, aar, termnr)

        # Også supergruppene til undervisningsenhet - og
        # -aktivitets-avledede grupper skal ha "kurs:"-prefiks.
        sync_group(kurs_id, "%s:enhetsansvar" % enhet_id,
                   "Ansvarlige %s %s %s%s" % (emnekode, termk,
                                              aar, enhet_suffix),
                   co.entity_account, enhet_ansv);
        #
        # Alle nåværende undervisningsmeldte samt nåværende+fremtidige
        # eksamensmeldte studenter.
        logger.debug(" student")
        alle_stud = {}
        for account_id in fnrs2account_ids(
            fs.GetStudUndervEnhet(Instnr, emnekode, versjon, termk,
                                  aar, termnr)[1]):
            alle_stud[account_id] = 1

        sync_group(kurs_id, "%s:student" % enhet_id,
                   "Studenter %s %s %s%s" % (emnekode, termk,
                                             aar, enhet_suffix),
                   co.entity_account, alle_stud);

        for aktkode in UndervEnhet[enhet_id].get('aktivitet', {}).keys():
            #
            # Ansvarlige for denne undervisningsaktiviteten.
            logger.debug(" aktivitetsansvar:%s" % aktkode)
            akt_ansv = {}
            for account_id in fnrs2account_ids(
                fs.GetAnsvUndAktivitet(Instnr, emnekode, versjon, termk,
                                       aar, termnr, aktkode)[1]):
                akt_ansv[account_id] = 1

            sync_group(kurs_id, "%s:aktivitetsansvar:%s" % (enhet_id, aktkode),
                       "Ansvarlige %s %s %s%s %s" % (
                emnekode, termk, aar, enhet_suffix,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, akt_ansv);

            # Studenter meldt på denne undervisningsaktiviteten.
            logger.debug(" student:%s" % aktkode)
            akt_stud = {}
            for account_id in fnrs2account_ids(
                fs.GetStudUndAktivitet(Instnr, emnekode, versjon, termk,
                                       aar, termnr, aktkode)[1]):
                if not alle_stud.has_key(account_id):
                    logger.warn("""OBS: Bruker <%s> (fnr <%s>) er med i undaktivitet <%s>, men ikke i undervisningsenhet <%s>.\n""" % (
                        account_id, account_id2fnr[account_id],
                        "%s:%s" % (enhet_id, aktkode), enhet_id))
                akt_stud[account_id] = 1

            sync_group(kurs_id, "%s:student:%s" % (enhet_id, aktkode),
                       "Studenter %s %s %s%s %s" % (
                emnekode, termk, aar, enhet_suffix,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, akt_stud)

    elif type == 'evu':
        kurskode, tidsrom = type_id
        kurs_id = FronterUtils.UE2KursID("evu", kurskode, tidsrom)
        logger.debug("Oppdaterer grupper for %s: " % enhet_id)
        #
        # Ansvarlige for EVU-kurset
        logger.debug(" evuAnsvar")
        evuans = get_evu_ansv(kurskode, tidsrom)
        sync_group(kurs_id, "%s:enhetsansvar" % enhet_id,
                   "Ansvarlige EVU-kurs %s, %s" % (kurskode, tidsrom),
                   co.entity_account, evuans)
        #
        # Alle påmeldte studenter
        logger.debug(" evuStudenter")
        evustud = get_evu_students(kurskode, tidsrom)
        sync_group(kurs_id, "%s:student" % enhet_id,
                   "Studenter EVU-kurs %s, %s" % (kurskode, tidsrom),
                   co.entity_account, evustud)

        for aktkode in UndervEnhet[enhet_id].get('aktivitet', {}).keys():
            #
            # Ansvarlige for kursaktivitet
            logger.debug(" aktivitetsansvar:%s" % aktkode)
            evu_akt_ansv = {}
            for account_id in fnrs2account_ids(
                fs.GetAnsvEvuAktivitet(kurskode, tidsrom, aktkode)[1]):
                evu_akt_ansv[account_id] = 1

            sync_group(kurs_id, "%s:aktivitetsansvar:%s" % (enhet_id, aktkode),
                       "Ansvarlige EVU-kurs %s, %s: %s" % (
                kurskode, tidsrom,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, evu_akt_ansv)

            # Studenter til denne kursaktiviteten
            logger.debug(" student:%s" % aktkode)
            evu_akt_stud = {}
            for account_id in fnrs2account_ids(
                fs.GetStudEvuAktivitet(kurskode, tidsrom, aktkode)[1]):
                if not evustud.has_key(account_id):
                    logger.warn("""OBS: Bruker <%s> (fnr <%s>) er med i aktivitet <%s>, men ikke i kurset <%s>.""" % (
                        account_id, account_id2fnr[account_id],
                        "%s:%s" % (enhet_id, aktkode), enhet_id))
                evu_akt_stud[account_id] = 1
            sync_group(kurs_id, "%s:student:%s" % (enhet_id, aktkode),
                       "Studenter EVU-kurs %s, %s: %s" % (
                kurskode, tidsrom,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, evu_akt_stud)
    logger.debug(" done")


def sync_group(affil, gname, descr, mtype, memb):
    logger.debug("sync_group(%s; %s; %s; %s; %s" % (affil, gname, descr, mtype, memb))
    if mtype == co.entity_group:   # memb has group_name as keys
        members = {}
        for tmp_gname in memb.keys():
            grp = get_group(tmp_gname)
            members[grp.entity_id] = 1
    else:                          # memb has account_id as keys
        members = memb.copy()
    gname = mkgname(gname, 'uio.no:fs:')
    correct_visib = co.group_visibility_none
    if (affil is None or               # Nivå 0; $gname er supergruppen
        affil == fs_supergroup or         # $gname er på nivå 1
        re.search(r'^(evu|kurs):[^:]+$', affil, re.I)): # $gname er på nivå 2
        # Grupper så langt oppe i strukturen skal være rent interne;
        # de brukes kun til kontroll av hierarki og eksport.
        gname = mkgname(gname)
        correct_visib = co.group_visibility_internal
    if affil is not None:
        AffiliatedGroups.setdefault(affil, {})[gname] = 1
    known_FS_groups[gname] = 1

    # Gjør objektet $Group klar til å modifisere gruppen med navn
    # $gname.
    try:
        group = get_group(gname)
        # Dersom gruppen $gname fantes, er $gr nå en peker til samme
        # objekt som $Group; i motsatt fall er $gr false.
        if group.visibility != correct_visib:
            logger.fatal("Group <%s> has wrong visibility." % gname)

        if group.description != descr:
            group.description = descr
            group.write_db()

        u, i, d = group.list_members(member_type=mtype)
        for member in u:
            member = member[1]      # member_id has index=1 (poor API design?)
            if members.has_key(member):
                del(members[member])
            else:
                group.remove_member(member, co.group_memberop_union)
                #
                # Supergroups will only contain groups that have been
                # automatically created by this script, hence it is
                # safe to automatically destroy groups that are no
                # longer member of their supergroup.

                if (mtype == co.entity_group and
                    correct_visib == co.group_visibility_internal and
                    (not known_FS_groups.has_key(member))):
                    destroy_group(member, 2)
    except Errors.NotFoundError:
        group = Factory.get('Group')(db)
        group.clear()
        group.populate(group_creator, correct_visib, gname, description=descr)
        group.write_db()

    for member in members.keys():
        group.add_member(member, mtype, co.group_memberop_union)

def destroy_group(gname, max_recurse):
    gr = get_group(gname)
    u, i, d = gr.list_members(member_type=co.entity_group)
    for subg in u:
        destroy_group(subg['entity_id'], max_recurse - 1)
    gr.delete()

def get_group(name):
    gr = Factory.get('Group')(db)
    gr.find_by_name(name)
    return gr

def get_account(name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    return ac

def mkgname(id, prefix='internal:'):
    if id[0:len(prefix)] == prefix:
        return id.lower()
    return ("%s%s" % (prefix, id)).lower()

def usage(exitcode=0):
    print """Usage: [optons]
    --db-user name: connect with given database username
    --db-service name: connect to given database"""
    sys.exit(exitcode)

def main():
    global fs, db, co, logger, emne_versjon, emne_termnr, \
           account_id2fnr, fnr2account_id, AffiliatedGroups, \
           known_FS_groups, fs_supergroup, group_creator, UndervEnhet
    try:
        opts, args = getopt.getopt(sys.argv[1:], "",
                                   ["db-user=", "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    db_user = None         # TBD: cereconf value?
    db_service = None      # TBD: cereconf value?
    for o, val in opts:
        if o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
    fs = FS(user = db_user, database = db_service)

    db = Factory.get('Database')()
    db.cl_init(change_program='CF_gen_groups')
    co = Factory.get('Constants')(db)
    logger = Logging.getLogger("console")
    emne_versjon = {}
    emne_termnr = {}
    account_id2fnr = {}
    fnr2account_id = {}
    AffiliatedGroups = {}
    known_FS_groups = {}
    UndervEnhet = {}

    fs_supergroup = "{supergroup}"
    group_creator = get_account(cereconf.INITIAL_ACCOUNTNAME).entity_id
    process_kursdata()
    logger.debug("commit...")
    db.commit()
    logger.info("All done")

if __name__ == '__main__':
    main()
