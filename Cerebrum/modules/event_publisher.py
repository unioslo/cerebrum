#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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
""" Translate changes to event messages and publish them.

This module is intended to send changelog entries to a Sevice bus, Message
Queue or Message Broker.

"""
import cerebrum_path
import Cerebrum.ChangeLog


class EventPublisher(Cerebrum.ChangeLog.ChangeLog):

    """ Class used to publish changes to an external system.

    This class is intended to be used with a Message Broker.

    """

    def cl_init(self, **kw):
        super(EventPublish, self).cl_init(**kw)
        self.queue = []

    def log_change(self,
                   subject_entity,
                   change_type_id,
                   destination_entity,
                   change_params=None,
                   skip_publish=False,
                   **kw):
        """ Queue a change to be published. """
        super(EventPublish, self).log_change(
            subject_entity,
            change_type_id,
            destination_entity,
            change_params=change_params,
            **kw)

        # TODO: Implement
        raise NotImplementedError()

        if skip_publish:
            return

        data = 'TODO'
        self.queue.append(data)

    def write_log(self):
        """ Flush local queue. """
        super(EventPublish, self).write_log()

        # TODO: Implement
        raise NotImplementedError()

        # TODO:
        #   Hvis MQ-klient kan opprette transaksjoner, vil vi kunne sende
        #   meldinger her.
        #   Hvis ikke, må meldinger sendes i publish_log
        if len(self.queue):
            # TODO: Send message
            pass

    def clear_log(self):
        """ Clear local queue """
        super(EventPublish, self).clear_log()
        self.queue = []

    def publish_log(self):
        """ Publish messages. """
        super(EventPublish, self).publish_log()

        # TODO: Implement
        raise NotImplementedError()

        # TODO:
        #   Hvis transaksjon - commit
        #
        #   Hvis ikke, send meldinger her.

    def unpublish_log(self):
        """ Abort message-pub """
        super(EventPublish, self).unpublish_log()

        # TODO: Implement
        raise NotImplementedError()

        # TODO:
        #   Hvis transaksjon - rollback
        #   Hvis ikke: Tøm kø?


if __name__ == '__main__':
    del cerebrum_path

    # Demo
