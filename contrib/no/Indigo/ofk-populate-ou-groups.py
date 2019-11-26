#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2009 University of Oslo, Norway
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

"""Automatically create and maintain affiliation-based groups in Cerebrum.

For each OU with a given tag/spread create and maintain
affiliation-based groups. Naming convention:
OU-ACRONYM_affiliation. Relevant OU spreads/tags are registered in
cereconf.AUTOGROUP_OU_SPREAD. Relevant affiliations are registered in
cereconf.AUTOGROUP_AFFILIATION.

* This script synchronizes (i.e. creates, changes memberships, deletes)
  groups based on the information already found in Cerebrum.
  Technically, it duplicates information otherwise available;
  however having these groups will make a number of tasks considerably easier.

* All such automatic groups are tagged with a special trait
  (trait_auto_aff). Only such automatic groups can have these
  trait. Beware! If you give these traits to *any* other group, it
  will be collected by this script and probably deleted (as no OU
  would be 'associated' with it).
  
* Members of these groups are primary account for qualified users.

"""

import getopt
import sys

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.utils.funcwrap import memoize
try:
    set()
except NameError:
    from Cerebrum.extlib.sets import Set as set


logger = Factory.get_logger("cronjob")
database = Factory.get("Database")()
database.cl_init(change_program="pop-auto-groups")
constants = Factory.get("Constants")(database)
account = Factory.get("Account")(database)
person = Factory.get("Person")(database)

def format_sko(*rest):
    """Format stedkode in a suitable fashion.

    Institution numbers is not part of sko here.
    """
    assert len(rest) == 3
    return "%02d%02d%02d" % rest
# end format_sko


def ou_id2ou_info(ou_id):
    """Locate information about the OU with the specified ou_id. Check
       for spread, we need groups only for OUs exported to Active
       Directory

       We need acronym and name elsewhere.

       @type ou_id: basestring
       @param ou_id:
         ou_id for the OU in question.

       @rtype: dict
       @return:
          A mapping with name and acronym or None, if OU is not found/is quarantined.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        if ou.get_entity_quarantine():
            return None
        if not ou.has_spread(constants.spread_ad_ou):
            return None
        return {"name": ou.get_name_with_language(name_variant=constants.ou_name,
                               name_language=constants.language_nb,
                               default=""),
                "acronym": ou.get_name_with_language(
                               name_variant=constants.ou_name_acronym,
                               name_language=constants.language_nb,
                               default=""),
                "ou_id": ou_id}
    except Errors.NotFoundError:
        return None

    # NOTREACHED
    assert False
# end ou_id2ou_info
ou_id2ou_info = memoize(ou_id2ou_info)


def get_create_account_id():
    """Fetch account_id for group creation.

    INITIAL_ACCOUNTNAME is the obvious choice (it will be the creator_id for
    auto groups created by this script.
    """

    account = Factory.get("Account")(database)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return account.entity_id
# end get_create_account_id
get_create_account_id = memoize(get_create_account_id)


def find_all_auto_groups():
    """Collect and return all groups that are administrered by this script.

    We tag all auto groups with a number of traits. It is the only sane and
    reliable way of gathering *all* of them later (using special name prefixes
    is too cumbersome and error prone; organising them into a hierarchy (like
    fronter groups) is a bit icky, since the tree has to be stored in a
    relational db.

    @rtype: dict
    @return:
      A mapping group_name -> group_id.
    """

    def slurp_data(result, trait):
        for row in entity.list_traits(code=trait):
            group_id = int(row["entity_id"])
            try:
                entity.clear()
                entity.find(group_id)
                group_name = entity.group_name
            except Errors.NotFoundError:
                logger.error("No group with entity_id=%r", group_id)
                continue
            result[group_name] = group_id

    result = dict()
    entity = Factory.get("Group")(database)
    logger.debug("Collecting all auto groups")
    slurp_data(result, constants.trait_auto_aff)

    logger.debug("Collected %d existing auto groups", len(result))
    return result
# end find_all_auto_groups


def group_name2group_id(group_name, description, current_groups, trait=NotSet):
    """Look up (and create if necessary) a group by name and return its id.

    Convert a specific auto group name to a group_id. Create the group if
    necessary and adorn it with proper traits.

    @type group_name: basestring
    @param group_name: Group name to look up/create.

    @type description: basestring
    @param description:
      In case a group needs creating, this will be the description registered
      in Cerebrum.

    @type current_groups: dict
    @param current_groups: Return value of L{find_all_auto_groups}.

    @type traits: a constant (int or basestring) or NotSet
    @param traits:
      Additional trait to adorn L{group_name} with. The trait is added *only*
      if the group is created.

    @rtype: int or long
    @return:
      Group id for the group with name group_name. This function also updates
      current_groups.
    """
    if group_name not in current_groups:
        group = Factory.get("Group")(database)
        group.populate(
            creator_id=get_create_account_id(),
            visibility=constants.group_visibility_internal,
            name=group_name,
            description=description,
            group_type=constants.group_type_unknown,
        )
        group.write_db()
        # before committing traits we need an existing group_id
        if trait != NotSet:
            # int() is just a safety mechanism to ensure that the trait
            # actually exists.
            group.populate_trait(int(constants.EntityTrait(trait)))
            group.write_db()
        if not group.has_spread(constants.spread_ad_grp):
            group.add_spread(constants.spread_ad_grp)
            group.write_db()
        logger.debug(
            "Created a new auto group. Id=%s, name=%s, description=%s",
            group.entity_id, group_name, description)
        current_groups[group_name] = group.entity_id

    return current_groups[group_name]


def employee2groups(row, current_groups, perspective):
    """Return groups that arise from the affiliation in row.

    A person's affiliation, represented by a db row, decides which groups this
    person should be a member of.

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
    person.clear()
    try:
        person.find(person_id)
    except Errors.NotFoundError:
        logger.error("Could not find person %s.", person_id)
        return list()
    primary_account_id = person.get_primary_account()
    if not primary_account_id:
        logger.error("No primary account found for %s.", person_id)
        return list()
    account.clear()
    try:
        account.find(primary_account_id)
    except Errors.NotFoundError:
        logger.error("This should never happen, could not find account %s", primary_account_id)
        return list()
    if account.is_deleted():
        logger.warn("Primary account %s is invalid, aborting membership assignement", account.account_name)
        return list()
    ou_id = row["ou_id"]
    ou_info = ou_id2ou_info(ou_id)
    if not ou_info:
        logger.warn("Missing ou information for ou_id=%s "
                    "(OU quarantined or missing); person_id=%s",
                    ou_id, person_id)
        return list()

    affiliation = int(row["affiliation"])
    prefix = "%s#" % ou_info["acronym"]
    result = list()


    # This affiliation (row) results in primary account of a person being member of
    # <acronym>#ANSATT.
    if affiliation == constants.affiliation_ansatt:
        # First, person_id is a member of ansatt@sko.
        group_name = prefix + "employee"
        employee_group_id = group_name2group_id(group_name,
                                                "Tilsatte ved " + ou_info["name"],
                                                current_groups,
                                                constants.trait_auto_aff)
        result.append((account.entity_id, constants.entity_person, employee_group_id))

    # This affiliation (row) results in primary account of a person being member of
    # <acronym>#TILKNYTTET
    if affiliation == constants.affiliation_tilknyttet:
        # First, person_id is a member of ansatt@sko.
        group_name = prefix + "affiliate"
        employee_group_id = group_name2group_id(group_name,
                                                "Tilknyttede personer ved " + ou_info["name"],
                                                current_groups,
                                                constants.trait_auto_aff)
        result.append((account.entity_id, constants.entity_person, employee_group_id))

    # This affiliation (row) results in primary account of a person being member of
    # <acronym>#ELEV.
    if affiliation == constants.affiliation_elev:
        # First, person_id is a member of ansatt@sko.
        group_name = prefix + "pupil"
        employee_group_id = group_name2group_id(group_name,
                                                "Elever ved " + ou_info["name"],
                                                current_groups,
                                                constants.trait_auto_aff)
        result.append((account.entity_id, constants.entity_person, employee_group_id))

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
      L{employee2groups} for the precise description of their meanings).

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

            # Add the member to the membership set of the right type.
            # Typically, any given group would have either all members as
            # people or as groups.
            d.setdefault(member_type, set()).add(member_id)
            count += 1

    logger.debug("After processing rule, we have %d groups", len(new_groups))
    logger.debug("... and <= %d members", count)
# end populate_groups_from_rule


def remove_members(group, member_sequence):
    """Remove several members from a group.

    This is just a convenience function.

    @type group: Factory.get('Group') instance
    @param group:
      Group from which the members are to be removed.

    @type member_sequence: sequence
    @param member_sequence:
      A sequence with person_ids to remove from group.
    """

    for entity_id in member_sequence:
        group.remove_member(entity_id)

    logger.debug("Removed %d members from group id=%s, name=%s",
                 len(member_sequence), group.entity_id, group.group_name)
# end remove_members


def add_members(group, member_sequence):
    """Add several members to a group.

    This is just a convenience function.

    @type group: Factory.get('Group') instance
    @param group:
      Group from which the members are to be removed.

    @type member_sequence: sequence
    @param member_sequence:
      A sequence with person_ids who are to become members of L{group}.
    """

    for entity_id in member_sequence:
        group.add_member(entity_id)

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
        group_members = set(int(x["member_id"]) for x in
                            group.search_members(group_id=group.entity_id))
        # now, synch the union members. sync'ing means making sure that the
        # members of group are exactly the ones in memberset.

        # those that are not in 'group_members', should be added
        add_count = 0
        to_add = list()
        for member_type, members in membership_info.iteritems():
            to_add = members.difference(group_members)
            add_count += len(to_add)
            add_members(group, to_add)

        # those that are in 'group_members', but not in membership_info,
        # should be removed.
        to_remove = group_members.copy()
        for member_type, members in membership_info.iteritems():
            to_remove = to_remove.difference(members)
        remove_members(group, to_remove)

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
        members = [x["member_id"] for x in
                   group.search_members(group_id=group.entity_id)]
        count = len(members)
        remove_members(group, members)
        logger.info("Removed %d members from defunct group id=%s, name=%s",
                    count, group_id, group_name)
# end empty_defunct_groups


def _locate_all_auto_traits():
    """Extract all automatically assigned traits from cereconf.

    cereconf.AFFILIATE_TRAITS contains a mapping for translating role ids in
    source data to trait descriptions for all automatically awarded
    traits. This function processes this mapping and returns a sequence of all
    auto traits.

    @rtype: sequence
    @return:
      A sequence of trait codes for all automatically awarded traits. The
      actual trait assignment (from role ids) happens in
      L{import_HR_person.py}. This script takes the traits and assigns group
      membersships based on them.
    """

    # IVR 2008-01-17 FIXME: This is a copy of a similar function from
    # import_HR_person.py. Duplication is bad.
    # Collect all known auto traits.
    if not hasattr(cereconf, "AFFILIATE_TRAITS"):
        return set()

    auto_traits = set()
    for trait_code_str in cereconf.AFFILIATE_TRAITS.itervalues():
        try:
            trait = constants.EntityTrait(trait_code_str)
            int(trait)
        except Errors.NotFoundError:
            logger.error("Trait <%s> is defined in cereconf.AFFILIATE_TRAITS, "
                         "but it is unknown i Cerebrum (code)", trait_code_str)
            continue

        # Check that the trait is actually associated with a person (and not
        # something else. AFFILIATE_TRAITS is supposed to "cover" person
        # objects ONLY!)
        if trait.entity_type != constants.entity_person:
            logger.error("Trait <%s> from AFFILIATE_TRAITS is associated with "
                         "<%s>, but we allow person traits only",
                         trait, trait.entity_type)
            continue

        auto_traits.add(int(trait))

    return auto_traits
# end _locate_all_auto_traits


def perform_sync(perspective, source_system):
    """Set up the environment for synchronisation and synch all groups.

    @type perspective: Cerebrum constant
    @param perspective:
      OU perspective, indicating which OU hierarchy should be searched in for
      parent-child OU relationships.

    @type source_system: Cerebrum constants
    @param source_system:
      Source system for filtering some of the Cerebrum data.
    """

    assert perspective is not None, "Must have a perspective"

    # Collect all existing auto groups. Whatever is left here after several
    # processing passes are groups that no longer have any reason to exist.
    current_groups = find_all_auto_groups()
    new_groups = dict()

    # Rules that decide which groups to build.
    # Each rule is a tuple. The first object is a callable that generates a
    # sequence of db-rows that are candidates for group addition (typically
    # person_id and a few more attributes). The second object is a callable
    # that yields a data structure indicating which group membership additions
    # should be performed; based on the db-rows generated by the first
    # callable.
    person = Factory.get("Person")(database)
    global_rules = [
        # Employee rule: (ansatt@<ou>, ansatt_vitenskapelig@<ou>, etc.)
        (lambda: person.list_affiliations(
                   affiliation=(constants.affiliation_ansatt,),
                   source_system=source_system),
         lambda *rest: employee2groups(perspective=perspective, *rest)),         
        (lambda: person.list_affiliations(
                   affiliation=(constants.affiliation_tilknyttet,),
                   source_system=source_system),
         lambda *rest: employee2groups(perspective=perspective, *rest)),         
        (lambda: person.list_affiliations(
                   affiliation=(constants.affiliation_elev,),
                   source_system=source_system),
         lambda *rest: employee2groups(perspective=perspective, *rest))         
        ]
    for rule in global_rules:
        # How do we get all the people for registering in the groups?
        person_generator = rule[0]
        # Given a row with a person, which groups should (s)he be registered in?
        row2groups = rule[1]
        # Let's go
        populate_groups_from_rule(person_generator, row2groups,
                                  current_groups, new_groups)

    current_groups = synchronise_groups(current_groups, new_groups)

    # As the last step of synchronisation, empty all groups for which we could
    # find no members.
    empty_defunct_groups(current_groups)
# end perform_sync


def perform_delete():
    """Delete all groups generated by this script.

    This functionality could be useful for testing purposes or 'one-off'
    administrative tasks.

    Since *all* autogroups have a special trait marking them, this task is
    rather easily accomplished. NB! Do not abuse this function (i.e. do NOT
    run populate-remove cycles back to back, as it is likely to pollute the
    change_log with creation/update/removal information).
    """

    # Collect all existing auto groups ...
    existing_groups = find_all_auto_groups()

    # ... empty all of them for members (otherwise deletion is not possible)
    empty_defunct_groups(existing_groups)

    # ... and delete the group themselves
    # We cannot use delete_defunct_groups, since it cares about the OUs'
    # quarantine status. In *this* function, we want to delete all groups *no*
    # matter what.
    group = Factory.get("Group")(database)
    logger.debug("Looking for groups to delete")

    for group_name, group_id in existing_groups.iteritems():
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
                        group_id, group_name, constants.trait_auto_aff)
            # IVR 2007-12-23 FIXME: Should we attempt to delete this group?
            continue

        group.delete()
        logger.info("Deleted group id=%s, name=%s", group_id, group_name)
# end perform_delete


def main():
    options, junk = getopt.getopt(sys.argv[1:],
                                  "p:ds:",
                                  ("perspective=",
                                   "dryrun",
                                   "source_system=",
                                   "remove-all-auto-groups",))

    dryrun = False
    perspective = None
    wipe_all = False
    source_system = constants.system_ekstens
    for option, value in options:
        if option in ("-p", "--perspective",):
            perspective = int(constants.OUPerspective(value))
        elif option in ("-d", "--dryrun",):
            dryrun = True
        elif option in ("-s", "--source_system",):
            source_system = getattr(constants, value)
        elif option in ("--remove-all-auto-groups",):
            wipe_all = True

    if wipe_all:
        perform_delete()
    else:
        logger.debug("All auto traits: %s", _locate_all_auto_traits())
        perform_sync(perspective, source_system)

    if dryrun:
        database.rollback()
        logger.debug("Rolled back all changes")
    else:
        database.commit()
        logger.debug("Committed all changes")
# end main


if __name__ == "__main__":
    main()
