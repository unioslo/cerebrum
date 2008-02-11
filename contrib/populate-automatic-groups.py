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
cerebrum-sites/doc/intern/felles/utvikling/auto-grupper-spesifikasjon.rst.

A few salient points:

* This script synchronizes (i.e. creates, changes memberships, deletes)
  several groups based on the information already found in
  Cerebrum. Technically, it duplicates information otherwise available;
  however having these groups will make a number of tasks considerably easier.

* All such automatic groups are tagged with special traits (trait_auto_group,
  trait_auto_meta_group). Only such automatic groups can have these
  trait. Beware! If you give these traits to *any* other group, it will be
  collected by this script and probably deleted (as no OU would be
  'associated' with it). Autogroups with human members are tagged with
  trait_auto_group; metagroups (autogroups with group members) are tagged with
  trait_auto_meta_group.

* Some groups have people as members (person_ids); others have other automatic
  groups as members.

* ansatt@<sko>, ansatt_vitenskapelig@<sko>, ansatt_tekadm@<sko>,
  ansatt_bilag@<sko> have person_id as members. The contain the employees (of
  the given type) at the specified OU. If a person_id is a member of
  ansatt_vitenskapelig, ansatt_tekadm or ansatt_bilag, (s)he is also a member
  of ansatt@<sko>.

* meta_ansatt@<sko1> are 'metagroups' in a sense. They contain other employee
  groups (specifically ansatt@<sko2>, where sko2 is sko1 or its child in the
  specified hierarchy). At the very least meta_ansatt@<sko1> will have one
  member -- ansatt@<sko1>. Should sko1 have any child OUs with employees, the
  for each such child OU sko2, meta_ansatt@<sko1> will have a member
  ansatt@<sko2>.
"""

import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet, simple_memoize
try:
    set()
except NameError:
    from Cerebrum.extlib.sets import Set as set





logger = Factory.get_logger("cronjob")
database = Factory.get("Database")()
database.cl_init(change_program="pop-auto-groups")
constants = Factory.get("Constants")(database)



def format_sko(*rest):
    """Format stedkode in a suitable fashion.

    Institution numbers is not part of sko here.
    """
    
    assert len(rest) == 3
    return "%02d%02d%02d" % rest
# end format_sko



def ou_id2ou_info(ou_id):
    """Locate information about the OU with the specied ou_id.

    We need sko and name elsewhere.

    @type ou_id: basestring
    @param ou_id:
      ou_id for the OU in question.

    @rtype: dict
    @return:
      A mapping with name and sko or None, if OU is not found/is quarantined.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        if ou.get_entity_quarantine():
            return None
        
        return {"sko": format_sko(ou.fakultet, ou.institutt, ou.avdeling),
                "name": ou.name,
                "ou_id": ou_id}
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
      ou_id for the OU in question. We look up the parent of this ou_id.

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



def ou_has_children(ou_id, perspective):
    """Check if ou_id has any subordinate OUs in perspective.

    @type ou_id: basestring
    @param ou_id:
      ou_id for the OU in question. We look up the parent of this ou_id.

    @type perspective: Cerebrum constant
    @param perspective:
      Perspective for parent information.

    @rtype: bool
    @return:
      True if ou_id has any children in perspective, False otherwise.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        return bool(ou.list_children(perspective, entity_id=ou_id))
    except Errors.NotFoundError:
        # If we can't find the OU, it does not have a parent :)
        return False

    # NOTREACHED
    assert False
# end ou_has_children
ou_has_children = simple_memoize(ou_has_children)



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
        for row in entity.list_traits(code=trait, return_name=True):
            group_id = int(row["entity_id"])
            group_name = row["name"]
            result[group_name] = group_id
    # end slurt_data

    result = dict()
    entity = Factory.get("Group")(database)
    logger.debug("Collecting all auto groups with humans")
    slurp_data(result, constants.trait_auto_group)
    logger.debug("Collecting all auto metagroups")
    slurp_data(result, constants.trait_auto_meta_group)

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
        group.populate(get_create_account_id(),        
                       constants.group_visibility_internal,
                       group_name,
                       description)
        group.write_db()
        # before committing traits we need an existing group_id
        if trait != NotSet:
            # int() is just a safety mechanism to ensure that the trait
            # actually exists.
            group.populate_trait(int(constants.EntityTrait(trait)))
            group.write_db()

        logger.debug("Created a new auto group. Id=%s, name=%s, description=%s",
                     group.entity_id, group_name, description)
        current_groups[group_name] = group.entity_id

    return current_groups[group_name]
# end group_name2group_id



def temporary_employee_hack(row, current_groups, perspective):
    """Return groups that arise from the affilaition in row.

    This function performs a similar task to L{employee2groups}. However,
    given, for the time being (2008-01-25), we'll populate meta_ansatt@<sko>
    groups differently.

    Specifically, given an affiliation in row with ou_id B, we generate the
    following groups and add row['person_id'] as member:

      * ansatt@B
      * ansatt_vitenskapelig@B or ansatt_tekadm@B, depending on aff status
      * *IF* B has subordinate OUs, then:
          meta_ansatt@B
      * meta_ansatt@C1
        meta_ansatt@C_n

        ... where C1 is a parent of B and C_{i+1} is a parent of C_i. The
        'chain' of OUs continues as long as possible in the specified
        perspective.

    IVR thinks this is weird, but JAZZ insists that this is what we want. In
    any event, this is supposed to be a temporary replacement of
    L{employee2groups}.

    The parameters and the result values are identical to L{employee2groups}.
    """

    person_id = row["person_id"]
    ou_id = row["ou_id"]
    ou_info = ou_id2ou_info(ou_id)
    if not ou_info:
        logger.debug("Missing ou information for ou_id=%s "
                     "(OU quarantined or missing); person_id=%s",
                     ou_id, person_id)
        return list()

    affiliation = int(row["affiliation"])
    status = int(row["status"])

    prefix = "meta_ansatt"
    suffix = "@%s" % ou_info["sko"]
    result = list()
    if status == constants.affiliation_status_ansatt_vitenskapelig:
        group_name = "ansatt_vitenskapelig" + suffix
        group_id = group_name2group_id(group_name,
                               "Vitenskapelige tilsatte ved "+ou_info["name"],
                               current_groups,
                               constants.trait_auto_group)
        result.append((person_id, constants.entity_person, group_id))
        logger.debug("Adding person id=%s to group id=%s name=%s",
                     person_id, group_id, group_name)
    elif status == constants.affiliation_status_ansatt_tekadm:
        group_name = "ansatt_tekadm" + suffix
        group_id = group_name2group_id(group_name,
                      "Teknisk-administrativt tilsatte ved " + ou_info["name"],
                      current_groups,
                      constants.trait_auto_group)
        result.append((person_id, constants.entity_person, group_id))
        logger.debug("Adding person id=%s to group id=%s name=%s",
                     person_id, group_id, group_name)
    elif status == constants.affiliation_status_ansatt_bil:
        group_name = "ansatt_bilag" + suffix
        group_id = group_name2group_id(group_name,
                                       "Bilagslønnede ved " + ou_info["name"],
                                       current_groups,
                                       constants.trait_auto_group)
        result.append((person_id, constants.entity_person, group_id))
        logger.debug("Adding person id=%s to group id=%s name=%s",
                     person_id, group_id, group_name)

    # Now we create ansatt@<sko> and all the metagroups.
    if affiliation == constants.affiliation_ansatt:
        # First, person_id is a member of ansatt@sko.
        employee_group_name = "ansatt" + suffix
        employee_group_id = group_name2group_id(employee_group_name,
                                                "Tilsatte ved "+ou_info["name"],
                                                current_groups,
                                                constants.trait_auto_group)
        result.append((person_id, constants.entity_person, employee_group_id))
        logger.debug("Adding person id=%s to group id=%s name=%s",
                     person_id, employee_group_id, employee_group_name)

        # If the OU is at the "bottom" of the hierarchy, we do NOT generate a
        # meta_ansatt group for it. Ask JAZZ for an explanation.
        if ou_has_children(ou_id, perspective):
            meta_group_name = "meta_ansatt" + suffix
            meta_group_id = group_name2group_id(
                  meta_group_name,
                  "Tilsatte ved %s og underordnede organisatoriske enheter" %
                   ou_info["name"],
                  current_groups,
                  constants.trait_auto_meta_group)
            result.append((person_id, constants.entity_person, meta_group_id))
            logger.debug("Person id=%s added to meta group id=%s, name=%s",
                         person_id, meta_group_id, meta_group_name)
        else:
            logger.debug("OU id=%s, name=%s, sko=%s has no children. "
                         "No meta group will be created",
                         ou_id, ou_info["name"], ou_info["sko"])

        # Walk up the OU-hierarchy and generate an membership for each
        # group. NB! meta_ansatt@<root OU> will have A LOT of members.
        tmp_ou_id = ou_id
        parent_info = ou_id2parent_info(tmp_ou_id, perspective)
        while parent_info:
            parent_name = "meta_ansatt@" + parent_info["sko"]
            meta_parent_id = group_name2group_id(
                parent_name,
                ("Tilsatte ved %s og underordnede organisatoriske enheter" %
                 parent_info["name"]),
                current_groups,
                constants.trait_auto_meta_group)
            result.append((person_id, constants.entity_person, meta_parent_id))
            logger.debug("Person id=%s added to meta group id=%s, name=%s",
                         person_id, meta_parent_id, parent_name)
            # Walk up 1 level
            tmp_ou_id = parent_info["ou_id"]
            parent_info = ou_id2parent_info(tmp_ou_id, perspective)

    return result
# end temporary_employee_hack



def employee2groups(row, current_groups, perspective):
    """Return groups that arise from the affiliation in row.

    A person's affiliation, represented by a db row, decides which groups this
    person should be a member of. Additionally, some of these memberships
    could trigger additional memberships (check the documentation for
    meta_ansatt@<sko>).

    *** FIXME *** The meta-group code here is probably broken! Re-check it
        before using this function!

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

    prefix = "meta_ansatt"
    suffix = "@%s" % ou_info["sko"]
    result = list()
    #
    # The employees are members of certain groups.
    if affiliation == constants.affiliation_ansatt:
        # First, person_id is a member of ansatt@sko.
        employee_group_id = group_name2group_id("ansatt" + suffix,
                                                "Tilsatte ved "+ou_info["name"],
                                                current_groups,
                                                constants.trait_auto_group)
        result.append((person_id, constants.entity_person, employee_group_id))
        # Then, ansatt@sko is a member of meta_ansatt@sko
        meta_name = prefix + suffix
        meta_group_id = group_name2group_id(
                   meta_name,
                   ("Tilsatte ved %s og underordnede organisatoriske enheter" % 
                    ou_info["name"]),
                   current_groups,
                   constants.trait_auto_meta_group)
        result.append((employee_group_id,
                       constants.entity_group,
                       meta_group_id))
        # And, naturally, ansatt@sko, is a direct member of meta_ansatt@parentsko
        parent_info = ou_id2parent_info(ou_id, perspective)
        if parent_info:
            parent_name = prefix + "@" + parent_info["sko"]
            meta_parent_id = group_name2group_id(
                parent_name,
                ("Tilsatte ved %s og underordnede organisatoriske enheter" %
                 parent_info["name"]),
                current_groups,
                constants.trait_auto_meta_group)
            result.append((employee_group_id,
                           constants.entity_group,
                           meta_parent_id))
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
                                 current_groups,
                                 constants.trait_auto_group)))
    elif status == constants.affiliation_status_ansatt_tekadm:
        result.append(
            (person_id,
             constants.entity_person,
             group_name2group_id("ansatt_tekadm" + suffix,
                                 "Teknisk-administrativt tilsatte ved " +
                                 ou_info["name"],
                                 current_groups,
                                 constants.trait_auto_group)))
    elif status == constants.affiliation_status_ansatt_bil:
        result.append(
            (person_id,
             constants.entity_person,
             group_name2group_id("ansatt_bilag" + suffix,
                                 "Bilagslønnede ved " + ou_info["name"],
                                 current_groups,
                                 constants.trait_auto_group)))

    return result
# end employee2groups



def employee_role2groups(row, current_groups, perspective):
    """Return groups that arise from roles in row.

    All employees can have roles associated with them in HR data. After some
    processing, these roles are stored in Cerebrum as person traits.
    cereconf.EMPLOYEE_TRAITS has the specific mapping of which roles are
    mapped to which traits.

    Once these person traits are stored in Cerebrum, we can look people up by
    these traits and register them as group members of certain groups. This
    function calculates which groups a person_id should be a member of, based
    on the information in L{row}.

    @type row:
    @param row:

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

      An empty sequence is returned if no memberships can be derived. This is
      identical to L{employee2groups}' return value.
    """

    person_id = row["entity_id"]
    ou_id = row["target_id"]
    trait_code = row["code"]
    description = row["strval"]
    # Now, we need to have the text description of 'role'. It has been mapped
    # to a trait_code by import_HR_person.py, and we need a reverse
    # mapping. This can be accomplished by using trait's strval, but is this
    # the right way?

    if row["entity_type"] != constants.entity_person:
        logger.warn("Entity with id=%s (type %s) is not a person entity, "
                    "although trait <%s> is assignable to persons only",
                    person_id, row["entity_type"], trait_code)
        return list()

    if not description.strip():
        logger.warn("Person id=%s with trait code=%s has no associated "
                    "description. No group can be created. Trait ignored",
                    person_id, trait_code)
        return list()

    ou_info = ou_id2ou_info(ou_id)
    if not ou_info:
        logger.warn("Missing OU information for ou_id=%s (trait for "
                    "person_id=%s trait code=%s",
                    ou_id, person_id, trait_code)
        return list()

    group_name = "%s@%s" % (description, ou_info["sko"])
    group_id = group_name2group_id(group_name,
                                   "Alle %s ved %s" % (description,
                                                       ou_info["name"]),
                                   current_groups,
                                   constants.trait_auto_group)
    return ((person_id, constants.entity_person, group_id),)
# end employee_role2groups



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
    # should be performed.
    person = Factory.get("Person")(database)
    global_rules = [
        # Employee rule: (ansatt@<ou>, ansatt_vitenskapelig@<ou>, etc.)
        (lambda: person.list_affiliations(
                   affiliation=(constants.affiliation_ansatt,),
                   source_system=source_system),
         # IVR 2008-01-25 The fix is temporary.
         lambda *rest: # employee2groups(perspective=perspective, *rest)),
                       temporary_employee_hack(perspective=perspective, *rest)),

        # Employee rule: role holder groups (e.g. EF-STIP@<ou>)
        (lambda: person.list_traits(code=_locate_all_auto_traits()),
         lambda *rest: employee_role2groups(perspective=perspective, *rest)),
        
        # Student rules
        # ...
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
    source_system = constants.system_sap
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

