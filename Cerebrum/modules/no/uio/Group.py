# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

""""""

import re
from Cerebrum import Group

class GroupUiOMixin(Group.Group):
    """Group mixin class providing functionality specific to UiO.
    """

    def illegal_name(self, name):
        # Avoid circular import dependency
        from Cerebrum.modules import PosixGroup

        if isinstance(self, PosixGroup.PosixGroup):
            if len(name) > 8:
                return "too long (%s)" % name
            if re.search("^[^a-z]", name):
                return "must start with a character (%s)" % name
            if re.search("[^a-z0-9\-_]", name):
                return "contains illegal characters (%s)" % name
        return False
