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
"""
Task module.

This module provides a way to store future tasks in Cerebrum.  The general
idea is to push tasks onto a given queue, and then something else will
regularly pop known task types off the queue for processing.

The queue itself is the *queue* value within the pushed item.

Each item must be uniquely identified within a queue by its *key* value.

A task consists of:

queue
    A queue name.

key
    A unique identifer/item name within the queue.

    This is typically used to store a unique, external identifier, and ensure
    that no duplicate tasks are queued.

    Example: 'jti' field from JWTs, employee id from the hr-system.

iat
    Creation timestamp.

    This is typically used to identify *when* a task has been added, and does
    *not* mirror any external iat value.

    If no iat is given, it will default to `now()`.

nbf
    A 'not before' value. If given, this will typically be used to delay
    processing of this item until the given time.

    If no nbf is given, it will default to `now()`.

reason (optional)
    An optional, human readable description of *why* a given task has been
    queued.

payload (optional)
    An optional payload.  Usage depends on the queue/task type.
"""

# Database module version (see makedb.py)
__version__ = '1.0'
