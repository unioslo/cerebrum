#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2007, 2008 University of Oslo, Norway
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

"""Synchronize several automatically maintained groups in Cerebrum.

The complete specification of this script is in
cerebrum-site/doc/intern/felles/utviling/auto-grupper-spesifikasjon.rst.

A few salient points:

* This script synchronizes (i.e. creates, changes memberships, deletes)
  several groups based on the information already found in
  Cerebrum. Technically, it duplicates information otherwise available;
  however having these groups will make a number of tasks considerably
  easier.

* All such automatic groups are tagged with a special trait. Only such
  automatic groups can have this trait.

* Some groups have people as members (person_ids); others have other automatic
  groups as members.
"""

import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
try:
    set()
except NameError:
    from Cerebrum.extlib.sets import Set as set





logger = Factory.get("cronjob")
database = Factory.get("Database")()
constants = Factory.get("Constants")(database)



def simple_memoize(callobj):
    """Memoize[1] a callable.

    [1] <http://en.wikipedia.org/wiki/Memoize>.
    
    The idea is to memoize a callable object supporting rest/optional
    arguments without placing a limit on the amount of cached pairs.

    @type callobj: callable
    @param callobj:
      An object for which callable(callobj) == True. I.e. something we can
      call (lambda, function, bound method, etc.)

    @rtype: function
    @return:
      A wrapper that caches the results of previous invocations of callobj.
    """
    
    cache = dict()
    def wrapper(*rest):
        if rest not in cache:
            cache[rest] = callobj(*rest)
        return cache[rest]
    # end wrapper

    return wrapper
# end simple_memoize


def format_sko(*rest):
    """Format stedkode in a suitable fashion.

    Institution numbers is not part of sko here.
    """
    
    assert len(rest) == 3
    return "%02d%02d%02d" % rest
# end format_sko



def ou_id2ou_info(ou_id):
    """Locate information about OU with the specied ou_id.

    We need sko and name elsewhere.

    @type ou_id: basestring
    @param ou_id:
      ou_id for the OU in question.

    @rtype: dict
    @return:
      A mapping with name and sko or None.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        if ou.get_entity_quarantine():
            return None
        
        return {"sko": format_sko(ou.fakultet, ou.institutt, ou.avdeling),
                "name": ou.name}
    except Errors.NotFoundError:
        return None

    # NOTREACHED
    assert False
# end ou_id2ou_info
ou_id2ou_info = simple_memoize(ou_id2ou_info)



def get_create_account_id():
    """Fetch account_id for group creation.

    INITIAL_ACCOUNTNAME is the obvious choice (it will be the creator_id for
    auto groups created by this script.
    """

    account = Factory.get("Account")(database)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return account.entity_id
# end get_create_account_id
get_create_account_id = simple_memoize(get_create_account_id)



def find_all_auto_groups():
    """Collect and return all groups that are administrered by this script.

    We tag all auto groups with trait_auto_group. It is the only sane and
    reliable way of gathering *all* of them later (using special name prefixes
    is too cumbersome and error prone; organising them into a hierarchy (like
    fronter groups) is a bit icky, since the tree has to be stored in a
    relational db.

    @rtype: dict
    @return:
      A mapping group_name -> group_id.
    """

    result = dict()
    entity = Factory.get("Group")(database)
    logger.debug("Collecting all auto groups")
    for row in entity.list_traits(code=constants.trait_auto_group,
                                  return_name=True):
        group_id = int(row["entity_id"])
        group_name = row["entity_name"]
        result[group_name] = group_id

    logger.debug("Collected %d existing auto groups", len(result))
    return result
# end find_all_auto_groups



def group_name2group_id(group_name, description, current_groups):
    """Look up (and create if necessary) a group by name and return its id.

    Convert a specific auto group name to a group_id. Create group if
    necessary and adorn it with proper traits.

    @type group_name: basestring
    @param group_name: Group name to look up/create.

    @type description: basestring
    @param description:
      In case a group needs creating, this will be the description registered
      in Cerebrum.

    @type current_groups: dict
    @param current_groups: Return value of L{find_all_auto_groups}.
    """
    
    if group_name not in current_groups:
        group = Factory.get("Group")(database)
        group.populate(get_create_account_id(),        
                       constants.group_visibility_internal,# FIXME: Is this correct?
                       group_name,
                       description)
        group.populate_trait(constants.trait_auto_group)
        group.write_db()
        current_groups[group_name] = group.entity_id

    return current_groups[group_name]
# end group_name2group_id



def employee2groups(row, current_groups):
    """Return groups in which a person is to be a member.

    A person's affiliation, represented by a db row, decides which groups this
    person should be a member of. If a person has several (albeit slightly
    different) affiliations, there is a possibility that same group ids would
    be returned by this function. The caller must ensure whatever is necessary
    to avoid duplicate registrations.

    @type row: A db_row instance
    @param row:
      A db_row representing one affiliation for a person.

    @type current_groups: dict
    @param current_groups:
      Return value of L{find_all_auto_groups}.
    """

    ou_info = ou_id2ou_info(row["ou_id"])
    if not ou_info:
        logger.warn("Missing ou information (sko, name) for ou_id=%s",
                    row["ou_id"])
        return []

    affiliation = int(row["affiliation"])
    status = int(row["status"])

    suffix = "@%s" % ou_info["sko"]
    result = list()
    if affiliation == constants.affiliation_ansatt:
        result.append(
            group_name2group_id("ansatt" + suffix,
                                "Tilsatte ved " + ou_info["name"],
                                current_groups))

    if status == constants.affiliation_status_ansatt_vitenskapelig:
        result.append(
            group_name2group_id(
            "ansatt_vitenskapelig" + suffix,
            "Vitenskapelige tilsatte ved " + ou_info["name"],
            current_groups))
    elif status == constants.affiliation_status_ansatt_tekadm:
        result.append(
            group_name2group_id(
            "ansatt_tekadm" + suffix,
            "Teknisk-administrativt tilsatte ved " + ou_info["name"],
            current_groups))
    elif status == constants.affiliation_status_ansatt_bil:
        result.append(
            group_name2group_id(
            "ansatt_bilag" + suffix,
            "Bilagslønnede ved " + ou_info["name"],
            current_groups))
        
    return result
# end employee2groups



def populate_groups_from_rule(person_generator, row2groups, current_groups,
                              new_groups):
    """Sweep all the people from generator and assign group memberships.

    There may be several rules for building all of the groups. For each rule,
    this functions assigns proper memberships to new_groups. Once we have
    finished processing the rules, we can synchronize the in-memory data
    structure with the database.

    @type person_generator: generator (or a function returning a sequence) of
    db_rows. 
    @param person_generator:
      Next db-row 'source' to process. Calling this yields something we can
      iterate across. The items in the sequence should be db_rows (or
      something which emulates them, like a dict)

    @type row2groups: callable
    @param row2groups:
      Function that converts a row returned by L{person_generator} to a list
      of group_ids. Calling row2groups on any row D returned by
      L{person_generator} returns a list of group ids where D['person_id']
      should be a a member. L{employee2groups} is an example of such a
      function.

    @type current_groups: dict
    @param current_groups:
      Cf. L{find_all_auto_groups}.

    @type new_groups: dict
    @param new_groups:
      A dictionary mapping group_ids to member sets. A group is created,
      before its id is inserted into this dictionary (i.e. we are guaranteed
      (at least at some isolation level) that all group_ids in this dict exist
      in Cerebrum.
    """

    count = 0
    for person in person_generator():
        group_ids = row2groups(person, current_groups)
        person_id = int(person["person_id"])
        count += 1
        
        for g_id in group_ids:
            # Add this person to the right group. We are interested in the
            # union-members only, really, so screw the rest.
            new_groups.setdefault(g_id, set()).add(person_id)

    logger.debug("After processing rule, we have %d groups", len(new_groups))
    logger.debug("... and <= %d new members", count)
# end populate_groups_from_rule        



def remove_members(group, member_sequence, operation):
    """Remove several members from a group.

    This is just a convenience function.

    @type group: Factory.get('Group') instance
    @param group:
      Group from which the members are to be removed.

    @type member_sequence: sequence
    @param member_sequence:
      A sequence with person_ids to remove from group.

    @type operation: A _GroupMembershipOpCode instance.
    @param operation:
      Membership type (union, intersection or difference).
    """

    for entity_id in member_sequence:
        group.remove_member(entity_id, operation)

    logger.debug("Removed %d members from group id=%s, name=%s",
                 len(member_sequence), group.entity_id, group.group_name)
# end remove_members



def add_members(group, member_sequence, member_type, operation):
    """Add several members to a group.

    This is just a convenience function.

    @type group: Factory.get('Group') instance
    @param group:
      Group from which the members are to be removed.

    @type member_sequence: sequence
    @param member_sequence:
      A sequence with person_ids who are to become members of L{group}.

    @type member_type: _EntityTypeCode instance
    @param member_type:
      Type of members we are introducing. Typically a person.

    @type operation: A _GroupMembershipOpCode instance.
    @param operation:
      Membership type (union, intersection or difference).
    """
    
    for entity_id in member_sequence:
        group.add_member(entity_id, member_type, operation)

    logger.debug("Added %d members to group id=%s, name=%s",
                 len(member_sequence), group.entity_id, group.group_name)
# end add_members
    


def synchronise_groups(groups_from_cerebrum, groups_from_data):
    """Synchronise current in-memory representation of groups with the db.

    The groups (through the rules) are built in-memory. This function
    synchronises the in-memory data structure with Cerebrum. For each group,
    read the membership info, compare it with groups_from_data, adjust the
    information, write_db() on the group.

    @type groups_from_cerebrum: dict
    @param: Cf. L{find_all_auto_groups}.

    @type groups_from_data: dict
    @param: Cf. L{populate_groups_from_rule}.
    """

    group = Factory.get("Group")(database)
    
    for group_id, memberset in groups_from_data.iteritems():
        try:
            group.clear()
            group.find(group_id)
            gname = group.group_name
        except Errors.NotFoundError:
            logger.warn("group_id=%s disappeared from Cerebrum. "
                        "Re-run the script?", group_id)
            continue

        union, intersect, diff = group.list_members()
        if intersect or diff:
            logger.warn("Auto group id=%s has %d intersection and %d "
                        "difference members. They will be removed",
                        group_id, len(intersect), len(diff))
            # auto groups are not supposed to have these.
            remove_members(group, intersect,
                           constants.group_memberop_intersection)
            remove_members(group, diff, constants.group_memberop_difference)

        # now, synch the union members. sync'ing means making sure that the
        # members of group are exactly the ones in memberset.
        union = set(int(x[1]) for x in union)

        to_remove = union.difference(memberset)
        to_add = memberset.difference(union)

        remove_members(group, to_remove, constants.group_memberop_union)
        add_members(group, to_add, constants.entity_person,
                    constants.group_memberop_union)

        if gname not in groups_from_cerebrum:
            logger.debug("New group id=%s, name=%s", group_id, gname)
        else:
            del groups_from_cerebrum[gname]
            logger.debug("Existing group id=%s, name=%s", group_id, gname)

        if to_remove or to_add:
            logger.debug("Updated group id=%s, name=%s; added=%d, removed=%d",
                         group_id, gname, len(to_add), len(to_remove))
            group.write_db()
        else:
            logger.debug("No changes to group id=%s, name=%s", group_id, gname)

    # These are groups that would not have existed, given today's data
    # situation. What should we do with them?
    for group_id, group_name in groups_from_cerebrum.iteritems():
        logger.info("Group id=%s, name=%s should no longer exist",
                    group.group_id, group_name)
# end synchronise_groups



def main():
    options, junk = getopt.getopt(sys.argv[1:],
                                  "p:",
                                  ("--perspective=",))

    perspective = None
    for option, value in options:
        if option in ("-p", "--perspective",):
            perspective = int(constants.OUPerspective(value))
    
    # collect all existing auto groups
    current_groups = find_all_auto_groups()
    new_groups = dict()

    # Rules that decide which groups to build.
    # Each rule is a tuple. The first object is a callable that generates a
    # sequence of db-rows that are candidates for group addition (typically
    # person_id and a few more attributes). The second object is a callable
    # that yields a sequence of groups ids, which an item returned by the
    # first callable should be a member of.
    global_rules = [
        # Employee rules (ansatt@<ou>, ansatt_vitenskapelig@<ou>, etc.)
        (lambda: person.list_affiliations(
                   affiliation=(constants.affiliation_ansatt,)),
         employee2groups),

        # Student rules
        ]
    for rule in global_rules:
        # How do we get all the people for registering in the groups?
        person_generator = rule[0]
        # Given a row with a person, which groups should he be registered in?
        row2groups = rule[1]
        # Let's go
        populate_groups_from_rule(person_generator, row2groups,
                                  current_groups, new_groups)

    synchronise_groups(current_groups, new_groups)

    # FIXME:
    # 1) remove defunct groups
    # 2) build scoped-groups
    # 3) clean up scoped-groups
# end main



if __name__ == "__main__":
    main()

        
    
        
