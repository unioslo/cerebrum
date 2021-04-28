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
from Cerebrum import Utils, Errors
from Cerebrum.utils.date_compat import get_datetime_tz
from Cerebrum.modules.bofhd.bofhd_core import (BofhdCommonMethods,
                                               BofhdCommandBase)
from Cerebrum.modules.bofhd.errors import (CerebrumError,
                                           PermissionDenied)
from Cerebrum.modules.bofhd.cmd_param import (AccountName,
                                              Command,
                                              FormatSuggestion)
from Cerebrum.modules.no.dfo.tasks import (get_tasks,
                                           EmployeeTasks)
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.utils.module import resolve


def get_task_class(config):
    return resolve(config.task_class)


class SapImport(BofhdCommonMethods):
    """This class exists to serve the bofh command <NAME>"""

    def __init__(self, db, dfo_pid):
        self.dfo_pid = dfo_pid
        self.pe = Utils.Factory.get('Person')(db)
        self.co = Utils.Factory.get('Constants')(db)
        self.data = {}
        self.queued_tasks = []

    def find_by_pid(self):
        """Verify that employee number is kosher"""
        # externalid_sap_ansattnr jon austad = 10169561
        # Remove comments and set to dfo_pid...   6072205
        # self.pe.find_by_external_id(self.co.externalid_dfo_pid,
        #                             self.dfo_pid)
        try:
            # self.pe.find_by_external_id(self.co.externalid_sap_ansattnr,
            #                             self.dfo_pid)
            self.pe.find_by_external_id(self.co.externalid_dfo_pid,
                                        self.dfo_pid)
            print(self.pe.__dict__)
            self.pe.clear()
            return True
        except Errors.NotFoundError:
            return False

    def make_event(self):
        """Make event"""
        event = None
        return event

    def push_to_queue(self, event):
        """Push dfo_pid to queued and thereby force an import."""
        tasks = get_tasks(event)

    def extract_from_queue(self, event):
        """Check what stuff lies ahead in queue"""
        # tasks = get_tasks(event)
        return None

    def __call__(self):
        event = 0
        if not self.find_by_pid():
            print('faaaail')
            return False
        event = self.make_event()
        self.push_to_queue(event)
        self.queued_tasks = self.extract_from_queue(event)


class BofhdExtension(BofhdCommandBase):
    all_commands = {}

    @classmethod
    def get_help_strings(cls):
        group_help = {
            'person': "Commands for administering persons",
        }

        command_help = {
            'person': {
                'dfosap_import': 'Trigger person-import from DFO-SAP',
            },
        }
        arg_help = {
            'dfo_pid':
            ['uname', 'Enter employee number',
             'Enter the employee number (ansattnummer, dfo_pid) for a person'],
        }
        return (group_help,
                command_help,
                arg_help)

    #
    # person dfosap_import
    #
    all_commands['person_dfosap_import'] = Command(
        ("person", "dfosap_import"),
        AccountName(help_ref="id:target:dfo_pid"),
        fs=FormatSuggestion([
            ('\nQueued tasks for %i:\n', ('dfo_pid')),
            ('%s', ('queued_tasks',)), ]),
        perm_filter='can_set_password')

    def person_dfosap_import(self, operator, dfo_pid):
        """Add an emnployee number to the queue  in order to
        trigger import and return whatever lies in queue."""

        # Primary intended users are Houston.
        # A different check is appropriate
        # ac = self._get_account(accountname, idtype='name')
        # if not self.ba.can_set_password(operator.get_entity_id(), ac):
        #     raise PermissionDenied("Access denied")
        simp = SapImport(self.db, dfo_pid)
        simp()
        return dfo_pid, simp.queued_tasks


if __name__ == '__main__':
    db = Utils.Factory.get('Database')()
    logger = Utils.Factory.get_logger('console')
    dfosap_import = BofhdExtension(db, logger)
