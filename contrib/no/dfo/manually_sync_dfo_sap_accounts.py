#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2021 University of Oslo, Norway
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
For each person there is added 2 minutes penalty to nbf based on previous
person's nbf.
"""

import logging
import argparse

import Cerebrum.logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.no.dfo.client import get_client, SapClientConfig
from Cerebrum.modules.no.dfo.tasks import EmployeeTasks
from Cerebrum.config.loader import read_config
from Cerebrum.utils.date import now
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.database.ctx import db_context
from datetime import timedelta

logger = logging.getLogger(__name__)


# creating a task and pushes it to the task queue for dfo and dfo_sap person id
def create_tasks(db_ctx, dfo_accounts):
    nbf = now()
    for account_id in dfo_accounts:
        try:
            nbf = nbf + timedelta(seconds=60*2)
            task = EmployeeTasks.create_manual_task(account_id,
                                                    sub='sap-dfo-fullsync',
                                                    nbf=nbf)
            result = TaskQueue(db_ctx).push_task(task)
            logger.info(result)
        except Exception as e:
            logger.warning('Could not create task and push to queue ' +
                           'for person %s', account_id)
            logger.error(e)


# fetching all dfo accounts and generate list with person id's
def get_dfo_accounts(config):
    client = get_client(config)
    dfo_acc = client.get_employee("")
    account_ids = set()

    for account in dfo_acc:
        # Converting to int to remove 00 prefix
        acc_id = int(account['id'])
        account_ids.add(acc_id)
    return account_ids


# fetching all dfo ids in cerebrum using persons with dfo id type as external id
def get_external_ids(db):
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    persons = pe.search_external_ids(id_type=co.externalid_dfo_pid)
    external_ids = set()
    for person in persons:
        external_ids.add(person['external_id'])
    return external_ids


# setting up config with path from args for dfo api
def get_config(path):
    config = SapClientConfig()
    config.load_dict(read_config(path))
    return config


def main(args=None):
    parser = argparse.ArgumentParser(
        description='Create manual tasks for DFO-SAP accounts to update'
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='config for dfo api'
    )
    add_commit_args(parser)
    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })
    args = parser.parse_args(args)

    Cerebrum.logutils.autoconf('tee', args)

    config = get_config(args.config)
    dryrun = not args.commit

    db = Factory.get('Database')()

    dfo_acc = get_dfo_accounts(config)
    external_ids = get_external_ids(db)
    all_ids = set.union(dfo_acc, external_ids)

    with db_context(Factory.get('Database')(), dryrun) as db_ctx:
        create_tasks(db_ctx, all_ids)


if __name__ == '__main__':
    main()
