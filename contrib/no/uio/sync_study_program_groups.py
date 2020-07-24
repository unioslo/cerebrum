#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2020 University of Oslo, Norway
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
This script creates and deletes study program groups in Cerebrum, so that they
match with information from FS.
"""
from __future__ import unicode_literals

import argparse
from collections import defaultdict
import logging
import six
import xml.etree.ElementTree as ET

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

import cereconf

logger = logging.getLogger(__name__)


class StudyProgramSync():

    def __init__(self, person_file, database, commit=False):
        self.person_file = person_file
        self.commit = commit
        self.database = database
        self.group = Factory.get("Group")(self.database)
        self.person = Factory.get("Person")(self.database)
        self.co = Factory.get("Constants")(self.database)
        self.creator_account = Factory.get('Account')(self.database)
        self.creator_account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)

    def build_fs_dict(self):
        """
        build a dict where the keys are names of study programs in FS
        and the value is a list of all members of each program
        """
        fs_dict = defaultdict(set)
        root = ET.parse(self.person_file).getroot()
        for aktiv in root.findall('opptak'):
            if aktiv.get('studentstatkode') != 'AKTIV':
                continue
            student = self.person.search_external_ids(
                id_type=self.co.externalid_studentnr,
                external_id=aktiv.get('studentnr_tildelt'))
            if not student:
                logger.error('student with studentnr %r not found in cerebrum',
                             aktiv.get('studentnr_tildelt'))
                continue
            study_program = 'm-studieprogram-' + aktiv.get('studieprogramkode')
            self.person.find(student[0]['entity_id'])
            primary_account = self.person.get_primary_account()
            if not primary_account:
                logger.info('no primary account for person %r',
                            self.person.entity_id)
            else:
                fs_dict[study_program].add(primary_account)
            self.person.clear()
        return fs_dict

    def build_cerebrum_dict(self):
        """
        build a dict where the keys are names of study program groups
        in cerebrum and the value is a list of all members of each group
        """
        crb_dict = defaultdict(set)
        group_members = self.group.search_members(
            group_type=self.co.group_type_study_program)
        for grp_mem in group_members:
            crb_dict[grp_mem['group_name']].add(grp_mem['member_id'])
        return crb_dict

    def create_groups(self, groups_to_create):
        """create the given groups"""
        for group in groups_to_create:
            self.group.populate(
                creator_id=self.creator_account.entity_id,
                visibility=self.co.group_visibility_all,
                name=group,
                description='Gruppe med primærbrukere til studenter på '
                'studieprogrammet {}'.format(
                    group.replace('m-strudieprogram-', '')),
                group_type=self.co.group_type_study_program
            )
            self.group.write_db()
            self.group.add_spread(self.co.spread_uio_nis_ng)
            self.group.write_db()
            self.group.clear()

    def delete_groups(self, groups_to_delete):
        """delete the given groups"""
        for group in groups_to_delete:
            self.group.find_by_name(group)
            self.group.delete()
            self.group.clear()

    def add_members_to_groups(self, members_to_add):
        """add the members to the given groups"""
        for group, members in members_to_add.items():
            self.group.find_by_name(group)
            for mem in members:
                self.group.add_member(mem)
            self.group.clear()

    def remove_members_from_groups(self, members_to_rem):
        """remove the members from the given groups"""
        for group, members in members_to_rem.items():
            self.group.find_by_name(group)
            for mem in members:
                self.group.remove_member(mem)
            self.group.clear()

    def sync_groups(self):
        """
        Update the study program groups in cerebrum to match the actual
        study programs as given by fs.
        """
        fs_dict = self.build_fs_dict()
        crb_dict = self.build_cerebrum_dict()

        groups_to_create = set(fs_dict) - set(crb_dict)
        groups_to_delete = set(crb_dict) - set(fs_dict)
        members_to_add = {group: fs_dict[group] - crb_dict[group]
                          for group in fs_dict
                          if fs_dict[group] - crb_dict[group]}
        members_to_rem = {group: crb_dict[group] - fs_dict[group]
                          for group in (set(crb_dict) - groups_to_delete)
                          if crb_dict[group] - fs_dict[group]}

        self.create_groups(groups_to_create)
        self.delete_groups(groups_to_delete)

        self.add_members_to_groups(members_to_add)
        self.remove_members_from_groups(members_to_rem)

        if self.commit:
            logger.info('Commiting changes')
            self.database.commit()
        else:
            logger.info('Rolling back changes')
            self.database.rollback()


def main():

    parser = argparse.ArgumentParser()
    database = Factory.get("Database")()
    database.cl_init(change_program=parser.prog)

    parser.add_argument(
        '-f', '--person-file',
        type=six.text_type,
        help='Path to file with person info',
        required=True
    )
    add_commit_args(parser)

    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    sync = StudyProgramSync(args.person_file, database, args.commit)
    sync.sync_groups()


if __name__ == '__main__':
    main()
