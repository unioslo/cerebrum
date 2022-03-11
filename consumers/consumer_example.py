#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 University of Oslo, Norway
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

"""Example consumer."""

from Cerebrum.Utils import Factory
from Cerebrum.modules.event.mapping import CallbackMap
from Cerebrum.modules.event_consumer import get_consumer

logger = Factory.get_logger('cronjob')
callback_functions = CallbackMap()
callback_filters = CallbackMap()


def user_is_legit(data):
    """Check if this user should be processed.

    :return boolean:
        To process or not."""
    return True


@callback_filters(user_is_legit)
@callback_functions('Cerebrum.event.user.create')
def handle_user_create(data):
    """Post-processing of user creation."""
    try:
        int(dict())
    except TypeError as e:
        logger.error("Could not post-process {}: {}".format(
            data.get('account_name'), e))


def callback(routing_key, content_type, body):
    """Call appropriate handler functions."""
    if content_type == 'application/json':
        import json
        body = json.loads(body)

    for cb in callback_functions.get_callbacks(routing_key):
        filters = callback_filters.get_callbacks(cb)
        if not filters or all(lambda x: x(), filters):
            cb(body)


def main():
    """Start consuming messages."""
    import argparse
    consumer = get_consumer(callback,
                            argparse.ArgumentParser().prog.rsplit('.', 1)[0])

    try:
        consumer.start()
    except KeyboardInterrupt:
        consumer.stop()
        consumer.close()

if __name__ == "__main__":
    main()
