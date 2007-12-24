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
cerebrum-sites/doc/intern/felles/utviling/auto-grupper-spesifikasjon.rst.

A few salient points:

* This script synchronizes (i.e. creates, changes memberships, deletes)
  several groups based on the information already found in
  Cerebrum. Technically, it duplicates information otherwise available;
  however having these groups will make a number of tasks considerably easier.

* All such automatic groups are tagged with a special trait
  (trait_auto_group). Only such automatic groups can have this trait. Beware!
  If you give this trait to *any* other group, it will be collected by this
  script and probably deleted (as no OU would be 'associated' with it). 

* Some groups have people as members (person_ids); others have other automatic
  groups as members.

* ansatt@<sko>, ansatt_vitenskapelig@<sko>, ansatt_tekadm@<sko>,
  ansatt_bilag@<sko> have person_id as members. The contain the employees (of
  the given type) at the specified OU. If a person_id is a member of
  ansatt_vitenskapelig, ansatt_tekadm or ansatt_bilag, (s)he is also a member
  of ansatt@<sko>.

* alle_ansatte@<sko1> are 'metagroups' in a sense. They contain other employee
  groups (specifically ansatt@<sko2>, where sko2 is a child of sko1 in the
  specified hierarchy). At the very least alle_ansatte@<sko1> will have one
  member -- ansatt@<sko1>. Should sko1 have any child OUs with employees, the
  for each such child OU sko2, alle_ansatte@<sko1> will have a member
  ansatt@<sko2>.
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





logger = Factory.get_logger("cronjob")
database = Factory.get("Database")()
database.cl_init(change_program="pop-auto-groups")
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



def sko2ou_id(sko):
    pass



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



def ou_id2parent_info(ou_id, perspective):
    """Similar to L{ou_id2ou_info}, except return info for the parent.


    @type ou_id: basestring
    @param ou_id:
      ou_id for the OU in question. We look up its parent.

    @type perspective: Cerebrum constant
    @param perspective:
      Perspective for parent information.

    @rtype: dict
    @return:
      Just like L{ou_id2ou_info}.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        parent_id = ou.get_parent(perspective)
        # If we are our own parent, pretend we don't have any.
        if ou_id == parent_id:
            return None
        return ou_id2ou_info(parent_id)
    except Errors.NotFoundError:
        return None

    # NOTREACHED
    assert False
# end ou_id2parent_info    
ou_id2parent_info = simple_memoize(ou_id2parent_info)    



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
        group_name = row["name"]
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

    @rtype: int or long
    @return:
      Group id for the group with name group_name. This function also updates
      current_groups.
    """
    
    if group_name not in current_groups:
        group = Factory.get("Group")(database)
        group.populate(get_create_account_id(),        
                       constants.group_visibility_internal,
                       group_name,
                       description)
        group.write_db()
        # before committing traits we need an existing group_id
        group.populate_trait(constants.trait_auto_group)
        group.write_db()

        logger.debug("Created a new auto group. Id=%s, name=%s, description=%s",
                     group.entity_id, group_name, description)
        current_groups[group_name] = group.entity_id

    return current_groups[group_name]
# end group_name2group_id



def employee2groups(row, current_groups, perspective):
    """Return groups that arise from the affiliation in row.

    A person's affiliation, represented by a db row, decides which groups this
    person should be a member of. Additionally, some of these memberships
    could trigger additional memberships (check the documentation for
    alle_ansatte@<sko>).

    @type row: A db_row instance
    @param row:
      A db_row representing one affiliation for one person.

    @type current_groups: dict
    @param current_groups:
      Return value of L{find_all_auto_groups}.

    @type perspective: Cerebrum constant
    @param perspective:
      Perspective for OU-hierarchy queries.

    @rtype: sequence
    @return:
      A sequence of triples (x, y, z), where
        - x is the member id (entity_id)
        - y is the member type (entity_person, entity_group, etc.)
        - z is the group id where x is to be member.

      An empty sequence is returned if no memberships can be derived. The
      reason for this complexity is that an 'employment' represented by a row
      may give rise to memberships where person_id does not participate.
    """

    person_id = row["person_id"]
    ou_id = row["ou_id"]
    ou_info = ou_id2ou_info(ou_id)
    if not ou_info:
        logger.warn("Missing ou information for ou_id=%s "
                    "(OU quarantined or missing); person_id=%s",
                    ou_id, person_id)
        return list()

    affiliation = int(row["affiliation"])
    status = int(row["status"])

    suffix = "@%s" % ou_info["sko"]
    result = list()
    #
    # The employees are members of certain groups.
    if affiliation == constants.affiliation_ansatt:
        # First, person_id is a member of ansatt@sko.
        employee_group_id = group_name2group_id("ansatt" + suffix,
                                                "Tilsatte ved "+ou_info["name"],
                                                current_groups)
        result.append((person_id, constants.entity_person, employee_group_id))
        # Then, ansatt@sko is a member of alle_ansatte@sko
        scoped_name = "alle_ansatte" + suffix
        scoped_group_id = group_name2group_id(
                   scoped_name,
                   ("Tilsatte ved %s og underordnede organisatoriske enheter" % 
                    ou_info["name"]),
                   current_groups)
        result.append((employee_group_id,
                       constants.entity_group,
                       scoped_group_id))
        # And, naturally, ansatt@sko, is a direct member of alle_ansatte@parentsko
        parent_info = ou_id2parent_info(ou_id, perspective)
        if parent_info:
            parent_name = "alle_ansatte@" + parent_info["sko"]
            scoped_parent_id = group_name2group_id(
                parent_name,
                ("Tilsatte ved %s og underordnede organisatoriske enheter" %
                 parent_info["name"]),
                current_groups)
            result.append((employee_group_id,
                           constants.entity_group,
                           scoped_parent_id))
        else:
            logger.warn("Missing parent info for OU id=%s, sko=%s, name=%s. "
                        "%s will not be a member of any parent group",
                        ou_id, ou_info["sko"], ou_info["name"],
                        scoped_name)
        
    if status == constants.affiliation_status_ansatt_vitenskapelig:
        result.append(
            (person_id,
             constants.entity_person, 
             group_name2group_id("ansatt_vitenskapelig" + suffix,
                                 "Vitenskapelige tilsatte ved "+ou_info["name"],
                                 current_groups)))
    elif status == constants.affiliation_status_ansatt_tekadm:
        result.append(
            (person_id,
             constants.entity_person,
             group_name2group_id("ansatt_tekadm" + suffix,
                                 "Teknisk-administrativt tilsatte ved " +
                                 ou_info["name"],
                                 current_groups)))
    elif status == constants.affiliation_status_ansatt_bil:
        result.append(
            (person_id,
             constants.entity_person,
             group_name2group_id("ansatt_bilag" + suffix,
                                 "Bilagslønnede ved " + ou_info["name"],
                                 current_groups)))

    return result
# end employee2groups



def populate_groups_from_rule(person_generator, row2groups, current_groups,
                              new_groups):
    """Sweep all the people from generator and assign group memberships.

    There may be several rules for building all of the groups. For each rule,
    this functions assigns proper memberships to new_groups. Once we have
    finished processing the rules, we can synchronize the in-memory data
    structure with the database.

    @type person_generator:
      Generator (or a function returning a sequence) of db_rows. 
    @param person_generator:
      Next db-row 'source' to process. Calling this yields something we can
      iterate across. The items in the sequence should be db_rows (or
      something which emulates them, like a dict)

    @type row2groups: callable
    @param row2groups:
      Function that converts a row returned by L{person_generator} to a list
      of memberships. Calling row2groups on any row D returned by
      L{person_generator} returns a list of triples (x, y, z) (cf.
      L{employee2groups} for a precise description of their meanings).

    @type current_groups: dict
    @param current_groups:
      Cf. L{find_all_auto_groups}.

    @type new_groups: dict
    @param new_groups:
      A dictionary mapping group_ids to membership info. Each membership info
      is a dictionary, mapping entity types to member ids. All group_ids
      referenced refer to groups existing in Cerebrum (i.e. we are guaranteed
      (at least at some isolation level) that all group_ids in this dict exist
      in Cerebrum.

      An example of this dictionary would be::

          {1: {<entity person>: set([10, 11, 12, 13]),
               <entity group>: set([20, 21, 22])}}

      ... meaning that group with id=1 has two types of members: people (with
    ids 10-13) and other groups (ids 20, 21, 22). Note that it is unlikely
    that a group would have *both* people and groups as members. It is either
    one or the other, but not both.
    """

    count = 0
    for person in person_generator():
        memberships = row2groups(person, current_groups)

        for member_id, member_type, group_id in memberships:
            # all known memberships for group_id
            d = new_groups.setdefault(group_id, dict())
            member_type = int(member_type)

            # Add the member to the membership list of the right type.
            # Typically, any given group would have either all members as
            # people or as groups.
            d.setdefault(member_type, set()).add(member_id)
            count += 1

    logger.debug("After processing rule, we have %d groups", len(new_groups))
    logger.debug("... and <= %d members", count)
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

    NB! L{groups_from_cerebrum} is modified by this function.

    @type groups_from_cerebrum: dict
    @param: Cf. L{find_all_auto_groups}.

    @type groups_from_data: dict
    @param: Cf. L{populate_groups_from_rule}.

    @rtype: type(groups_from_cerebrum)
    @return:
      Modified L{groups_from_cerebrum}.
    """

    group = Factory.get("Group")(database)
    
    for group_id, membership_info in groups_from_data.iteritems():
        try:
            group.clear()
            group.find(group_id)
            gname = group.group_name
        except Errors.NotFoundError:
            logger.warn("group_id=%s disappeared from Cerebrum.", group_id)
            continue

        # select just the entity_ids (we don't care about entity_type)
        union, intersect, diff = [[x[1] for x in seq]
                                  for seq in group.list_members()]
        if intersect or diff:
            logger.warn("Auto group id=%s name=%S has %d intersection and %d "
                        "difference members. They will be removed",
                        group_id, gname, len(intersect), len(diff))
            # auto groups are not supposed to have these.
            remove_members(group, intersect,
                           constants.group_memberop_intersection)
            remove_members(group, diff, constants.group_memberop_difference)

        # now, synch the union members. sync'ing means making sure that the
        # members of group are exactly the ones in memberset.
        union = set(union)

        # those that are not in 'union', should be added
        add_count = 0
        to_add = list()
        for member_type, members in membership_info.iteritems():
            to_add = members.difference(union)
            add_count += len(to_add)
            add_members(group, to_add, member_type,
                        constants.group_memberop_union)

        # those that are in 'union', but not in membership_info, should be
        # removed.
        to_remove = union.copy()
        for member_type, members in membership_info.iteritems():
            to_remove = to_remove.difference(members)
        remove_members(group, to_remove, constants.group_memberop_union)

        if gname not in groups_from_cerebrum:
            logger.debug("New group id=%s, name=%s", group_id, gname)
        else:
            del groups_from_cerebrum[gname]
            logger.debug("Existing group id=%s, name=%s", group_id, gname)

        if to_remove or to_add:
            logger.debug("Updated group id=%s, name=%s; added=%d, removed=%d",
                         group_id, gname, add_count, len(to_remove))
        else:
            logger.debug("No changes to group id=%s, name=%s", group_id, gname)

        # It's harmless when no changes are made, and placing it here makes
        # the code simpler.
        group.write_db()

    return groups_from_cerebrum
# end synchronise_groups



def empty_defunct_groups(groups_from_cerebrum):
    """Help synchronise in-memory data structure with Cerebrum db.

    When employment information disappears (expires, or is otherwise removed
    from Cerebrum), some previously existing groups may loose all their
    members. Such groups will no longer be in the most recent data structure
    built by this script, but they'd still have members in Cerebrum. Thus, all
    such members are removed by this script.

    @type groups_from_cerebrum: dict
    @param groups_from_cerebrum:
      A mapping returned by L{find_all_auto_groups} minus all of the groups
      removed by previous functions (like L{synchronise_groups}).
    """

    logger.debug("Emptying defunct groups")
    group = Factory.get("Group")(database)
    # These are groups that would not have existed, given today's data
    # situation. What should we do with them?
    for group_name, group_id in groups_from_cerebrum.iteritems():
        logger.info("Group id=%s, name=%s should no longer have members.",
                    group_id, group_name)
        # Remove all members
        try:
            group.clear()
            group.find(group_id)
        except Errors.NotFoundError:
            logger.warn("Group id=%s, name=%s disappeared from Cerebrum",
                        group_id, group_name)
            continue

        logger.info("Removing all members from group id=%s, name=%s",
                    group_id, group_name)
        count = 0
        for mem_type in group.list_members():
            # select entity_ids
            members = [x[1] for x in mem_type]
            count += len(members)
            remove_members(group, members, constants.group_memberop_union)

        logger.info("Removed %d members from defunct group id=%s, name=%s",
                    count, group_id, group_name)
# end empty_defunct_groups



def delete_defunct_groups(groups):
    """Sweep all auto groups and delete those that should not be in the db.

    Each group is 'associated' via its name with an OU. When the OUs are no
    longer available (removed or quarantined), we should nuke the groups as
    well.

    The *ugly* *ugly* part here is the way groups are mapped to corresponding
    OUs. We cannot easily associate an OU with a group, and thus, OU would
    have to be deduced from the groups's name. Such an arrangement is prone to
    breakage.

    @type groups: dict
    @param groups:
      A dictionary as returned by L{find_all_auto_groups}, and subsequently
      cleared of all groups that *should* be in Cerebrum.
    """

    group = Factory.get("Group")(database)
    ou = Factory.get("OU")(database)
    logger.debug("Looking for groups to delete")

    for group_name, group_id in groups.iteritems():
        logger.debug("Considering group id=%s, name=%s for deletion",
                     group_id, group_name)
        
        try:
            group.clear()
            group.find(group_id)
        except Errors.NotFoundError:
            logger.warn("Group id=%s, name=%s disappeared.",
                        group_id, group_name)
            continue

        if '@' not in group_name:
            logger.warn("Group id=%s, name=%s has trait %s and a "
                        "non-conformant name. This should be fixed.",
                        group_id, group_name, constants.trait_auto_group)
            # IVR 2007-12-23 FIXME: Should we attempt to delete this group?
            continue

        name, sko = group_name.split("@")
        if not sko.isdigit() or len(sko) != 6:
            logger.warn("Group id=%s, name=%s has non-digit sko=%s."
                        "This should not be an auto group, but it has the "
                        "proper trait (%s)",
                        group_id, group_name, sko, constants.trait_auto_group)
            # IVR 2007-12-23 FIXME: Should we attempt to delete this group?
            continue

        fak, inst, avd = [int(x) for x in (sko[:2], sko[2:4], sko[4:])]
        try:
            ou.clear()
            ou.find_stedkode(fak, inst, avd, cereconf.DEFAULT_INSTITUSJONSNR)
            if not ou.get_entity_quarantine(only_active=True):
                logger.debug("OU id=%s sko=%s exists and is not quarantined. "
                             "Group id=%s name=%s will NOT be deleted",
                             ou.entity_id, sko, group_id, group_name)
                continue
        except Errors.NotFoundError:
            logger.info("OU for sko=%s no longer exists. "
                        "Group id=%s name=%s will be deleted.",
                        sko, group_id, group_name)

        # If we get here, then the group has to be deleted.
        group.delete()
        logger.info("Deleted group id=%s, name=%s", group_id, group_name)
# end delete_defunct_groups
    


def main():
    options, junk = getopt.getopt(sys.argv[1:],
                                  "p:d",
                                  ("perspective=",
                                   "dryrun",))

    dryrun = False
    perspective = None
    for option, value in options:
        if option in ("-p", "--perspective",):
            perspective = int(constants.OUPerspective(value))
        elif option in ("-d", "--dryrun",):
            dryrun = True

    assert perspective is not None, "Must have a perspective"
    # collect all existing auto groups
    # whatever is left here after several processing passes are groups that no
    # longer have data foundation of their existence.
    current_groups = find_all_auto_groups()
    new_groups = dict()

    # Rules that decide which groups to build.
    # Each rule is a tuple. The first object is a callable that generates a
    # sequence of db-rows that are candidates for group addition (typically
    # person_id and a few more attributes). The second object is a callable
    # that yields a sequence of groups ids, which an item returned by the
    # first callable should be a member of.
    person = Factory.get("Person")(database)
    global_rules = [
        # Employee rules (ansatt@<ou>, ansatt_vitenskapelig@<ou>, etc.)
        (lambda: person.list_affiliations(
                   affiliation=(constants.affiliation_ansatt,)),
         lambda *rest: employee2groups(perspective=perspective, *rest)),
        
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

    current_groups = synchronise_groups(current_groups, new_groups)

    # As the last step of synchronisation, empty all groups for which we could
    # find no members.
    empty_defunct_groups(current_groups)
    # And finally, from these empty groups, delete the ones that should no
    # longer exist.
    delete_defunct_groups(current_groups)

    if dryrun:
        database.rollback()
        logger.debug("Rolled back all changes")
    else:
        database.commit()
        logger.debug("Committed all changes")
# end main



if __name__ == "__main__":
    main()

