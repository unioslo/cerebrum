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
from Cerebrum.modules.tasks.formatting import TaskFormatter
from Cerebrum.modules.tasks.task_queue import (TaskQueue,
                                               sql_search)
from Cerebrum.Utils import Factory

class SapImport(BofhdCommonMethods):
    """This class exists to serve the bofh command person dfosap_import"""

    def __init__(self, db, dfo_pid):
        self.dfo_pid = dfo_pid
        self.db_ = db
        self.pe = Factory.get('Person')(db)
        self.co = Factory.get('Constants')(db)
        self.queued_tasks = []

        self.find_by_pid()
        task = self.make_task()
        self.push_to_queue(task)
        self.extract_from_queue()

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
        task = EmployeeTasks.create_manual_task(self.dfo_pid)
        return task

    def push_to_queue(self, task):
        """Push task to queue, thereby forcing an import"""
        TaskQueue(self.db_).push(task)

    def extract_from_queue(self):
        """Find the existing tasks in the queue for the person"""
        format_table = TaskFormatter(('queue', 'key', 'iat', 'nbf', 'attempts'))
        items=sql_search(self.db_)

        for index,row in enumerate(format_table(items, header=True)):
            if self.dfo_pid in row or index < 2:
                self.queued_tasks.append(row)


class BofhdExtension(BofhdCommonMethods):
    all_commands = {}
    authz = UioAuth

    @classmethod
    def get_help_strings(cls):
        command_help = {
            'person': {
                'dfosap_import': 'Trigger person-import from DFO-SAP',
            },
        }
        arg_help = {
            'dfo_pid':
            ['dfo_pid', 'Enter employee number',
             'Enter the employee number (ansattnummer, dfo_pid) for a person'],
        }
        return ({},
                command_help,
                arg_help)

    #
    # person dfosap_import
    #
    all_commands['person_dfosap_import'] = Command(
        ("person", "dfosap_import"),
        SimpleString(help_ref='dfo_pid'),
        fs=FormatSuggestion([
            (u'DFØ PID %s added to queue \n', ('dfo_pid',)),
            (u'Tasks in queue for this person: \n %s', ('queued_tasks',))
        ]),
        perm_filter='is_schoolit'
    )

    def person_dfosap_import(self, operator, dfo_pid):
        """Add an emnployee number to the queue  in order to
        trigger import and return whatever lies in queue."""
        self.ba.is_schoolit(operator.get_entity_id())

        simp = SapImport(self.db, dfo_pid)

        return [{'dfo_pid': dfo_pid,
                 "queued_tasks": '\n'.join(simp.queued_tasks)}]
