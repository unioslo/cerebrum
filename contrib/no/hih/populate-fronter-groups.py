#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2011 University of Oslo, Norway
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
import re

import cerebrum_path
import cereconf

from Cerebrum import Database
from Cerebrum import Errors

from Cerebrum.modules.no.hih.access_FS import FS
from Cerebrum.Utils import Factory

def usage(exitcode):
    print "Usage: populate-fronter-groups.py"
    sys.exit(exitcode)


def institutt_grupper():
    # sko 220000 has id = 5735
    alle_stud_22 = person.list_affiliations(affiliation=const.affiliation_student, ou_id=5735)
    alle_ans_22 = person.list_affiliations(affiliation=const.affiliation_ansatt, ou_id=5735)    
    # sko 230000 has id = 5748 
    alle_stud_23 = person.list_affiliations(affiliation=const.affiliation_student, ou_id=5748)
    alle_ans_23 = person.list_affiliations(affiliation=const.affiliation_ansatt, ou_id=5748) 
    
    # groups used are: ans-220000, stud-220000, ans-230000, stud-230000
    # no other 'institutter' exist at HiH for now
    
    # group membership has to be expressed through membership of the
    # primary account
    # 
    # stud-groups (220000 and 230000)
    grp.clear()
    try:
        grp.find_by_name('stud-220000')
    except Errors.NotFoundError:
        logger.error("Could not find instituttgruppe %s, aborting", 'stud-220000')
        return
    for row in alle_stud_22:
        primary_acc_id = None
        person.clear()
        person.find(row['person_id'])
        primary_acc_id = person.get_primary_account()
        if primary_acc_id == None:
            logger.warn("Could not find any accounts for student %s at 220000", row['person_id'])
            continue
        if not grp.has_member(primary_acc_id):
            grp.add_member(primary_acc_id)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m
    grp.clear()
    try:
        grp.find_by_name('stud-230000')
    except Errors.NotFoundError:
        logger.error("Could not find instituttgruppe %s, aborting", 'stud-230000')
        return
    for row in alle_stud_23:
        primary_acc_id = None
        person.clear()
        person.find(row['person_id'])
        primary_acc_id = person.get_primary_account()
        if primary_acc_id == None:
            logger.warn("Could not find any accounts for student %s at 230000", row['person_id'])
            continue
        if not grp.has_member(primary_acc_id):
            grp.add_member(primary_acc_id)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m
    
    # ans-groups (220000 and 230000)
    grp.clear()
    try:
        grp.find_by_name('ans-220000')
    except Errors.NotFoundError:
        logger.error("Could not find instituttgruppe %s, aborting", 'ans-220000')
        return
    for row in alle_ans_22:
        primary_acc_id = None
        person.clear()
        person.find(row['person_id'])
        primary_acc_id = person.get_primary_account()
        if primary_acc_id == None:
            logger.warn("Could not find any accounts for ans %s at 220000", row['person_id'])
            continue        
        if not grp.has_member(primary_acc_id):
            grp.add_member(primary_acc_id)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m
    grp.clear()
    try:
        grp.find_by_name('ans-230000')
    except Errors.NotFoundError:
        logger.error("Could not find instituttgruppe %s, aborting", 'ans-230000')
        return
    for row in alle_ans_23:
        primary_acc_id = None
        person.clear()
        person.find(row['person_id'])
        primary_acc_id = person.get_primary_account()
        if primary_acc_id == None:
            logger.warn("Could not find any accounts for ans %s at 230000", row['person_id'])
            continue
        if not grp.has_member(primary_acc_id):
            grp.add_member(primary_acc_id)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m

def studieprog_grupper(fsconn):
    for x in fs.info.list_studieprogrammer():
        if x['status_utgatt'] == 'J':
            logger.debug("Studieprogram %s is expired, skipping.", x['studieprogramkode'])
            continue
        # create all connected kull-groups and update memeberships
        kull_grupper(fsconn, x['studieprogramkode'])

        # naming studieprogram-groups with a prefix (studieprog-) and
        # studieprogramkode from FS. description for group will be the
        # full name of the studieprogram
        grp_name = "studieprogram-%s" % x['studieprogramkode']
        grp.clear()
        try:
            grp.find_by_name(grp_name)
        except Errors.NotFoundError:
            logger.info("Could not find group %s, creating", grp_name)
            # all groups are created/owned by bootstrap_account, id = 2
            grp.populate(creator_id=2,
                         visibility=const.group_visibility_all,
                         name=grp_name, 
                         description='Alle studenter på ' + x['studieprognavn'])
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m

        # check if the group is tagged for export to LMS, tagg if not
        if not grp.has_spread(const.spread_lms_group):
            grp.add_spread(const.spread_lms_group)
            logger.debug("Added spread to LMS for studieprog group %s", grp_name)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m

        # studieprog-group is either found or created. checking memberships
        for x in fs.undervisning.list_studenter_studieprog(x['studieprogramkode']):
            fnr = "%06d%05d" % (int(x['fodselsdato']), int(x['personnr']))
            person.clear()
            try:
                person.find_by_external_id(const.externalid_fodselsnr, fnr, source_system=const.system_fs,
                                           entity_type=const.entity_person)
            except Errors.NotFoundError:
                logger.error("Could not find person %s in Cerebrum", fnr)
                continue
            # all memberships are based on primary account
            primary_acc_id = person.get_primary_account()
            if primary_acc_id == None:
                logger.error("Could not find any primary account for person %s, skipping", fnr)
                continue
            if not grp.has_member(primary_acc_id):
                grp.add_member(primary_acc_id)
                logger.debug("Added %s to group %s", primary_acc_id, grp.group_name)
                try:
                    grp.write_db()
                except db.DatabaseError, m:
                    raise CerebrumError, "Database error: %s" % m


def kull_grupper(fsconn, studieprogramkode):
    for x in fs.undervisning.list_kull_at_studieprog(studieprogramkode):
        # groups are named by a prefix = kull- and also
        # studieprogkode, kullnavn, terminkode and arstall from fs
        grp_name = 'kull-%s-%s-%s-%s' % (studieprogramkode, x['studiekullnavn'], x['terminkode'], x['arstall'])
        grp.clear()
        try:
            grp.find_by_name(grp_name)
        except Errors.NotFoundError:
            logger.info("Could not find kull group %s, creating", grp_name)
            # all groups are created/owned by bootstrap_account, id = 2
            desc = "Alle studenter på kull %s, %s %s (%s)" % (x['studiekullnavn'], 
                                                              x['terminkode'], 
                                                              x['arstall'], 
                                                              studieprogramkode)
            grp.populate(creator_id=2,
                         visibility=const.group_visibility_all,
                         name=grp_name, 
                         description=desc)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m

        # check if the group is tagged for export to LMS, tagg if not
        if not grp.has_spread(const.spread_lms_group):
            grp.add_spread(const.spread_lms_group)
            logger.debug("Added spread to LMS for kull group %s", grp_name)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m
        # update memberships in kull-group
        for x in fs.undervisning.list_studenter_kull(studieprogramkode, x['terminkode'], x['arstall']):
            fnr = "%06d%05d" % (int(x['fodselsdato']), int(x['personnr']))
            person.clear()
            try:
                person.find_by_external_id(const.externalid_fodselsnr, fnr, source_system=const.system_fs,
                                           entity_type=const.entity_person)
            except Errors.NotFoundError:
                logger.error("Could not find person %s in Cerebrum", fnr)
                continue
            # all memberships are based on primary account
            primary_acc_id = person.get_primary_account()
            if primary_acc_id == None:
                logger.error("Could not find any primary account for person %s, skipping", fnr)
                continue
            if not grp.has_member(primary_acc_id):
                grp.add_member(primary_acc_id)
                logger.debug("Added %s to group %s", primary_acc_id, grp.group_name)
                try:
                    grp.write_db()
                except db.DatabaseError, m:
                    raise CerebrumError, "Database error: %s" % m

def undervisningsmelding_grupper(fsconn):
    for x in fs.undervisning.list_undervisningenheter():
        grp_name = 'emne-%s-%s-%s' % (x['emnekode'], x['terminkode'], x['arstall'])
        grp.clear()
        try:
            grp.find_by_name(grp_name)
        except Errors.NotFoundError:
            logger.info("Could not find emne group %s, creating", grp_name)
            # all groups are created/owned by bootstrap_account, id = 2
            desc = "Alle studenter undervisningsmeldt på %s, %s %s" % (x['emnekode'], 
                                                                       x['arstall'], 
                                                                       x['terminkode'])
            grp.populate(creator_id=2,
                         visibility=const.group_visibility_all,
                         name=grp_name, 
                         description=desc)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m

        # check if the group is tagged for export to LMS, tagg if not
        if not grp.has_spread(const.spread_lms_group):
            grp.add_spread(const.spread_lms_group)
            logger.debug("Added spread to LMS for kull group %s", grp_name)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m

        # update memberships in emne-groups
        for y in fs.undervisning.list_studenter_underv_enhet(x['institusjonsnr'], 
                                                             x['emnekode'],
                                                             x['versjonskode'], 
                                                             x['terminkode'], 
                                                             x['arstall'], 
                                                             x['terminnr']):
            fnr = "%06d%05d" % (int(y['fodselsdato']), int(y['personnr']))
            person.clear()
            try:
                person.find_by_external_id(const.externalid_fodselsnr, fnr, source_system=const.system_fs,
                                           entity_type=const.entity_person)
            except Errors.NotFoundError:
                logger.error("Could not find person %s in Cerebrum", fnr)
                continue
            # all memberships are based on primary account
            primary_acc_id = person.get_primary_account()
            if primary_acc_id == None:
                logger.error("Could not find any primary account for person %s, skipping", fnr)
                continue
            if not grp.has_member(primary_acc_id):
                grp.add_member(primary_acc_id)
                logger.debug("Added %s to group %s", primary_acc_id, grp.group_name)
                try:
                    grp.write_db()
                except db.DatabaseError, m:
                    raise CerebrumError, "Database error: %s" % m
        
def main():
    global db, const, ou, grp, person, acc, fs, logger

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)
    grp = Factory.get("Group")(db)
    person = Factory.get("Person")(db)
    acc = Factory.get("Account")(db)
    logger = Factory.get_logger("cronjob")
    db.cl_init(change_program='pop-lms-grps')

    fsdb = Database.connect(user='I0208_cerebrum', service='FSHIH.uio.no', DB_driver='cx_Oracle') 
    fs = FS(fsdb)

    logger.info("Updating studieprogram groups")
    studieprog_grupper(fs)

    logger.info("Updating instittut groups")
    institutt_grupper()

    logger.info("Updating emne/underv.enh groups")
    undervisningsmelding_grupper(fs)
    
    logger.info("All done, commiting to database")
    db.rollback()

if __name__ == '__main__':
    main()
