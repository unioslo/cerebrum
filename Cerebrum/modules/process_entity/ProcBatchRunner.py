#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2006 University of Oslo, Norway
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
from __future__ import unicode_literals

import re
import sys
import getopt

import cerebrum_path
import procconf

from Cerebrum.Utils import Factory, auto_super
from Cerebrum.modules.process_entity.ProcUtils import ProcFactory
from Cerebrum import Errors


# Classes like this are very segmented. Sequential code may be split
# up into several methods to allow better Mixin support. Crucial
# code should be split into a method so it can be overridden.


class ProcBatchRunner(object):
    """Class for wrapping process_entity into a batch job. Deals
    with parameters to the script and invoking APIs where actual
    work is done."""

    __metaclass__ = auto_super

    def __init__(self, argv, logger):
        self.short_args = 'hd'
        self.long_args = ['help', 'dry-run', ]

        self.logger = logger
        self.dryrun = False
        try:
            opts, args = getopt.getopt(argv,
                                       self.short_args,
                                       self.long_args)
        except getopt.GetoptError as e:
            self.logger.warning(e)
            self.usage(1)

        for opt, val in opts:
            if opt in ('-h', '--help'):
                self.usage()
            elif opt in ('-d', '--dry-run'):
                self.dryrun = True

        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.proc = ProcFactory.get('Handler')(self.db, logger)
        self.process_entities()

    @staticmethod
    def usage(exit_code=0):
        print("""
        This is a script for processing data in Cerebrum according to
        a set of rules defined by business logic and a config file.
          -h, --help         This message
          -d, --dry-run      Dry-run the process
        """)
        sys.exit(exit_code)

    def process_entities(self):
        """Here we simulate a ChangeLogHandler and create events
        for the ProcHandler to process. This is basically listing
        all enitities that are defined to be handled by
        'process_entity' and passing them to ProcHandler to
        evaluate.

        Entities we define are: Person, OU and Group. Account is
        handled by internal rules in ProcHandler."""

        for p in procconf.PROC_METHODS:
            self.logger.debug("Calling %s()" % p)
            getattr(self, p)()
        if self.dryrun:
            self.logger.info("rollback()")
            self.proc.rollback()
        else:
            self.logger.info("commit()")
            self.proc.commit()

    def process_persons(self):
        """Feed the Handler Person objects."""
        per = Factory.get('Person')(self.db)

        for row in per.list_persons():
            p_id = int(row['person_id'])
            per.clear()
            per.find(p_id)
            self.proc.process_person(per)

    def process_groups(self):
        """Feed the Handler Group names. Groups can be deleted before
        they are processed by this handler."""
        grp = Factory.get('Group')(self.db)

        # Add all imported groups into the list we want to examine.
        # Also add all generated groups with their "parent" gone.
        group_names = dict()
        for row in grp.list_traits(self.co.trait_group_imported):
            e_id = int(row['entity_id'])
            try:
                grp.clear()
                grp.find(e_id)
                group_name = grp.group_name
            except Errors.NotFoundError:
                self.logger.error("No group with id %r", e_id)
                continue
            group_names[group_name] = None
        for row in grp.list_traits(self.co.trait_group_derived):
            e_id = int(row['entity_id'])
            try:
                grp.clear()
                grp.find(e_id)
                group_name = grp.group_name
            except Errors.NotFoundError:
                self.logger.error("No group with id %r", e_id)
                continue
            normal_name = procconf.NORMAL(group_name)
            if not normal_name:
                self.logger.warning("Group '%s' has an odd name for a generated group. Skipping" % row['name'])
                continue
            if normal_name not in group_names:
                self.logger.debug(
                    "prc_grps: Group '%s' added to check list. Derived from '%s'" % (normal_name, row['name']))
                group_names[normal_name] = None
        for name in group_names:
            self.proc.process_group(name)

    def process_OUs(self):
        """Feed the Handler OU objects."""
        ou = Factory.get('OU')(self.db)

        for row in ou.search():
            ou.clear()
            ou.find(row['ou_id'])
            self.proc.process_ou(ou)

    def process_account_types(self):
        """Feed the handler account_types that should be updated. An
        account_type will result in being member of a special group.
        Traverse the groups and account_types to sync them. In a
        Changelog setting, this information will be fed to the Handler
        by the ChangeLog.

        In this batch job, we generate a map of affiliations and
        groups and send the correct add/del requests to the Handler.
        This is a bit ineffective, but has to be like this to mimic
        the ChangeLog"""
        grp = Factory.get('Group')(self.db)
        ac = Factory.get('Account')(self.db)
        ou = Factory.get('OU')(self.db)

        # Build up a cache of account_types
        ac2aff = {}
        for row in ac.list_accounts_by_type(affiliation=(self.co.affiliation_ansatt,
                                                         self.co.affiliation_teacher,
                                                         self.co.affiliation_elev)):
            ac2aff.setdefault((int(row['affiliation']), int(row['ou_id'])), []).append(row['account_id'])

        group_name_re = re.compile('(\w+)\s+(\w+)')
        # TODO: move into procconf.py
        txt2aff = {'Tilsette': (self.co.affiliation_ansatt, self.co.affiliation_teacher),
                   'Elevar': (self.co.affiliation_elev,)}
        aff_grp2ac = {}
        # Resolve the group into an OU and an affiliation. 
        for row in grp.list_traits(self.co.trait_group_affiliation):
            grp.clear()
            grp.find(row['entity_id'])
            self.logger.debug("Processing '%s'." % grp.group_name)
            m = group_name_re.search(grp.group_name)
            if m:
                affiliation = m.group(2)
                ou_acronym = m.group(1)
            else:
                # Group's name doesn't match the criteria. Fail.
                self.logger.warning("Group '%s' has an odd name for a generated aff group. Skipping" % grp.group_name)
                continue
            ous = ou.search_name_with_language(entity_type=self.co.entity_ou,
                                               name_variant=self.co.ou_name_acronym,
                                               name=ou_acronym,
                                               name_language=self.co.language_nb)
            if len(ous) > 1:
                self.logger.warning("Acronym '%s' results in more than one OU. "
                                    "Skipping" % ou_acronym)
                continue
            if len(ous) == 0:
                self.logger.warning("Acronym '%s' doesn't resolve to an OU." %
                                    ou_acronym)
                # TBD: What to do? Delete the group? Let The Handler deal with it?
                continue
            ou.clear()
            ou.find(ous[0]['entity_id'])
            # Send a delete call to the Handler if the group has accounts in it
            # without the proper account_type.
            for member in grp.search_members(group_id=grp.entity_id):
                member_id = int(member["member_id"])
                for a in txt2aff[affiliation]:
                    if ((int(a), ou.entity_id) in ac2aff and
                            member_id in ac2aff[(int(a), ou.entity_id)]):
                        aff_grp2ac.setdefault(
                            (int(a), ou.entity_id), []
                        ).append(member_id)
                        break
                else:
                    self.proc.ac_type_del(member_id, affiliation, ou.entity_id)

        # Let the handler take take of added account_types.
        for i in ac2aff:
            for account in ac2aff[i]:
                if not (i in aff_grp2ac and account in aff_grp2ac[i]):
                    self.proc.ac_type_add(account, i[0], i[1])
    # end process_account_types

# end class ProcBatchRunner
