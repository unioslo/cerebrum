#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Tildeler og oppdaterer kvoter iht. til retningslinjer-SFA.txt.
#
# Foreløbig kan denne kun kjøres som en større batch-jobb som
# oppdaterer alle personer.
#
# Noen definisjoner:
# - kopiavgift_fritak fritak fra å betale selve kopiavgiften
# - betaling_fritak fritak for å betale for den enkelte utskrift

import getopt
import os
import sys
import time
import xml.sax

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

db = Factory.get('Database')()
update_program = 'quota_update'
ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)
pu = PPQUtil.PPQUtil(db)
const = Factory.get('Constants')(db)
processed_person = {}
person = Person.Person(db)
pq_logger = bofhd_pq_utils.SimpleLogger('pq_bofhd.log')
processed_pids = {}

# term_init_mask brukes til å identifisere de kvotetildelinger som har
# skjedde i dette semesteret.  Den definerer også tidspunktet da
# forrige-semesters gratis-kvote nulles, og ny initiell kvote
# tildeles.

# All PQ_DATES has the format month, day.  Date is inclusive

require_kopipenger = True
term_init_prefix = PPQUtil.get_term_init_prefix(*time.localtime()[0:3])
require_kopipenger = PPQUtil.is_free_period(*time.localtime()[0:3])

class ThreeLevelDataParser(xml.sax.ContentHandler):
    """General parser for processing files like:

    <data><person><elem1/><elem2/></person></data>, where person is
    group_tag, and elem1 and elem2 are data_tags.  A callback will be
    delivered when closing each group_tag, having a dict of lists as
    argument.  The keys of the dict are from data_tags, and the list
    contains a dict of the attrs in each tag.
    """

    # TODO: Move this method to Util.py (or someplace similar) and add
    # an option to either be an iterator or receive callbacks.
    def __init__(self, filename, callback, group_tag,
                 data_tags, encoding='iso8859-1'):
        self._callback = callback
        self.group_tag = group_tag
        self.data_tags = data_tags
        self._level = 0
        self._encoding = encoding
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        ok = False
        if self._level == 0:
            pass
        elif self._level == 1:
            if name == self.group_tag:
                self._data = {}
                ok = True
        if ok or self._level == 2:
            if ok or name in self.data_tags:
                tmp = {}
                for k in attrs.keys():
                    tmp[k.encode(self._encoding)] = attrs[k].encode(self._encoding)
                self._data.setdefault(name.encode(self._encoding), []).append(tmp)
        self._level += 1

    def endElement(self, name):
        self._level -= 1
        if self._level == 1:
            if name == self.group_tag and len(self._data) > 1:
                self._callback(self._data)

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
            ppq.set_status_attr(person_id, {'has_blocked_quota': has_blocked_quota})
            pq_logger.info("set has_blocked_quota=%i for %i" % (has_quota, person_id))
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
            'default', int(autostud.pc.default_values['print_start']), person_id))
        pu.set_free_pages(person_id,
                          int(autostud.pc.default_values['print_start']),
                          '%s%s' % (term_init_prefix, 'default'),
                          update_program=update_program)

    # Determine and set new quota, filtering out any initial quotas
    # granted previously this term.
    new_weekly = None
    new_max = None
    for q in quota:
        if q.has_key('start'):
            if q['id'] not in free_this_term.get(person_id, []):
                logger.debug("grant %s for %i" % (q['id'], person_id))
                pu.add_free_pages(person_id,
                                  q['start'],
                                  '%s%s' % (term_init_prefix, q['id']),
                                  update_program=update_program)
                pq_logger.info("grant %s=%i for %i" % (
                    q['id'], q['start'], person_id))
        if q.has_key('weekly'):
            new_weekly = (new_weekly or 0) + q['weekly']
        if q.has_key('max'):
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
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))

        if not fnr2pid.has_key(fnr):
            logger.warn("fnr %s is an unknown person" % fnr)
            return
        person_id = fnr2pid[fnr]
    processed_person[person_id] = True
    logger.debug("callback for %s" % person_id)
    logger.set_indent(3)

    # Sjekk at personen er underlagt kvoteregimet
    if not quota_victims.has_key(person_id):
        logger.debug("not a quota victim %s" % person_id)
        logger.set_indent(0)
        # assert that person does _not_ have quota
        set_quota(person_id, has_quota=False)
        return
    
    # Blokker de som ikke har betalt/ikke har kopiavgift-fritak
    if (require_kopipenger and
        not har_betalt.get(person_id, False) and
        not kopiavgift_fritak.get(person_id, False)):
        logger.debug("block %s (bet=%i, fritak=%i)" % (
            person_id, har_betalt.get(person_id, False),
            kopiavgift_fritak.get(person_id, False)))
        set_quota(person_id, has_quota=True, has_blocked_quota=True)
        logger.set_indent(0)
        return

    # Sjekk matching mot studconfig.xml
    quota=None
    try:
        profile = autostud.get_profile(person_info,
                                       member_groups=person_id_member.get(person_id, []))
        quota = profile.get_pquota(as_list=True)
    except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
        # A common situation, so we won't log it
        profile = None
    except Errors.NotFoundError, msg:
        logger.warn("(person) not found error for %s: %s" %  (person_id, msg))
        profile = None
    
    # Har fritak fra kvote
    if (betaling_fritak.has_key(person_id) or 
        profile and profile.get_printer_betaling_fritak()):
        set_quota(person_id, has_quota=False)
        logger.set_indent(0)
        return

    set_quota(person_id, has_quota=True, has_blocked_quota=False, quota=quota)
    logger.set_indent(0)

def get_bet_fritak_data(lt_person_file):
    # Finn pc-stuevakter/gruppelærere mfl. ved å parse LT-dumpen (3.2)
    ret = {}
    fnr2pid = {}
    for p in person.list_external_ids(source_system=const.system_lt,
                                      id_type=const.externalid_fodselsnr):
        fnr2pid[p['external_id']] = int(p['person_id'])
    def lt_callback(data):
        person = data['person'][0]
        fnr = fodselsnr.personnr_ok(
            "%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                                  int(person['fodtar']), int(person['personnr'])))
        for g in data.get('gjest', []):
            if g['gjestetypekode'] in ('PCVAKT', 'GRP-LÆRER', 'ST-POL FRI',
                                       'ST-ORG FRI', 'EF-FORSKER', 'EF-STIP',
                                       'EMERITUS', 'GJ-FORSKER', 'REG-ANSV',
                                       'EKST. KONS', 'SENIORFORS'):
                if not fnr2pid.has_key(fnr):
                    logger.warn("Unknown LT-person %s" % fnr)
                    return
                ret[fnr2pid[fnr]] = True
                return
    ThreeLevelDataParser(lt_person_file, lt_callback, "person", ["gjest"])
    return ret

def get_students():
    """Finner studenter iht. 0.1"""
    
    ret = []
    tmp_gyldige = {}
    tmp_slettede = {}

    now = db.TimestampFromTicks(time.time())
    # Alle personer med student affiliation
    for row in person.list_affiliations(include_deleted=True, fetchall=False):
        aff = (int(row['affiliation']), int(row['status']))
        slettet = row['deleted_date'] and row['deleted_date'] < now
        if slettet:
            tmp_slettede.setdefault(int(row['person_id']), []).append(aff)
        else:
            tmp_gyldige.setdefault(int(row['person_id']), []).append(aff)

    logger.debug("listed all affilations, calculating")

    fritak_tilknyttet = (int(const.affiliation_tilknyttet_pcvakt),
                         int(const.affiliation_tilknyttet_grlaerer),
                         int(const.affiliation_tilknyttet_bilag))
    for pid in tmp_gyldige.keys():
        if [x for x in tmp_gyldige[pid] if x[1] in fritak_tilknyttet]:
            # Fritak via TILKNYTTET affiliation
            continue
        elif (int(const.affiliation_student),
            int(const.affiliation_status_student_aktiv)) in tmp_gyldige[pid]:
            # Har minst en gyldig STUDENT/aktiv affiliation
            ret.append(pid)
            continue
        elif [x for x in tmp_gyldige[pid]
              if x[0] == int(const.affiliation_student)]:
            # Har en gyldig STUDENT affiliation (!= aktiv)
            if not [x for x in tmp_gyldige[pid]
                    if not (x[0] == int(const.affiliation_student) or
                            (x[0] == int(const.affiliation_manuell) and
                             x[1] == int(const.affiliation_manuell_inaktiv_student)))]:
                # ... og ingen gyldige ikke-student affiliations
                ret.append(pid)
                continue

    for pid in tmp_slettede.keys():
        if tmp_gyldige.has_key(pid):
            continue
        if [x for x in tmp_slettede[pid]
              if x[0] == int(const.affiliation_student)]:
            # Har en slettet STUDENT/* affiliation, og ingen ikke-slettede
            ret.append(pid)

    logger.debug("person.list_affiliations -> %i quota_victims" % len(ret))
    return ret

def fetch_data(drgrad_file, fritak_kopiavg_file, betalt_papir_file, lt_person_file):
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

    betaling_fritak = get_bet_fritak_data(lt_person_file)
    logger.debug("Fritak for: %s" % betaling_fritak)
    # Finn alle som skal rammes av kvoteregimet
    quota_victim = {}

    for pid in get_students():
        quota_victim[pid] = True

    # Ta bort de som ikke har konto
    account = Account.Account(db)
    account_id2pid = {}
    has_account = {}
    for row in account.list_accounts_by_type(filter_expired=False, fetchall=False):
        account_id2pid[int(row['account_id'])] = int(row['person_id'])
        has_account[int(row['person_id'])] = True
    for p_id in quota_victim.keys():
        if not has_account.has_key(p_id):
            del(quota_victim[p_id])
    logger.debug("after removing non-account people: %i" % len(quota_victim))

    # Ansatte har fritak
    # TODO: sparer litt ytelse ved å gjøre dette i get_students()
    for row in person.list_affiliations(affiliation=const.affiliation_ansatt,
                                        include_deleted=False, fetchall=False):
        if int(row['status']) not in (
            int(const.affiliation_status_ansatt_vit),
            int(const.affiliation_status_ansatt_tekadm)):
            continue
        if quota_victim.has_key(int(row['person_id'])):
            del(quota_victim[int(row['person_id'])])
    logger.debug("removed employees: %i" % len(quota_victim))

    # Mappe fødselsnummer til person-id
    fnr2pid = {}
    for p in person.list_external_ids(source_system=const.system_fs,
                                      id_type=const.externalid_fodselsnr):
        fnr2pid[p['external_id']] = int(p['person_id'])

    # Dr.grads studenter har fritak
    for row in GeneralDataParser(drgrad_file, "drgrad"):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(row['fodselsdato']),
                                                  int(row['personnr'])))
        pid = fnr2pid.get(fnr, None)
        if not pid:
            continue
        if quota_victim.has_key(pid):
            del(quota_victim[pid])        
    logger.debug("removed drgrad: %i" % len(quota_victim))

    # map person-id til gruppemedlemskap.  Hvis gruppe-medlemet er av
    # typen konto henter vi ut owner_id.
    person_id_member = {}
    group = Group.Group(db)
    count = [0, 0]
    groups = autostud.pc.known_select_criterias['medlem_av_gruppe'].values()
    logger.debug("Finding members in %s" % groups)
    for g in groups:
        group.clear()
        group.find(g)
        for m in group.get_members():
            if account_id2pid.has_key(m):
                person_id_member.setdefault(account_id2pid[m], []).append(g)
                count[0] += 1
            else:
                person_id_member.setdefault(m, []).append(g)
                count[1] += 1
    logger.debug("memberships: persons:%i, p_m=%i, a_m=%i" % (
        len(person_id_member), count[1], count[0]))

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
        desc_mask=term_init_prefix+'%%'):
        free_this_term.setdefault(int(row['person_id']), []).append(
            row['description'][len(term_init_prefix):])
    logger.debug("free_this_term: %i" % len(free_this_term))

    logger.debug("Prefetch returned %i students" % len(quota_victim))
    return fnr2pid, quota_victim, person_id_member, kopiavgift_fritak, \
           har_betalt, free_this_term, betaling_fritak

def auto_stud(studconfig_file, student_info_file, studieprogs_file,
              emne_info_file, drgrad_file, fritak_kopiavg_file,
              betalt_papir_file, lt_person_file, ou_perspective=None):
    global fnr2pid, quota_victims, person_id_member, \
           kopiavgift_fritak, har_betalt, free_this_term, autostud, betaling_fritak
    logger.debug("Preparing AutoStud framework")
    autostud = AutoStud.AutoStud(db, logger, debug=False,
                                 cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file,
                                 ou_perspective=ou_perspective)

    # Finne alle personer som skal behandles, deres gruppemedlemskap
    # og evt. fritak fra kopiavgift
    (fnr2pid, quota_victims, person_id_member, kopiavgift_fritak,
     har_betalt, free_this_term, betaling_fritak) = fetch_data(
        drgrad_file, fritak_kopiavg_file, betalt_papir_file, lt_person_file)
    logger.debug("Victims: %s" % quota_victims)
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
        if not processed_person.has_key(p):
            recalc_quota_callback({'person_id': p})

    # Turn off quota for anyone that has quota and that we didn't
    # process
    logger.info("Turn off quota for those who still has quota")
    for row in ppq.get_quoata_status(has_quota_filter=True):
        if not processed_pids.has_key(int(row['person_id'])):
            set_quota(int(row['person_id']), has_quota=False)

def process_data():
    has_processed = {}
    
    # Alle personer med student-affiliation:
    for p in fs.getAlleMedStudentAffiliation():
        person_id = find_person(p['dato'], p['pnr'])
        handle_quota(person_id, p)
        has_processed[person_id] = True

    # Alle account som kun har student-affiliations (denne er ment å
    # ramme de som tidligere har vært studenter, men som har en konto
    # som ikke er sperret enda).
    for p in fooBar():
        person_id = find_person(p['dato'], p['pnr'])
        if has_processed.has_key(person_id):
            continue
        handle_quota(person_id, p)

def main():
    global logger
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'b:e:f:rs:C:D:L:S:', [
            'help', 'student-info-file=', 'emne-info-file=',
            'studie-progs-file=', 'studconfig-file=', 'drgrad-file=',
            'ou-perspective=', 'fritak-kopiavg-file=', 'betalt-papir-file=',
            'lt-person-file='])
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
        elif opt in ('-L', '--lt-person-file'):
            lt_person_file = val
        elif opt in ('-S', '--studie-progs-file'):
            studieprogs_file = val
        elif opt in ('--ou-perspective',):
            ou_perspective = const.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined

    # TODO: AutoStud framework should be updated to use the standard
    # logging framework.  Then we can also move the extra opts for loop up
    workdir=None
    to_stdout=False
    log_level = AutoStud.Util.ProgressReporter.DEBUG
    if workdir is None:
        workdir = "%s/ps-%s.%i" % (cereconf.AUTOADMIN_LOG_DIR,
                                   time.strftime("%Y-%m-%d", time.localtime()),
                                   os.getpid())
        os.mkdir(workdir)
    logger = AutoStud.Util.ProgressReporter(
        "%s/run.log.%i" % (workdir, os.getpid()), stdout=to_stdout,
        loglevel=log_level)
    for opt, val in opts:
        if opt in ('-r',):
            auto_stud(studconfig_file, student_info_file,
                      studieprogs_file, emne_info_file, drgrad_file,
                      fritak_kopiavg_file, betalt_papir_file, lt_person_file,
                      ou_perspective)

def usage(exitcode=0):
    print """Usage: [options]
    -s | --student-info-file file:
    -e | --emne-info-file file:
    -C | --studconfig-file file:
    -L | --lt-person-file file:
    -S | --studie-progs-file file:
    -D | --drgrad-file file:
    -f | --fritak-avg-file file:
    -b | --betalt-papir-file:
    -w | --weekly:  run weekly quota update (TODO)
    --ou-perspective perspective:
    -r | --recalc-pq: start quota recalculation

contrib/no/uio/quota_update.py -s /cerebrum/dumps/FS/merged_persons_small.xml -e /cerebrum/dumps/FS/emner.xml -C contrib/no/uio/studconfig.xml -S /cerebrum/dumps/FS/studieprogrammer.xml -D /cerebrum/dumps/FS/drgrad.xml -L /cerebrum/dumps/LT/person.xml -f /cerebrum/dumps/FS/fritak_kopi.xml -b /cerebrum/dumps/FS/betalt_papir.xml -r
"""
    # ./contrib/no/uio/import_from_FS.py --db-user ureg2000 --db-service FSPROD.uio.no --misc-tag drgrad --misc-func GetStudinfDrgrad --misc-file drgrad.xml 
    # ./contrib/no/uio/import_from_FS.py --db-user ureg2000 --db-service FSPROD.uio.no --misc-tag betfritak --misc-func GetStudFritattKopiavg --misc-file fritak_kopi.xml
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: e0fc5f99-a3bf-4739-9f8a-be8d46142ed1
