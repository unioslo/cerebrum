# -*- coding: utf-8 -*-
# Copyright 2002-2016 University of Oslo, Norway
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

"""The PosixGroup module implements a specialisation of the `Group'
core class.

The specialided subclass, called PosixGroup.PosixGroup, supports the additional
group parameters that are needed for building Unix-style file groups.
Currently, the only Posix-specific parameter is `posix_gid', which is a numeric
GID.

When this module is used, the PosixGroupBase should be mixed into the base
group class. The PosixGroup class should be used when you're working with known
posix groups.

"""
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from .posix.mixins import PosixGroupMixin


Group_class = Factory.get("Group")
assert issubclass(Group_class, PosixGroupMixin)


class PosixGroup(Group_class):
    """ Implementation of posix group.

    A Posix group contains an additional attribute that only applies to Posix
    groups - the posix GID.

    """

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('posix_gid',)

    def clear(self):
        self.__super.clear()
        self.clear_class(PosixGroup)
        self.__updated = []

    # We do not allow giving PosixGroups names that differ from the
    # names of the Groups they are based on, as we anticipate that
    # doing so would lead to chaos.
    #
    # If one wants to build a PosixGroup on top of a Group whose name
    # is not proper for PosixGroup, one might define a _new_
    # PosixGroup and add the Group as its only (union) member.
    def populate(self, creator_id=None, visibility=None, name=None,
                 description=None, expire_date=None, group_type=None,
                 gid=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            super(PosixGroup, self).populate(
                creator_id=creator_id,
                visibility=visibility,
                name=name,
                description=description,
                expire_date=expire_date,
                group_type=group_type,
            )
        self.__in_db = False
        if gid is None:
            gid = self._get_gid()
        self.posix_gid = gid

    def write_db(self):
        self.__super.write_db()
        if not self.__updated:
            return
        if not self.__in_db:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=posix_group]
              (group_id, posix_gid)
            VALUES (:g_id, :posix_gid)""", {'g_id': self.entity_id,
                                            'posix_gid': self.posix_gid})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=posix_group]
            SET posix_gid=:posix_gid
            WHERE group_id=:g_id""", {'g_id': self.entity_id,
                                      'posix_gid': self.posix_gid})

        self._db.log_change(self.entity_id,
                            self.clconst.posix_group_promote,
                            None,
                            change_params={'gid': int(self.posix_gid), })
        del self.__in_db
        self.__in_db = True
        self.__updated = []

    def __eq__(self, other):
        assert isinstance(other, PosixGroup)
        if self.posix_gid == other.posix_gid:
            return self.__super.__eq__(other)
        return False

    def new(self, creator_id, visibility, name, description=None,
            expire_date=None, gid=None):
        PosixGroup.populate(self,
                            creator_id=creator_id,
                            visibility=visibility,
                            name=name,
                            description=description,
                            expire_date=expire_date,
                            gid=gid)
        PosixGroup.write_db(self)
        PosixGroup.find(self, self.entity_id)

    def find(self, group_id):
        super(PosixGroup, self).find(group_id)
        self.posix_gid = self._get_posix_gid()
        self.__in_db = True

    def list_posix_groups(self):
        """Return group_id and posix_gid of all PosixGroups in database"""
        return self.query("""
        SELECT group_id, posix_gid
        FROM [:table schema=cerebrum name=posix_group]""")

    def find_by_gid(self, gid):
        group_id = self.query_1("""
        SELECT group_id
        FROM [:table schema=cerebrum name=posix_group]
        WHERE posix_gid=:gid""", locals())
        self.find(group_id)

    def _get_gid(self):
        """Returns the next free GID from 'posix_gid_seq'"""
        while True:
            # Pick a new GID
            gid = self.nextval('posix_gid_seq')
            # We check if the GID is in any of the reserved ranges.
            # If it is, we'll skip past the range (call setval), and
            # pick a new GID that is past the reserved range.
            for x in sorted(cereconf.GID_RESERVED_RANGE):
                # TODO: Move this check to some unit-testing stuff sometime
                if x[1] < x[0]:
                    raise Errors.ProgrammingError(
                        'Wrong order in cereconf.GID_RESERVED_RANGE')
                if gid >= x[0] and gid <= x[1]:
                    self._db.setval('posix_gid_seq', x[1])
                    gid = self.nextval('posix_gid_seq')
            # We check if the GID is in use, if not, return, else start over.
            try:
                self.query_1("""
                SELECT posix_gid
                FROM [:table schema=cerebrum name=posix_group]
                WHERE posix_gid=:gid""", locals())
            except Errors.NotFoundError:
                return gid
