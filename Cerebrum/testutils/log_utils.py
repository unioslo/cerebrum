# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
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
Various test utils for logging.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging


class StrictNullHandler(logging.Handler):
    """
    A log handler that formats log records without catching errors.

    This is a NullHandler, so the basic idea is to do nothing with the log
    records.  However, we want to go though all the steps, including formatting
    the log message.
    """

    def emit(self, record):
        """
        "Emit" the log record.

        As we are a NullHandler-like handler, we don't actually do anything
        with the record, but we want to format it to check that this won't
        cause any issues.

        Note that most other handlers catch formatting errors here.
        """
        self.format(record)
