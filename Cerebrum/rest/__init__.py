# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
The Cerebrum API.

This module and it's submodules provides the Cerebrum API.  This API is built
using mainly *flask* and *flask-restx*.

:mod:`Cerebrum.rest.api`
    Contains the main app factory, as well as common modules for auth, io,
    database integration, etc...

:mod:`Cerebrum.rest.api.v1`
    Contains the actual API endpoints.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
