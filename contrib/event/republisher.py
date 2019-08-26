#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

"""This job publishes events residing in the event-backlog.

The event-backlog is filled with events, if the broker is down, or the network
is broken. This script should be run regularly (every five minutes or so), to
publish the messages.

The backlog is normally handeled by the event_publisher, but this only happens
when new events are beeing generated.
"""

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')


def do_it():
    db = Factory.get('Database')()
    db._EventPublisher__try_send_messages()
    db.commit()

if __name__ == '__main__':
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse

    argp = argparse.ArgumentParser(description=u"""Republish failed events.""")
    args = argp.parse_args()
    do_it()
