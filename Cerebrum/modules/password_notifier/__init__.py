# -*- coding: utf-8 -*-
#
# Copyright 2016-2023 University of Oslo, Norway
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
Password Notifier modules.

This module implements password change notifications.  This can be used
together with :mod:`Cerebrum.modules.pwcheck.history`
(``mod_password_history``) to require regular, periodic password changes.

- Requires a config (see :mod:`.config`)
- Can be extended with custom subclasses
- Triggered by ``contrib/notify_change_password.py``

"""
