#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

import string
import urlparse

from mx.DateTime import now
from mx.DateTime import DateTimeDelta

import cereconf

from Cerebrum import Group
from Cerebrum.Entity import EntityName
from Cerebrum.Group import Group as Group_class
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.modules.EntityTrait import EntityTrait




class VirtGroup(Group_class, EntityContactInfo, EntityTrait):
    """VirtGroup extension of VirtHome.

    This class tailors Cerebrum.Group:Group to VirtHome's needs.

    TBD: Do we need to make a special version of *_member() functions that
    check the member type? (i.e. can a virtgroup have any other members than
    VA/FA?)
    """

    DEFAULT_GROUP_LIFETIME = DateTimeDelta(180)
    


    def __init__(self, *rest, **kw):
        self.__super.__init__(*rest, **kw)

        self.legal_chars = set(string.letters + string.digits + " .@-")
    # end __init__
    
    

    def populate(self, creator_id, name, description):
        """Populate a VirtGroup's instance, subject to some constraints."""

        assert not self.illegal_name(name), "Invalid group name %s" % (name,)
        assert description.strip()

        self.__super.populate(
            creator_id=creator_id,
            visibility=self.const.group_visibility_all,
            name=name,
            description=description,
            group_type=self.const.group_type_unknown,
        )
        #self.expire_date = now() + self.DEFAULT_GROUP_LIFETIME
    # end populate



    def set_group_resource(self, url):
        """Unconditionally reassign a new URL to this group.

        If URL is None (or ''), we'll remove whatever URL was in the database.
        """

        # Check the URL's validity before doing anything to the database.
        self.verify_group_url(url)
        resources = self.get_contact_info(self.const.system_virthome,
                                          self.const.virthome_group_url)
        if resources:
            # There can be at most one URL...
            r = resources[0]
            # If the old value matches the new one, there is nothing to do.
            if r["contact_value"] == url:
                return

            # If the old value doesn't match the new one, we delete the old one
            # first. Helps us avoid multiple URLs for one group.
            self.delete_contact_info(self.const.system_virthome,
                                     self.const.virthome_group_url)

        if url:
            self.add_contact_info(self.const.system_virthome,
                                  self.const.virthome_group_url,
                                  url)
    # end set_group_resource

    

    def verify_group_url(self, url):
        """Check that the URL at least looks sane.

        We allow empty/None values here.
        """
        if not url:
            return True
        
        resource = urlparse.urlparse(url)
        if resource.scheme not in ("http", "https", "ftp",):
            raise ValueError("Invalid url for group <%s>: <%s>" %
                             (self.group_name, url))

        return True
    # end verify_group_url


    
    def illegal_name(self, name):
        """Return a string with error message if groupname is illegal"""

        if not name.strip():
            return "Group name is empty"

        if (name.startswith(" ") or name.endswith(" ")):
            return "Group name cannot start/end with space"

        if any(x not in self.legal_chars for x in name):
            return "Illegal character in group name"
        
        if name.count("@") != 1:
            return "Group name is missing a realm"

        tmp_name, tmp_realm = name.split("@")
        if tmp_realm != cereconf.VIRTHOME_REALM:
            return "Wrong realm <%s> for VirtGroup <%s>"

        return False
    # end illegal_name
# end VirtGroup

