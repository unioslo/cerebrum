# -*- coding: utf-8 -*-
#
# Copyright 2002-2025 University of Oslo, Norway
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
""" Default `cereconf` module. """

# Provide defaults for all attributes/settings:
from Cerebrum.default_config import *  # noqa: F401, F403

# Put any changes to the default settings below.
#
# Note: Import specific attributes if you need to refer to them, e.g.:
#
#     from Cerebrum.default_config import FOO_PATH
#
#     BAR_PATH = os.path.join(FOO_PATH, "bar")
#
# Note: Make copies if you need to modify existing, mutatable values, e.g.:
#
#     from Cerebrum.default_config import FOO_STRUCTURE
#
#     FOO_STRUCTURE = dict(FOO_STRUCTURE)
#     FOO_STRUCTURE.update({
#       'foo': "bar",
#     })
#
