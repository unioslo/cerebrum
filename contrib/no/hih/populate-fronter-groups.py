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
    ('ans-220000',  {'affiliation': const.affiliation_ansatt,  'ou_id': 5735}),
    # sko 230000 has id = 5748 
    ('stud-230000', {'affiliation': const.affiliation_student, 'ou_id': 5748}),
    ('ans-230000',  {'affiliation': const.affiliation_ansatt,  'ou_id': 5748}),
   )

def usage(exitcode=0):
    print """Usage: populate-fronter-groups.py

    --remove        This option causes the old groups to be deleted, that is
                    all groups on the form kull-*, emne-* and studieprogram-*
                    that is not populated gets deleted.

                    Another thing it does is removing existing group members
                    from the group that should not be there.
    
                    Note that removing students from their old groups removes
                    their access to the corresponding rooms and data in
                    Fronter. Do not do this unless the instance has accepted
                    the effect.

    --dryrun        Do not actually do anything with the database.

    -h --help       Show this and quit.
    """
    sys.exit(exitcode)

def fill_group(groupname, members, remove_others=False):
    """Add the given members to the given group. If L{remove_others} is True,
    existing members of the group that is not mentioned in L{members} are
    removed from the group."""
    logger.debug("Processing group %s, %d members given", groupname,
                                                          len(members))
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

def institutt_grupper(remove_others=False):
    """Create and populate groups that is specific for the HiH instance,
    depending on the persons' affiliations and OUs. This includes both student
    and some employee groups, and its members are defined in
    L{institutt_group_settings}.
    
    If L{remove_others} is True, extra group members are removed from
    the groups, that is, the members that does not have the correct
    affiliation anymore."""
    for groupname, aff_targets in institutt_group_settings:
        members = set()
        # add the person's primary account:
        for row in person.list_affiliations(**aff_targets):
            try:
                members.add(pe2primary[row['person_id']])
            except KeyError:
                logger.warn("Couldn't find account for person %s (group %s)",
                            row['person_id'], groupname)
        fill_group(groupname, members, remove_others)
    logger.debug("institutt_grupper done")

def studieprog_grupper(fsconn, remove_others=False):
    """Create and populate groups for active study programs that is defined in FS."""
    groups = set()
    kullgroups = set()
    for x in fs.info.list_studieprogrammer():
        if x['status_utgatt'] == 'J':
            logger.debug("Studieprogram %s is expired, skipping.", x['studieprogramkode'])
            continue
        # create all connected kull-groups and update memeberships
        kullgroups.update(kull_grupper(fsconn, x['studieprogramkode']))

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
        groups.add(grp.entity_id)

        # studieprog-group is either found or created. checking memberships
        members = set()
        for x in fs.undervisning.list_studenter_studieprog(x['studieprogramkode']):
            fnr = "%06d%05d" % (int(x['fodselsdato']), int(x['personnr']))
            # all memberships are based on primary account
            try:
                members.add(fnr2primary[fnr])
            except KeyError:
                logger.error("Person %s not found, or no primary account", fnr)
                continue
        fill_group(grp_name, members, remove_others)
    # delete old groups
    if remove_others:
        if groups:
            delete_old_groups(match='studieprogram-%', active=groups)
        if kullgroups:
            delete_old_groups(match='kull-%-%-%-%', active=kullgroups)

def kull_grupper(fsconn, studieprogramkode, remove_others=False):
    groups = set()
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
        groups.add(grp.entity_id)

        # check if the group is tagged for export to LMS, tagg if not
        if not grp.has_spread(const.spread_lms_group):
            grp.add_spread(const.spread_lms_group)
            logger.debug("Added spread to LMS for kull group %s", grp_name)
            try:
                grp.write_db()
            except db.DatabaseError, m:
                raise Errors.CerebrumError, "Database error: %s" % m
        # update memberships in kull-group
        members = set()
        for x in fs.undervisning.list_studenter_kull(studieprogramkode, x['terminkode'], x['arstall']):
            fnr = "%06d%05d" % (int(x['fodselsdato']), int(x['personnr']))
            try:
                members.add(fnr2primary[fnr])
            except KeyError:
                logger.error("Person %s not found, or no primary account", fnr)
                continue
        fill_group(grp_name, members, remove_others)
    return groups

def undervisningsmelding_grupper(fsconn, remove_others=False):
    groups = set()
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
        groups.add(grp.entity_id)

        # update memberships in emne-groups
        members = set()
        for y in fs.undervisning.list_studenter_underv_enhet(x['institusjonsnr'], 
                                                             x['emnekode'],
                                                             x['versjonskode'], 
                                                             x['terminkode'], 
                                                             x['arstall'], 
                                                             x['terminnr']):
            fnr = "%06d%05d" % (int(y['fodselsdato']), int(y['personnr']))
            try:
                members.add(fnr2primary[fnr])
            except KeyError:
                logger.error("Person %s not found, or no primary account", fnr)
                continue
        fill_group(grp_name, members, remove_others)
    # delete old groups
    if remove_others and groups:
        delete_old_groups(match='emne-%-%-%', active=groups)

def delete_old_groups(match, active):
    """Go through the database and delete old groups that does not match any
    of the given active groups."""
    if not match or match == '*' or match == '%':
        raise Exception('Want to delete all groups? Given match: %s' % match)
    if len(active) <= 0:
        raise Exception("No active groups, can't delete them all")
    for row in grp.search(name=match):
        if row['group_id'] in active:
            continue
        logger.debug("Deleting group: %s" % row['name'])
        grp.clear()
        grp.find(row['group_id'])
        grp.delete()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                                   ['help', 'remove',
                                    'dryrun'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    global fs, pe2primary, fnr2primary
    dryrun = False
    remove_others = False

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--remove'):
            remove_others = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    # cache the primary accounts
    pe2primary = dict((r['person_id'], r['account_id']) for r in
                      acc.list_accounts_by_type(primary_only=True))
    # TODO: only get fnr from system_fs?
    fnr2primary = dict((r['external_id'], pe2primary[r['entity_id']]) for r in
                       person.list_external_ids(id_type=const.externalid_fodselsnr)
                       if pe2primary.has_key(r['entity_id']))

    fsdb = Database.connect(user=cereconf.FS_USER,
                            service=cereconf.FS_DATABASE_NAME,
                            DB_driver='cx_Oracle') 
    fs = FS(fsdb)

    logger.info("Updating studieprogram groups")
    studieprog_grupper(fs, remove_others)

    logger.info("Updating instittut groups")
    institutt_grupper(remove_others)

    logger.info("Updating emne/underv.enh groups")
    undervisningsmelding_grupper(fs, remove_others)
    
    if dryrun:
        logger.info("All done, rolled back changes")
        db.rollback()
    else:
        logger.info("All done, commiting to database")
        db.commit()

if __name__ == '__main__':
    main()
