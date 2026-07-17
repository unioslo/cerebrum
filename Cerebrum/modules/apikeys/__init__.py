# -*- coding: utf-8 -*-
#
# Copyright 2019-2024 University of Oslo, Norway
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
Module to store API client passlist in Cerebrum.

This module provides a passlist for known API clients.  Each client identifier
should map to exactly one user account for that client.

The :mod:`Cerebrum.rest` API delegates all authentication and authorization to
an API gateway.  The gateway should add credentials and a client identifier to
all forwarded requests.

1. Check the gateway credentials (as we can only trust requests that comes
   from *our* API gateway and API definition.

2. Look up the client identifier (using this module), and set the
   auditlog/changelog operator to the mapped account for the request.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

# database schema version (mod_apikeys)
__version__ = '1.0'
