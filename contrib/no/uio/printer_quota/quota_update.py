#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2019 University of Oslo, Norway
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

import functools
import getopt
import sys
from datetime import datetime

import cereconf
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.StudentInfo import GeneralDataParser
from Cerebrum.modules.no.uio.pq_exemption import pq_exemption
from Cerebrum.modules.xmlutils.system2parser import system2parser


db = Factory.get('Database')()
db.cl_init(change_program='quota_update')

pe = Factory.get('Person')(db)
co = Factory.get('Constants')(db)

pq = pq_exemption.PrinterQuotaExemption(db)

logger = Factory.get_logger("cronjob")

processed_pids = {}
processed_person = {}


def set_pq_exempt(person_id, exempt):
    """Set exempt for a person

    Checks if the person has a quota set before and uses the appropriate
    functions to update the database.

    :param int person_id: entity id of person
    :param bool exempt: True if the person has quota, False if not
    :return: None
    """
    processed_pids[int(person_id)] = True
    pq.set(person_id, exempt)
    logger.info("set exempt=%i for %i" % (exempt, person_id))
    db.commit()


def recalc_quota_callback(person_info, fnr2pid, quota_victims,
                          kopiavgift_fritak, betaling_fritak):
    # Kun kvoteverdier styres av studconfig.xml.  De øvrige
    # parameterene er for komplekse til å kunne uttrykkes der uten å
    # introdusere nye tag'er.
    person_id = person_info.get('person_id', None)
    if person_id is None:
        try:
            fnr = fodselsnr.personnr_ok("%06d%05d" % (
                int(person_info['fodselsdato']),
                int(person_info['personnr'])
            ))
        except fodselsnr.InvalidFnrError:
            logger.warn('Invalid FNR detected')
        if fnr not in fnr2pid:
            logger.warn("fnr %r is an unknown person", fnr)
            return
        person_id = fnr2pid[fnr]
    processed_person[person_id] = True
    logger.debug("callback for %r", person_id)

    # Sjekk at personen er underlagt kvoteregimet
    if person_id not in quota_victims:
        logger.debug("not a quota victim %r", person_id)
        # assert that person does _not_ have quota
        set_pq_exempt(person_id, exempt=True)
        return

    # Har fritak fra kvote
    if person_id in betaling_fritak:
        logger.debug("%s is exempt from quota", person_id)
        set_pq_exempt(person_id, exempt=True)
        return

    # Set quota for those without har kopiavgift-fritak
    if person_id not in kopiavgift_fritak:
        logger.debug("block %r (fritak=%r)",
                     person_id,
                     kopiavgift_fritak.get(person_id, False))
        set_pq_exempt(person_id, exempt=False)
        return

    set_pq_exempt(person_id, exempt=False)


def get_bet_fritak_utv_data(sysname, person_file):
    """Finn pc-stuevakter/gruppelærere mfl. ved å parse SAP-dumpen."""
    ret = {}
    sap_ansattnr2pid = {}
    roller_fritak = cereconf.PQUOTA_ROLLER_FRITAK

    for p in pe.search_external_ids(source_system=co.system_sap,
                                    id_type=co.externalid_sap_ansattnr,
                                    fetchall=False):
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
                    logger.warn("Unknown person (%r) from %r", sap_nr, sysname)
                    continue
                ret[sap_ansattnr2pid[sap_nr]] = True
    return ret


def get_students():
    """Finner studenter iht. 0.1"""
    ret = []
    tmp_gyldige = {}
    tmp_slettede = {}

    now = datetime.now()
    # Alle personer med student affiliation
    for row in pe.list_affiliations(include_deleted=True, fetchall=False):
        aff = (int(row['affiliation']), int(row['status']))
        slettet = row['deleted_date'] and row['deleted_date'] < now
        if slettet:
            tmp_slettede.setdefault(int(row['person_id']), []).append(aff)
        else:
            tmp_gyldige.setdefault(int(row['person_id']), []).append(aff)

    logger.debug("listed all affilations, calculating")
    logger.debug("Gyldige: %r", tmp_gyldige)
    for pid in tmp_gyldige.keys():
        if (
                int(co.affiliation_student),
                int(co.affiliation_status_student_aktiv)
        ) in tmp_gyldige[pid]:
            # Har minst en gyldig STUDENT/aktiv affiliation
            ret.append(pid)
            logger.debug("%r: STUDENT/aktiv", pid)
            continue
        elif [x for x in tmp_gyldige[pid]
              if x[0] == int(co.affiliation_student)]:
            # Har en gyldig STUDENT affiliation (!= aktiv)
            if not [x for x in tmp_gyldige[pid] if not (
                    x[0] == int(co.affiliation_student)
            )]:
                # ... og ingen gyldige ikke-student affiliations
                ret.append(pid)
                logger.debug("%r: stud-aff and no non-studaff", pid)
                continue

    logger.debug("Slettede: %r", tmp_slettede)
    for pid in tmp_slettede.keys():
        if pid in tmp_gyldige:
            continue
        if [x for x in tmp_slettede[pid] if x[0] == int(
                co.affiliation_student
        )]:
            # Har en slettet STUDENT/* affiliation, og ingen ikke-slettede
            ret.append(pid)

    logger.debug("person.list_affiliations -> %i quota_victims" % len(ret))
    logger.debug("Victims: %r", ret)
    return ret


def fetch_data(drgrad_file, fritak_kopiavg_file,
               sysname, person_file, autostud):
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
    logger.debug("Fritak for: %r", betaling_fritak)
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
    for row in pe.list_affiliations(
            affiliation=co.affiliation_ansatt,
            status=(co.affiliation_status_ansatt_bil,
                    co.affiliation_status_ansatt_vit,
                    co.affiliation_status_ansatt_tekadm,),
            source_system=co.system_sap,
            include_deleted=False, fetchall=False
    ):
        if int(row['person_id']) in quota_victim:
            del(quota_victim[int(row['person_id'])])
    logger.debug("removed employees: %i" % len(quota_victim))

    # Alle personer som har disse typer tilknyttet affiliation skal ha fritak
    for row in pe.list_affiliations(
            affiliation=co.affiliation_tilknyttet,
            status=(co.affiliation_tilknyttet_bilag,
                    co.affiliation_tilknyttet_ekst_forsker,
                    co.affiliation_tilknyttet_ekst_partner,
                    co.affiliation_tilknyttet_ekst_stip,
                    co.affiliation_tilknyttet_emeritus,
                    co.affiliation_tilknyttet_gjesteforsker,
                    co.affiliation_tilknyttet_innkjoper,),
            source_system=co.system_sap,
            include_deleted=False, fetchall=False
    ):
        if int(row['person_id']) in quota_victim:
            del(quota_victim[int(row['person_id'])])
    logger.debug("removed tilknyttet people: %i" % len(quota_victim))

    # Mappe fødselsnummer til person-id
    fnr2pid = {}
    for p in pe.search_external_ids(source_system=co.system_fs,
                                    id_type=co.externalid_fodselsnr,
                                    fetchall=False):
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
                                           member_type=co.entity_account)]):
            if m in account_id2pid:
                person_id_member.setdefault(account_id2pid[m], []).append(g)
                count[0] += 1
            else:
                person_id_member.setdefault(m, []).append(g)
                count[1] += 1
    logger.debug("memberships: persons:%i, p_m=%i, a_m=%i",
                 len(person_id_member), count[1], count[0])

    # Fetch any affiliations used as select criteria
    person_id_affs = {}
    for sm in autostud.pc.select_tool.select_map_defs.values():
        if not isinstance(sm, AutoStud.Select.SelectMapPersonAffiliation):
            continue
        for aff_attrs in sm._select_map.keys():
            affiliation = aff_attrs[0]
            for row in pe.list_affiliations(
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

    logger.debug("Prefetch returned %i students" % len(quota_victim))
    n = 0
    for pid in betaling_fritak.keys():
        if pid in quota_victim:
            n += 1
    logger.debug("%i av disse har betaling_fritak" % n)
    return (fnr2pid, quota_victim, person_id_member, person_id_affs,
            kopiavgift_fritak, betaling_fritak)


def auto_stud(studconfig_file, student_info_file, studieprogs_file,
              emne_info_file, drgrad_file, fritak_kopiavg_file,
              sysname, person_file, ou_perspective=None):
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
        betaling_fritak
    ) = fetch_data(
        drgrad_file,
        fritak_kopiavg_file,
        sysname,
        person_file,
        autostud
    )
    logger.debug("Victims: %r", quota_victims)
    # Start call-backs via autostud modulen med vanlig
    # merged_persons.xml fil.  Vi har da mulighet til å styre kvoter
    # via de vanlige select kriteriene.  Callback metoden må sjekke
    # mot unntak.

    logger.info("Starting callbacks from %r", student_info_file)
    autostud.start_student_callbacks(
        student_info_file,
        functools.partial(recalc_quota_callback,
                          fnr2pid=fnr2pid,
                          quota_victims=quota_victims,
                          kopiavgift_fritak=kopiavgift_fritak,
                          betaling_fritak=betaling_fritak
                          )
    )

    # For de personer som ikke fikk autostud-callback må vi kalle
    # quota_callback funksjonen selv.
    logger.info("process persons that didn't get callback")
    for p in quota_victims.keys():
        if p not in processed_person:
            recalc_quota_callback(
                {'person_id': p},
                fnr2pid, quota_victims, kopiavgift_fritak,
                betaling_fritak)

    # Turn off quota for anyone that has quota and that we didn't
    # process
    logger.info("Turn off quota for those who still has quota")
    for row in pq.list(only_without_exempt=True):
        if int(row['person_id']) not in processed_pids:
            set_pq_exempt(int(row['person_id']), exempt=True)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'b:e:f:rs:C:D:P:S:', [
            'help', 'student-info-file=', 'emne-info-file=',
            'studie-progs-file=', 'studconfig-file=', 'drgrad-file=',
            'ou-perspective=', 'fritak-kopiavg-file=',
            'person-file='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)

    ou_perspective = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
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
            ou_perspective = co.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined

    for opt, val in opts:
        if opt in ('-r', '--recalc-pq'):
            auto_stud(studconfig_file, student_info_file,
                      studieprogs_file, emne_info_file, drgrad_file,
                      fritak_kopiavg_file, sysname,
                      person_file, ou_perspective)


def usage(exitcode=0):
    print(r"""Usage: [options]
    -s | --student-info-file file:
    -e | --emne-info-file file:
    -C | --studconfig-file file:
    -P | --person-file source_system:file:
    -S | --studie-progs-file file:
    -D | --drgrad-file file:
    -f | --fritak-avg-file file:
    --ou-perspective perspective:
    -r | --recalc-pq: start quota recalculation

contrib/no/uio/quota_update.py \
    -s /cerebrum/dumps/FS/merged_persons_small.xml \
    -e /cerebrum/dumps/FS/emner.xml \
    -C contrib/no/uio/studconfig.xml \
    -S /cerebrum/dumps/FS/studieprogrammer.xml \
    -D /cerebrum/dumps/FS/drgrad.xml \
    -P system_sap:/cerebrum/dumps/SAP/SAP2BAS/sap2bas_2007-7-16-301.xml \
    -f /cerebrum/dumps/FS/fritak_kopi.xml \
    -r
""")
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
