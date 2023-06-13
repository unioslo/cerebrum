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
A file containing two classes that is related to TaskQueue whenever a
password is changed. NotifyChangePasswordMixin is a mixin class for setting a
new password, the functionality within will check if user is a sysadm_account
and add it to queue if that is the case. NotifyPasswordQueueHandler is used for
handling tasks and inherits queue_handler.
"""
from Cerebrum import Account
from Cerebrum.Utils import Factory
from Cerebrum.modules.tasks.task_models import Task
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks import queue_handler
from Cerebrum.modules.no.uio.sysadm_utils import is_sysadm_account


class NotifyChangePasswordMixin(Account.Account):
    def set_password(self, password):
        super(NotifyChangePasswordMixin, self).set_password(password)
        if not is_sysadm_account(self):
            return
        task = ChangedPasswordQueueHandler.create_changed_password_task(
            self.account_name)
        self.__task = task

    def clear(self):
        try:
            del self.__task
        except AttributeError:
            pass
        super(NotifyChangePasswordMixin, self).clear()

    def write_db(self):
        try:
            task = self.__task
            del self.__task
        except AttributeError:
            task = None
        ret = super(NotifyChangePasswordMixin, self).write_db()
        if task is not None:
            TaskQueue(self._db).push_task(task)
        return ret

class ChangedPasswordQueueHandler(queue_handler.QueueHandler):
    queue = 'notify-changed-password'
    max_attempts = 12

    @classmethod
    def create_changed_password_task(cls, key, nbf=None):
        return Task(
            queue=cls.queue,
            key=key,
            nbf=nbf,
            attempts=0,
        )
