#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
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
This script creates and syncs OU PosixGroups for all OUs existing in Cerebrum

# ***************** General script execution explaination ***************** #

# Load dicts to speed up process

# Load ou corresponding to default_start_ou

# Call recursive function with loaded ou
   # if loaded ou does not have group, create group
   # else remove group_id from group_delete_list

   # if loaded ou has parent ou
      # if group corresponding to loaded ou is not member of group
      corresponding to parent ou, add membership
      # else remove member from members_delete_dict

   # for each affiliated person on loaded ou
      # if person (account) and its affiliation do not exist on group
      corresponding to loaded ou, add membership
      # else remove member from members_delete_dict

   # for each child of loaded ou
      # run recursive function

# Remove non synced data
   # Remove all members remaining in members_delete_dict
   # Remove/Expire all empty ou-groups:*:TEKNISK/VITENSKAPELIG/STUDENT/EVT
   # Remove/Expire all groups remaining in group_delete_list
"""

import argparse
import logging
import sys

import cereconf
import mx.DateTime
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixGroup
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)

group_dict = members_dict = ou_affiliates_dict = group_description_dict = stedkode_dict = description_group_dict = {}
group_delete_list = members_delete_dict = None

# Default values
default_perspective = 1
default_prefix = 'ou_groups'
default_separator = ':'
default_start_ou = 3  # Universitetet i Tromsø
default_group_visibility = None
default_spread = None
default_creator = None
default_memberop = None
group_type_id = None
group_namespace = None
account_type_id = None

db = Factory.get('Database')()
db.cl_init(change_program='process_ou_groups.py')

co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
# Used to create container groups for account members
possible_member_types = ['VITENSKAPELIG', 'TEKNISK', 'STUDENT', 'DRGRAD']
# Used to determine which aff_code_statuses correspond to which container group
member_type_mappings = {
    'VITENSKAPELIG': [int(co.affiliation_tilknyttet_fagperson),
                      int(co.affiliation_manuell_gjesteforsker),
                      int(co.affiliation_status_ansatt_vitenskapelig)],
    'TEKNISK': [int(co.affiliation_status_ansatt_tekadm), ],
    'STUDENT': [int(co.affiliation_status_student_aktiv), ],
    'DRGRAD': [int(co.affiliation_status_student_drgrad), ]}


def ou_name(ou):
    return ou.get_name_with_language(name_variant=co.ou_name,
                                     name_language=co.language_nb,
                                     default="")


# end ou_name

def process_ou_groups(ou, perspective):
    """
    Recursive function that will create groups and add spreads and members to
    them.

    """
    global group_dict, members_dict, ou_affiliates_dict, stedkode_dict
    global group_delete_list, members_delete_dict
    global db, default_group_visibility, default_creator
    global default_spread
    global group_type_id, default_memberop, account_type_id
    global group_description_dict, description_group_dict

    logger.info("Now processing OU %s (%s)", ou.entity_id, ou_name(ou))

    gr = PosixGroup.PosixGroup(db)
    aux_gr = PosixGroup.PosixGroup(db)

    if ou.entity_id not in group_dict:
        logger.info("Create PosixGroup and give spread")
        # create group and give spread
        gr_name = ou_name(ou) + ' (' + stedkode_dict[ou.entity_id] + ')'
        gr.populate(creator_id=default_creator,
                    visibility=default_group_visibility,
                    name=gr_name,
                    description='ou_group:' + stedkode_dict[ou.entity_id])
        gr.write_db()
        # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
        # gr.add_spread(default_spread)
        current_group = gr.entity_id
        group_dict[ou.entity_id] = current_group
        group_description_dict[current_group] = gr.description
        description_group_dict[gr.description] = current_group
    else:
        # remove from delete dict
        logger.info("PosixGroup already exists")
        current_group = group_dict[ou.entity_id]
        group_delete_list.remove(current_group)

    # if loaded ou has parent ou
    if ou.get_parent(perspective):
        logger.info(
            'OU has parent - checking if group needs to be made member of '
            'parent group.')
        parent_group = group_dict[ou.get_parent(perspective)]

        # if group corresponding to loaded ou is not member of group
        # corresponding to parent ou
        if parent_group not in members_dict:
            members_dict[parent_group] = []
        if not (current_group, None) in members_dict[parent_group]:
            # add group member
            logger.info(
                "Add current group (%s) as member of parent group (%s)",
                current_group, parent_group)

            gr.clear()
            gr.find(parent_group)
            gr.add_member(current_group)

            members_dict[parent_group].append((current_group, None))
        else:
            # remove member from members_delete_dict
            logger.info(
                "Current group already member of supposed parent group")
            members_delete_dict[parent_group].remove((current_group, None))

    # for each affiliated person on loaded ou
    if ou.entity_id not in ou_affiliates_dict:
        logger.info("No affiliates on current OU")
    else:
        logger.info("Cycling affiliates of current OU")
        for affiliate in ou_affiliates_dict[ou.entity_id]:
            # if person and its affiliation does not exist on group
            # corresponding to loaded ou, add membership*

            if current_group not in members_dict:
                members_dict[current_group] = []

            if affiliate not in members_dict[current_group]:
                # add membership
                logger.info(
                    "Affiliate %s is not member - will be added as group "
                    "member, type %s",
                    affiliate[0], affiliate[1])

                container_exists = False
                for aux_affiliate in members_dict[current_group]:
                    if aux_affiliate[1] == affiliate[1]:
                        container_exists = True
                        break

                # kbj005 17.12.2014:
                # We can have a situation where members_dict[current_group]
                # has no members of the type in affiliate[1] (e.g. 'STUDENT'),
                # but a container for this type
                # (e.g. 'ou_group:319100:STUDENT') exists in the database.
                # This situation will not be detected by the above test, and
                # container_exists will be False although the container does
                # exist in the database, leading to an error when the script
                # tries to create a group in the database that already exists.
                # description_group_dict contains info about all ou and
                # container groups in the database, so checking if the
                # container is in description_group_dict is a safer way to
                # find out if it exists in the database.
                # NOTE: The test above here could probably be replaced with the
                # test below here, thus avoiding the need for two tests.
                if not container_exists:
                    if ('ou_group:' + stedkode_dict[ou.entity_id] + ':' +
                            affiliate[1] in description_group_dict):
                        container_exists = True

                # Create container group
                if not container_exists:
                    gr.clear()
                    gr_name = ou_name(ou) + ' (' + stedkode_dict[
                        ou.entity_id] + ')' + ' - ' + affiliate[1]
                    gr.populate(creator_id=default_creator,
                                visibility=default_group_visibility,
                                name=gr_name,
                                description='ou_group:' + stedkode_dict[
                                    ou.entity_id] + ':' + affiliate[1])
                    gr.write_db()
                    # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
                    # gr.add_spread(default_spread)
                    aux_gr.clear()
                    aux_gr.find(current_group)
                    aux_gr.add_member(gr.entity_id)
                    members_dict[current_group].append((gr.entity_id, None))
                else:
                    gr.clear()
                    gr.find(description_group_dict['ou_group:' + stedkode_dict[
                        ou.entity_id] + ':' + affiliate[1]])

                gr.add_member(affiliate[0])

                members_dict[current_group].append(affiliate)
                group_description_dict[gr.entity_id] = gr.description
                description_group_dict[gr.description] = gr.entity_id
            else:
                # remove member from members_delete_dict
                members_delete_dict[current_group].remove(affiliate)

    # for each child of loaded ou, run recursive function
    children = ou.list_children(perspective)
    for child in children:
        ou.clear()
        ou.find(long(child['ou_id']))
        process_ou_groups(ou, perspective)

    return


def clean_up_ou_groups():
    """Function that will remove obsolete groups and members"""
    global group_delete_list, members_delete_dict, group_description_dict
    global description_group_dict, db, default_spread, group_namespace

    gr = PosixGroup.PosixGroup(db)

    # Remove all members remaining in members_delete_dict
    for group_id in members_delete_dict.keys():

        for member in members_delete_dict[group_id]:
            member_id = member[0]
            member_type = member[1]

            if member_type is None:
                working_group = group_id
            else:
                working_group = description_group_dict[
                    group_description_dict[group_id] + ':' + member_type]

            gr.clear()
            gr.find(working_group)
            logger.info("Removing old member %s from group %s",
                        member_id, working_group)
            gr.remove_member(member_id)

    # Remove all empty ou-groups:*:TEKNISK/VITENSKPELIG/STUDENT/EVT
    for member_type in possible_member_types:
        logger.info("Searching empty container groups for " + member_type)
        groups = gr.search(description='ou_group:%:' + member_type)
        for group in groups:
            gr.clear()
            gr.find(group[0])
            if not list(gr.search_members(group_id=gr.entity_id)):
                obsolete_group = gr.entity_id
                obsolete_group_name = gr.get_name(group_namespace)
                logger.info("Expiring empty container group %s (%s)",
                            obsolete_group, obsolete_group_name)
                gr.expire_date = mx.DateTime.now()
                logger.info(
                    "Removing spread for empty container group %s (%s)",
                    obsolete_group, obsolete_group_name)
                # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
                # gr.delete_spread(default_spread)
                gr.write_db()
                logger.info("Prefixing its group_name with its group_id")
                gr.update_entity_name(group_namespace, '#' + str(
                    obsolete_group) + '# ' + obsolete_group_name)
                for old_parent in gr.search(member_id=obsolete_group,
                                            indirect_members=False):
                    gr.clear()
                    gr.find(old_parent["group_id"])
                    logger.info(
                        "Removing its membership from parent group %s (%s)",
                        gr.entity_id, gr.get_name(group_namespace))
                    gr.remove_member(obsolete_group)
                    gr.write_db()

    # Remove all groups remaining in group_delete_list
    for group_id in group_delete_list:
        gr.clear()
        gr.find(group_id)
        logger.info(
            "Expiring unused OU group %s (%s)", group_id, gr.description)
        gr.expire_date = mx.DateTime.now()
        logger.info("Removing spread for unused OU group %s (%s)",
                    group_id, gr.description)
        # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
        # gr.delete_spread(default_spread)
        gr.write_db()
        logger.info("Prefixing its group_name with its group_id")
        gr.update_entity_name(group_namespace,
                              '#' + str(group_id) + '# ' + gr.get_name(
                                  group_namespace))

    return


def main(inargs=None):
    global group_dict, members_dict, ou_affiliates_dict
    global group_delete_list, members_delete_dict, stedkode_dict
    global db, default_perspective, default_start_ou
    global group_description_dict, possible_member_types, member_type_mappings
    global default_creator, default_spread, default_group_visibility
    global default_memberop, group_type_id, account_type_id
    global description_group_dict, group_namespace

    # Parse arguments
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-p', '--perspective',
                        help='filter process on determined perspective code',
                        default=default_perspective)
    parser = add_commit_args(parser, default=True)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    ou = Factory.get('OU')(db)
    gr = PosixGroup.PosixGroup(db)

    # Load default constant values
    co = Factory.get('Constants')(db)
    default_group_visibility = co.group_visibility_all
    default_spread = co.spread_uit_ad_group
    default_memberop = co.group_memberop_union
    group_type_id = co.entity_group
    account_type_id = co.entity_account
    group_namespace = co.group_namespace

    # Load group_dict - {ou_id:group_id}
    #      group_delete_list - [ou_id,]
    #      group_description_dict - {group_id:description}
    logger.info("Loading dict: ou > group_id")
    group_dict = {}
    group_description_dict = {}
    group_delete_list = []
    stedkoder = ou.get_stedkoder()
    groups = gr.search(description='ou_group:*')

    for stedkode in stedkoder:
        stedkode_dict[stedkode['ou_id']] = (
                str(stedkode['fakultet']).zfill(2) +
                str(stedkode['institutt']).zfill(2) +
                str(stedkode['avdeling']).zfill(2)
        )
    for group in groups:
        # Cache group description no matter what
        group_description_dict[group['group_id']] = group['description']
        description_group_dict[group['description']] = group['group_id']

        # Skip group caching if group is a container for account members
        skip = False
        for possible_type in possible_member_types:
            if group['description'].find(possible_type) > -1:
                skip = True
            break
        if skip is True:
            continue

        # OU groups are cached
        elems = group['description'].split(':')

        if len(elems) == 2:
            group_delete_list.append(group['group_id'])

        # Only OU groups (and not containers) are cached!
        for stedkode in stedkoder:
            if len(elems) == 2 and elems[1] == str(stedkode['fakultet']).zfill(
                    2) + \
                    str(stedkode['institutt']).zfill(2) + \
                    str(stedkode['avdeling']).zfill(2):
                group_dict[stedkode['ou_id']] = group['group_id']
                break

    # Load members dict - {group_id:(member_id, member_type)}
    # *** member_type is: GRUPPE, TEKNISK, VITENSKAPELIG, STUDENT, GJEST... ***
    logger.info("Loading dict: group_id > members")
    members_dict = {}
    members_delete_dict = {}
    aux_group = PosixGroup.PosixGroup(db)
    working_group = PosixGroup.PosixGroup(db)

    # NO NEED TO EXECUTE QUERY AGAIN:
    # groups = gr.search(description = 'ou_group:*')
    for group in groups:

        # Skip member caching if group is a container for account members
        skip = False
        for possible_type in possible_member_types:
            if group['description'].find(possible_type) > -1:
                skip = True
                break
        if skip is True:
            continue

        working_group.clear()
        working_group.find(group['group_id'])
        for member in working_group.search_members(
                group_id=working_group.entity_id):
            # For each account member container, fill inn members for OU group
            member_is_ou = True
            member_type = int(member["member_type"])
            member_id = int(member["member_id"])

            for possible_type in possible_member_types:
                if (member_type == group_type_id and
                        group_description_dict[member_id] ==
                        group_description_dict[
                            group['group_id']] + ':' + possible_type):

                    aux_group.clear()
                    aux_group.find(member_id)
                    for aux_member in aux_group.search_members(
                            group_id=aux_group.entity_id):
                        aux_member_id = int(aux_member["member_id"])
                        aux_member_type = int(aux_member["member_type"])

                        if aux_member_type == account_type_id:
                            if group['group_id'] not in members_dict:
                                members_dict[group['group_id']] = []
                                members_delete_dict[group['group_id']] = []
                            members_dict[group['group_id']].append(
                                (aux_member_id, possible_type))
                            members_delete_dict[group['group_id']].append(
                                (aux_member_id, possible_type))
                    member_is_ou = False
                    break

            if member_is_ou:
                if group['group_id'] not in members_dict:
                    members_dict[group['group_id']] = []
                    members_delete_dict[group['group_id']] = []
                members_dict[group['group_id']].append((member_id, None))
                members_delete_dict[group['group_id']].append(
                    (member_id, None))

    # 159419L: [(159933L, None), (159938L, None)]

    # Load person to account dict (for local use)
    ac = Factory.get('Account')(db)
    primary_acs = ac.list_accounts_by_type(primary_only=True)
    person2acc = {}
    for primary_ac in primary_acs:
        person2acc[primary_ac['person_id']] = primary_ac['account_id']

    # Load creator id (global)
    ac.clear()
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator = ac.entity_id

    # Load ou affiliates dict - {ou_id:[(person_id, affiliation),]}
    logger.info("Loading dict: ou_id > affiliates")
    ou_affiliates_dict = {}

    pe = Factory.get('Person')(db)
    affs = pe.list_affiliations()
    for aff in affs:
        for possible_type in possible_member_types:
            if aff['status'] in member_type_mappings[possible_type]:
                tmp_acc_id = None
                if aff['person_id'] in person2acc:
                    tmp_acc_id = person2acc[aff['person_id']]
                else:
                    logger.debug(
                        'Could not find primary account for person: %s',
                        aff['person_id'])
                    break

                aff_tuple = (tmp_acc_id, possible_type)

                # Skip repeated entries and avoid creating entries for an OU
                # until it has affiliates
                if (aff['ou_id'] not in ou_affiliates_dict or
                        aff_tuple not in ou_affiliates_dict[aff['ou_id']]):
                    if aff['ou_id'] not in ou_affiliates_dict:
                        ou_affiliates_dict[aff['ou_id']] = []
                    ou_affiliates_dict[aff['ou_id']].append(aff_tuple)
                    continue

    # Get start OU from ou_structure tree
    ou.clear()
    ou.find(default_start_ou)

    # Enter recursive function to process groups
    logger.info("Starting to process groups, first out is: %s", ou_name(ou))
    process_ou_groups(ou=ou, perspective=args.perspective)
    logger.info("Finished processing groups")

    # Delete groups belonging to no longer imported OUs and removing old
    # members
    logger.info(
        "Starting to clean up the mess left behind "
        "(Please read: expiring and deleting obsolete elements)")
    clean_up_ou_groups()
    logger.info("Finished cleaning up")

    if args.commit:
        db.commit()
        logger.info("Committing all changes to DB")
    else:
        db.rollback()
        logger.info("Dryrun, rolling back changes")



def usage():
    print """
    usage:: python process_ou_groups.py
    -p | --perspective : filter process on determined perspective code
    -d | --dryrun      : do not commit changes
    """
    sys.exit(1)


if __name__ == '__main__':
    main()
