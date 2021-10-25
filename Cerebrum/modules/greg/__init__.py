# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Greg related modules.

Greg (Guest registration) is an autoritative system for people with a temporary
need for user accounts and access to IT resources.

Overview
--------

1. Greg sends out notifications using AMQP whenever a person (guest) is
created/modified/deleted.

2. A consumer script parses the message, and creates a *task* (see
   py:mod:`Cerebrum.modules.tasks` and py:mod:`.tasks`).

3. An import script periodically processes the import/update tasks, and fetches
   up to date information from Greg.  The result is a Person object in
   Cerebrum, which is in sync with Greg.

4. Other maintenance scripts creates, updates, and disables user accounts for
   these guests, based on the current state in Cerebrum.


Configuration
-------------

cereconf.CLASS_CONSTANTS
    Must include ``Cerebrum.modules.greg.constants/GregConstants``, to provide
    Greg-related constants.
"""
