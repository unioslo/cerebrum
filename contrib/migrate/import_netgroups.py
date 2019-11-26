#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2007 University of Oslo, Norway
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

__doc__ = """Usage: %s

    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    -s, --spread  : Spread that new groups should have
    -h, --help    . Print this message and exit
    
    This program imports historical data about file and net groups
    from. The script will attempt to assign the given (option) spread
    to a group, also creating the group if it is not already
    registered.

    The file read needs to be formated as:
    <gname>:<desc>:<mgroup*|maccount*>

    gname - name of the group to be registered/updated
    desc - description of the group (usually what it is used for)
    mgroup - name(s) of group(s) that are members 
    maccount - user names of the groups account members

    * - zero or more, comma-separated

    Any lines not formatted like this are disregarded in their
    entirity.
    
""" % __file__.split("/")[-1]

 
import string
import getopt
import sys
import time
from sets import Set

import cereconf

from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _SpreadCode


## TODO: this is _wrong_.
## What should be done is to find which constraints Cerebrum puts on
## group names an implement the function valid_groupname according to
## that.
## Another issue to consider is if the end system groups are exported
## to have more strict constraints than Cerebrum. It would probably be
## a good idea to create a cereconf variable to set the character set
## allowed.
valid_groupname_chars = string.ascii_letters + string.digits + 'æÆøØåÅ-_. '

unknown_entities = {}

db = Factory.get('Database')()
db.cl_init(change_program='import_groups')
constants = Factory.get('Constants')(db)
logger = Factory.get_logger("console")

account_init = Factory.get('Account')(db)
account_init.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
default_creator_id = account_init.entity_id

person = Factory.get('Person')(db)
group = Factory.get('Group')(db)
account_member = Factory.get('Account')(db)
group_member = Factory.get('Group')(db)

dryrun = False


def valid_groupname(name):
    """Check if groupname is valid.
    
    Two criterias must be met:
    1. The name is a subset of the legal characters
    2. name must not begin or end with whitespace, or have 2 or more
       contiguous whitespce in the middle.

    Return True if criterias are met, False otherwise.
    """
    # White space is allowed, but not in the start or end of the
    # name. 2 or more whitespce is also a problem because of LDAP
    if name.startswith(' ') or name.endswith(' ') or name.count('  ') > 0:
        logger.error("Group name cannot start or end with <space>, " +
                     "or have 2 or more contiguous spaces. " +
                     "Skipping group '%s'" % name)
        return False
    if not Set(name).issubset(Set(valid_groupname_chars)):
        logger.error("Invalid character found in groupname '%s'. Skipping" %
                     name)
        return False
    return True


def read_filelines(infile):
    """Reads file and does basic verification of contents. Returns an
    array consisting of group-data, where each entry is a dictionary
    containing group-name, group description and a string representing
    group memberships.

    """    
    group_data = []

    stream = open(infile, 'r')
    for line in stream:
        line = line.rstrip('\r\n')
        logger.debug5("Processing line: '%s'", line)

        fields = string.split(line.strip(), ":")
        if len(fields) < 3:
            logger.error("Bad line: %s. Skipping", line)
            continue

        current_group = {}
        current_group['name'] = fields[0]
        current_group['description'] = fields[1]
        current_group['members'] = fields[2]

        # Validity checks for groupnames. Invalids will NOT be imported to Cerebrum
        if current_group['name'] == "":
            logger.error("Empty groupname in line '%s'. Skipping" % line)
            continue
        if not valid_groupname(current_group['name']):
            continue

        group_data.append(current_group)

    return group_data


def create_group(groupname, description, spread):
    """Create group based on given data if the group doesn't exist
    already. For all groups, add 'spread' if the groups doesn't have
    that spread already.
    """
    logger.debug("Processing group: name=%r (desc=%r)", groupname, description)

    try:
        group.clear()
        group.find_by_name(groupname)
        logger.debug("Group '%s' exists.", groupname)
    except Errors.NotFoundError:
        group.populate(
            creator_id=default_creator_id,
            visibility=constants.group_visibility_all,
            name=groupname,
            description=description,
            expire_date=time.strftime("%Y-%m-%d", time.localtime()),
            group_type=constants.group_type_unknown)
        group.write_db()
        if not dryrun:
            db.commit()
            logger.info("Created group '%s'.", groupname)

    if not group.has_spread(int(spread)):
        group.add_spread(int(spread))
        group.write_db()
        if not dryrun:
            db.commit()
            logger.info("Added spread '%s' to group '%s'.", spread, groupname)


def assign_memberships(groupname, members):
    """Assign membership in groups for groups and users.

    The function uses a cascading system for looking up entitites
    represented by the name given for a particular potential member,
    checking in the following order:

    - Users with the given name as username.
    - Users with the given name as an external id, typically names
      that have been 'cleaned up'.
    - Groups with the given name as groupname.

    Note that this function only assigns memberships for the given
    members to the given group; it does not remove any users that
    already might be in the group.

    """
    if members == "":
        logger.warn("Group '%s' has no members" % groupname)
        return
    
    member_list = string.split(members.strip(),",")
    
    group.clear()
    try:
        group.find_by_name(groupname)
    except Errors.NotFoundError:	
        logger.error("Unable to find group '%s'; why wasn't it created earlier?" %
                     groupname)
        return
        
    logger.debug("Adding members to group: '%s'" % groupname)

    for member in member_list:
        member = member.strip()
        logger.debug("Looking at potential member: '%s'" % member)
        addee = None
        entity_type = None

        # Check for entries in the "external_id"-table first, since
        # anyone who is listed there will have an updated username
        # that we wish to use instead of the potentially old one we're
        # looking at now.
	try:
            person.clear()
            person.find_by_external_id(constants.externalid_uname, member.lower())
            # this is not the most robust code, but it should work for all person objects available
            # at this point 
            tmp = person.get_accounts()
            if len(tmp) == 0:
                logger.warn("Skipping, no valid accounts found for '%s'" % (member.lower()))
                continue
            account_id = int(tmp[0]['account_id'])
            account_member.clear()
            account_member.find(account_id)
            addee = account_member
            entity_type = constants.entity_account
            logger.info("Found account '%s' for user with external name '%s'" % (addee.account_name, member.lower()))
	except Errors.NotFoundError:
            logger.warn("Didn't find user with external name '%s'" % member.lower())
            try:
                account_member.clear()
                account_member.find_by_name(member.lower())
                addee = account_member
                entity_type = constants.entity_account
                logger.debug("Found account '%s' for user with name '%s'" % (addee.account_name, member.lower()))
            except Errors.NotFoundError:
                logger.warn("Didn't find user with name '%s'" % member.lower())
                try:
                    group_member.clear()
                    group_member.find_by_name(member)
                    addee = group_member
                    entity_type = constants.entity_group
                except Errors.NotFoundError:
                    logger.debug("Didn't find group with name '%s'", member)
                    logger.error("Trying to assign membership for a non-existing " +
                                 "entity '%s' to group '%s'" % (member, groupname))
                    unknown_entities[member] = 1 # Add to dict, so we can report all later
                    continue
            
        if not group.has_member(addee.entity_id):
            group.add_member(addee.entity_id)

            group.write_db()
            if not dryrun:
                db.commit()
                logger.info("Added '%s' to group '%s'.", member, groupname)
        else:
            logger.debug("%s '%s' already member of  group '%s'." %
                          (entity_type, member, groupname))
            

def usage():
    print __doc__


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:ds:h',
                                   ['file=', 'dryrun', 'spread=', 'help'])
    except getopt.GetoptError:
        usage()

    opt_spread = None
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            global dryrun
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
	elif opt in ('-s','--spread'):
	    opt_spread = val
        elif opt in ('-h', '--help'):
            usage()
            sys.exit(0)

    try:
        spread = getattr(constants, opt_spread)
        if not isinstance(spread, _SpreadCode):
            raise AttributeError
    except AttributeError:
        logger.error("Unable to find valid spread named '%s'" % opt_spread)
        sys.exit(1)

    groups = read_filelines(infile)

    # First all groups are created...
    for current_group in groups:
        create_group(current_group['name'], current_group['description'], spread)

    # ... then assign memberships in them
    # Important since groups can be members of groups
    for current_group in groups:
        assign_memberships(current_group['name'], current_group['members'])

    if unknown_entities:
        unknown_entities_keys = unknown_entities.keys()
        unknown_entities_keys.sort()
        logger.error("The following enitities were assigned memberships, " +
                     "but are unknown to Cerebrum: '%s'" % "', '".join(unknown_entities_keys))


if __name__ == '__main__':
    main()
    
