# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
from __future__ import unicode_literals

"""Functionality for transforming a Cerebrum.modules.amqp.handlers.Event 
into a `hr_id` necessary to do an import
"""

import re
import json
import logging

logger = logging.getLogger(__name__)

SUB_2_HR_ID = re.compile(r'employees\((\d+)\)')


def extract_message(event):
    try:
        return json.loads(event.body)
    except Exception:
        # TODO:
        #   Log warning or raise exception?
        logger.warning('Received malformed message %r', event.body)
        return None


def extract_hr_id(body):
    """Extract 'hr_id' from a sap message body

    This is used by the sap consumer to fetch info about a person.

    :type body: dict"""
    sub = body.get('sub')
    if sub:
        match = SUB_2_HR_ID.search(sub)
        if match:
            return match.group(1)
    return None


def event_to_hr_id(event):
    """Extract 'hr_id' from a sap Event

    :type event: Cerebrum.modules.amqp.handlers.Event
    """
    body = extract_message(event)
    if body:
        return extract_hr_id(body)
    return None
