#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
Script containing functionality for sending sms to persons in
task queue related to password change.
"""

import io
import logging
import argparse
import cereconf
import functools
from os import path

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.sms import SMSSender
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks.queue_processor import QueueProcessor
from Cerebrum.modules.no.uio.changed_password_notifier import ChangedPasswordQueueHandler

logger = logging.getLogger(__name__)
sms = SMSSender(logger=logger)

def get_message(uname, time):
    with io.open(path.join(cereconf.TEMPLATE_DIR,
                           'changed_password_notifier.template'), 'r',
                 encoding='UTF-8') as f:
        template = f.read()
    return template.format(account_name=uname, time= time)

def send_sms(uname, task_iat, phone_number):
    if not phone_number:
        return False
    try:
        time_format = "%d.%m.%Y %H:%M:%S"
        time = task_iat.strftime(time_format)
        message = get_message(uname, time)
        return sms(phone_number, message)
    except Exception as e:
        logger.warning("Failed during execution of sending message")
        return False

def task_callback(db, task, dryrun):
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    ac.find_by_name(task.key)
    pe.find(ac.owner_id)

    spec = map(lambda (s): (co.human2constant(s), co.human2constant("MOBILE")),
               cereconf.SYSTEM_LOOKUP_ORDER)
    mobile = pe.sort_contact_info(spec, pe.get_contact_info())

    # Task is handled when there is no registered phone number to receive sms
    if not mobile:
        logger.info("Could not find mobile phone number for %s", task.key)
        return []

    person_in_systems = [int(af['source_system']) for af in
                             pe.list_affiliations(person_id=pe.entity_id)]
    mobile = filter(lambda x: x['source_system'] in person_in_systems,
                        mobile)[0]['contact_value']

    if dryrun:
        logger.info('Dryrun for id - %s', task.key)
    else:
        if not send_sms(ac.account_name, task.iat, mobile):
            raise Exception("Sms to " + str(mobile) + " failed with task key - " +
                            task.key)
    return []

def run_tasks(dryrun):
    callback = functools.partial(task_callback, dryrun=dryrun)
    max_attempts = ChangedPasswordQueueHandler.max_attempts
    proc = QueueProcessor(ChangedPasswordQueueHandler(callback),
                          limit=max_attempts, dryrun=dryrun)
    tasks = proc.select_tasks()
    for task in tasks:
        proc.process_task(task)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Handle password change tasks and send sms to people affected",
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)
    dryrun = not args.commit
    run_tasks(dryrun)


if __name__ == '__main__':
    main()
