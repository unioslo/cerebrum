#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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

import re
import sys
import getopt

import cerebrum_path
import procconf

from Cerebrum.Utils import Factory, auto_super
from Cerebrum.modules.process_entity.ProcUtils import ProcFactory

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
        self.long_args = ['help', 'dry-run',]

        self.logger = logger
        self.dryrun = False
        try:
            opts, args = getopt.getopt(argv,
                                       self.short_args,
                                       self.long_args)
        except getopt.GetoptError, e:
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


    def usage(self, exit_code=0):
        print """
        This is a script for processing data in Cerebrum according to
        a set of rules defined by business logic and a config file.
          -h, --help         This message
          -d, --dry-run      Dry-run the process
        """
        sys.exit(exit_code)


    def process_entities(self):
        """Here we simulate a ChangeLogHandler and create events
        for the ProcHandler to process. This is basically listing
        all enitities that are defined to be handled by
        'process_entity' and passing them to ProcHandler to
        evaluate.

        Entities we define are: Person, OU and Group. Account is
        handled by internal rules in ProcHandler."""
        self.logger.info("process_persons()")
        self.process_persons()
        self.logger.info("process_groups()")
        self.process_groups()
        self.logger.info("process_OUs()")
        self.process_OUs()
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
        for row in grp.list_traits(self.co.trait_group_imported, return_name=True):
            group_names[row['name']] = None
        for row in grp.list_traits(self.co.trait_group_derived, return_name=True):
            m = re.search("^cerebrum_(.+)", row['name'])
            if not m:
                self.logger.warning("Group '%s' has an odd name for a generated group. Skipping" % row['name'])
                continue
            if not group_names.has_key(m.group(1)):
                group_names[m.group(1)] = None
        for name in group_names:
            print name
            self.proc.process_group(name)


    def process_OUs(self):
        """Feed the Handler OU objects."""
        ou = Factory.get('OU')(self.db)

        for row in ou.list_all():
            ou_id = int(row['ou_id'])
            ou.clear()
            ou.find(ou_id)
            self.proc.process_ou(ou)
