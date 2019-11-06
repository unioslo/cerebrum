#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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
"""
Import guest user data from SYSTEM-X.
"""
from __future__ import print_function, unicode_literals

import argparse
import collections
import datetime
import logging

import mx.DateTime

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uit.access_SYSX import SYSX
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


def affiliation_key(person_id, ou_id, affiliation):
    return "%s:%s:%s" % (int(person_id), int(ou_id), int(affiliation))


def _load_cere_aff(db):
    co = Factory.get('Constants')(db)
    cb_aff = set()
    pers = Factory.get("Person")(db)
    logger.debug('Finding sysx affs...')
    for row in pers.list_affiliations(source_system=co.system_x):
        k = affiliation_key(row['person_id'], row['ou_id'], row['affiliation'])
        cb_aff.add(k)
    logger.info('Found %d sysx affs in Cerebrum', len(cb_aff))
    return cb_aff


def rem_old_aff(db, old_affs, stats):
    co = Factory.get('Constants')(db)
    person = Factory.get("Person")(db)
    grace = datetime.timedelta(days=0)
    today = datetime.date.today()
    logger.debug('Removing %d old sysx affs...', len(old_affs))
    for aff_key in old_affs:
        ent_id, ou, affi = aff_key.split(':')
        person.clear()
        person.find(int(ent_id))
        for aff in person.list_affiliations(int(ent_id),
                                            affiliation=int(affi),
                                            ou_id=int(ou)):
            last_date = aff['last_date'].pydate()
            end_grace_period = last_date + grace
            if today > end_grace_period:
                logger.warning(
                    "Deleting affiliation for person_id=%r, ou_id=%r, "
                    "affiliation=%r, last_date=%r, grace=%r",
                    ent_id, ou, affi, last_date, grace)
                person.delete_affiliation(ou, affi, co.system_x)
                stats['deletedaff'] += 1
    logger.info('Removed %d old sysx affs', len(old_affs))


def process_sysx_persons(db, source_file, remove_old_affs=True):
    stats = collections.defaultdict(int)
    sysx = SYSX(source_file)
    sysx.list()

    if remove_old_affs:
        old_affs = _load_cere_aff(db)
    else:
        old_affs = set()

    for p in sysx.sysxids:
        create_sysx_person(db, sysx.sysxids[p], old_affs, stats)

    if remove_old_affs:
        rem_old_aff(db, old_affs, stats)

    return dict(stats)


def check_expired_sourcedata(expire_date):
    if not expire_date:
        # This is how it's always been!
        return True
    return expire_date < datetime.date.today()


def create_sysx_person(db, sxp, update_affs, stats):
    """
    Create or update person with sysx data.

    :param db:
    :param sxp: Person dict from ``SYSX``
    :param update_affs: A set of current SYSX aff keys
    :param stats: A defaultdict with counts
    """

    co = Factory.get('Constants')(db)
    add_sysx_id = fnr_found = False

    sysx_id = sxp['id']
    fnr = sxp['fnr']
    fornavn = sxp['fornavn']
    etternavn = sxp['etternavn']
    fullt_navn = "%s %s" % (fornavn, etternavn)

    if check_expired_sourcedata(sxp['expire_date']):
        logger.info(
            "Skipping sysx_id=%r (%s), expire_date=%r",
            sysx_id, fullt_navn, sxp['expire_date'])
        stats['skipped'] += 1
        return

    # check if approved. Ditch if not.
    if not sxp['approved']:
        logger.error(
            "Skipping sysx_id=%r (%s), not approved",
            sysx_id, fullt_navn)
        stats['skipped'] += 1
        return

    my_stedkode = Factory.get('OU')(db)
    pers_sysx = Factory.get('Person')(db)
    pers_fnr = Factory.get('Person')(db)

    try:
        pers_sysx.find_by_external_id(co.externalid_sys_x_id, sysx_id)
    except Errors.NotFoundError:
        add_sysx_id = True

    if fnr:
        try:
            fnr = fodselsnr.personnr_ok(fnr)
        except fodselsnr.InvalidFnrError:
            logger.error("Skipping sysx_id=%r (%s), invalid fnr",
                         sysx_id, fullt_navn)
            stats['skipped'] += 1
            return
        birth_date = datetime.date(*fodselsnr.fodt_dato(fnr))

        if fodselsnr.er_kvinne(fnr):
            gender = co.gender_female
        else:
            gender = co.gender_male

        try:
            pers_fnr.find_by_external_id(co.externalid_fodselsnr, fnr)
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError as e:
            # This persons fnr has multiple rows in entity_external_id table
            # This is an error, person should not have not more than one entry.
            # Don't know which person object to use, return error message.
            logger.error(
                "Skipping sysx_id=%r (%s), matched multiple persons (%s)",
                sysx_id, fullt_navn, e)
            stats['skipped'] += 1
            return
        else:
            if not add_sysx_id and (pers_fnr.entity_id != pers_sysx.entity_id):
                logger.error(
                    "Skipping sysx_id=%r (%s), matched multiple persons (sysx "
                    "id matched person_id=%r, sysx fnr matched person_id=%r)",
                    sysx_id, fullt_navn, pers_sysx.entity_id,
                    pers_fnr.entity_id)
                stats['skipped'] += 1
                return
            fnr_found = True

    else:
        # foreigner without norwegian ssn,
        birth_date = sxp['birth_date']
        if not birth_date:
            logger.error("sysx_id=%r (%s) is missing birth date",
                         sysx_id, fullt_navn)

        if sxp['gender'] == 'M':
            gender = co.gender_male
        elif sxp['gender'] == 'F':
            gender = co.gender_female
        else:
            logger.error("Skipping sysx_id=%r (%s), invalid gender %r",
                         sysx_id, fullt_navn, sxp['gender'])
            stats['skipped'] += 1
            return

    logger.info("Processing sysx_id=%r (%s)", sysx_id, fullt_navn)
    if fnr_found:
        person = pers_fnr
    else:
        person = pers_sysx

    # person object located, populate...
    try:
        person.populate(mx.DateTime.DateFrom(birth_date), gender)
    except Errors.CerebrumError:
        logger.error("Skipping sysx_id=%r (%s), populate() failed",
                     sysx_id, fullt_navn, exc_info=True)
        stats['skipped'] += 1
        return

    person.affect_names(co.system_x, co.name_first, co.name_last, co.name_full)
    person.populate_name(co.name_first, fornavn)
    person.populate_name(co.name_last, etternavn)
    person.populate_name(co.name_full, fullt_navn)

    # add external ids
    if fnr:
        person.affect_external_id(co.system_x,
                                  co.externalid_fodselsnr,
                                  co.externalid_sys_x_id)
        person.populate_external_id(co.system_x, co.externalid_fodselsnr, fnr)
        logger.debug("Set NO_BIRTHNO for sysx_id=%r (%s)",
                     sysx_id, fullt_navn)
    else:
        person.affect_external_id(co.system_x, co.externalid_sys_x_id)

    person.populate_external_id(co.system_x, co.externalid_sys_x_id, sysx_id)
    logger.debug("Set sysx_id for sysx_id=%r (%s)", sysx_id, fullt_navn)

    # setting affiliation and affiliation_status
    affiliation = co.PersonAffiliation(sxp['affiliation'])
    affiliation_status = co.PersonAffStatus(affiliation,
                                            sxp['affiliation_status'])
    # Assert that the affs are real
    int(affiliation), int(affiliation_status)

    # get ou_id of stedkode used
    fak = sxp['ou'][0:2]
    ins = sxp['ou'][2:4]
    avd = sxp['ou'][4:6]

    # KEB
    if fak == '0':
        logger.warning("sysx_id=%r (%s) has invalid sko=%r",
                       sysx_id, fullt_navn, sxp['ou'])
        ins = avd = fak
    try:
        my_stedkode.find_stedkode(fak, ins, avd,
                                  cereconf.DEFAULT_INSTITUSJONSNR)
    except EntityExpiredError:
        logger.error("Skipping sysx_id=%r (%s), expired sko=%r",
                     sysx_id, fullt_navn, sxp['ou'])
        stats['skipped'] += 1
        return

    ou_id = int(my_stedkode.entity_id)

    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    op = person.write_db()

    # populate the person affiliation table
    person.populate_affiliation(co.system_x,
                                ou_id,
                                int(affiliation),
                                int(affiliation_status))

    # make sure we don't delete this aff when processing deleted affs
    aff_key = affiliation_key(person.entity_id, ou_id, affiliation)
    update_affs.discard(aff_key)

    op2 = person.write_db()

    logger.debug("OP codes: op=%s,op2=%s" % (op, op2))

    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
        stats['unchanged'] += 1
    elif op is None and op2 is False:
        logger.info("**** AFF UPDATE ****")
        stats['updated'] += 1
    elif op is True:
        logger.info("**** NEW ****")
        stats['added'] += 1
    elif op is False:
        logger.info("**** UPDATE ****")
        stats['updated'] += 1
    return


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Import guest user data from SYSTEM-X",
    )
    parser.add_argument(
        'filename',
        help='Read and import SYSTEM-X guests from %(metavar)s',
        metavar='<file>',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='import_SYSX')

    stats = process_sysx_persons(db, args.filename)

    logger.info("Stats: %r", dict(stats))

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
