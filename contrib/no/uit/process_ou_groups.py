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
from datetime import datetime

import cereconf
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixGroup
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def ou_name(co, ou):
    return ou.get_name_with_language(name_variant=co.ou_name,
                                     name_language=co.language_nb,
                                     default="")


class OuGroupProcessor(object):

    def __init__(self, db, perspective):
        """

        :param db: Cerebrum database object
        :param basestring perspective: OU Perspective e.g 'FS'
        """

        # Dicts
        self.group_dict = {}
        self.members_dict = {}
        self.ou_affiliates_dict = {}
        self.group_description_dict = {}
        self.stedkode_dict = {}
        self.description_group_dict = {}
        self.members_delete_dict = {}

        self.group_delete_list = []

        # Default values
        self.default_start_ou = 3  # Universitetet i Tromsø
        # self.default_spread = self.co.spread_uit_ad_group

        # Initialize database objects
        self._db = db
        self._co = Factory.get('Constants')(self._db)
        self.ou = Factory.get('OU')(self._db)
        self.gr = PosixGroup.PosixGroup(self._db)
        self.ac = Factory.get('Account')(self._db)

        self.perspective = self._co.OUPerspective(perspective)

        # Load creator id (global)
        self.ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.default_creator = self.ac.entity_id
        self.ac.clear()

        # Used to determine which aff_code_statuses correspond to which
        # container group
        self.member_type_mappings = {
            'VITENSKAPELIG': [
                int(self._co.affiliation_tilknyttet_fagperson),
                int(self._co.affiliation_manuell_gjesteforsker),
                int(self._co.affiliation_status_ansatt_vitenskapelig)],
            'TEKNISK':
                [int(self._co.affiliation_status_ansatt_tekadm), ],
            'STUDENT':
                [int(self._co.affiliation_status_student_aktiv), ],
            'DRGRAD':
                [int(self._co.affiliation_status_student_drgrad), ],
        }

    def process_ou_groups(self, ou, perspective):
        """
        Recursive function that will create groups and add spreads and members
        to them.

        """
        logger.info("Now processing OU %s (%s)",
                    ou.entity_id, ou_name(self._co, ou))

        gr = PosixGroup.PosixGroup(self._db)
        aux_gr = PosixGroup.PosixGroup(self._db)

        # TODO: Should these groups have a custom uit group_type?
        group_type = self._co.group_type_unknown

        if ou.entity_id not in self.group_dict:
            logger.info("Create PosixGroup and give spread")
            # create group and give spread
            gr_name = ou_name(self._co, ou) + ' (' + self.stedkode_dict[
                ou.entity_id] + ')'
            gr.populate(
                creator_id=self.default_creator,
                visibility=self._co.group_visibility_all,
                name=gr_name,
                description='ou_group:' + self.stedkode_dict[ou.entity_id],
                group_type=group_type,
            )
            gr.write_db()
            # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
            # gr.add_spread(self.default_spread)
            current_group = gr.entity_id
            self.group_dict[ou.entity_id] = current_group
            self.group_description_dict[current_group] = gr.description
            self.description_group_dict[gr.description] = current_group
        else:
            # remove from delete dict
            logger.info("PosixGroup already exists")
            current_group = self.group_dict[ou.entity_id]
            self.group_delete_list.remove(current_group)

        # if loaded ou has parent ou
        if ou.get_parent(perspective):
            logger.info(
                'OU has parent - checking if group needs to be made member of '
                'parent group.')
            parent_group = self.group_dict[ou.get_parent(perspective)]

            # if group corresponding to loaded ou is not member of group
            # corresponding to parent ou
            if parent_group not in self.members_dict:
                self.members_dict[parent_group] = []
            if not (current_group, None) in self.members_dict[parent_group]:
                # add group member
                logger.info(
                    "Add current group (%s) as member of parent group (%s)",
                    current_group, parent_group)

                gr.clear()
                gr.find(parent_group)
                gr.add_member(current_group)

                self.members_dict[parent_group].append((current_group, None))
            else:
                # remove member from members_delete_dict
                logger.info(
                    "Current group already member of supposed parent group")
                self.members_delete_dict[parent_group].remove(
                    (current_group, None))

        # for each affiliated person on loaded ou
        if ou.entity_id not in self.ou_affiliates_dict:
            logger.info("No affiliates on current OU")
        else:
            logger.info("Cycling affiliates of current OU")
            for affiliate in self.ou_affiliates_dict[ou.entity_id]:
                # if person and its affiliation does not exist on group
                # corresponding to loaded ou, add membership*

                if current_group not in self.members_dict:
                    self.members_dict[current_group] = []

                if affiliate not in self.members_dict[current_group]:
                    # add membership
                    logger.info(
                        "Affiliate %s is not member - will be added as group "
                        "member, type %s",
                        affiliate[0], affiliate[1])

                    container_exists = False
                    for aux_affiliate in self.members_dict[current_group]:
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
                        if ('ou_group:' + self.stedkode_dict[ou.entity_id] +
                                ':' + affiliate[1] in
                                self.description_group_dict):
                            container_exists = True

                    # Create container group
                    if not container_exists:
                        gr.clear()
                        gr_name = (
                                ou_name(self._co, ou) +
                                ' (' + self.stedkode_dict[ou.entity_id] + ')' +
                                ' - ' +
                                affiliate[1])
                        gr_desc = ('ou_group:' +
                                   self.stedkode_dict[ou.entity_id] +
                                   ':' +
                                   affiliate[1])
                        gr.populate(
                            creator_id=self.default_creator,
                            visibility=self._co.group_visibility_all,
                            name=gr_name,
                            description=gr_desc,
                            group_type=group_type,
                        )
                        gr.write_db()
                        # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
                        # gr.add_spread(self.default_spread)
                        aux_gr.clear()
                        aux_gr.find(current_group)
                        aux_gr.add_member(gr.entity_id)
                        self.members_dict[current_group].append(
                            (gr.entity_id, None))
                    else:
                        gr.clear()
                        gr_desc = ('ou_group:' +
                                   self.stedkode_dict[ou.entity_id] +
                                   ':' +
                                   affiliate[1])
                        gr.find(self.description_group_dict[gr_desc])

                    gr.add_member(affiliate[0])

                    self.members_dict[current_group].append(affiliate)
                    self.group_description_dict[gr.entity_id] = gr.description
                    self.description_group_dict[gr.description] = gr.entity_id
                else:
                    # remove member from members_delete_dict
                    self.members_delete_dict[current_group].remove(affiliate)

        # for each child of loaded ou, run recursive function
        children = ou.list_children(perspective)
        for ou_id in children:
            ou.clear()
            ou.find(ou_id)
            self.process_ou_groups(ou, perspective)

        return

    def clean_up_ou_groups(self):
        """Function that will remove obsolete groups and members"""

        gr = PosixGroup.PosixGroup(self._db)

        # Remove all members remaining in members_delete_dict
        for group_id in self.members_delete_dict.keys():

            for member in self.members_delete_dict[group_id]:
                member_id = member[0]
                member_type = member[1]

                if member_type is None:
                    working_group = group_id
                else:
                    working_group = self.description_group_dict[
                        self.group_description_dict[group_id] +
                        ':' +
                        member_type]

                gr.clear()
                gr.find(working_group)
                logger.info("Removing old member %s from group %s",
                            member_id, working_group)
                gr.remove_member(member_id)

        # Remove all empty ou-groups:*:TEKNISK/VITENSKPELIG/STUDENT/EVT
        for member_type in self.member_type_mappings:
            logger.info("Searching empty container groups for " + member_type)
            groups = gr.search(description='ou_group:%:' + member_type)
            for group in groups:
                gr.clear()
                gr.find(group[0])
                if not list(gr.search_members(group_id=gr.entity_id)):
                    obsolete_group = gr.entity_id
                    obsolete_group_name = gr.get_name(self._co.group_namespace)
                    logger.info("Expiring empty container group %s (%s)",
                                obsolete_group, obsolete_group_name)
                    gr.expire_date = datetime.now()
                    logger.info(
                        "Removing spread for empty container group %s (%s)",
                        obsolete_group, obsolete_group_name)
                    # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
                    # gr.delete_spread(self.default_spread)
                    gr.write_db()
                    logger.info("Prefixing its group_name with its group_id")
                    gr.update_entity_name(self._co.group_namespace, '#' + str(
                        obsolete_group) + '# ' + obsolete_group_name)
                    for old_parent in gr.search(member_id=obsolete_group,
                                                indirect_members=False):
                        gr.clear()
                        gr.find(old_parent["group_id"])
                        logger.info(
                            "Removing its membership from parent group "
                            "%s (%s)",
                            gr.entity_id,
                            gr.get_name(self._co.group_namespace))
                        gr.remove_member(obsolete_group)
                        gr.write_db()

        # Remove all groups remaining in group_delete_list
        for group_id in self.group_delete_list:
            gr.clear()
            gr.find(group_id)
            logger.info(
                "Expiring unused OU group %s (%s)", group_id, gr.description)
            gr.expire_date = datetime.now()
            logger.info("Removing spread for unused OU group %s (%s)",
                        group_id, gr.description)
            # SPREAD DISABLED UNTIL AD IS READY. RMI000 - 20080207
            # gr.delete_spread(self.default_spread)
            gr.write_db()
            logger.info("Prefixing its group_name with its group_id")
            gr.update_entity_name(self._co.group_namespace,
                                  '#' + str(group_id) + '# ' + gr.get_name(
                                      self._co.group_namespace))

        return

    def process(self):

        # Load group_dict - {ou_id:group_id}
        #      group_delete_list - [ou_id,]
        #      group_description_dict - {group_id:description}
        logger.info("Loading dict: ou > group_id")
        stedkoder = self.ou.get_stedkoder()
        groups = self.gr.search(description='ou_group:*')

        for stedkode in stedkoder:
            self.stedkode_dict[stedkode['ou_id']] = (
                    str(stedkode['fakultet']).zfill(2) +
                    str(stedkode['institutt']).zfill(2) +
                    str(stedkode['avdeling']).zfill(2)
            )
        for group in groups:
            # Cache group description no matter what
            group_id = group['group_id']
            group_desc = group['description']
            self.group_description_dict[group_id] = group_desc
            self.description_group_dict[group_desc] = group_id

            # Skip group caching if group is a container for account members
            skip = False
            for possible_aff in self.member_type_mappings:
                if group['description'].find(possible_aff) > -1:
                    skip = True
                break
            if skip is True:
                continue

            # OU groups are cached
            elems = group['description'].split(':')

            if len(elems) == 2:
                self.group_delete_list.append(group['group_id'])

            # Only OU groups (and not containers) are cached!
            for stedkode in stedkoder:
                if len(elems) == 2 and elems[1] == str(
                        stedkode['fakultet']).zfill(
                        2) + \
                        str(stedkode['institutt']).zfill(2) + \
                        str(stedkode['avdeling']).zfill(2):
                    self.group_dict[stedkode['ou_id']] = group['group_id']
                    break

        # Load members dict - {group_id:(member_id, member_type)}
        # member_type is: GRUPPE, TEKNISK, VITENSKAPELIG, STUDENT, GJEST...
        logger.info("Loading dict: group_id > members")
        aux_group = PosixGroup.PosixGroup(self._db)
        working_group = PosixGroup.PosixGroup(self._db)

        for group in groups:
            group_id = group['group_id']
            # Skip member caching if group is a container for account members
            skip = False
            for possible_aff in self.member_type_mappings:
                if group['description'].find(possible_aff) > -1:
                    skip = True
                    break
            if skip is True:
                continue

            working_group.clear()
            working_group.find(group_id)
            for member in working_group.search_members(
                    group_id=working_group.entity_id):
                # For each account member container, fill inn members for OU
                # group
                member_is_ou = True
                member_type = int(member["member_type"])
                member_id = int(member["member_id"])

                for possible_aff in self.member_type_mappings:
                    if (member_type == self._co.entity_group and
                            self.group_description_dict[member_id] ==
                            self.group_description_dict[
                                group_id] + ':' + possible_aff):

                        aux_group.clear()
                        aux_group.find(member_id)
                        for aux_member in aux_group.search_members(
                                group_id=aux_group.entity_id):
                            aux_member_id = int(aux_member["member_id"])
                            aux_member_type = int(aux_member["member_type"])

                            if aux_member_type == self._co.entity_account:
                                if group_id not in self.members_dict:
                                    self.members_dict[group_id] = []
                                    self.members_delete_dict[group_id] = []
                                self.members_dict[group_id].append(
                                    (aux_member_id, possible_aff))
                                self.members_delete_dict[group_id].append(
                                    (aux_member_id, possible_aff))
                        member_is_ou = False
                        break

                if member_is_ou:
                    if group_id not in self.members_dict:
                        self.members_dict[group_id] = []
                        self.members_delete_dict[group_id] = []
                    self.members_dict[group_id].append((member_id, None))
                    self.members_delete_dict[group_id].append(
                        (member_id, None))

        # 159419L: [(159933L, None), (159938L, None)]

        # Load person to account dict (for local use)
        primary_acs = self.ac.list_accounts_by_type(primary_only=True)
        person2acc = {}
        for primary_ac in primary_acs:
            person2acc[primary_ac['person_id']] = primary_ac['account_id']

        # Load ou affiliates dict - {ou_id:[(person_id, affiliation),]}
        logger.info("Loading dict: ou_id > affiliates")
        self.ou_affiliates_dict = {}

        pe = Factory.get('Person')(self._db)
        affs = pe.list_affiliations()
        for aff in affs:
            for possible_aff, status in self.member_type_mappings.items():
                if aff['status'] in status:
                    if aff['person_id'] in person2acc:
                        tmp_acc_id = person2acc[aff['person_id']]
                    else:
                        logger.debug(
                            'Could not find primary account for person: %s',
                            aff['person_id'])
                        break

                    aff_tuple = (tmp_acc_id, possible_aff)

                    # Skip repeated entries and avoid creating entries for an
                    # OU until it has affiliates
                    if (aff['ou_id'] not in self.ou_affiliates_dict or
                            aff_tuple not in
                            self.ou_affiliates_dict[aff['ou_id']]):
                        if aff['ou_id'] not in self.ou_affiliates_dict:
                            self.ou_affiliates_dict[aff['ou_id']] = []
                        self.ou_affiliates_dict[aff['ou_id']].append(aff_tuple)
                        continue

        # Get start OU from ou_structure tree
        self.ou.clear()
        self.ou.find(self.default_start_ou)

        # Enter recursive function to process groups
        logger.info("Starting to process groups, first out is: %s",
                    ou_name(self._co, self.ou))
        self.process_ou_groups(ou=self.ou, perspective=self.perspective)
        logger.info("Finished processing groups")

        # Delete groups belonging to no longer imported OUs and removing old
        # members
        logger.info(
            "Starting to clean up the mess left behind "
            "(Please read: expiring and deleting obsolete elements)")
        self.clean_up_ou_groups()
        logger.info("Finished cleaning up")


def main(inargs=None):

    # Default values
    # FIXME: Get this from somewhere sensible instead of hardcoding it
    default_perspective = 'FS'

    # Parse arguments
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-p', '--perspective',
        help='filter process on determined perspective code e.g FS',
        default=default_perspective)
    parser = add_commit_args(parser, default=False)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='process_ou_groups.py')

    processor = OuGroupProcessor(db, args.perspective)
    processor.process()

    if args.commit:
        db.commit()
        logger.info("Committing all changes to DB")
    else:
        db.rollback()
        logger.info("Dryrun, rolling back changes")


if __name__ == '__main__':
    main()
