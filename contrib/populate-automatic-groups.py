#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2007, 2008, 2014 University of Oslo, Norway
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

r"""Populate and update several automatically maintained groups in Cerebrum.

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

* Some groups have people as members (person_ids), or their primary account if
  the --account switch is turned on; others have other automatic groups as
  members.

* ansatt-<sko>, ansatt-vitenskapelig-<sko>, ansatt-tekadm-<sko>,
  ansatt-bilag-<sko> have person_id as members. They contain the employees (of
  the given type) at the specified OU. If a person_id is a member of
  ansatt-vitenskapelig, ansatt-tekadm or ansatt-bilag, (s)he is also a member
  of ansatt-<sko>.

* meta-ansatt-<sko1> are 'metagroups' in a sense. They contain other employee
  groups (specifically ansatt-<sko2>, where sko2 is sko1 or its child in the
  specified hierarchy). At the very least meta-ansatt-<sko1> will have one
  member -- ansatt-<sko1>. Should sko1 have any child OUs with employees, the
  for each such child OU sko2, meta-ansatt-<sko1> will have a member
  ansatt-<sko2>.

A typical run for UiO would be something like this:

populate-automatic-groups.py --dryrun -s system_sap -p SAP \\
        -c affiliation_status_ansatt_vitenskapelig:ansatt-vitenskapelig \\
        -c affiliation_status_ansatt_tekadm:ansatt-tekadm \\
        -c affiliation_status_ansatt_bil:ansatt-bilag \\
        -c affiliation_ansatt:ansatt

If you want to look at the resulting structure, issue this:

populate-automatic-groups.py -p SAP -o

... or, if you want to see which groups exist for sko 13-xx-xx and 33-15-xx
and how they are structured:

populate-automatic-groups.py -p SAP -o -f '^13' -f '^3315'

FIXME: Profile this baby.
"""

import collections
import getopt
import re
import sys

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.utils.funcwrap import memoize


logger = Factory.get_logger("cronjob")
database = Factory.get("Database")()
database.cl_init(change_program="pop-auto-groups")
constants = Factory.get("Constants")(database)
INDENT_STEP = 2

ignored_groups = []


class group_attributes(object):

    """Named-tuple like object for caching some group attributes in memory."""

    def __init__(self, group_proxy):
        """Initzialize cache-object.

        :param Group group: Group object to cache.
        """
        self.group_id = group_proxy.entity_id
        self.group_name = group_proxy.group_name
        self.description = group_proxy.description
    # end __init__
# end group_attributes


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

    :type ou_id: basestring
    :param ou_id:
      ou_id for the OU in question.

    :rtype: dict
    :return:
      A mapping with name and sko or None, if OU is not found/is quarantined.
    """
    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        if ou.get_entity_quarantine():
            return None

        return {"sko": format_sko(ou.fakultet, ou.institutt, ou.avdeling),
                "name": ou.get_name_with_language(
                    name_variant=constants.ou_name,
                    name_language=constants.language_nb,
                    default=""),
                "ou_id": ou_id}
    except Errors.NotFoundError:
        return None

    # NOTREACHED
    assert False
# end ou_id2ou_info
ou_id2ou_info = memoize(ou_id2ou_info)


def ou_id2parent_info(ou_id, perspective):
    """Similar to L{ou_id2ou_info}, except return info for the parent.

    :type ou_id: basestring
    :param ou_id:
      ou_id for the OU in question. We look up the parent of this ou_id.

    :type perspective: Cerebrum constant
    :param perspective:
      Perspective for parent information.

    :rtype: dict
    :return:
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
ou_id2parent_info = memoize(ou_id2parent_info)


def ou_get_children(ou_id, perspective):
    """Check if ou_id has any subordinate OUs in perspective.

    :type ou_id: basestring
    :param ou_id:
      ou_id for the OU in question. We look up the parent of this ou_id.

    :type perspective: Cerebrum constant
    :param perspective:
      Perspective for parent information.

    :rtype: sequence of int
    :return:
      A sequence of children's ou_ids in the specified perspective.
    """
    ou = Factory.get("OU")(database)
    try:
        ou.find(ou_id)
        return [x["ou_id"]
                for x in ou.list_children(perspective, entity_id=ou_id)]
    except Errors.NotFoundError:
        # If we can't find the OU, it does not have a parent :)
        return False

    # NOTREACHED
    assert False
# end ou_get_children
ou_get_children = memoize(ou_get_children)


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


def group_name_is_valid(group_name):
    r"""Check whether a given name conforms to the auto group name format.

    The format in question is <something>-<sko>, where <sko> is \d{6}.
    """
    return re.search("[a-zA-Z0-9_-]+-\d{6}$", group_name) is not None
# end group_name_is_valid


def find_all_auto_groups():
    """Collect and return all groups that are administrered by this script.

    We tag all auto groups with a number of traits. It is the only sane and
    reliable way of gathering *all* of them later (using special name prefixes
    is too cumbersome and error prone; organising them into a hierarchy (like
    fronter groups) is a bit icky, since the tree has to be stored in a
    relational db.

    :rtype: dict
    :return:
      A mapping group_name -> group_id.
    """
    def slurp_data(result, trait):
        group = Factory.get("Group")(database)
        for row in entity.list_traits(code=trait):
            group_id = int(row["entity_id"])
            try:
                group.clear()
                group.find(group_id)
            except Errors.NotFoundError:
                continue

            result[group.group_name] = group_attributes(group)
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

    :type group_name: basestring
    :param group_name: Group name to look up/create.

    :type description: basestring
    :param description:
      In case a group needs creating, this will be the description registered
      in Cerebrum.

    :type current_groups: dict
    :param current_groups: Return value of L{find_all_auto_groups}.

    :type traits: a constant (int or basestring) or NotSet
    :param traits:
      Additional trait to adorn L{group_name} with. The trait is added *only*
      if the group is created.

    :rtype: int or long
    :return:
      Group id for the group with name group_name. This function also updates
      current_groups.
    """
    if group_name not in current_groups:
        group = Factory.get("Group")(database)

        # perhaps the group already exists without its trait?
        # if so we'd like to log a warning and not touch this group
        try:
            group.find_by_name(group_name)
        except Errors.NotFoundError:
            pass
        else:
            if group_name not in ignored_groups:
                logger.warn("Group %s is missing trait '%s', ignoring group",
                            group_name, str(trait))
                ignored_groups.append(group_name)
            return None

        group.populate(
            creator_id=get_create_account_id(),
            visibility=constants.group_visibility_internal,
            name=group_name,
            description=description,
            group_type=constants.group_type_affiliation
        )
        group.write_db()
        # before committing traits we need an existing group_id
        if trait != NotSet:
            # int() is just a safety mechanism to ensure that the trait
            # actually exists.
            group.populate_trait(int(constants.EntityTrait(trait)))
            group.write_db()

        logger.debug(
            "Created a new auto group. Id=%s, name=%s, description=%s",
            group.entity_id, group_name, description)
        current_groups[group_name] = group_attributes(group)

    # If the OU that the group is linked to changed its name, the group's
    # description should reflect that change. It does not happen often, but it
    # is a possibility and the group should be adapted accordingly.
    elif description != current_groups[group_name].description:
        group = Factory.get("Group")(database)
        try:
            group.find_by_name(group_name)
        except Errors.NotFoundError:
            logger.error("This is impossible -- auto-group %s vanished"
                         "from the database while syncing",
                         group_name)
            return current_groups[group_name]

        logger.debug("Group %s (id=%s) changes description (%s -> %s)",
                     group_name, group.entity_id,
                     current_groups[group_name].description,
                     description)
        group.description = description
        group.write_db()
        current_groups[group_name].description = description

    return current_groups[group_name].group_id
# end group_name2group_id


def _load_selection_helper(iterable):
    """Construct a data structure suitable for group membership selection.

    :type iterable: an iterator over tuples (str, str)
    :param iterable:
      An iterator over (human representation of aff/status, group
      prefix). human representation may be whatever
      L{ConstantsBase.human2constant} accepts. group prefix is the prefix for
      a group an aff/status holder is to be a member of.
      L{cereconf.AUTOMATIC_GROUP_LEGAL_PREFIXES} lists the permissible values.

    :rtype: dict (PersonAffiliation/PersonAffStatus -> str)
    :return:
      A dictionary mapping person affiliations/aff statuses to group prefixes
      where an affiliation/status holder is to be a member.
    """
    result = dict()
    co = Factory.get("Constants")()
    for human_repr, prefix in iterable:
        if prefix not in cereconf.AUTOMATIC_GROUP_LEGAL_PREFIXES:
            logger.warn("Prefix '%s' is illegal for automatic groups. Ignored",
                        prefix)
            continue

        co_object = co.human2constant(human_repr, (co.PersonAffStatus,
                                                   co.PersonAffiliation))
        if co_object is None:
            logger.warn("Failed to remap human representation <%s> to const",
                        human_repr)
        else:
            result[co_object] = prefix

    return result
# end load_selection_helper


def load_registration_criteria(criteria):
    """Function generates a data structure for selecting group members.

    The script is driven by affiliations/statuses: a person with a certain
    affiliation (or affiliation status) becomes a member of a certain
    group. Specifically which affiliation/status results in which group
    membership is determined in two ways:

      1) There may be settings in cereconf.AUTOMATIC_GROUPS.
      2) There may be settings specified on the command line.

    Command line settings supersedes cereconf's settings.

    The resulting data structure is a dict, mapping affiliation, or
    affiliation status to a group prefix for an automatically administered
    group. L{cereconf.AUTOMATIC_GROUP_LEGAL_PREFIXES} lists the valid prefixes.
    'ansatt'-groups are special: they are ALSO members of the corresponding
    'meta-ansatt' groups.
    """
    logger.debug("AUTO_GROUPS=%s", getattr(cereconf, "AUTOMATIC_GROUPS", {}))
    result = _load_selection_helper(
        getattr(cereconf, "AUTOMATIC_GROUPS", {}).items())
    result.update(_load_selection_helper(criteria.items()))
    logger.debug("The following affs/statuses will result in memberships")
    logger.debug("Result is %s", result)
    for aff_or_status in result:
        prefix = result[aff_or_status]
        logger.debug("%s %s -> membership in '%s'",
                     isinstance(aff_or_status, constants.PersonAffStatus)
                     and "Status" or "Affiliation",
                     str(aff_or_status),
                     prefix)
    return result
# end load_registration_criteria


def affiliation2groups(row, current_groups, select_criteria, perspective):
    """Return groups that arise from the affiliation/aff status in row.

    A person's affiliation/status, represented by a db row, decides which
    groups this person should be a member of. Also, some of these memberships
    could trigger additional memberships (check the documentation for
    meta-ansatt-<sko>).

    :type row: A db_row instance
    :param row:
      A db_row representing one affiliation for one person.

    :type current_groups: dict
    :param current_groups:
      Return value of L{find_all_auto_groups}.

    :param select_criteria:
      See L{perform_sync}.

    :type perspective: Cerebrum constant
    :param perspective:
      Perspective for OU-hierarchy queries.

    :rtype: sequence
    :return:
      A sequence of triples (x, y), where
        - x is the member id (entity_id)
        - y is the group id where x is to be member.

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
    suffix = "-%s" % ou_info["sko"]
    result = list()

    employee_group_id = None
    for key in (status, affiliation):
        if key not in select_criteria:
            continue

        group_prefix = select_criteria[key]
        description = (cereconf.AUTOMATIC_GROUP_LEGAL_PREFIXES[group_prefix] %
                       ou_info["name"])
        group_name = group_prefix + suffix
        group_id = group_name2group_id(group_name,
                                       description,
                                       current_groups,
                                       constants.trait_auto_group)
        # Consult the configuration to see if we should try to populate
        # meta-groups with memberships.
        if group_prefix in cereconf.AUTOMATIC_GROUP_POPULATE_META_PREFIX:
            employee_group_id = group_id

        if group_id is not None:
            result.append((person_id, group_id))
            logger.debug("Added person id=%s to group id=%s, name=%s",
                         person_id, group_id, group_name)

    # Now the fun begins. All employees are members of certain groups.
    #
    # This affiliation (row) results in person_id being member of ansatt-<sko>.
    if employee_group_id is not None:
        # Now it becomes difficult, since we have to create a chain of
        # meta-ansatt group memberships.
        tmp_ou_id = ou_id
        # The first step is not really a parent -- it's the OU itself. I.e.
        # ansatt-<sko> is a member of meta-ansatt-<sko>. It's like that by
        # design (consider asking "who's an employee at <sko> or subordinate
        # <sko>?". The answer is "meta-ansatt-<sko>" and it should obviously
        # include ansatt-<sko>)
        parent_info = ou_id2ou_info(tmp_ou_id)
        prefix = "meta-%s" % group_prefix
        description = cereconf.AUTOMATIC_GROUP_LEGAL_PREFIXES[prefix]
        while parent_info:
            parent_name = prefix + "-" + parent_info["sko"]
            meta_parent_id = group_name2group_id(
                parent_name,
                description % parent_info["name"],
                current_groups,
                constants.trait_auto_meta_group)

            if meta_parent_id is not None:
                result.append((employee_group_id, meta_parent_id))
                logger.debug("Group name=%s (from person_id=%s) added to "
                             "meta group id=%s, name=%s",
                             group_prefix + suffix, person_id,
                             meta_parent_id, parent_name)

            parent_info = ou_id2parent_info(tmp_ou_id, perspective)
            if parent_info:
                tmp_ou_id = parent_info["ou_id"]

    return result
# end affiliation2groups


def populate_groups_from_rule(generator, row2groups, current_groups,
                              new_groups):
    """Sweep all the people from generator and assign group memberships.

    There may be several rules for building all of the groups. For each rule,
    this functions assigns proper memberships to new_groups. Once we have
    finished processing the rules, we can synchronize the in-memory data
    structure with the database.

    :type person_generator:
      Generator (or a function returning a sequence) of db_rows (person_ids).
     :type primary_generator:
      Generator (or a function returning a sequence) of db_rows (account_ids
      posing as person_ids).
    :param person_generator:
      Next db-row 'source' to process. Calling this yields something we can
      iterate across. The items in the sequence should be db_rows (or
      something which emulates them, like a dict)
    :param primary_generator:
      Next db-row 'source' to process. Calling this yields something we can
      iterate across. The items in the sequence should be db_rows (or
      something which emulates them, like a dict)

    :type row2groups: callable
    :param row2groups:
      Function that converts a row returned by L{person_generator} to a list
      of memberships. Calling row2groups on any row D returned by
      L{person_generator} returns a list of tuples (x, y) (cf.
      L{affiliation2groups} for the precise description of their meanings).

    :type current_groups: dict
    :param current_groups:
      Cf. L{find_all_auto_groups}.

    :type new_groups: dict
    :param new_groups:
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
    for person in generator():
        memberships = row2groups(person, current_groups)

        for member_id, group_id in memberships:
            # all known memberships for group_id
            new_groups.setdefault(group_id, set()).add(member_id)
            count += 1

    logger.debug("After processing rule, we have %d groups", len(new_groups))
    logger.debug("... and <= %d members", count)
# end populate_groups_from_rule


def remove_members(group, member_sequence):
    """Remove several members from a group.

    This is just a convenience function.

    :type group: Factory.get('Group') instance
    :param group:
      Group from which the members are to be removed.

    :type member_sequence: sequence
    :param member_sequence:
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

    :type group: Factory.get('Group') instance
    :param group:
      Group from which the members are to be removed.

    :type member_sequence: sequence
    :param member_sequence:
      A sequence with person_ids who are to become members of L{group}.
    """
    for entity_id in member_sequence:
        group.add_member(entity_id)

    logger.debug("Added %d members to group id=%s, name=%s",
                 len(member_sequence), group.entity_id, group.group_name)
# end add_members


def synchronise_spreads(group, spreads, omit_spreads):
    """Force a specific spread set for group.

    Each automatic group must have a specific set of spreads. Exactly that
    spread set is forced upon all groups administered by this script.

    :param group:
      Group proxy bound to a specific group_id

    :type spreads: set of tuples (str, const.Spread) or NotSet.
    :param spreads:
      A set of tuples, (prefix, spread), where prefix is matched against
      group.group_name. If the value is NotSet, leave the spreads of this
      specific group unchanged.

    :type omit_spreads: set of tuples (str, const.Spread)
    :param omit_spreads:
      A set of tuples, (prefix, spread), where prefix is matched against
      group.group_name. These spreads are not touched by PAG.

    """
    if spreads is NotSet:
        return

    group_name = group.group_name
    own_spreads = set(constants.Spread(x["spread"])
                      for x in group.get_spread())
    omitted_spreads = set(
        constants.Spread(x[1])
        for x in omit_spreads
        if group_name.startswith(x[0])
    )
    given_spreads = set(constants.Spread(x[1])
                        for x in spreads
                        if group_name.startswith(x[0]))
    # Exclude ommited spreads, so they don't get touched
    own_spreads = own_spreads.difference(omitted_spreads)

    for spread in given_spreads.difference(own_spreads):
        logger.debug("Assigning spread %s to group %s (id=%s)",
                     str(spread), group_name, group.entity_id)
        group.add_spread(spread)

    for spread in own_spreads.difference(given_spreads):
        logger.debug("Removing spread %s to group %s (id=%s)",
                     str(spread), group_name, group.entity_id)
        group.delete_spread(spread)
# end synchronise_spreads


def synchronise_groups(groups_from_cerebrum, groups_from_data, spreads,
                       omit_spreads):
    """Synchronise current in-memory representation of groups with the db.

    The groups (through the rules) are built in-memory. This function
    synchronises the in-memory data structure with Cerebrum. For each group,
    read the membership info, compare it with groups_from_data, adjust the
    information, write_db() on the group.

    NB! L{groups_from_cerebrum} is modified by this function.

    :type groups_from_cerebrum: dict
    :param: Cf. L{find_all_auto_groups}.

    :type groups_from_data: dict
    :param: Cf. L{populate_groups_from_rule}.

    :type spreads: set of tuples
    :param spreads:
      Spreads to assign for our auto-groups.

    :type omit_spreads: set of tuples
    :param omit_spreads:
      Spreads that should not be touched.

    :rtype: type(groups_from_cerebrum)
    :return:
      Modified L{groups_from_cerebrum}.
    """
    group = Factory.get("Group")(database)

    for group_id, members_from_data in groups_from_data.iteritems():
        try:
            group.clear()
            group.find(group_id)
            gname = group.group_name
        except Errors.NotFoundError:
            logger.warn("group_id=%s disappeared from Cerebrum.", group_id)
            continue

        synchronise_spreads(group, spreads, omit_spreads)

        # select just the entity_ids (we don't care about entity_type)
        group_members = set(int(x["member_id"]) for x in
                            group.search_members(group_id=group.entity_id))
        # now, synch the union members. sync'ing means making sure that the
        # members of group are exactly the ones in memberset.

        # those that are not in 'group_members', should be added
        to_add = members_from_data.difference(group_members)
        add_members(group, to_add)

        # those that are in 'group_members', but not in members_from_data,
        # should be removed.
        to_remove = group_members.difference(members_from_data)
        remove_members(group, to_remove)

        if gname not in groups_from_cerebrum:
            logger.debug("New group id=%s, name=%s", group_id, gname)
        else:
            del groups_from_cerebrum[gname]
            logger.debug("Existing group id=%s, name=%s", group_id, gname)

        if to_remove or to_add:
            logger.debug("Updated group id=%s, name=%s; added=%d, removed=%d",
                         group_id, gname, len(to_add), len(to_remove))
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

    :type groups_from_cerebrum: dict
    :param groups_from_cerebrum:
      A mapping returned by L{find_all_auto_groups} minus all of the groups
      removed by previous functions (like L{synchronise_groups}).
    """
    logger.debug("Emptying defunct groups")
    group = Factory.get("Group")(database)
    # These are groups that would not have existed, given today's data
    # situation. What should we do with them?
    for group_name in groups_from_cerebrum:
        group_id = groups_from_cerebrum[group_name].group_id
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


def delete_defunct_groups(groups):
    """Sweep all auto groups and delete those that should not be in the db.

    Each group is 'associated' via its name with an OU. When the OUs are no
    longer available (removed or quarantined), we should nuke the groups as
    well.

    The *ugly* *ugly* part here is the way groups are mapped to corresponding
    OUs. We cannot easily associate an OU with a group, and thus, OU would
    have to be deduced from the groups's name. Such an arrangement is prone to
    breakage.

    :type groups: dict
    :param groups:
      A dictionary as returned by L{find_all_auto_groups}, and subsequently
      cleared of all groups that *should* be in Cerebrum.
    """
    group = Factory.get("Group")(database)
    ou = Factory.get("OU")(database)
    logger.debug("Looking for groups to delete")

    for group_name in groups:
        group_id = groups[group_name].group_id
        logger.debug("Considering group id=%s, name=%s for deletion",
                     group_id, group_name)

        try:
            group.clear()
            group.find(group_id)
        except Errors.NotFoundError:
            logger.warn("Group id=%s, name=%s disappeared.",
                        group_id, group_name)
            continue

        if group.get_extensions():
            logger.warn("Group id=%s, name=%s is a %r group, unable to delete",
                        group.entity_id, group.group_name,
                        group.get_extensions())
            continue

        if not group_name_is_valid(group_name):
            logger.warn("Group id=%s, name=%s has trait %s and a "
                        "non-conformant name. This should be fixed.",
                        group_id, group_name, constants.trait_auto_group)
            # IVR 2007-12-23 FIXME: Should we attempt to delete this group?
            continue

        name, sko = group_name.rsplit("-", 1)
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


def perform_sync(select_criteria, perspective, source_system, spreads,
                 omit_spread, populate_with_primary_acc=False):
    """Set up the environment for synchronisation and synch all groups.

    :type select_criteria: a dict (aff/status constant -> str)
    :param select_criteria:
      A data structure representing selection criteria for selecting
      individuals.

    :type perspective: Cerebrum constant
    :param perspective:
      OU perspective, indicating which OU hierarchy should be searched in for
      parent-child OU relationships.

    :type source_system: Cerebrum constants
    :param source_system:
      Source system for filtering some of the Cerebrum data.

    :type spreads: set of tuples
    :param spreads: Spreads to assign for our auto-groups.

    :type omit_spreads: set of tuples
    :param omit_spreads: Spreads that should not be touched.

    :type populate_with_primary_acc: bool
    :param populate_with_primary_acc: Wether or not to put the primary account,
      instead of the person, into the groups.

    """
    assert perspective is not None, "Must have a perspective"

    # Collect all existing auto groups. Whatever is left here after several
    # processing passes are groups that no longer have any reason to exist.
    current_groups = find_all_auto_groups()
    new_groups = dict()

    person = Factory.get("Person")(database)
    selecting_affiliations = [x
                              for x in select_criteria
                              if isinstance(x, constants.PersonAffiliation)]
    # TBD: If the select list is empty, should the script abort, or just go for
    # all affiliations?
    if not selecting_affiliations:
        selecting_affiliations = None

    # Rules that decide which groups to build.
    # Each rule is a tuple. The first object is a callable that generates a
    # sequence of db-rows that are candidates for group addition (typically
    # person_id and a few more attributes). The second object is a callable
    # that yields a data structure indicating which group membership are
    # inferred from the db-rows returned by the first callable.
    global_rules = [
        # Affiliation-based rule, e.g. rules that populate ansatt-<ou>
        (lambda: person.list_affiliations(
         affiliation=selecting_affiliations,
         source_system=source_system),
         lambda row, current_groups: affiliation2groups(row,
                                                        current_groups,
                                                        select_criteria,
                                                        perspective),
         lambda: person.list_affiliations(
            affiliation=selecting_affiliations,
            source_system=source_system,
            ret_primary_acc=True)),

        # Trait-based rules: a person with a trait -> membership in a group
        # (lambda: person.list_traits(code=_locate_all_auto_traits()),
        #  lambda *rest: <something-that-reads traits>),

        # Student rules
        # ...
    ]
    for rule in global_rules:
        # How do we get all the people for registering in the groups?
        person_generator = rule[0]
        # exchange-relatert-jazz
        # it seems that using row2groups is good enough, and we don't
        # really need to create another rule, Jazz (2013-12)
        #
        # Given a row with a person, which groups should (s)he be registered
        # in?
        row2groups = rule[1]
        # exchange-relatert-jazz
        # if we want to add primary accounts to auto-groups in stead of
        # people we create a primary_generator
        primary_generator = rule[2]
        #
        # Let's go
        #
        # exchange-relatert-jazz
        # pop-auto-groups may be used to populate person-groups
        # or primary_acc groups, by using the "-a"/"--account"
        # switch
        if not populate_with_primary_acc:
            populate_groups_from_rule(person_generator, row2groups,
                                      current_groups, new_groups)
        else:
            populate_groups_from_rule(primary_generator, row2groups,
                                      current_groups, new_groups)

    current_groups = synchronise_groups(current_groups, new_groups, spreads,
                                        omit_spread)

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

    # ... and delete the group themselves We cannot use delete_defunct_groups,
    # since it cares about the OUs' quarantine status. In *this* function, we
    # want to delete *all* groups no matter what.
    group = Factory.get("Group")(database)
    logger.debug("Looking for groups to delete")

    for group_name in existing_groups:
        group_id = existing_groups[group_name].group_id
        logger.debug("Considering group id=%s, name=%s for deletion",
                     group_id, group_name)
        try:
            group.clear()
            group.find(group_id)
        except Errors.NotFoundError:
            logger.warn("Group id=%s, name=%s disappeared.",
                        group_id, group_name)
            continue

        if group.get_extensions():
            logger.warn("Group id=%s, name=%s is a %r group, unable to delete",
                        group.entity_id, group.group_name,
                        group.get_extensions())
            continue

        if not group_name_is_valid(group_name):
            logger.warn("Group id=%s, name=%s has trait %s and a "
                        "non-conformant name. This should be fixed.",
                        group_id, group_name, constants.trait_auto_group)
            # IVR 2007-12-23 FIXME: Should we attempt to delete this group?
            continue

        group.delete()
        logger.info("Deleted group id=%s, name=%s", group_id, group_name)
# end perform_delete


class gnode(object):

    """Class to facilitate group tree output."""

    # TODO: Describe this class thouroughly.
    person_id2uname = dict()

    def __init__(self, gid, gname):
        """Initialize group tree class.

        :param int gid: Group id.
        :param str gname: Group name.
        """
        self._gid = gid
        self._gname = gname
        self._group_children = dict()
        self._non_group_children = set()
        self._parent = None
        self._description = self._fetch_description()
    # end __init__

    def _fetch_description(self):
        group = Factory.get("Group")(database)
        group.find(self._gid)
        return group.description
    # end _fetch_description

    def __hash__(self):
        """Return a hash value for the object."""
        return hash(self._gid)

    def __str__(self):
        """Return a string representation of the object."""
        return self.prepare_output(0)

    def prepare_output(self, indent=0):
        """Return formated output."""
        humans = "%d humans" % len(self._non_group_children)
        if 0 < len(self._non_group_children) <= 15:
            humans = ("\n" +
                      " " * indent +
                      ", ".join(str(self.person_id2uname.get(x, x))
                                for x in self._non_group_children))

        components = [self._description,
                      "(name=%s)" % str(self._gname),
                      "(id=%s)" % self._gid,
                      humans]

        return "group %s" % ", ".join(components)
    # end prepare_output

    def add_group_child(self, gnode_other):
        """Add child in group hierarchy."""
        if gnode_other._gid in self._group_children:
            return

        self._group_children[gnode_other._gid] = gnode_other
    # end add_child

    def add_nongroup_child(self, key):
        """Add a child that is not a group."""
        self._non_group_children.add(key)
    # end add_nongroup_child

    def add_parent(self, node):
        """Set the parent node."""
        self._parent = node
    # end add_parent

    def get_parent(self):
        """Return the parent node."""
        return self._parent
    # end get_parent

    def matches_filters(self, *filters):
        """Check if the group name matches the supplied filters."""
        # Any node matches an empty filter set
        if not filters:
            return True

        for name_filter in filters:
            if name_filter.search(self._gname):
                return True

        return False
    # end matches_filters

    def output(self, stream, indent=0):
        """Write the group tree to the supplied stream."""
        stream.write(" " * indent)
        stream.write(self.prepare_output(indent + INDENT_STEP))
        stream.write("\n")
        for child in self._group_children.itervalues():
            child.output(stream, indent + INDENT_STEP)
    # end output
# end gnode


def person_id2uname():
    """Construct a dict mapping person_id to primary uname."""
    logger.debug("Caching humans->accounts...")
    acc = Factory.get("Account")(database)
    acc_id2name = dict((x["entity_id"], x["entity_name"])
                       for x in acc.list_names(constants.account_namespace))
    pid2uname = dict((x["person_id"], acc_id2name[x["account_id"]])
                     for x in acc.list_accounts_by_type(primary_only=True))

    logger.debug("%d entries in the cache", len(pid2uname))
    return pid2uname
# end person_id2uname


def build_ou_roots(filters, perspective):
    """Construct a collection of OUs whose sko match any of the filters.

    :rtype: dict (int -> dict)
    :return:
      A dict mapping ou_ids to ou information blocks (small dicts with sko,
      ou_id and name)
    """
    logger.debug("Calculating OU root set, %d filter(s)", len(filters))

    # Now the only sensible plan of attack is to do this by OU-tree.
    ou = Factory.get("OU")(database)
    # ou_id -> ou_info block
    ou_set = dict((x["ou_id"], ou_id2ou_info(x["ou_id"]))
                  for x in ou.search(filter_quarantined=True))

    logger.debug("Starting with %d OUs in total", len(ou_set))
    # Choose only the nodes that match at least one regular expression
    filtered_set = dict((ou_id, ou_set[ou_id])
                        for ou_id in ou_set
                        if any(pattern.search(ou_set[ou_id]["sko"])
                               for pattern in filters))

    # From these nodes, select those that are parentless IN THE filtered set.
    # These are the nodes that we can start output from (they represent a
    # logical root of the OU-tree matching a given regex. E.g. if the user
    # specifies '15', the topmost matching node is '150000' (it's parent is
    # probably some bogus proforma OU not matched by '15')).
    ou_roots = dict()
    for ou_id in filtered_set:
        parent = ou_id2parent_info(ou_id, perspective)
        if not parent or parent["ou_id"] not in filtered_set:
            ou_roots[ou_id] = filtered_set[ou_id]

    return ou_roots
# end build_ou_roots


def output_group_forest(filters, perspective):
    """Construct a forest of auto groups.

    We want to be able to output a forest (i.e. a collection of group trees)
    of automatic groups for statistical purposes. This function constructs
    such a tree and returns it as a dict.
    """
    group_forest = build_complete_group_forest()
    # If none are specified -- match all
    if not filters:
        filters = [".*", ]
    logger.debug("%d nodes in the root set", len(group_forest))
    logger.debug("%d filters: %s", len(filters), filters)
    filters = [re.compile(pattern) for pattern in filters]

    ou_roots = build_ou_roots(filters, perspective)
    # Now that we have a root set matching the filters, we can output
    # everything recursively
    work_queue = collections.deque((0, ou_roots[ou_id])
                                   for ou_id in ou_roots)
    while work_queue:
        # right end removal
        indent, current_ou = work_queue.pop()
        sko = current_ou["sko"]
        # Output all groups for this sko (recursively)
        existing_groups = list()
        for prefix in cereconf.AUTOMATIC_GROUP_LEGAL_PREFIXES:
            gname = prefix + "-" + sko
            if gname not in group_forest:
                continue
            existing_groups.append(group_forest[gname])

        if not existing_groups:
            continue

        output_ou(current_ou, indent, sys.stdout)
        for tmp in existing_groups:
            tmp.output(sys.stdout, indent + INDENT_STEP)

        # Enqueue all the children of current_ou
        work_queue.extend((indent + INDENT_STEP, ou_id2ou_info(child_id))
                          for child_id in
                          ou_get_children(current_ou["ou_id"],
                                          perspective)
                          if ou_id2ou_info(child_id))
# end output_group_forest


def output_ou(ou_info, indent, stream):
    """Format an OU for output."""
    indent = " " * indent
    if indent > 0:
        indent = "*" + indent[1:]

    stream.write(indent)
    stream.write("OU %s (id=%s)" % (ou_info["sko"], ou_info["ou_id"]))
    stream.write("\n")
# end output_ou


def build_complete_group_forest():
    """Build a complete forest of all auto groups.

    Returns such a forest as a dictionary mapping gname to gnode instance.
    """
    gnode.person_id2uname = person_id2uname()

    logger.debug("Building complete node forest")

    #
    # map all groups to nodes.
    scratch = dict()
    existing_groups = find_all_auto_groups()
    for gname in existing_groups:
        gid = existing_groups[gname].group_id
        node = gnode(gid, gname)
        scratch[gid] = node

    logger.debug("%d auto group nodes. linking up children", len(scratch))

    #
    # Calculate children relationships and link the nodes together
    #
    # Nodes are taken out of the work queue - scratch - and inserted into
    # forest, once processed.
    group = Factory.get("Group")(database)
    for gid in scratch:
        node = scratch[gid]
        children = list(group.search_members(group_id=gid,
                                             indirect_members=False))
        group_children = [x for x in children
                          if x["member_type"] == constants.entity_group]
        non_group_children = [x for x in children
                              if x["member_type"] != constants.entity_group]

        for x in non_group_children:
            node.add_nongroup_child(x["member_id"])

        for x in group_children:
            child_id = x["member_id"]
            if child_id in scratch:
                child_node = scratch[child_id]
            else:
                assert False, "%s is not in scratch buffer" % child_id

            node.add_group_child(child_node)
            child_node.add_parent(node)

    logger.debug("Built auto group tree -- %d node(s)", len(scratch))
    # gname -> node (rather than gid -> node)
    result = dict()
    for gid in scratch:
        node = scratch[gid]
        result[node._gname] = node

    return result
# end build_complete_forest


def usage(exitcode):
    """Help text for the commandline options."""
    print """Usage: populate-automatic-groups.py -p SYSTEM [OPTIONS]

    -p --perspective SYSTEM     Set the system perspective to fetch the OU
                                structure from, e.g. SAP or FS. This sets what
                                system that controls the OU hierarchy which
                                should be used for the group hierarchy.

    -s --source_system SYSTEM   Set the source system to fetch the person
                                affiliations from. Could be a single system or
                                a list of systems. Defaults to 'system_sap'.

    -c --collect CRITERIA       Update the select criterias for what
                                affiliations or statuses that shoul be
                                collected and used for populating auto groups.
                                Note that this comes in addition to what is set
                                in the mapping in cereconf.AUTOMATIC_GROUPS.

                                Format: The aff or status must be tailed with a
                                colon and what group prefix to use. Example:

                                    affilation_status_tilknyttet_eremitus:auto-eremitus

    -a --accounts               Populate the groups with primary accounts
                                instead of persons.

    -r --spread PREFIX:SPREAD   Add a spread to the auto groups. Each given
                                spread must have a prefix that must match the
                                start of the group name for the spread to be
                                given. Examples:

                                   ansatt:group@ad # Each group starting with
                                                   # "ansatt..." will get to
                                                   # AD.

                                   :group@ldap # All groups will get to LDAP,
                                               # since the prefix is blank and
                                               # will match all groups.

    --omit-spread SPREAD        These spreads will be ommitted from
                                syncronization.
                                In other words, they won't be touched.  Should
                                be specified in the same way as for --spread.

    --remove-all-auto-groups    Delete all auto groups, which means all groups
                                that has the autogroup trait.

    -o --output-groups          Print out the group forest of auto groups and
                                quit, without doing any changes.

    -f --filters                Add an output filter that is used for finding
                                the root OUs that are used when printing out
                                the forest - see --output-groups.

    -d --dryrun                 Do not commit the changes.

    -h --help                   Show this and quit.

    """
    print __doc__
    sys.exit(exitcode)


def main():
    """Argument parsing and start of execution."""
    options, junk = getopt.getopt(sys.argv[1:],
                                  "p:ds:c:of:ar:h",
                                  ("perspective=",
                                   "dryrun",
                                   "source_system=",
                                   "remove-all-auto-groups",
                                   "collect=",
                                   "output-groups",
                                   "filters=",
                                   "spread=",
                                   "omit-spread=",
                                   "accounts",
                                   "help"))

    dryrun = False
    perspective = None
    wipe_all = False
    populate_with_primary_acc = False
    source_system = constants.system_sap
    select_criteria = dict()
    output_groups = False
    output_filters = list()
    const = Factory.get("Constants")()
    spreads = NotSet
    omit_spreads = set()

    for option, value in options:
        if option in ("-p", "--perspective"):
            perspective = int(constants.OUPerspective(value))
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-s", "--source_system"):
            source_system = getattr(constants, value)
        elif option in ("--remove-all-auto-groups",):
            wipe_all = True
        elif option in ("-c", "--collect"):
            aff_or_status, prefix = value.split(":")
            select_criteria[aff_or_status] = prefix
        elif option in ("-f", "--filters"):
            output_filters.append(value)
        elif option in ("-o", "--output-groups"):
            output_groups = True
        elif option in ("-h", "--help"):
            usage(1)
        elif option in ('-a', '--accounts'):
            populate_with_primary_acc = True
        elif option in ("-r", "--spread"):
            try:
                prefix, spread = value.split(":")
            except ValueError:
                print "Missing prefix in %s, e.g. ansatt:group@ldap" % option
                sys.exit(1)
            spread = const.human2constant(spread, const.Spread)
            if spread is None:
                logger.warn("Unknown spread value %s", value)
                continue

            if spreads is NotSet:
                spreads = set()
            spreads.add((prefix, spread))
        elif option in ("--omit-spread"):
            prefix, spread = value.split(":")
            spread = const.human2constant(spread, const.Spread)
            if spread is None:
                logger.warn("Unknown spread value %s", value)
                continue

            omit_spreads.add((prefix, spread))
    if output_groups:
        output_group_forest(output_filters, perspective)
        sys.exit(0)
    elif wipe_all:
        perform_delete()
    else:
        select_criteria = load_registration_criteria(select_criteria)
        perform_sync(select_criteria, perspective, source_system, spreads,
                     omit_spreads, populate_with_primary_acc)

    if dryrun:
        database.rollback()
        logger.debug("Rolled back all changes")
    else:
        database.commit()
        logger.debug("Committed all changes")


if __name__ == "__main__":
    main()
