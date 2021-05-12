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
from Cerebrum.Utils import Factory
from Cerebrum.utils.date_compat import get_datetime_tz
from Cerebrum.modules.bofhd.bofhd_core import (BofhdCommonMethods,
                                               BofhdCommandBase)
from Cerebrum.modules.bofhd.errors import (CerebrumError,
                                           PermissionDenied)
from Cerebrum.modules.bofhd.cmd_param import (Id,
                                              PersonId,
                                              SimpleString,
                                              AccountName,
                                              Command,
                                              FormatSuggestion)
from Cerebrum.modules.no.dfo.tasks import (get_tasks,
                                           EmployeeTasks)
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.utils.module import resolve
from Cerebrum.modules.tasks.task_queue import TaskQueue

from Cerebrum.modules.tasks import process

from Cerebrum.database.ctx import db_context

#from Cerebrum.modules.bofhd.auth import BofhdAuth

from Cerebrum.modules.no.uio.bofhd_auth import UioAuth


#crb-config-uio/etc/cerebrum/config/hr-import-employees.yml #config

#python /cerebrum/share/cerebrum/contrib/hr-import/create-task.py -c /cerebrum/etc/cerebrum/config/hr-import-employees.yml 6069138 --commit

#task_class: "Cerebrum.modules.no.dfo.tasks:EmployeeTasks"

#ref.for å liste opp tasks i kø:
#contrib/hr-import/list-tasks.py

#def get_task_class(config):
#    return resolve(config.task_class)


class SapImport(BofhdCommonMethods):
    """This class exists to serve the bofh command person dfosap_import"""

    def __init__(self, db, dfo_pid):
        self.dfo_pid = dfo_pid
        self.pe = Utils.Factory.get('Person')(db)
        self.co = Utils.Factory.get('Constants')(db)
        self.data = {}
        #self.queued_tasks = []
        self.queued_tasks = None

    def find_by_pid(self):
        """Verify employee number"""
        #sim dfo pid 6065447
        #sim sap ansattnr 10193177
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
        """Push task to queue, thereby forcing an import."""
        dryrun = True #while testing TODO: remove
        with db_context(Factory.get('Database')(), dryrun) as db:
            TaskQueue(db).push(task)

    def extract_from_queue(self, task):
        """Check what stuff lies ahead in queue"""
        #TODO
        # tasks = get_tasks(task)

        """
        def get_task_handler(config):
        import_cls = resolve(config.import_class)
        logger.info('import_cls: %s', config.import_class)

        task_cls = resolve(config.task_class)
        logger.info('task_cls: %s', config.task_class)

        get_importer = functools.partial(import_cls, config=config)
        return task_cls(get_importer)

        config = TaskImportConfig.from_file(args.config)
        handle = get_task_handler(config)

        format_table = TaskFormatter(('queue', 'key', 'nbf'))

        with db_context(Factory.get('Database')(), dryrun=True) as db:
        items = sql_search(db, queues=handle.all_queues, limit=args.limit)
        for row in format_table(items, header=True):
             print(row)

        """
        return 10 #placeolder


    def __call__(self):
        self.find_by_pid()
        task = self.make_task()
        self.push_to_queue(task)
        #self.queued_tasks = self.extract_from_queue(task)


#class BofhdExtension(BofhdCommandBase):
class BofhdExtension(BofhdCommonMethods):
    all_commands = {}
    authz = UioAuth

    """
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
    """
    #
    # person dfosap_import
    #
    all_commands['person_dfosap_import'] = Command(
        ("person", "dfosap_import"),
        SimpleString(),
        fs=FormatSuggestion([
            ('DFØ PID %s added to queue', ('dfo_pid',))
        ]),
        perm_filter=''
    )

    def person_dfosap_import(self, operator, dfo_pid):
        """Add an emnployee number to the queue  in order to
        trigger import and return whatever lies in queue."""

        #TODO: make something like this maybe self.ba.can_import_person(operator.get_entity_id, dfo_pid)

        #self.ba.can_set_password(operator.get_entity_id())

        # Primary intended users are Houston.
        # A different check is appropriate
        # ac = self._get_account(accountname, idtype='name')
        # if not self.ba.can_set_password(operator.get_entity_id(), ac):
        #     raise PermissionDenied("Access denied")
        simp = SapImport(self.db, dfo_pid)
        simp()

        return [{'dfo_pid': dfo_pid}]
        #                "queued_tasks": simp.queued_tasks}


if __name__ == '__main__':
    db = Utils.Factory.get('Database')()
    logger = Utils.Factory.get_logger('console')
    #dfosap_import = BofhdExtension(db, logger)
    dfosap_import = SapImport(db, "6065447")
    dfosap_import()
