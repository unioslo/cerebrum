# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" This module contains tools for the bofh command `person dfosap_import"""

import datetime
from six import text_type

from Cerebrum import Errors
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (SimpleString,
                                              Command,
                                              FormatSuggestion)
from Cerebrum.modules.bofhd.errors import (CerebrumError,
                                           PermissionDenied)
from Cerebrum.modules.no.dfo.tasks import EmployeeTasks
from Cerebrum.modules.no.uio.bofhd_auth import UioAuth
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks import process
from Cerebrum.Utils import Factory


class SapImport(BofhdCommonMethods):
    """This class exists to serve the bofh command person dfosap_import"""

    def __init__(self, db, dfo_pid):
        self.dfo_pid = dfo_pid
        self.pe = Factory.get('Person')(db)
        self.co = Factory.get('Constants')(db)
        self.data = {}
        self.queued_tasks = []

    def find_by_pid(self):
        """Verify employee number"""
        try:
            self.pe.find_by_external_id(self.co.externalid_dfo_pid,
                                        self.dfo_pid)
            self.pe.clear()
        except Errors.NotFoundError:
            raise CerebrumError('Invalid DFØ PID')

    def make_task(self):
        """Make task containing dfo pid"""
        task_cls = EmployeeTasks(process.QueueHandler)
        task = task_cls.create_manual_task(self.dfo_pid)
        return task

    def push_to_queue(self, task):
        """Push task to queue, thereby forcing an import"""
        #dryrun = True #while testing TODO: remove
        with db_context(Factory.get('Database')(), False) as db:
            TaskQueue(db).push(task)

    def extract_from_queue(self, task):
        """Check what stuff lies ahead in queue"""
        # TODO: fill list self.queued_tasks with list of tasks for self.dfo_pid
        # already in queue
        self.queued_tasks = []

    def __call__(self):
        self.find_by_pid()
        task = self.make_task()
        self.push_to_queue(task)
        #self.queued_tasks = self.extract_from_queue(task)


class BofhdExtension(BofhdCommonMethods):
    all_commands = {}
    authz = UioAuth

    #
    # person dfosap_import
    #
    all_commands['person_dfosap_import'] = Command(
        ("person", "dfosap_import"),
        SimpleString(),
        fs=FormatSuggestion([
            (u'DFØ PID %s added to queue', ('dfo_pid',))
        ]),
        perm_filter='is_superuser'
    )

    def person_dfosap_import(self, operator, dfo_pid):
        """Add an emnployee number to the queue  in order to
        trigger import and return whatever lies in queue."""

        if not self.ba.is_superuser(operator.get_entity_id()):
             raise PermissionDenied("Must be superuser to execute this command")

        simp = SapImport(self.db, dfo_pid)
        simp()

        return [{'dfo_pid': dfo_pid}]
        #"queued_tasks": simp.queued_tasks}
