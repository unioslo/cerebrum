# Copyright 2002 University of Oslo, Norway
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

"""API for accessing the core group structures in Cerebrum.

Note that even though the database allows us to define groups in
``group_info`` without giving the group a name in ``entity_name``, it
would probably turn out to be a bad idea if one tried to use groups in
that fashion.  Hence, this module **requires** the caller to supply a
name when constructing a Group object."""

from Cerebrum.Entity import Entity, EntityName

class Group(Entity, EntityName):
    def clear(self):
        self.group_id = None
        self.creator_id = None
        self.visibility = None
        self.description = None
        self.create_date = None
        self.expire_date = None
        self.group_name = None

    def populate(self, creator, visibility, name,
                 description=None, create_date=None, expire_date=None):
        """Populate group instance's attributes without database access."""
        self.creator_id = creator.entity_id
        self.visibility = visibility
        self.group_name = name
        self.description = description
        self.create_date = create_date
        self.expire_date = expire_date
        super(Group, self).populate(self.const.entity_group)

    def write_db(self, as_object=None):
        """Write group instance to database.

        If ``as_object`` is set, it should be another group object.
        That object's entity_id will be the one that is updated with
        this object's attributes.

        Otherwise, a new entity_id is generated and used to insert
        this object."""

        assert self.__write_db
        super(Group, self).write_db(as_object)
        self.group_id = self.entity_id
        if as_object is None:
            cols = [('entity_type', ':e_type'),
                    ('group_id', ':g_id'),
                    ('description', ':desc'),
                    ('visibility', ':visib')
                    ('creator_id', ':creator_id')]
            # Columns that have default values through DDL.
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=group_info] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         {'e_type': int(self.const.entity_group),
                          'g_id': self.group_id,
                          'desc': self.description,
                          'visib': self.visibility,
                          'creator_id': self.creator_id,
                          # Even though the following two bind
                          # variables will only be used in the query
                          # when their values aren't None, there's no
                          # reason we should take extra steps to avoid
                          # including them here.
                          'create_date': self.create_date,
                          'exp_date': self.expire_date})
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=entity_name]
              (entity_id, value_domain, entity_name)
            VALUES (:g_id, :domain, :name)""",
                         {'g_id': self.group_id,
                          'domain': int(self.const.group_namespace),
                          'name': self.group_name})
        else:
            cols = [('description', ':desc'),
                    ('visibility', ':visib')
                    ('creator_id', ':creator_id')]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))
            self.execute("""
            UPDATE [:table schema=cerebrum name=group_info]
            SET %(defs)s
            WHERE group_id=:g_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols if x[0] <> 'group_id'])},
                         {'g_id': self.group_id,
                          'desc': self.description,
                          'visib': self.visibility,
                          'creator_id': self.creator_id,
                          # Even though the following two bind
                          # variables will only be used in the query
                          # when their values aren't None, there's no
                          # reason we should take extra steps to avoid
                          # including them here.
                          'create_date': self.create_date,
                          'exp_date': self.expire_date})
            self.execute("""
            UPDATE [:table schema=cerebrum name=entity_name]
            SET entity_name=:name
            WHERE
              entity_id=:g_id AND
              value_domain=:domain""",
                         {'g_id': self.group_id,
                          'domain': int(self.const.group_namespace),
                          'name': self.group_name})
        ## EntityName.write_db(self, as_object)
        self.__write_db = False

    def __eq__(self, other):
        assert isinstance(other, Group)
        if (self.creator_id <> other.creator_id or
            self.visibility <> other.visibility or
            self.group_name <> other.group_name or
            self.description <> other.description or
            self.create_date <> other.create_date or
            self.expire_date <> other.expire_date):
            return False
        # TBD: Should this compare member sets as well?
        return True

    def new(self, creator, visibility, name,
            description=None, create_date=None, expire_date=None):
        """Insert a new group into the database."""
        Group.populate(self, creator, visibility, name, description,
                        create_date, expire_date)
        Group.write_db(self)
        Group.find(self, self.group_id)

    def find(self, group_id):
        """Connect object to group with ``group_id`` in database."""
        (self.group_id, self.description, self.visibility, self.creator_id,
         self.create_date, self.expire_date, self.group_name) = \
         self.query_1("""
        SELECT gi.group_id, gi.description, gi.visibility, gi.creator_id,
               gi.create_date, gi.expire_date, en.entity_name
        FROM [:table schema=cerebrum name=group_info] gi,
             [:table schema=cerebrum name=entity_name] en
        WHERE
          gi.group_id=:g_id AND
          en.entity_id=:g_id AND
          en.value_domain=:domain""",
                      {'g_id': group_id
                       'domain': int(self.const.group_namespace)})
        super(self, Group).find(group_id)

    def find_by_name(self, name, domain):
        """Connect object to group having ``name`` in ``domain``."""
        group_id = self.query_1("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_name]
        WHERE value_domain=:domain AND entity_name=:name""", locals())
        self.find(group_id)

    def add_member(self, member, op):
        """Add ``member`` to group with operation type ``op``."""
        assert isinstance(member, Entity)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=group_member]
          (group_id, operation, member_type, member_id)
        VALUES (:g_id, :op, :m_type, :m_id)""",
                     {'g_id': self.group_id,
                      'op': int(op),
                      'm_type': member.entity_type,
                      'm_id': member.entity_id})

    def remove_member(self, member, op):
        """Remove ``member``'s membership of operation type ``op`` in group."""
        self.execute("""
        DELETE [:table schema=cerebrum name=group_member
        WHERE
          group_id=:g_id AND
          operation=:op AND
          member_id=:m_id""", {'g_id': self.group_id,
                               'op': int(op),
                               'm_id': member.entity_id})

    def list_members(self, domain):
        """Return a list of lists indicating the members of the group.

        The top-level list returned is on the form
          [union, intersection, difference]
        where each of the sublists contains the names of members with
        the indicated membership operation.

        """
        members = [[], [], []]
        union, intersection, difference = members
        for op, name in self.query("""
        SELECT m.operation, n.entity_name
        FROM [:table schema=cerebrum name=group_member] m,
             [:table schema=cerebrum name=entity_name] n
        WHERE
          m.group_id=:g_id AND
          m.group_id = n.entity_id AND
          n.value_domain=:domain""", {'g_id': self.group_id,
                                      'domain': domain}):
            if int(op) == int(self.const.group_memberop_union):
                union.append(name)
            elif int(op) == int(self.const.group_memberop_intersection):
                intersection.append(name)
            elif int(op) == int(self.const.group_memberop_difference):
                difference.append(name)
        return members
