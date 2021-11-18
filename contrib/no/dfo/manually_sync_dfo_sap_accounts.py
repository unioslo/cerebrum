#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2009, 2010, 2012 University of Oslo, Norway
# This file is part of Cerebrum.
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Script for filling up task queue with id for persons from source system SAPDFO
and accounts from DFØ to force synchronization.
For each person there is added 5 minutes penalty to nbf based on previous
person's nbf.
"""

import logging
import argparse

import Cerebrum.logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.no.dfo.client import get_client, SapClientConfig
from Cerebrum.config.loader import read_config
from Cerebrum.utils.date import now
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.database.ctx import db_context
from datetime import timedelta

logger = logging.getLogger(__name__)


def create_tasks(db, dryrun):
    account_ids = get_dfo_accounts()
    person_ids = get_persons(db)
    all_persons = merge_lists(account_ids, person_ids)
    nbf = now()
    test = all_persons[:25]
    for person_id in test:
        nbf = nbf + timedelta(seconds=60*5)
        task = get_task(person_id, nbf, db)
        with db_context(Factory.get('Database')(), dryrun) as db:
            result = TaskQueue(db).push_task(task)
            logger.info(result)


def get_dfo_accounts():
    config = SapClientConfig()
    config.load_dict(read_config('../../../../crb-config-uio/etc/' +
                                 'cerebrum/config/hr-import-client.yml'))
    client = get_client(config)
    accounts = client.get_employee("")
    account_ids = []

    for account in accounts:
        # Converting to int to remove 00 prefix
        acc_id = int(account['id'])
        account_ids.append(acc_id)
    return account_ids


def get_persons(db):
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    persons = pe.list_affiliations(source_system=co.system_dfo_sap)
    person_ids = []
    for person in persons:
        person_ids.append(person['person_id'])
    return person_ids


def merge_lists(account_ids, person_ids):
    for account_id in account_ids:
        if account_id not in person_ids:
            person_ids.append(account_id)
    return person_ids


def get_task(person_id, nbf, db):
    queue = 'dfo-employee'
    sub = 'forced-sapdfo-sync'

    old_task = TaskQueue.get_task(TaskQueue(db), queue, sub, person_id)

    payload = task_models.Payload(
        fmt='dfo_event',
        version=1,
        data={'id': person_id, 'uri': 'dfo:ansatte'})
    new_task = task_models.Task(
        queue=queue,
        sub=sub,
        key=person_id,
        nbf=nbf,
        attempts=0,
        reason='forced-sync: on={when}'.format(when=now()),
        payload=payload,
    )

    task = task_models.merge_tasks(new_task, old_task)

    return task


def main(args=None):
    db = Factory.get('Database')()

    parser = argparse.ArgumentParser(
        description='Create manual tasks for DFO-SAP accounts to update'
    )
    add_commit_args(parser)
    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })
    args = parser.parse_args(args)
    Cerebrum.logutils.autoconf('tee', args)
    dryrun = not args.commit

    create_tasks(db, dryrun)


if __name__ == '__main__':
    main()
