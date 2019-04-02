#! /usr/bin/env python
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
from __future__ import print_function

import getopt
import sys
import os
import mx.DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uit.access_SYSX import SYSX

from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

progname = __file__.split(os.sep)[-1]
__doc__ = """
    usage:: %s [-s|--source_file <filename>] [-u|--update] [-d|--dryrun]
    -s file | --source_file file : source file containing information needed to
                                   create person and user entities in cerebrum
    -u      | --update_data      : updates the datafile containing guests from
                                   the guest database
    --dryrun : do no commit changes to database
""" % progname

SPLIT_CHAR = ':'
logger_name = cereconf.DEFAULT_LOGGER_TARGET
logger = sysx = old_aff = None
include_delete = True
skipped = added = updated = unchanged = deletedaff = 0

db = Factory.get('Database')()
db.cl_init(change_program='import_SYSX')
person = Factory.get('Person')(db)
co = Factory.get('Constants')(db)


def _load_cere_aff():
    cb_aff = {}
    pers = Factory.get("Person")(db)
    for row in pers.list_affiliations(source_system=co.system_x):
        k = "%s:%s:%s" % (row['person_id'], row['ou_id'], row['affiliation'])
        cb_aff[str(k)] = True
    return cb_aff


def rem_old_aff():
    global deletedaff
    person = Factory.get("Person")(db)
    grace = 0
    for k, v in old_aff.items():
        if v:
            ent_id, ou, affi = k.split(':')
            person.clear()
            person.find(int(ent_id))
            for aff in person.list_affiliations(int(ent_id),
                                                affiliation=int(affi),
                                                ou_id=int(ou)):
                last_date = aff['last_date']
                end_grace_period = last_date + mx.DateTime.DateTimeDelta(grace)
                if mx.DateTime.today() > end_grace_period:
                    logger.warn(
                        "Deleting sysX affiliation for person_id=%s,"
                        "ou=%s,affi=%s last_date=%s,grace=%s",
                        ent_id, ou, affi, last_date, grace)
                    person.delete_affiliation(ou, affi, co.system_x)
                    deletedaff += 1


def process_sysx_persons(source_file, update):
    global old_aff
    sysx = SYSX(source_file, update=update)
    sysx.list()
    old_aff = _load_cere_aff()

    for p in sysx.sysxids:
        create_sysx_person(sysx.sysxids[p])
    if include_delete:
        rem_old_aff()


def check_expired_sourcedata(expire_date):
    expire = mx.DateTime.DateFrom(expire_date)
    today = mx.DateTime.today()
    if expire < today:
        return True
    else:
        return False


# sxp =  dict from access_SYSX.prepare_data funtion
def create_sysx_person(sxp):
    global skipped, added, updated, unchanged, include_delete, old_aff
    add_nobirthno = add_sysx_id = fnr_found = False

    id = sxp['id']
    personnr = sxp['personnr']
    fornavn = sxp['fornavn']
    etternavn = sxp['etternavn']
    fullt_navn = "%s %s" % (fornavn, etternavn)
    approved = sxp['approved']

    # logger.debug("Trying to process %s %s ID=%s,approved=%s" %
    #                       (fornavn,etternavn,id,approved))
    if check_expired_sourcedata(sxp['expire_date']):
        logger.info(
            "Skip %s (SysXId=%s)(pnr=%s), it is expired %s",
            fullt_navn, id, personnr, sxp['expire_date'])
        skipped += 1
        return

    # check if approved. Ditch if not.
    if approved != 'Yes':
        logger.error(
            "Person: %s (id=%s) not approved, Skip." % (fullt_navn, id))
        return

    my_stedkode = Factory.get('OU')(db)
    my_stedkode.clear()
    pers_sysx = Factory.get('Person')(db)
    pers_fnr = Factory.get('Person')(db)

    try:
        pers_sysx.find_by_external_id(co.externalid_sys_x_id, id)
    except Errors.NotFoundError:
        add_sysx_id = True
        # not found by sysX_id

    if personnr != "":
        try:
            fnr = fodselsnr.personnr_ok(personnr)
        except fodselsnr.InvalidFnrError:
            logger.error("Ugyldig fødselsnr: %s on sysX id=", personnr, id)
            return
        (year, mon, day) = fodselsnr.fodt_dato(fnr)
        gender = co.gender_male
        if fodselsnr.er_kvinne(fnr):
            gender = co.gender_female

        try:
            pers_fnr.find_by_external_id(co.externalid_fodselsnr, fnr)
        except Errors.NotFoundError:
            add_nobirthno = True
        except Errors.TooManyRowsError:
            # This persons fnr has multiple rows in entity_external_id table
            # This is an error, person should not have not more than one entry.
            # Don't know which person object to use, return error message.
            logger.error(
                "Person with ssn:%s has multiple entries in "
                "entity_external_id. Resolve manually" % fnr)
            return
        else:
            if not add_sysx_id and (pers_fnr.entity_id != pers_sysx.entity_id):
                logger.error(
                    "SysXID=%s with fnr=%s is owned by different personid's! "
                    "Fnr owned by person_id=%s in db "
                    "Resolve manually",
                    pers_sysx.entity_id, fnr, pers_fnr.entity_id)
                return
            fnr_found = True

    else:
        # foreigner without norwegian ssn,
        date_field = sxp['fodsels_dato'].split(".")
        year = int(date_field[2])
        mon = int(date_field[1])
        day = int(date_field[0])
        if sxp['gender'] == 'M':
            gender = co.gender_male
        elif sxp['gender'] == 'F':
            gender = co.gender_female
        else:
            logger.error("Invalid gender from SysXId=%s" % id)
            return

    logger.info(
        "Processing '%s', SysXId=%s, fnr='%s'" % (fullt_navn, id, personnr))
    if fnr_found:
        person = pers_fnr
    else:
        person = pers_sysx

    # person object located, populate...
    try:
        person.populate(mx.DateTime.Date(year, mon, day), gender)
    except Errors.CerebrumError as m:
        logger.error("Person %s populate failed: %s" % (personnr or id, m))
        return

    person.affect_names(co.system_x, co.name_first, co.name_last, co.name_full)
    person.populate_name(co.name_first, fornavn)
    person.populate_name(co.name_last, etternavn)
    person.populate_name(co.name_full, fullt_navn)

    # add external ids
    if personnr:
        person.affect_external_id(co.system_x,
                                  co.externalid_fodselsnr,
                                  co.externalid_sys_x_id)
        person.populate_external_id(co.system_x, co.externalid_fodselsnr, fnr)
        logger.debug("Set NO_BIRTHNO for id=%s,fnr=%s" % (id, personnr))
    else:
        person.affect_external_id(co.system_x, co.externalid_sys_x_id)
    person.populate_external_id(co.system_x, co.externalid_sys_x_id, id)
    logger.debug("Set syx_id for id=%s,fnr=%s" % (id, personnr))

    # setting affiliation and affiliation_status
    aff = sxp['affiliation']
    aff_stat = sxp['affiliation_status']
    affiliation = int(co.PersonAffiliation(aff))
    affiliation_status = int(co.PersonAffStatus(aff, aff_stat))

    # get ou_id of stedkode used
    fak = sxp['ou'][0:2]
    ins = sxp['ou'][2:4]
    avd = sxp['ou'][4:6]

    # KEB
    if fak == '0':
        logger.warn(
            "Person with SysX id=%s and fnr=%s, has invalid stedkode: %s%s%s",
            id, personnr, fak, ins, avd)
        ins = fak
        avd = fak
    try:
        my_stedkode.find_stedkode(fak, ins, avd,
                                  cereconf.DEFAULT_INSTITUSJONSNR)
    except EntityExpiredError as err:
        logger.error("Person with SysX id %s on expired stedkode %s%s%s",
                     id, fak, ins, avd)
        return

    ou_id = int(my_stedkode.entity_id)

    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    op = person.write_db()

    # populate the person affiliation table
    person.populate_affiliation(co.system_x,
                                ou_id,
                                affiliation,
                                affiliation_status
                                )
    # make sure we don't delete this aff when processing deleted affs
    if include_delete:
        key_a = "%s:%s:%s" % (person.entity_id, ou_id, int(affiliation))
        if key_a in old_aff:
            logger.debug("Don't delete affiliation: %s", key_a)
            old_aff[key_a] = False
    op2 = person.write_db()
    # Update last-seen date
    try:
        person.set_affiliation_last_date(co.system_x,
                                         ou_id,
                                         affiliation,
                                         affiliation_status
                                         )
    except AttributeError as m:
        logger.warn("WHOOOO. AttributeErrror: %s" % m)
        # in case this is a new person object...
    except Errors.ProgrammingError as m:
        logger.warn("WHOOOO. Programming errror: %s" % m)

    logger.debug("OP codes: op=%s,op2=%s" % (op, op2))

    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
        unchanged += 1
    elif op is None and op2 is False:
        logger.info("**** AFF UPDATE ****")
        updated += 1
    elif op is True:
        logger.info("**** NEW ****")
        added += 1
    elif op is False:
        logger.info("**** UPDATE ****")
        updated += 1
    return 0


def main():
    global sysx, logger
    logger = Factory.get_logger(logger_name)

    dryrun = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:ud',
                                   ['source_file', 'update', 'dryrun'])
    except getopt.GetoptError as m:
        print("Unknown option: {}".format(m))
        usage()

    ret = 0
    source_file = None
    update = 0
    for opt, val in opts:
        if opt in ('-s', '--source_file'):
            source_file = val
        elif opt in ('-u', '--update'):
            update = 1
        elif opt in ('--dryrun',):
            dryrun = True
    process_sysx_persons(source_file, update)

    if dryrun:
        logger.info("Dryrun: Rollback all changes")
        db.rollback()
    else:
        logger.info("Committing all changes to database")
        db.commit()

    fmt_str = ("Stats: Added: %d, Updated=%d, Skipped=%d, "
               "Unchanged=%d, Deleted affs=%d")
    fmt_var = (added, updated, skipped, unchanged, deletedaff)
    logger.info(fmt_str % fmt_var)


def usage():
    print(__doc__)
    sys.exit(1)


if __name__ == '__main__':
    main()
