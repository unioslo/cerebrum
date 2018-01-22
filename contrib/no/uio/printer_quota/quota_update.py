#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004-2018 University of Oslo, Norway
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

"""Tildeler og oppdaterer kvoter iht. til retningslinjer-SFA.txt.

Foreløbig kan denne kun kjøres som en større batch-jobb som oppdaterer alle
personer.

Noen definisjoner:
- kopiavgift_fritak fritak fra å betale selve kopiavgiften
- betaling_fritak fritak for å betale for den enkelte utskrift

"""

import getopt
import mx
import sys
import time

import cerebrum_path
import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.printer_quota import bofhd_pq_utils
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import PPQUtil
from Cerebrum.modules.no.uio.AutoStud.StudentInfo import GeneralDataParser
from Cerebrum.modules.xmlutils.system2parser import system2parser

db = Factory.get('Database')()
update_program = 'quota_update'
ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)
pu = PPQUtil.PPQUtil(db)
const = Factory.get('Constants')(db)
processed_person = {}
person = Person.Person(db)
logger = Factory.get_logger("cronjob")
pq_logger = bofhd_pq_utils.SimpleLogger('pq_bofhd.log')
processed_pids = {}
utv_quota = 250
utv_person = {}

# term_init_mask brukes til å identifisere de kvotetildelinger som har
# skjedde i dette semesteret.  Den definerer også tidspunktet da
# forrige-semesters gratis-kvote nulles, og ny initiell kvote
# tildeles.

# All PQ_DATES has the format month, day.  Date is inclusive

require_kopipenger = True
term_init_prefix = PPQUtil.get_term_init_prefix(*time.localtime()[0:3])
require_kopipenger = not PPQUtil.is_free_period(*time.localtime()[0:3])


def set_quota(person_id, has_quota=False, has_blocked_quota=False,
              quota=None):
    logger.debug("set_quota(%i, has=%i, blocked=%i)" % (
        person_id, has_quota, has_blocked_quota))
    processed_pids[int(person_id)] = True
    if quota is None:
        quota = []
    # Opprett pquota_status entry m/riktige has_*quota settinger
    try:
        ppq_info = ppq.find(person_id)
        new_has = has_quota and 'T' or 'F'
        new_blocked = has_blocked_quota and 'T' or 'F'
        if ppq_info['has_quota'] != new_has:
            ppq.set_status_attr(person_id, {'has_quota': has_quota})
            pq_logger.info("set has_quota=%i for %i" % (has_quota, person_id))
        if ppq_info['has_blocked_quota'] != new_blocked:
            ppq.set_status_attr(
                person_id,
                {'has_blocked_quota': has_blocked_quota}
            )
            pq_logger.info("set has_blocked_quota=%i for %i" % (
                has_blocked_quota, person_id))
    except Errors.NotFoundError:
        ppq_info = {'max_quota': None,
                    'weekly_quota': None}
        ppq.new_quota(person_id, has_quota=has_quota,
                      has_blocked_quota=has_blocked_quota)
        pq_logger.info("new empty quota for %i" % person_id)

    if not has_quota or has_blocked_quota:
        logger.debug("skipping quota calculation for %i" % person_id)
        db.commit()
        return

    # Tildel default kvote for dette semesteret
    if 'default' not in free_this_term.get(person_id, []):
        logger.debug("grant %s for %i" % ('default', person_id))
        pq_logger.info("set initial %s=%i for %i" % (
            'default',
            int(autostud.pc.default_values['print_start']),
            person_id)
        )
        pu.set_free_pages(person_id,
                          int(autostud.pc.default_values['print_start']),
                          '%s%s' % (term_init_prefix, 'default'),
                          update_program=update_program,
                          force=True)

    # Tildele eventuelle utvidede fri-kvoter jmf. 2.2 og 2.3
    for uq in utv_person.get(person_id, []):
        if uq not in free_this_term.get(person_id, []):
            logger.debug("grant %s for %i" % (uq, person_id))
            pq_logger.info("set initial %s=%i for %i" % (
                uq, utv_quota, person_id))
            pu.add_free_pages(person_id,
                              utv_quota,
                              '%s%s' % (term_init_prefix, uq),
                              update_program=update_program)

    # Determine and set new quota, filtering out any initial quotas
    # granted previously this term.
    new_weekly = None
    new_max = None
    for q in quota:
        for quota_type in ('start', 'free_akk'):
            if q.get(quota_type, 0) > 0:
                qid = "%s:%s" % (q['id'], quota_type)
                if qid not in free_this_term.get(person_id, []):
                    logger.debug("grant %s for %i" % (qid, person_id))
                    pageunits_accum = increment = 0
                    if quota_type == 'start':
                        increment = q[quota_type]
                    else:
                        pageunits_accum = q[quota_type]
                    pu.add_free_pages(person_id,
                                      increment,
                                      '%s%s' % (term_init_prefix, qid),
                                      pageunits_accum=pageunits_accum,
                                      update_program=update_program)
                    pq_logger.info("grant %s=%i for %i" % (
                        qid, q[quota_type], person_id))
        if 'weekly' in q:
            new_weekly = (new_weekly or 0) + q['weekly']
        if 'max' in q:
            new_max = (new_max or 0) + q['max']
    if new_weekly != ppq_info['weekly_quota']:
        ppq.set_status_attr(person_id, {'weekly_quota': new_weekly})
        pq_logger.info("set weekly_quota=%i for %i" % (new_weekly, person_id))
    if new_max != ppq_info['max_quota']:
        ppq.set_status_attr(person_id, {'max_quota': new_max})
        pq_logger.info("set max_quota=%i for %i" % (new_max, person_id))
    db.commit()


def recalc_quota_callback(person_info):
    # Kun kvoteverdier styres av studconfig.xml.  De øvrige
    # parameterene er for komplekse til å kunne uttrykkes der uten å
    # introdusere nye tag'er.
    person_id = person_info.get('person_id', None)
    logger.set_indent(0)
    if person_id is None:
        try:
            fnr = fodselsnr.personnr_ok("%06d%05d" % (
                int(person_info['fodselsdato']),
                int(person_info['personnr'])
            ))
        except InvalidFnrError:
            logger.warn('Invalid FNR detected')
        if fnr not in fnr2pid:
            logger.warn("fnr %s is an unknown person" % fnr)
            return
        person_id = fnr2pid[fnr]
    processed_person[person_id] = True
    logger.debug("callback for %s" % person_id)
    logger.set_indent(3)

    # Sjekk at personen er underlagt kvoteregimet
    if person_id not in quota_victims:
        logger.debug("not a quota victim %s" % person_id)
        logger.set_indent(0)
        # assert that person does _not_ have quota
        set_quota(person_id, has_quota=False)
        return

    # Sjekk matching mot studconfig.xml
    quota = None
    try:
        profile = autostud.get_profile(
            person_info,
            member_groups=person_id_member.get(
                person_id,
                []
            ),
            person_affs=person_id_affs.get(
                person_id,
                []
            )
        )
        quota = profile.get_pquota(as_list=True)
    except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
        # A common situation, so we won't log it
        profile = None
    except Errors.NotFoundError, msg:
        logger.warn("(person) not found error for %s: %s" % (person_id, msg))
        profile = None
    # Blokker de som ikke har betalt/ikke har kopiavgift-fritak
    if (
            require_kopipenger and
            not har_betalt.get(person_id, False) and
            not kopiavgift_fritak.get(person_id, False) and
            not (profile and profile.get_printer_kopiavgift_fritak())
    ):
        logger.debug("block %s (bet=%i, fritak=%i)" % (
            person_id, har_betalt.get(person_id, False),
            kopiavgift_fritak.get(person_id, False)))
        set_quota(person_id, has_quota=True, has_blocked_quota=True)
        logger.set_indent(0)
        return

    # Har fritak fra kvote
    if (
            person_id in betaling_fritak or
            profile and profile.get_printer_betaling_fritak()
    ):
        logger.debug("%s is exempt from quota", person_id)
        set_quota(person_id, has_quota=False)
        logger.set_indent(0)
        return

    set_quota(person_id, has_quota=True, has_blocked_quota=False, quota=quota)
    logger.set_indent(0)


def get_bet_fritak_utv_data(sysname, person_file):
    """Finn pc-stuevakter/gruppelærere mfl. ved å parse SAP-dumpen."""
    ret = {}
    sap_ansattnr2pid = {}
    roller_fritak = cereconf.PQUOTA_ROLLER_FRITAK

    for p in person.list_external_ids(source_system=const.system_sap,
                                      id_type=const.externalid_sap_ansattnr):
        sap_ansattnr2pid[p['external_id']] = int(p['entity_id'])

    # Parse person file
    parser = system2parser(sysname)(person_file, logger, False)
    for pers in parser.iter_person():
        sap_nr = pers.get_id(pers.SAP_NR)
        for employment in pers.iteremployment():
            if (
                    employment.is_guest() and employment.is_active() and
                    employment.code in roller_fritak
            ):
                if sap_nr not in sap_ansattnr2pid:
                    logger.warn(
                        "Unknown person from %s %s" % (sysname, sap_nr)
                    )
                    continue
                ret[sap_ansattnr2pid[sap_nr]] = True
    return ret


def get_students():
    """Finner studenter iht. 0.1"""
    ret = []
    tmp_gyldige = {}
    tmp_slettede = {}

    now = mx.DateTime.now()
    # Alle personer med student affiliation
    for row in person.list_affiliations(include_deleted=True, fetchall=False):
        aff = (int(row['affiliation']), int(row['status']))
        slettet = row['deleted_date'] and row['deleted_date'] < now
        if slettet:
            tmp_slettede.setdefault(int(row['person_id']), []).append(aff)
        else:
            tmp_gyldige.setdefault(int(row['person_id']), []).append(aff)

    logger.debug("listed all affilations, calculating")
    # we don't use this anymore. keeping it just in case some similar
    # requirement occurs
    #
    # fritak_tilknyttet = (int(const.affiliation_tilknyttet_pcvakt),
    #                     int(const.affiliation_tilknyttet_grlaerer),
    #                     int(const.affiliation_tilknyttet_bilag))
    logger.debug2("Gyldige: %s" % str(tmp_gyldige))
    for pid in tmp_gyldige.keys():
        if (
                int(const.affiliation_student),
                int(const.affiliation_status_student_aktiv)
        ) in tmp_gyldige[pid]:
            # Har minst en gyldig STUDENT/aktiv affiliation
            ret.append(pid)
            logger.debug2("%i: STUDENT/aktiv" % pid)
            continue
        elif [x for x in tmp_gyldige[pid]
              if x[0] == int(const.affiliation_student)]:
            # Har en gyldig STUDENT affiliation (!= aktiv)
            if not [x for x in tmp_gyldige[pid] if not (
                    x[0] == int(const.affiliation_student)
            )]:
                # ... og ingen gyldige ikke-student affiliations
                ret.append(pid)
                logger.debug2("%i: stud-aff and no non-studaff" % pid)
                continue

    logger.debug2("Slettede: %s" % str(tmp_slettede))
    for pid in tmp_slettede.keys():
        if pid in tmp_gyldige:
            continue
        if [x for x in tmp_slettede[pid] if x[0] == int(
                const.affiliation_student
        )]:
            # Har en slettet STUDENT/* affiliation, og ingen ikke-slettede
            ret.append(pid)

    logger.debug("person.list_affiliations -> %i quota_victims" % len(ret))
    logger.debug("Victims: %s" % ret)
    return ret


def fetch_data(drgrad_file, fritak_kopiavg_file, betalt_papir_file,
               sysname, person_file):
    """Finner alle personer som rammes av kvoteordningen ved å:

    - finne alle som har en student-affiliation (0.1)
    - ta bort ansatte (1.2.1)
    - ta bort dr-grads stipendiater (1.2.2)

    I.e. vi fjerner alle som har fullstendig fritak fra ordningen.  De
    som kun har fritak fra kopiavgiften er ikke fjernet.

    Finner alle gruppe-medlemskap, enten via person eller account for
    de som rammes av ordningen.

    Finner fritak fra kopiavgift (1.2.3 og 1.2.4)
    """

    logger.debug("Prefetching data")

    betaling_fritak = get_bet_fritak_utv_data(sysname, person_file)
    logger.debug2("Fritak for: %s" % betaling_fritak)
    # Finn alle som skal rammes av kvoteregimet
    quota_victim = {}

    for pid in get_students():
        quota_victim[pid] = True

    # Ta bort de som ikke har konto
    account = Account.Account(db)
    account_id2pid = {}
    has_account = {}
    for row in account.list_accounts_by_type(fetchall=False):
        account_id2pid[int(row['account_id'])] = int(row['person_id'])
        has_account[int(row['person_id'])] = True
    for p_id in quota_victim.keys():
        if p_id not in has_account:
            del(quota_victim[p_id])
    logger.debug("after removing non-account people: %i" % len(quota_victim))

    # Ansatte har fritak
    # TODO: sparer litt ytelse ved å gjøre dette i get_students()
    for row in person.list_affiliations(
            affiliation=const.affiliation_ansatt,
            status=(const.affiliation_status_ansatt_bil,
                    const.affiliation_status_ansatt_vit,
                    const.affiliation_status_ansatt_tekadm,),
            source_system=const.system_sap,
            include_deleted=False, fetchall=False
    ):
        if int(row['person_id']) in quota_victim:
            del(quota_victim[int(row['person_id'])])
    logger.debug("removed employees: %i" % len(quota_victim))

    # Alle personer som har disse typer tilknyttet affiliation skal ha fritak
    for row in person.list_affiliations(
            affiliation=const.affiliation_tilknyttet,
            status=(const.affiliation_tilknyttet_bilag,
                    const.affiliation_tilknyttet_ekst_forsker,
                    const.affiliation_tilknyttet_gjesteforsker,
                    const.affiliation_tilknyttet_innkjoper,),
            source_system=const.system_sap,
            include_deleted=False, fetchall=False
    ):
        if int(row['person_id']) in quota_victim:
            del(quota_victim[int(row['person_id'])])
    logger.debug("removed tilknyttet people: %i" % len(quota_victim))

    # Mappe fødselsnummer til person-id
    fnr2pid = {}
    for p in person.list_external_ids(source_system=const.system_fs,
                                      id_type=const.externalid_fodselsnr):
        fnr2pid[p['external_id']] = int(p['entity_id'])

    # Dr.grads studenter har fritak
    for row in GeneralDataParser(drgrad_file, "drgrad"):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(row['fodselsdato']),
                                                  int(row['personnr'])))
        pid = fnr2pid.get(fnr, None)
        if not pid:
            continue
        if pid in quota_victim:
            del(quota_victim[pid])
    logger.debug("removed drgrad: %i" % len(quota_victim))

    # map person-id til gruppemedlemskap.  Hvis gruppe-medlemet er av
    # typen konto henter vi ut owner_id.
    person_id_member = {}
    group = Group.Group(db)
    count = [0, 0]
    groups = autostud.pc.group_defs.keys()
    logger.debug("Finding members in %s" % groups)
    for g in groups:
        group.clear()
        group.find(g)
        for m in set([int(row["member_id"]) for row in
                      group.search_members(group_id=group.entity_id,
                                           indirect_members=True,
                                           member_type=const.entity_account)]):
            if m in account_id2pid:
                person_id_member.setdefault(account_id2pid[m], []).append(g)
                count[0] += 1
            else:
                person_id_member.setdefault(m, []).append(g)
                count[1] += 1
    logger.debug("memberships: persons:%i, p_m=%i, a_m=%i" % (
        len(person_id_member), count[1], count[0]))

    # Fetch any affiliations used as select criteria
    person_id_affs = {}
    for sm in autostud.pc.select_tool.select_map_defs.values():
        if not isinstance(sm, AutoStud.Select.SelectMapPersonAffiliation):
            continue
        for aff_attrs in sm._select_map.keys():
            affiliation = aff_attrs[0]
            for row in person.list_affiliations(
                affiliation=affiliation, include_deleted=False,
                fetchall=False
            ):
                person_id_affs.setdefault(int(row['person_id']), []).append(
                    (int(row['ou_id']),
                     int(row['affiliation']),
                     int(row['status'])))

    # fritak fra selve kopiavgiften (1.2.3 og 1.2.4)
    kopiavgift_fritak = {}
    for row in GeneralDataParser(fritak_kopiavg_file, "betfritak"):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(row['fodselsdato']),
                                                  int(row['personnr'])))
        pid = fnr2pid.get(fnr, None)
        if not pid:
            continue
        kopiavgift_fritak[pid] = True
    logger.debug("%i personer har kopiavgiftsfritak" % len(kopiavgift_fritak))

    # De som har betalt kopiavgiften
    har_betalt = {}
    for row in GeneralDataParser(betalt_papir_file, "betalt"):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(row['fodselsdato']),
                                                  int(row['personnr'])))
        pid = fnr2pid.get(fnr, None)
        if not pid:
            continue
        har_betalt[pid] = True
    logger.debug("%i personer har betalt kopiavgift" % len(har_betalt))

    # Hent gratis-tildelinger hittil i år
    free_this_term = {}
    for row in ppq.get_history_payments(
        transaction_type=const.pqtt_quota_fill_free,
        desc_mask=term_init_prefix+'%%'
    ):
        free_this_term.setdefault(int(row['person_id']), []).append(
            row['description'][len(term_init_prefix):])
    logger.debug("free_this_term: %i" % len(free_this_term))

    logger.debug("Prefetch returned %i students" % len(quota_victim))
    n = 0
    for pid in betaling_fritak.keys():
        if pid in quota_victim:
            n += 1
    logger.debug("%i av disse har betaling_fritak" % n)
    return (fnr2pid, quota_victim, person_id_member, person_id_affs,
            kopiavgift_fritak, har_betalt, free_this_term, betaling_fritak)


def auto_stud(studconfig_file, student_info_file, studieprogs_file,
              emne_info_file, drgrad_file, fritak_kopiavg_file,
              betalt_papir_file, sysname, person_file, ou_perspective=None):
    global fnr2pid, quota_victims, person_id_member, person_id_affs, \
        kopiavgift_fritak, har_betalt, free_this_term, autostud, \
        betaling_fritak
    logger.debug("Preparing AutoStud framework")
    autostud = AutoStud.AutoStud(db, logger, debug=False,
                                 cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file,
                                 ou_perspective=ou_perspective)

    # Finne alle personer som skal behandles, deres gruppemedlemskap
    # og evt. fritak fra kopiavgift
    (
        fnr2pid,
        quota_victims,
        person_id_member,
        person_id_affs,
        kopiavgift_fritak,
        har_betalt,
        free_this_term,
        betaling_fritak
    ) = fetch_data(
        drgrad_file,
        fritak_kopiavg_file,
        betalt_papir_file,
        sysname,
        person_file
    )
    logger.debug2("Victims: %s" % quota_victims)
    # Start call-backs via autostud modulen med vanlig
    # merged_persons.xml fil.  Vi har da mulighet til å styre kvoter
    # via de vanlige select kriteriene.  Callback metoden må sjekke
    # mot unntak.

    logger.info("Starting callbacks from %s" % student_info_file)
    autostud.start_student_callbacks(student_info_file,
                                     recalc_quota_callback)

    # For de personer som ikke fikk autostud-callback må vi kalle
    # quota_callback funksjonen selv.
    logger.info("process persons that didn't get callback")
    for p in quota_victims.keys():
        if p not in processed_person:
            recalc_quota_callback({'person_id': p})

    # Turn off quota for anyone that has quota and that we didn't
    # process
    logger.info("Turn off quota for those who still has quota")
    for row in ppq.get_quota_status(has_quota_filter=True):
        if int(row['person_id']) not in processed_pids:
            set_quota(int(row['person_id']), has_quota=False)

# # rogerha 2007-07-16: what is this code? It's buggy and not used so
# # I comment it.
# def process_data():
#     has_processed = {}
#
#     # Alle personer med student-affiliation:
#     for p in fs.getAlleMedStudentAffiliation():
#         person_id = find_person(p['dato'], p['pnr'])
#         handle_quota(person_id, p)
#         has_processed[person_id] = True
#
#     # Alle account som kun har student-affiliations (denne er ment å
#     # ramme de som tidligere har vært studenter, men som har en konto
#     # som ikke er sperret enda).
#     for p in fooBar():
#         person_id = find_person(p['dato'], p['pnr'])
#         if has_processed.has_key(person_id):
#             continue
#         handle_quota(person_id, p)


def main():
    global logger
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'b:e:f:rs:C:D:P:S:', [
            'help', 'student-info-file=', 'emne-info-file=',
            'studie-progs-file=', 'studconfig-file=', 'drgrad-file=',
            'ou-perspective=', 'fritak-kopiavg-file=', 'betalt-papir-file=',
            'person-file='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)

    ou_perspective = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-b', '--betalt-papir-file'):
            betalt_papir_file = val
        elif opt in ('-e', '--emne-info-file'):
            emne_info_file = val
        elif opt in ('-f', '--fritak-kopiavg-file'):
            fritak_kopiavg_file = val
        elif opt in ('-s', '--student-info-file'):
            student_info_file = val
        elif opt in ('-C', '--studconfig-file'):
            studconfig_file = val
        elif opt in ('-D', '--drgrad-file'):
            drgrad_file = val
        elif opt in ('-P', '--person-file'):
            sysname, person_file = val.split(':')
        elif opt in ('-S', '--studie-progs-file'):
            studieprogs_file = val
        elif opt in ('--ou-perspective',):
            ou_perspective = const.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined

    for opt, val in opts:
        if opt in ('-r',):
            auto_stud(studconfig_file, student_info_file,
                      studieprogs_file, emne_info_file, drgrad_file,
                      fritak_kopiavg_file, betalt_papir_file, sysname,
                      person_file, ou_perspective)


def usage(exitcode=0):
    print """Usage: [options]
    -s | --student-info-file file:
    -e | --emne-info-file file:
    -C | --studconfig-file file:
    -P | ---person-file source_system:file:
    -S | --studie-progs-file file:
    -D | --drgrad-file file:
    -f | --fritak-avg-file file:
    -b | --betalt-papir-file:
    -w | --weekly:  run weekly quota update (TODO)
    --ou-perspective perspective:
    -r | --recalc-pq: start quota recalculation

contrib/no/uio/quota_update.py -s /cerebrum/dumps/FS/merged_persons_small.xml -e /cerebrum/dumps/FS/emner.xml -C contrib/no/uio/studconfig.xml -S /cerebrum/dumps/FS/studieprogrammer.xml -D /cerebrum/dumps/FS/drgrad.xml -P system_sap:/cerebrum/dumps/SAP/SAP2BAS/sap2bas_2007-7-16-301.xml -f /cerebrum/dumps/FS/fritak_kopi.xml -b /cerebrum/dumps/FS/betalt_papir.xml -r
"""
    # ./contrib/no/uio/import_from_FS.py --db-user ureg2000 --db-service FSPROD.uio.no --misc-tag drgrad --misc-func GetStudinfDrgrad --misc-file drgrad.xml
    # ./contrib/no/uio/import_from_FS.py --db-user ureg2000 --db-service FSPROD.uio.no --misc-tag betfritak --misc-func GetStudFritattKopiavg --misc-file fritak_kopi.xml
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
