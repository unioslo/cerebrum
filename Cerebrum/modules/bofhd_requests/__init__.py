# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
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
Bofhd Requests are delayed/queued maintenance tasks for entities.

Historically, the BofhdRequests were tasks that were too expensive to run in a
bofhd command.  This was expanded to include other expensive tasks, or tasks
that had a high failure rate (i.e. because we rely on external systems being
up).

Use the :mod:`Cerebrum.modules.tasks` for similar behaviour.
"""

# bofhd_requests sqlmodule version (see makedb.py / mod_bofhd_requests.sql)
__version__ = "1.1"
