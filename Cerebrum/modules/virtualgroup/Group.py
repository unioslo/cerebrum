# coding: utf-8
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


"""Implementation of the Virtual group core"""

from Cerebrum import Errors
from Cerebrum.Group import Group, populator


class VirtualGroup(Group):
    __read_attr__ = ('__in_db', 'virtual_group_type')
    # Get these from Group
    # __write_attr__ = ('description', 'visibility', 'creator_id',
    #                   'create_date', 'expire_date', 'group_name')

    @populator('virtual_group', 'virtualgroup')
    def populate_virtual_group(self, creator_id=None, visibility=None,
                               name=None, description=None, create_date=None,
                               virtual_group_type=None,
                               expire_date=None, parent=None):
        """Populate group instance's attributes without database access."""
        # TBD: Should this method call self.clear(), or should that be
        # the caller's responsibility?
        if parent is not None:
            self.__xerox__(parent)
        else:
            super(VirtualGroup, self).populate(
                group_type=None, entity_type=self.const.entity_virtual_group)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        self.creator_id = creator_id
        self.visibility = int(visibility)
        self.description = description
        if not self.__in_db or create_date is not None:
            # If the previous operation was find, self.create_date will
            # have a value, while populate usually is not called with
            # a create_date argument.  This check avoids a group_mod
            # change-log entry caused when this is the only change to the
            # entity
            self.create_date = create_date
        self.expire_date = expire_date
        # TBD: Should this live in EntityName, and not here?  If yes,
        # the attribute should probably have a more generic name than
        # "group_name".
        self.group_name = name
        self.virtual_group_type = virtual_group_type

    def write_db(self):
        """Write group instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Group entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.

        """
        super(VirtualGroup, self).write_db()
        try:
            is_new = not self.__in_db
        except AttributeError:
            return
        if self.entity_type != self.const.entity_virtual_group:
            return
        if not self._Group__updated:
            return
        print "updated = {}".format(self._Group__updated)
        if 'group_name' in self._Group__updated:
            tmp = self.illegal_name(self.group_name)
            if tmp:
                raise self._db.IntegrityError, "Illegal groupname: %s" % tmp

        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('group_id', ':g_id'),
                    ('description', ':desc'),
                    ('visibility', ':visib'),
                    ('virtual_group_type', ':virtual_group_type'),
                    ('creator_id', ':creator_id')]
            # Columns that have default values through DDL.
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=virtual_group_info]
                         (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         {'e_type': int(self.const.entity_virtual_group),
                          'g_id': self.entity_id,
                          'desc': self.description,
                          'visib': int(self.visibility),
                          'creator_id': self.creator_id,
                          # Even though the following two bind
                          # variables will only be used in the query
                          # when their values aren't None, there's no
                          # reason we should take extra steps to avoid
                          # including them here.
                          'create_date': self.create_date,
                          'virtual_group_type': self.virtual_group_type,
                          'exp_date': self.expire_date})
            self._db.log_change(self.entity_id, self.const.group_create, None)
            self.add_entity_name(self.const.group_namespace, self.group_name)
        else:
            cols = [('description', ':desc'),
                    ('visibility', ':visib'),
                    ('creator_id', ':creator_id')]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            cols.append(('expire_date', ':exp_date'))
            self.execute("""
            UPDATE [:table schema=cerebrum name=virtual_group_info]
            SET %(defs)s
            WHERE group_id=:g_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols if x[0] != 'group_id'])},
                {'g_id': self.entity_id,
                 'desc': self.description,
                 'visib': int(self.visibility),
                 'creator_id': self.creator_id,
                 # Even though the following two bind
                 # variables will only be used in the query
                 # when their values aren't None, there's no
                 # reason we should take extra steps to avoid
                 # including them here.
                 'create_date': self.create_date,
                 'exp_date': self.expire_date})
            self._db.log_change(self.entity_id, self.const.group_mod, None)
            self.update_entity_name(
                self.const.group_namespace,
                self.group_name)
        # EntityName.write_db(self, as_object)
        del self.__in_db
        self.__in_db = True
        self._Group__updated = []
        return is_new

    def delete(self):
        """ Delete group and entity from database."""
        if self.__in_db:
            # Remove name of group from the group namespace.
            try:
                self.delete_entity_name(self.const.group_namespace)
            except Errors.NotFoundError:
                # This group does not have a name. It is an error, but it does
                # not really matter, since the group is being removed.
                pass
            # Remove entry in table `virtual_group_info'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=virtual_group_info]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.group_destroy, None)
        # Class Group is a core class; when its delete() method is
        # called, the underlying Entity object is also removed.
        super(VirtualGroup, self).delete()

    def group_types(self):
        ret = super(VirtualGroup, self).group_types()
        ret.add(self.const.entity_virtual_group)
        return ret

    def find(self, group_id):
        """Connect object to group with ``group_id`` in database."""
        self.__super.find(group_id)
        if self.entity_type != self.const.entity_virtual_group:
            return
        (self.description, self.visibility, self.creator_id,
         self.create_date, self.expire_date, self.group_name,
         self.virtual_group_type) = \
            self.query_1("""
        SELECT gi.description, gi.visibility, gi.creator_id,
               gi.create_date, gi.expire_date, en.entity_name,
               gi.virtual_group_type
        FROM [:table schema=cerebrum name=virtual_group_info] gi
        LEFT OUTER JOIN
             [:table schema=cerebrum name=entity_name] en
        ON
          gi.group_id = en.entity_id AND
          en.value_domain = :domain
        WHERE
          gi.group_id=:g_id""",
                         {'g_id': group_id,
                          'domain': int(self.const.group_namespace)})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self._Group__updated = []

    def add_member(self, member_id):
        """Add L{member_id} to this group.

        :type member_id: int
        :param member_id:
          Member (id) to add to this group. This must be an entity
          (i.e. registered in entity_info).
        """
        if self.entity_type != self.const.entity_virtual_group:
            return super(VirtualGroup, self).add_member(member_id)
        raise RuntimeError("Group {} is a virtual group; can't add members"
                           .format(self.group_name))

    def remove_member(self, member_id):
        """Remove L{member_id}'s membership from this group.

        :type member_id: int
        :param member_id: Member (id) to remove from this group.
        """
        if self.entity_type != self.const.entity_virtual_group:
            return super(VirtualGroup, self).remove_member(member_id)
        raise RuntimeError("Group {} is a virtual group; can't add members"
                           .format(self.group_name))
