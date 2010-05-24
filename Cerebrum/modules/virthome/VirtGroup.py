#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-
#
# Copyright 2009 University of Oslo, Norway
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


"""The VirtGroup module presents an API to the data about groups available in
VirtHome.

This module mimicks some of the functionality of Cerebrum/Group.py and relies
on Cerebrum/{Entity.py,Group.py} and a few others.
"""

import urlparse

from mx.DateTime import now
from mx.DateTime import DateTimeDelta

import cerebrum_path
import cereconf

from Cerebrum import Group
from Cerebrum.Entity import EntityName
from Cerebrum.Group import Group as Group_class
from Cerebrum.Entity import EntityContactInfo




class VirtGroup(Group_class, EntityContactInfo):
    """VirtGroup extension of VirtHome.

    This class tailors Cerebrum.Group:Group to VirtHome's needs.

    TBD: Do we need to make a special version of *_member() functions that
    check the member type? (i.e. can a virtgroup have any other members than
    VA/FA?)
    """

    DEFAULT_GROUP_LIFETIME = DateTimeDelta(180)
    


    def populate(self, creator_id, name, description, url):
        """Populate a VirtGroup's instance, subject to some constraints."""

        assert not self.illegal_name(name), "Invalid group name %s" % (name,)
        assert description.strip()

        if url is not None:
            url = url.strip()

        if url:
            resource = urlparse.urlparse(url)
            if resource.scheme not in ("http", "https", "ftp",):
                raise ValueError("Invalid url for group <%s>: <%s>" % (name, url))

        self.__super.populate(creator_id,
                              self.const.group_visibility_all,
                              name,
                              description)
        self.expire_date = now() + self.DEFAULT_GROUP_LIFETIME
        if url:
            self.populate_contact_info(self.const.system_virthome,
                                       self.const.virthome_group_url,
                                       url)
    # end populate



    def illegal_name(self, name):
        """Return a string with error message if groupname is illegal"""

        if not name.strip():
            return "Group name is empty"

        if name.count("@") != 1:
            return "Group name is missing a realm"


        tmp_name, tmp_realm = name.split("@")
        if tmp_realm != cereconf.VIRTHOME_REALM:
            return "Wrong realm <%s> for VirtGroup <%s>"

        return False
    # end illegal_name
# end VirtGroup

