# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

"""Access to Cerebrum groups that are also POSIX file groups."""

from Cerebrum import Group
from Cerebrum import Errors

class PosixGroup(Group.Group):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('posix_gid',)

    def clear(self):
        self.__super.clear()
        for attr in PosixGroup.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in PosixGroup.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    # We do not allow giving PosixGroups names that differ from the
    # names of the Groups they are based on, as we anticipate that
    # doing so would lead to chaos.
    #
    # If one wants to build a PosixGroup on top of a Group whose name
    # is not proper for PosixGroup, one might define a _new_
    # PosixGroup and add the Group as its only (union) member.
    def populate(self, creator_id=None, visibility=None, name=None,
                 description=None, create_date=None, expire_date=None,
                 gid=None, parent=None):
        if parent is not None:
            self.__xerox__(parent)
        else:
            Group.Group.populate(self, creator_id, visibility, name, description,
                           create_date, expire_date)
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
        del self.__in_db
        self.__in_db = True
        self.__updated = False

    def __eq__(self, other):
        assert isinstance(other, PosixGroup)
        if self.posix_gid == other.posix_gid:
            return self.__super.__eq__(other)
        return False

    def new(self, creator_id, visibility, name, description=None,
            create_date=None, expire_date=None, gid=None):
        PosixGroup.populate(self, creator_id, visibility, name, description,
                            create_date, expire_date, gid)
        PosixGroup.write_db(self)
        PosixGroup.find(self, self.entity_id)

    def find(self, group_id):
        super(PosixGroup, self).find(group_id)
        self.posix_gid = self.query_1("""
        SELECT posix_gid
        FROM [:table schema=cerebrum name=posix_group]
        WHERE group_id=:g_id""", {'g_id': self.entity_id})
        self.__in_db = True

    def find_by_gid(self, gid):
        group_id = self.query_1("""
        SELECT group_id
        FROM [:table schema=cerebrum name=posix_group]
        WHERE posix_gid=:gid""", locals())
        self.find(group_id)

    def _get_gid(self):
        while True:
            gid = self.nextval('posix_gid_seq')
            try:
                self.query_1("""
                SELECT posix_gid
                FROM [:table schema=cerebrum name=posix_group]
                WHERE posix_gid=:gid""", locals())
            except Errors.NotFoundError:
                return gid

    def delete(self):
        if self.__in_db:
            # Remove entry in table `posix_group'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=posix_group]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})

##     def _check_name(self, name):
##         name_len = len(name)
##         if name_len == 0:
##             raise ValueError, "PosixGroup can't have empty name."
##         if name_len > 8:
##             raise ValueError,\
##                   "PosixGroup name '%s' longer than 8 characters." % name
##         for c in name:
##             if c not in tuple('abcdefghijklmnopqrstuvwxyz0123456789'):
##                 raise ValueError, \
##                       "PosixGroup name '%s' contains illegal char '%s'." % \
##                       (name, c)
