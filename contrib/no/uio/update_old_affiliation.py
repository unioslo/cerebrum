#!/usr/bin/env python2.2

import getopt
import time
import sys
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.Stedkode import Stedkode

"""Lister alle personer som har en affiliation av typen
MANUEL/inaktiv_ansatt eller MANUELL/inaktiv_student.

For hver person gjøres følgende:

  Dersom personen har en aktiv STUDENT/ANSATT affiliation der
  stedkode stemmer omtrentlig, slettes (som i nuke_affiliation) inaktiv
  affiliationen.  Evt. brukere med inaktiv affiliationen oppdateres
  til å peke mot den aktive affiliaitonen med samme priority som den
  tidligere hadde.

  Dersom personen etter dette blir stående med en inaktiv status, og det
  er mindre enn 90 dager siden denne ble satt:  next_person

  Dersom personen ikke har noen brukere med denne affiliationen,
  slettes inaktiv affiliationen.  next_person

  Send mail til brukeren med oppfordring om å kontakte sin LITA for å
  bli korrekt registrert. (TODO)
"""

if True:  # Do not use if database has numeric(X,N) where N > 0
    import psycopg
    def float_to_int(v):
        if v is None:
            return v
        try:
            return int(v)
        except ValueError:
            return long(v)
    MY_INT = psycopg.new_type((1700,), "MY_INT", float_to_int)
    psycopg.register_type(MY_INT)
    cereconf.CLASS_DBDRIVER = ['Cerebrum.Database/PsycoPG']

db = Factory.get('Database')()
db.cl_init(change_program="upd_old_affs")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
sko = Stedkode(db)

person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")
threshold = time.time() - 3600*24*90   # 90 days

aff_mapping = {
    int(co.affiliation_manuell_inaktiv_ansatt): int(co.affiliation_ansatt),
    int(co.affiliation_manuell_inaktiv_student): int(co.affiliation_student)
    }

sko_cache = {}
def map_sko(ou_id):
    if not sko_cache.has_key(ou_id):
        sko.clear()
        sko.find(ou_id)
        sko_cache[ou_id] = "%02d%02d%02d (%i)" % (
            sko.fakultet, sko.institutt, sko.avdeling, ou_id)
    return sko_cache[ou_id] 

def map_aff(ou_id, old_status, tgt_aff, person_affs):
    """Gå gjennom OU'ene den gamle statusen var knyttet til, og
    returner status, ou_id, create_date, src_sys for den som matcher
    best.  For to stedkoder som matcher like godt, returneres den vi
    fant først."""
    
    old_sko = map_sko(ou_id)
    for sko_level in (6, 4, 2):
        for status, ou_id, create_date, deleted_date, src_sys in \
                person_affs.get(tgt_aff, []):
            if old_sko[0:sko_level] == map_sko(ou_id)[0:sko_level]:
                return status, ou_id, create_date, src_sys
    return None

def prefetch_affiliations():
    all_person_affs = {}
    # For alle personer m/affiliations av typen:
    # - STUDENT/*, ANSATT/*, MANUELL/inaktiv_ansatt, MANUELL/inaktiv_student
    # Bygg opp mappingen
    # {person_id:
    #    {affiliation: {
    #        affiliation_status: [[ou_id, create_date, deleted_date,
    #                              source_system]]}}}
    for aff, aff_status in (
        (co.affiliation_manuell, co.affiliation_manuell_inaktiv_student),
        (co.affiliation_manuell, co.affiliation_manuell_inaktiv_ansatt),
        (co.affiliation_ansatt, None),
        (co.affiliation_student, None)):
        for row in person.list_affiliations(
            affiliation=aff, status=aff_status,
            include_deleted=True):
            all_person_affs.setdefault(int(row['person_id']), {}).setdefault(
                int(row['affiliation']), []).append([
                int(row['status']), int(row['ou_id']),
                row['create_date'], row['deleted_date'], row['source_system']])

    manuell_account_affs = {}
    # For alle konto med manuell_inaktiv_* status, bygg mappingen:
    # {owner_id: {account_id: [ou, pri]}}
    for aff, aff_status in (
        (co.affiliation_manuell, co.affiliation_manuell_inaktiv_student),
        (co.affiliation_manuell, co.affiliation_manuell_inaktiv_ansatt)):
        for row in ac.list_accounts_by_type(affiliation=aff,
                                            status=int(aff_status)):
            manuell_account_affs.setdefault(
                int(row['person_id']), {}).setdefault(
                int(row['account_id']), []).append(
                [int(row['ou_id']), int(row['priority'])])
    return all_person_affs, manuell_account_affs

def process_persons():
    all_person_affs, manuell_account_affs =  prefetch_affiliations()
    
    for p_id, person_affs in all_person_affs.items():
        logger.debug("Checking %i" % p_id)
        person_manuell_affs = person_affs.get(
            int(co.affiliation_manuell), None)
        if person_manuell_affs is None:
            continue        # Har ikke manuell affiliation

        # Gå gjennom personens manuell affiliations.
        # Vi bryr oss ikke om affiliationen er slettet.
    
        for status, ou_id, create_date, deleted_date, src_sys in \
                person_manuell_affs:
            if not aff_mapping.has_key(status):
                continue
            # Finn de av personens konti som peker på denne person-aff.
            ac_targets = []
            for ac_id, ac_dta in manuell_account_affs.get(p_id, {}).items():
                for ac_ou, ac_pri in ac_dta:
                    # Since the person aff is of type manual, and we
                    # only have fetched manual account_affs, it is
                    # sufficient to verify that the ou is the same
                    if ac_ou == ou_id:
                        ac_targets.append([ac_id, ac_ou, ac_pri])

            if not ac_targets:
                if create_date < threshold and not deleted_date:
                    logger.debug("Delete affiliation, person %i: %s@%s" % (
                        p_id, co.PersonAffStatus(status), map_sko(ou_id)))
                    person.clear()
                    person.find(p_id)
                    person.delete_affiliation(
                        ou_id, co.affiliation_manuell, src_sys)
                continue

            new_aff_dta = map_aff(
                ou_id, status, aff_mapping[status], person_affs)
            if new_aff_dta is None:
                # Unable to map inaktiv to aktiv affiliation
                if create_date < threshold:
                    logger.warn("Person %i: old affiliation: %s@%s" % (
                        p_id, co.PersonAffStatus(status), map_sko(ou_id)))
                continue

            for ac_id, ac_ou, ac_pri in ac_targets:
                logger.debug("Fixing account %i: %s@%s -> @%s" % (
                    ac_id, co.PersonAffStatus(status), map_sko(ac_ou),
                    map_sko(new_aff_dta[1])))
                ac.clear()
                ac.find(ac_id)
                ac.del_account_type(ac_ou, int(co.affiliation_manuell))
                ac.set_account_type(
                    new_aff_dta[1], aff_mapping[status], priority=ac_pri)
        db.commit()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-p',):
            process_persons()
    if not opts:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    -p : process all persons
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 0d012c15-186e-4aed-ac92-76b43860d101
