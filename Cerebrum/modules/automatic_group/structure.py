# coding: utf-8
#
# Copyright 2020-2026 University of Oslo, Norway
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
Utilities for building group hierarchies based on org trees.

TODO
====
This module needs revision.  It was built for- and only used for *manager
groups* (see :mod:`Cerebrum.modules.no.uio.hr_import.leader_groups`).

However, a lot of manager group specific behaviour is hard-coded and the
module is not really re-usable for other purposes.  Most of this module should
probably be moved to a separate *manager group* module, or it should be
generalized more.

Also, *manager* groups as currently implemented are a bit counter-intuitive.  A
given manager group contains the manager at the given org unit and all sub
units.  For granting access, it would probably be more useful with a manager
group where members are all parent units.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
