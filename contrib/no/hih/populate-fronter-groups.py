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

"""
Script for generating and populating groups in HiH's Cerebrum out of student
information retrieved from FS. The groups are later exported to Fronter by
generate_fronter_xml.py.
"""

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
logger = Factory.get_logger("cronjob")
db = Factory.get("Database")()
db.cl_init(change_program='pop-lms-grps')
const = Factory.get("Constants")(db)
ou = Factory.get("OU")(db)
grp = Factory.get("Group")(db)
person = Factory.get("Person")(db)
acc = Factory.get("Account")(db)

# The settings for 'intitutt' groups at HiH:
#
# Groups used are: ans-220000, stud-220000, ans-230000, stud-230000,
# no other 'institutter' exist at HiH for now.
#
# Group membership has to be expressed through membership of the primary
# account.
institutt_group_settings = (
    # sko 220000 has id = 5735
    ('stud-220000', {'affiliation': const.affiliation_student, 'ou_id': 5735}),
    ('ans-220000', {'affiliation': const.affiliation_ansatt, 'ou_id': 5735}),
    # sko 230000 has id = 5748 
    ('stud-230000', {'affiliation': const.affiliation_student, 'ou_id': 5748}),
    ('ans-230000', {'affiliation': const.affiliation_ansatt, 'ou_id': 5748}),
   )

def usage(exitcode=0):
    print """Usage: populate-fronter-groups.py

    --delete-groups Delete the groups before creating and populating new
                    groups. This cleans up and removes old groups from the
                    database, which in effect also removes students from their
                    old rooms in Fronter.

                    Note that removing students from old rooms in Fronter also
                    removes their access to old data in Fronter, so do not do
                    this unless the instance knows about the effect.

    --dryrun        Do not actually do anything with the database.

    -h --help       Show this and quit.
    """
    sys.exit(exitcode)


def institutt_grupper(remove_extra_members=False):
    """Create and populate groups that is specific for the HiH instance,
    depending on the persons' affiliations and OUs. This includes both student
    and some employee groups, and its members are defined in
    L{institutt_group_settings}.
    
    If L{remove_extra_members} is True, extra group members are removed from
    the groups, that is, the members that does not have the correct
    affiliation anymore."""

    def fill_group(groupname, members, remove_others=False):
        """Add the given members to the given group. If L{remove_others} is
        True, existing members of the group that is not mentioned in
        L{members} are removed from the group."""
        logger.debug("Processing group %s, %d members given", groupname, len(members))

        grp.clear()
        try:
            grp.find_by_name(groupname)
        except Errors.NotFoundError:
            logger.error("Could not find group %s, aborting", groupname)
            return
        existing_members = set(row['member_id'] for row in
                         grp.search_members(group_id=grp.entity_id))
        if remove_others:
            for mem in existing_members:
                if mem not in members:
                    logger.info('Removing mem %s from group %s', mem, groupname)
                    grp.remove_member(mem)
        for mem in members:
            if mem not in existing_members:
                logger.info('Adding mem %s to group %s', mem, groupname)
                grp.add_member(mem)

    # cache the primary accounts
    pe2primary = dict((r['person_id'], r['account_id']) for r in
                      acc.list_accounts_by_type(primary_only=True))

    for group, aff_targets in institutt_group_settings:
        members = set()
        # add the person's primary account:
        for row in person.list_affiliations(**aff_targets):
            try:
                members.add(pe2primary[row['person_id']])
            except KeyError:
                logger.warn("Couldn't find account for ans %s (%s)",
                            row['person_id'], group)
        fill_group(group, members, remove_extra_members)
    logger.debug("institutt_grupper done")

def studieprog_grupper(fsconn):
    """Create and populate groups for active study programs that is defined in FS."""
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

def delete_fronter_groups():
    """Go through the database and delete all fronter study groups that has
    previously been created by this script."""
    # TODO: would this spam the change_logger?
    for match in ('studieprogram-%', 'kull-%-%-%-%', 'emne-%-%-%'):
        for row in grp.search(name=match):
            logger.debug("Deleting group: %s" % row['name'])
            grp.clear()
            grp.find(row['group_id'])
            grp.delete()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['help', 'delete-groups',
                                    'dryrun'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    global fs
    dryrun = False
    delete_groups = False

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--delete-groups'):
            delete_groups = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    fsdb = Database.connect(user=cereconf.FS_USER,
                            service=cereconf.FS_DATABASE_NAME,
                            DB_driver='cx_Oracle') 
    fs = FS(fsdb)

    if delete_groups:
        logger.info("Deleting all fronter groups")
        delete_fronter_groups()
        logger.info("Fronter groups eliminated from db, now do the rebuild")

    logger.info("Updating studieprogram groups")
    studieprog_grupper(fs)

    logger.info("Updating instittut groups")
    institutt_grupper(delete_groups)

    logger.info("Updating emne/underv.enh groups")
    undervisningsmelding_grupper(fs)
    
    if dryrun:
        logger.info("All done, rolled back changes")
        db.rollback()
    else:
        logger.info("All done, commiting to database")
        db.commit()

if __name__ == '__main__':
    main()
