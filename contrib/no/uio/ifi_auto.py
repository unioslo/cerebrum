#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2005 University of Oslo, Norway
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

"""Create e-mail addresses and filegroups for the courses at Dept. of
Informatics.
"""

from __future__ import unicode_literals

import sys
import getopt
import re
import time
from six import text_type

from mx import DateTime
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules import PosixGroup


db = co = logger = group_creator = dryrun = None


def get_email_target_and_address(address):
    ea = Email.EmailAddress(db)
    try:
        ea.find_by_address(address)
    except Errors.NotFoundError:
        return (None, None)
    et = Email.EmailTarget(db)
    et.find(ea.email_addr_target_id)
    return (et, ea)


def delete_email_address(address):
    et, ea = get_email_target_and_address(address)
    if et is None:
        logger.debug("Would delete <%s>", address)
        return
    logger.info("Deleting <%s>", address)

    # We can't delete this EA, if there is an epat attached to it.
    # Before we can drop ea, remove epat (or we'll get constraint violation
    # from the db)
    try:
        epat = Email.EmailPrimaryAddressTarget(db)
        epat.find(ea.email_addr_target_id)
        epat.delete()
        logger.debug("Deleted *primary* address <%s>", address)
    except Errors.NotFoundError:
        pass

    ea.delete()
    for r in et.get_addresses():
        logger.info("There are addresses left")
        return
    logger.debug("Deleting target as well")
    et.delete()


def update_email_address(address, group):
    et, ea = get_email_target_and_address(address)
    if et:
        if et.email_target_type != co.email_target_multi:
            logger.error("Wrong existing target type for <%s>", address)
            return
        if et.email_target_entity_id == group.entity_id:
            logger.debug("Up-to-date <%s>", address)
            return
        et.email_target_entity_id = group.entity_id
        logger.info("Updating <%s>", address)
        et.write_db()
    else:
        et = Email.EmailTarget(db)
        try:
            et.find_by_target_entity(group.entity_id)
            logger.info("Added address <%s>", address)
        except Errors.NotFoundError:
            et.populate(co.email_target_multi,
                        target_entity_type=co.entity_group,
                        target_entity_id=group.entity_id)
            et.write_db()
            logger.info("Created <%s>", address)
        ed = Email.EmailDomain(db)
        lp, dom = address.split('@')
        ed.find_by_domain(dom)
        ea = Email.EmailAddress(db)
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()


def find_leaf(group):
    target_group = None
    for member in group.search_members(group_id=group.entity_id):
        member_type = int(member["member_type"])
        member_id = int(member["member_id"])

        if member_type == co.entity_account:
            return group
        elif member_type == co.entity_group:
            g = get_group(member_id)
            if re.search(r'-sek(:\d|$)', g.group_name):
                continue
            # if there was another group member, we shouldn't recurse.
            if target_group:
                return group
            else:
                target_group = g
    # if group passed as argument has _no_ members, return None
    if target_group is None:
        return target_group
    else:
        return find_leaf(target_group)
# end find_leaf


def sync_email_address(address, group):
    if group is None:
        delete_email_address(address)
    else:
        update_email_address(address, group)

# the horrors, the horrors.
# http://www.uio.no/for-ansatte/arbeidsstotte/sta/enheter/mn/institutter/ifi/epostlister/


def shorten_course_name(course):
    fgname = course
    fgname = fgname.replace("matinf", "mi", 1)
    fgname = fgname.replace("infmat", "mi", 1)
    fgname = fgname.replace("infverk", "iv", 1)
    fgname = fgname.replace("humit", "hi", 1)
    # there are currently no MODxxxx courses, perhaps they won't return.
    # so I reuse the "im" abbreviation for MED-INFxxxx
    fgname = fgname.replace("medinf", "im", 1)
    fgname = fgname.replace("mod", "im", 1)
    fgname = fgname.replace("infps", "ip", 1)
    # INFxxx used to stay as infxxx, but there won't be any more three digit
    # codes, so we change it to just "i" unconditionally.
    fgname = fgname.replace("inf", "i", 1)
    fgname = fgname.replace("in", "in", 1)
    fgname = fgname.replace("dig", "id", 1)
    fgname = fgname.replace("tool", "it", 1)
    return fgname[:6]


def convert_activitynumber(act):
    # support for TVI has not been added, it will probably not return

    if act == 'grl':
        return 'g'      # the filegroup for all the teachers
    elif act in range(200, 300):
        delim = 'p'     # activity for profession students
        act = act % 100
    elif act in range(300, 400):
        delim = 'm'     # activity MOD students
        act = act % 100
    else:
        delim = '-'
    act -= 1
    if act < 26:
        return delim + "%c" % (ord('a') + act)
    else:
        return "%c%c" % (ord('a') + act/26, ord('a') + act % 26)


def make_filegroup_name(course, act, names):
    """Return a name which can be used for a filegroup.  If the group
    would duplicate a different filegroup, return None.

    """
    # If there is both a 3000 and a 4000 course, they are guaranteed to
    # have the same teachers.  This could be a HUMIT course, too.
    m = re.search(r'(.*)4(\d{3})(\D*)$', course)
    if m:
        if m.group(1) + '3' + m.group(2) + m.group(3) in names:
            return None

    # HUMITxxxxMN and HUMITxxxx are the same.  We prefer the long
    # version with 'MN' since the teachers happen to be registered
    # there at the time of writing (FIXME).
    m = re.search(r'^(humit\d{4})$', course)
    if m:
        if m.group(1) + 'mn' in names:
            return None
    return names[course] + convert_activitynumber(act)


def add_members(gname, new_members):
    """Add the new members to existing group gname.

    This is not a sync, so other members are left alone. The new_members is a
    dict with group_id as key. The value for each key is arbitrary."""

    group = get_group(gname)
    for memb in group.search_members(group_id=group.entity_id,
                                     member_type=co.entity_group):
        member_id = int(memb["member_id"])
        if member_id in new_members:
            del new_members[member_id]
    for memb in new_members.keys():
        logger.debug("Adding %s to %s", get_group(memb).group_name, gname)
        if not group.has_member(memb):
            group.add_member(memb)
    group.write_db()
# end add_members


def sync_filegroup(fgname, group, course, act):
    posix_group = PosixGroup.PosixGroup(db)
    # Make the group last a year or so.  To avoid changing the database
    # every night, we only change expire date if it has less than three
    # month to live.
    expdate = DateTime.TimestampFromTicks(int(time.time() + 12*31*24*3600))
    refreshdate = DateTime.TimestampFromTicks(int(time.time() + 3*31*24*3600))
    try:
        fgroup = get_group(fgname)
    except Errors.NotFoundError:
        logger.info("Created new file group %s", fgname)
        posix_group.populate(group_creator, co.group_visibility_all, fgname,
                             "Gruppelærere %s gruppe %s" %
                             (course.upper(), act),
                             expire_date=expdate)
        posix_group.write_db()
    else:
        posix_group.find(fgroup.entity_id)
        # make sure the group is alive
        if posix_group.expire_date and posix_group.expire_date < refreshdate:
            logger.info("Extending life of %s from %s to %s", fgname,
                        posix_group.expire_date, refreshdate)
            posix_group.expire_date = expdate
            posix_group.write_db()
    uptodate = False
    for row in posix_group.search_members(group_id=posix_group.entity_id,
                                          member_filter_expired=False):
        member_type = int(row["member_type"])
        member_id = int(row["member_id"])
        if member_type != co.entity_group:
            logger.info("Removing member %d from %s", member_id, fgname)
            posix_group.remove_member(member_id)
        elif member_id != group.entity_id:
            logger.info("Removing group member %d from %s", member_id, fgname)
            posix_group.remove_member(member_id)
        else:
            uptodate = True
    if not uptodate:
        logger.info("Adding %s to %s", group.group_name, fgname)
        if not posix_group.has_member(group.entity_id):
            posix_group.add_member(group.entity_id)

    # finally check the spread.  we leave any additionally added spreads
    # alone.
    uptodate = False
    for r in posix_group.get_spread():
        if int(r['spread']) == int(co.spread_ifi_nis_fg):
            uptodate = True
            break
    if not uptodate:
        logger.info("Adding NIS_fg@ifi to %s", fgname)
        posix_group.add_spread(co.spread_ifi_nis_fg)
    return posix_group


def process_groups(super, fg_super):
    # make a note of what filegroups are automatically maintained
    auto_fg = {}
    try:
        fg_super_gr = get_group(fg_super)
    except Errors.NotFoundError:
        # first time we run this
        fg_super_gr = Factory.get('Group')(db)
        fg_super_gr.populate(group_creator, co.group_visibility_internal,
                             fg_super, "Ikke-eksporterbar gruppe.  Hvilke "
                             "filgrupper som er automatisk opprettet som "
                             "følge av Ifi-automatikk")
        fg_super_gr.write_db()
    else:
        for row in fg_super_gr.search_members(group_id=fg_super_gr.entity_id,
                                              member_type=co.entity_group,
                                              member_filter_expired=False):
            auto_fg[int(row["member_id"])] = True

    # fetch super group's members and update accordingly
    todo = {}
    vortex_access = {}
    # short_name contains the shortened name for every known course
    short_name = {}
    start_group = get_group(super)
    for row in start_group.search_members(group_id=start_group.entity_id,
                                          member_type=co.entity_group,
                                          member_filter_expired=False):
        member_id = int(row["member_id"])

        group = get_group(member_id)
        if group.group_name.startswith(('sinf', 'sin')):
            continue
        course = act = None
        m = re.match(r'g(\w+)-(\d+)$', group.group_name)
        if m:
            course = m.group(1)
            act = int(m.group(2))
            # activity 0 is the course itself
            if act == 0:
                vortex_access[member_id] = True
            # this group often has a single member which is a
            # different group, so get rid of needless indirection.
            leaf = find_leaf(group)
        else:
            m = re.match(r'g(\w+)$', group.group_name)
            if m:
                course = m.group(1)
                act = 'grl'
            # we don't want to recurse in this case, we might end up
            # with a leaf node which has already been assigned a
            # different e-mail address.  this would trigger a
            # constraint.
            #
            # FIXME: handle the case where a single e-mail target is
            # in charge of more than one group.
            leaf = get_group(group.group_name)
        if course:
            sync_email_address("%s-%s@ifi.uio.no" % (course, act), leaf)
            if course not in short_name:
                short_name[course] = shorten_course_name(course)
            if leaf and act:
                todo["%s-%s" % (course, act)] = (course, act, leaf)

    for course, act, group in todo.values():
        fgname = make_filegroup_name(course, act, short_name)
        if fgname is None:
            logger.debug("Skipping %s-%s, it is an alias", course, act)
            continue
        fgroup = sync_filegroup(fgname, group, course, act)
        if fgroup.entity_id in auto_fg:
            del auto_fg[fgroup.entity_id]
        else:
            logger.info("New automatic filegroup %s for %s-%s",
                        fgname, course, act)

            if not fg_super_gr.has_member(fgroup.entity_id):
                fg_super_gr.add_member(fgroup.entity_id)

    add_members("ifivtx", vortex_access)

    # the groups in auto_fg are obsolete, and we remove all members.  we
    # will however keep the PosixGroup around, since the files still
    # exist on disk, and it is painful if the gid changes every time a
    # course is held (they are usually held either during Spring or
    # Autumn, so half the year they are invalid).
    for fgname in auto_fg:
        fgroup = get_group(fgname)
        for row in fgroup.search_members(group_id=fgroup.entity_id,
                                         member_filter_expired=False):
            logger.info("Remove %s %d from obsolete filegroup %s",
                        co.EntityType(row["member_type"]),
                        row["member_id"], fgroup.group_name)
            fgroup.remove_member(row["member_id"])

        fgroup.write_db()
# end process_groups


def get_group(id):
    gr = Factory.get('Group')(db)
    if isinstance(id, text_type):
        gr.find_by_name(id)
    else:
        gr.find(id)
    return gr


def get_account(name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    return ac


def main():
    global db, co, logger, group_creator, dryrun

    db = Factory.get('Database')()
    db.cl_init(change_program='ifi_auto')
    co = Factory.get('Constants')(db)
    logger = Factory.get_logger("cronjob")
    dryrun = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], '?',
                                   ['dryrun', 'help'])
    except getopt.GetoptError:
        usage()
    for opt, val in opts:
        if opt == '--dryrun':
            dryrun = True
        if opt in ('-?', '--help'):
            usage(0)

    supergroup = "internal:uio.no:fs:{autogroup}"
    fg_supergroup = "internal:uio.no:fs:{ifi_auto_fg}"
    group_creator = get_account(cereconf.INITIAL_ACCOUNTNAME).entity_id
    process_groups(supergroup, fg_supergroup)
    if not dryrun:
        logger.debug("commit...")
        db.commit()
    logger.info("All done")


def usage(exitcode=64):
    print """Usage: ifi_auto.py [options]
    Update e-mail addresses and filegroups associated with courses
    taught at Deptartment of Informatics.

    Options:
        --dryrun: don't commit changes to database
        --logger-name={console|cronjob}
        --logger-level={debug|info|warning|error}
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
