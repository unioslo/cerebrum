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

from Cerebrum import Utils
from Cerebrum.Entity import Entity, EntityName

class Group(EntityName, Entity):

    # TODO: Eventually, this metaclass definition should be part of
    # the class definitions in Entity.py, but as that probably will
    # break a lot of code, we're starting here.
    __metaclass__ = Utils.mark_update

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('description', 'visibility', 'creator_id',
                      'create_date', 'expire_date', 'group_name')

    def clear(self):
        self.__super.clear()
        for attr in Group.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in Group.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def populate(self, creator, visibility, name,
                 description=None, create_date=None, expire_date=None,
                 parent=None):
        """Populate group instance's attributes without database access."""
        # TBD: Should this method call self.clear(), or should that be
        # the caller's responsibility?
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_group)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.creator_id = creator.entity_id
        self.visibility = int(visibility)
        self.description = description
        self.create_date = create_date
        self.expire_date = expire_date
        # TBD: Should this live in EntityName, and not here?  If yes,
        # the attribute should probably have a more generic name than
        # "group_name".
        self.group_name = name

    def write_db(self):
        """Write group instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Group entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.

        """
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('group_id', ':g_id'),
                    ('description', ':desc'),
                    ('visibility', ':visib'),
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
                          'g_id': self.entity_id,
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
            # TBD: This is superfluous (and wrong) to do here if
            # there's a write_db() method in EntityName.
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=entity_name]
              (entity_id, value_domain, entity_name)
            VALUES (:g_id, :domain, :name)""",
                         {'g_id': self.entity_id,
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
                         {'g_id': self.entity_id,
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
            # TBD: Maybe this is better done in EntityName.write_db()?
            self.execute("""
            UPDATE [:table schema=cerebrum name=entity_name]
            SET entity_name=:name
            WHERE
              entity_id=:g_id AND
              value_domain=:domain""",
                         {'g_id': self.entity_id,
                          'domain': int(self.const.group_namespace),
                          'name': self.group_name})
        ## EntityName.write_db(self, as_object)
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def delete(self):
        if self.__in_db:
            # Empty this group's set of members.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_member]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
            # Remove name of group from the group namespace.
            self.delete_name(self.const.group_namespace)
            # Remove entry in table `group_info'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_info]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
        # Class Group is a core class; when its delete() method is
        # called, the underlying Entity object is also removed.
        Entity.delete(self)

## TBD: Do we really need __eq__ methods once all Entity subclass
## instances properly keep track of their __updated attributes?
    def __eq__(self, other):
        assert isinstance(other, Group)
        if (self.creator_id == other.creator_id
            and self.visibility == other.visibility
            and self.group_name == other.group_name
            and self.description == other.description
            # The 'create_date' attributes should only be included in
            # the comparison of it is set in both objects.
            and (self.create_date is None
                 or other.create_date is None
                 or self.create_date == other.create_date)
            and (self.expire_date is None
                 or other.expire_date is None
                 or self.expire_date == other.expire_date)):
            # TBD: Should this compare member sets as well?
            return self.__super.__eq__(other)
        return False

    def new(self, creator, visibility, name,
            description=None, create_date=None, expire_date=None):
        """Insert a new group into the database."""
        Group.populate(self, creator, visibility, name, description,
                       create_date, expire_date)
        Group.write_db()
        # TBD: What is the following call meant to do?
        Group.find(self, self.entity_id)

    def find(self, group_id):
        """Connect object to group with ``group_id`` in database."""
        self.__super.find(group_id)
        (self.description, self.visibility, self.creator_id,
         self.create_date, self.expire_date, self.group_name) = \
         self.query_1("""
        SELECT gi.description, gi.visibility, gi.creator_id,
               gi.create_date, gi.expire_date, en.entity_name
        FROM [:table schema=cerebrum name=group_info] gi,
             [:table schema=cerebrum name=entity_name] en
        WHERE
          gi.group_id=:g_id AND
          en.entity_id=gi.group_id AND
          en.value_domain=:domain""",
                      {'g_id': group_id,
                       'domain': int(self.const.group_namespace)})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

    def find_by_name(self, name, domain=None):
        """Connect object to group having ``name`` in ``domain``."""
        if domain is None:
            domain = self.const.group_namespace
        EntityName.find_by_name(self, domain, name)

    def validate_member(self, member):
        """Raise ValueError iff ``member`` not of proper type."""
        if isinstance(member, Entity):
            return True
        raise ValueError

    def add_member(self, member, op):
        """Add ``member`` to group with operation type ``op``."""
        self.validate_member(member)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=group_member]
          (group_id, operation, member_type, member_id)
        VALUES (:g_id, :op, :m_type, :m_id)""",
                     {'g_id': self.entity_id,
                      'op': int(op),
                      'm_type': int(member.entity_type),
                      'm_id': member.entity_id})

    def remove_member(self, member, op):
        """Remove ``member``'s membership of operation type ``op`` in group."""
        self.validate_member(member)
        self.execute("""
        DELETE [:table schema=cerebrum name=group_member]
        WHERE
          group_id=:g_id AND
          operation=:op AND
          member_id=:m_id""", {'g_id': self.entity_id,
                               'op': int(op),
                               'm_id': member.entity_id})

    def list_members(self):
        """Return a list of lists indicating the members of the group.

        The top-level list returned is on the form
          [union, intersection, difference]
        where each of the sublists contains
          (``entity_type``, ``entity_id``)
        tuples indicating the members with the indicated membership
        operation.

        """
        members = [[], [], []]
        op2set = {int(self.const.group_memberop_union): members[0],
                  int(self.const.group_memberop_intersection): members[1],
                  int(self.const.group_memberop_difference): members[2]}
        for op, mtype, mid in self.query("""
        SELECT operation, member_type, member_id
        FROM [:table schema=cerebrum name=group_member]
        WHERE group_id=:g_id""", {'g_id': self.entity_id}):
            op2set[int(op)].append((mtype, mid))
        return members

    def get_members(self, _trace=()):
        my_id = self.entity_id
        if my_id in _trace:
            # TODO: Circular list definition, log value of _trace.
            return ()
        u, i, d = self.list_members()
        if not u:
            # The only "positive" members are unions; if there are
            # none of those, the resulting set must be empty.
            return ()
        # TBD: Should this just be a Group instance?
        temp = self.__class__(self._db)
        def expand(set):
            ret = []
            for mtype, m_id in set:
                if mtype == self.const.entity_account:
                    ret.append(m_id)
                elif mtype == self.const.entity_group:
                    temp.find(m_id)
                    ret.extend(temp.get_members(_trace + (my_id,)))
            return ret
        # Expand u to get a set of account_ids.
        res = expand(u)
        if i:
            res = intersect(res, expand(i))
        if d:
            res = difference(res, expand(d))
        return res

# Python 2.3 has a 'set' module in the standard library; for now we'll
# roll our own.
def intersect(a, b):
    return [x for x in a if x in b]

def difference(a, b):
    return [x for x in a if x not in b]
