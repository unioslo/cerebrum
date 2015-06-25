#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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

from string import ascii_lowercase, digits
from Cerebrum.Group import Group


class TsdGroup(Group):
    # The illegal_name is called by e.g. write_db(),
    # and if it returns truth, it is raised as an
    # IntegrityError.
    # TSD Nexus XMLRPC API specifies the constraints on the names
    def illegal_name(self, name, max_length=None):
        """Check that name
        * Contains only
          - lower case ASCII,
          - digits 0-9, or
          - dash ("-").
        * Starts with a letter
        * Doesn't end with a digit
        """
        illegal_chars = set(x for x in name
                            if x not in ascii_lowercase
                            and x not in digits
                            and x != '-')
        if illegal_chars:
            return "Name contains characters '%s' " \
                "(only a-z, - and 0-9 allowed)" % ''.join(illegal_chars)
        # this should not strike, as project name is always first, but
        # it cant hurt to test.
        if not name[0] in ascii_lowercase:
            return "Group can only start with a-z, found '%s'" % name[0]
        if not name[-1] in ascii_lowercase + digits:
            return "Group name must end with a letter or a digit, not '%s'" % \
                name[-1]
        # adhere to overridden default param to max_length if exists
        s = super(TsdGroup, self).illegal_name
        return s(name) if max_length is None else s(name, max_length)
