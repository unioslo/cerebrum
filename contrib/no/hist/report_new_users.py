#!/usr/bin/python

# Lag oversikt over brukere med angitte spread(s) bygget i løpet av
# siste døgn.

import sys
import getopt
import time
import pickle
import os

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum import OU
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum.modules.no.uio import AutoStud


def usage(exitcode=0):
    print """Usage: report_new_users.py {options}
Valid options are:

  -S sep
        Use the string 'sep' as output field separator

  -s spread
        Report new users that have the given spread.  Specify 'spread'
        by the name of the corresponding Constants class attribute.

        This option can not be combined with the '-f' option.

  -d delta
        Limit '-s' output to users created at most 'delta' days ago.

  -D YYYY-MM-DD
  --start-date YYYY-MM-DD
        Limit '-s' output to users created on or after the specified
        date.  Default is yesterday.

  -f fnrfile
        Report new users belonging to persons whose fnr is listed in
        'fnrfile'.  The file 'fnrfile' should contain 11-digit fnrs,
        one per line.

        This option can not be combined with the '-s' option.

Exactly one of the '-s' or '-f' options must be specified.  All output
is written to stdout.

"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'S:D:d:f:s:',
                                   ['help', 'start-date'])
    except getopt.GetoptError:
        usage(1)

    if args:
        usage(1)

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    studnr2data = read_student_data("/cerebrum/dumps/FS/merged_persons.xml")

    field_sep = '¤'
    sdate = None
    spread = None
    fnrfile = None
    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '-S':
            if not val:
                print "Can't use null field separator."
                usage(1)
            field_sep = val
        elif opt in ('-D', '--start-date'):
            sdate = db.Date(*([int(x) for x in val.split("-", 2)]))
        elif opt == '-d':
            sdate = db.DateFromTicks(time.time() - int(val)*24*60*60)
        elif opt == '-s':
            spread = val
        elif opt == '-f':
            fnrfile = val
    if spread is not None and fnrfile is not None:
        # Kan ikke angi både spread og fnr-fil.
        usage(1);        
    if spread is not None:
        dump_new_users(db, const, studnr2data, field_sep,
                       spread=val, start_date=sdate)
    elif fnrfile is not None:
        dump_new_users(db, const, studnr2data, field_sep,
                       fnr_file=fnrfile, start_date=sdate)
    else:
        # Må angi minst en av spread eller fnr-fil.
        usage(1)        
                           
def dump_new_users(db, const, studnr2data, field_sep, spread=None,
                   fnr_file=None, start_date=None):
    entity = Entity.Entity(db)
    if start_date is None:
        start_date = today(db)
    if spread is not None:
        scode = int(getattr(const, spread))
        rows = entity.list_all_with_spread(scode)
    elif fnr_file is not None:
        account = Account.Account(db)
        person = Person.Person(db)
        rows = []
        f = open(fnr_file)
        for fnr in f.readlines():
            fnr = fnr.rstrip()
            person.clear()
            try:
                person.find_by_external_id(const.externalid_fodselsnr, fnr)
            except Errors.NotFoundError:
                print "no users for %s" % fnr
                continue
            for r in account.list_accounts_by_owner_id(person.entity_id):
                rows.append({'entity_id': r['account_id']})
        
    # Finn brukerens nyeste passord, i klartekst.
    changelog = db.get_log_events(start_id=0, max_id=None, types=(const.account_password,))

    for r in rows:
        try:
            account = _get_account(db, r['entity_id'])
        except Errors.NotFoundError:
            # Feil entity_type?  Bør ikke kunne skje, da hver enkelt
            # spread er begrenset til en enkelt entity_type.
            continue
        atypes = account.get_account_types()
        if account.create_date < start_date:
            # Hopp over accounts som er eldre enn angitt start-dato.
            # print "SKIP %s because it's to old\n" % account.account_name
            continue

        # Finn en (tilfeldig) av stedkodene brukeren har
        # tilknytning til.
        try:
            sko = _get_ou(db, atypes[0].ou_id)
            stedkode = "%02d%02d%02d" % (sko.fakultet, sko.institutt,
                                         sko.avdeling)
        except:
            stedkode = ''

        # Finn brukerens nyeste passord, i klartekst.
        pwd_rows = [row for row in changelog
                    if row.subject_entity == account.entity_id]
        try:
            pwd = pickle.loads(pwd_rows[-1].change_params)['password']
        except:
            pwd = ''

        # Finn personen som eier brukeren, og dermed dennes for- og
        # etternavn.
        person = _get_person(db, account.owner_id)

        # Finn en (tilfeldig) affiliation, og tilsvarende -status,
        # for brukeren.
        aff = affstatus = ''
        try:
            aff = Constants._PersonAffiliationCode(int(atypes[0].affiliation))
            for x in person.get_affiliations():
                if x.affiliation == aff and x.ou_id == atypes[0].ou_id:
                    affstatus = Constants._PersonAffStatusCode(
                        int(aff), int(x.status))
                    break
        except:
            pass

        # Finn brukerens eiers for- og etternavn (fra FS)
        fname = lname = fullname = ''
        try:
            fname = person.get_name(const.system_fs,
                                    const.name_first)
            lname = person.get_name(const.system_fs,
                                    const.name_last)
            fullname = person.get_name(const.system_cached,
                                       const.name_full)
        except:
            pass

        # Finn student-nummer for brukerens eier.
        try:
            studnr = person.get_external_id(
                const.system_fs, const.externalid_studentnr)[0]['external_id']
        except:
            studnr = ''

        # Nyeste kullkode studenten er med i, samt studieprogrammet og
        # studieretningen knyttet til denne kullkoden.
        kull, stprog, stretn, klassekode = studnr2data.get(studnr, ('','','',''))

        sys.stdout.write(
            (field_sep.join(("%(brukernavn)s", "%(pwd)s", "%(sko)s",
                             "%(studentnr)s", "%(fullname)s", "%(fname)s",
                             "%(lname)s", "%(aff)s", "%(affstatus)s",
                             "%(kull)s", "%(klasse)s", "%(stprog)s", "%(stretn)s"))
             + "\n") % {'brukernavn': account.account_name,
                        'pwd': pwd,
                        'sko': stedkode,
                        'studentnr': studnr,
                        'fullname': fullname,
                        'fname': fname,
                        'lname': lname,
                        'aff': aff,
                        'affstatus': affstatus,
                        'kull': kull,
                        'klasse': klassekode,
                        'stprog': stprog,
                        'stretn': stretn,
                        })
        sys.stdout.flush()


def _get_ou(db, e_id):
    ou = Factory.get("OU")(db)
    ou.find(e_id)
    return ou

def _get_person(db, e_id):
    person = Person.Person(db)
    person.find(e_id)
    return person

def _get_account(db, e_id):
    account = Account.Account(db)
    account.find(e_id)
    return account

def yesterday(db):
    now = time.time();
    return db.DateFromTicks(now - 60*60*24)

def today(db):
    return db.DateFromTicks(time.time())

def read_student_data(fname):
    studnr2data = {}
    def callback(data):
        if not data.has_key('aktiv'):
            return
        for info in data['aktiv']:
            studnr = info['studentnr_tildelt']
            kull = info['kullkode']
            studretn = info['studieretningkode']
            studprog = info['studieprogramkode']
            klassekode = info['klassekode']
            if not studnr2data.has_key(studnr):
                studnr2data[studnr] = (kull, studretn, studprog, klassekode)
            else:
                present_kull = studnr2data[studnr][0]
                if kull > present_kull:
                    studnr2data[studnr] = (kull, studretn, studprog, klassekode)

    # Trenger strengt tatt ikke logging her, men må ha et
    # logger-objekt å sende til StudentInfoParser -- så da logger vi
    # til /dev/null.
    logger = AutoStud.Util.ProgressReporter("/dev/null", stdout=False)
    logger.info("Started")
    StudentInfo.StudentInfoParser(fname, callback, logger)
    logger.info("Completed")
    return studnr2data

if __name__ == '__main__':
    main()
