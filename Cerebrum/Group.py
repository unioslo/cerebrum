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

"""API for accessing the core group structures in Cerebrum.

Note that even though the database allows us to define groups in
``group_info`` without giving the group a name in ``entity_name``, it
would probably turn out to be a bad idea if one tried to use groups in
that fashion.  Hence, this module **requires** the caller to supply a
name when constructing a Group object."""

from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Entity import Entity, EntityName, EntityQuarantine
try:
    from sets import Set
except ImportError:
    # It's the same module taken from python 2.3, it should
    # work fine in 2.2  
    from Cerebrum.extlib.sets import Set


class Group(EntityQuarantine, EntityName, Entity):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('description', 'visibility', 'creator_id',
                      'create_date', 'expire_date', 'group_name')

    def clear(self):
        self.__super.clear()
        self.clear_class(Group)
        self.__updated = []

    def populate(self, creator_id, visibility, name,
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
        self.creator_id = creator_id
        self.visibility = int(visibility)
        self.description = description
        self.create_date = create_date
        self.expire_date = expire_date
        # TBD: Should this live in EntityName, and not here?  If yes,
        # the attribute should probably have a more generic name than
        # "group_name".
        self.group_name = name

    def illegal_name(self, name):
        """Return a string with error message if username is illegal"""
        return False

    def write_db(self):
        """Write group instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Group entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.

        """
        tmp = self.illegal_name(self.group_name)
        if tmp:
            raise self._db.IntegrityError, "Illegal groupname: %s" % tmp
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
            self._db.log_change(self.entity_id, self.const.group_mod, None)
            self.update_entity_name(self.const.group_namespace, self.group_name)
        ## EntityName.write_db(self, as_object)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        if self.__in_db:
            # Empty this group's set of members.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_member]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
            # Remove name of group from the group namespace.
            self.delete_entity_name(self.const.group_namespace)
            # Remove entry in table `group_info'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_info]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.group_destroy, None)
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
        self.populate(creator, visibility, name, description,
                      create_date, expire_date)
        self.write_db()

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
        self.__updated = []

    def find_by_name(self, name, domain=None):
        """Connect object to group having ``name`` in ``domain``."""
        if domain is None:
            domain = self.const.group_namespace
        EntityName.find_by_name(self, name, domain)

    def validate_member(self, member):
        """Raise ValueError iff ``member`` not of proper type."""
        if isinstance(member, Entity):
            return True
        raise ValueError

    def add_member(self, member_id, type, op):
        """Add ``member`` to group with operation type ``op``."""
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=group_member]
          (group_id, operation, member_type, member_id)
        VALUES (:g_id, :op, :m_type, :m_id)""",
                     {'g_id': self.entity_id,
                      'op': int(op),
                      'm_type': int(type),
                      'm_id': member_id})
        self._db.log_change(member_id, self.clconst.group_add, self.entity_id)

    def has_member(self, member_id, type, op):
        try:
            self.query_1("""
            SELECT 'x' FROM [:table schema=cerebrum name=group_member]
            WHERE group_id=:g_id AND
                  operation=:op AND
                  member_type=:m_type AND
                  member_id=:m_id""", {'g_id': self.entity_id,
                                       'op': int(op),
                                       'm_id': member_id,
                                       'm_type': int(type)})
            return True
        except Errors.NotFoundError:
            return False

    def remove_member(self, member_id, op):
        """Remove ``member``'s membership of operation type ``op`` in group."""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=group_member]
        WHERE
          group_id=:g_id AND
          operation=:op AND
          member_id=:m_id""", {'g_id': self.entity_id,
                               'op': int(op),
                               'm_id': member_id})
        self._db.log_change(member_id, self.clconst.group_rem, self.entity_id)

    def list_groups_with_entity(self, entity_id, include_indirect_members=0):
        """Return a list where entity_id is a direct member"""
        if include_indirect_members:
            raise NotImplementedError
        return self.query("""
        SELECT group_id, operation, member_type
        FROM [:table schema=cerebrum name=group_member]
        WHERE member_id=:member_id""", {'member_id': entity_id})

    def list_members(self, spread=None, member_type=None, get_entity_name=False):
        """Return a list of lists indicating the members of the group.

        The top-level list returned is on the form
          [union, intersection, difference]
        where each of the sublists contains
          (``entity_type``, ``entity_id``)
        tuples indicating the members with the indicated membership
        operation.

        """
        extfrom = extwhere = extcols = ""
        if member_type is not None:
            extwhere = "member_type=:member_type AND "
            member_type = int(member_type)
        if spread is not None:
            extfrom = ", [:table schema=cerebrum name=entity_spread] es"
            extwhere = """gm.member_id=es.entity_id AND es.spread=:spread AND """
        if get_entity_name:
            extcols += ", entity_name"
            extfrom += ", [:table schema=cerebrum name=entity_name] en"
            # TBD: Is the value_domain check really neccesary?
            extwhere += """gm.member_id=en.entity_id AND
              ((en.value_domain=:group_dom AND gm.member_type=:entity_group) OR
              (en.value_domain=:account_dom AND gm.member_type=:entity_account))
              AND """
        members = [[], [], []]
        op2set = {int(self.const.group_memberop_union): members[0],
                  int(self.const.group_memberop_intersection): members[1],
                  int(self.const.group_memberop_difference): members[2]}
        for row in self.query("""
        SELECT operation, member_type, member_id %s
        FROM [:table schema=cerebrum name=group_member] gm %s
        WHERE %s gm.group_id=:g_id""" % (extcols, extfrom, extwhere), {
            'g_id': self.entity_id,
            'spread': spread,
            'member_type': member_type,
            'group_dom': int(self.const.group_namespace),
            'account_dom': int(self.const.account_namespace),
            'entity_group': int(self.const.entity_group),
            'entity_account': int(self.const.entity_account)}):
            op2set[int(row[0])].append(row[1:])
            # Could have been, but some way breaks mr. internet
            # in auth
            #op2set[int(row[0])].append(row)
            # don't confuse legacy code by including operation
            #del row[0]
        return members

    def get_members(self, _trace=(), spread=None, get_entity_name=False):
        """Return a flattened list of entity ids of all account
        members in this group and its subgroups.  If spread is set,
        only include accounts with that spread.  If get_entity_name is
        set, return a list [id, name] for each account."""
        
        if self.entity_id in _trace:
            # TODO: Circular list definition, log value of _trace.
            return Set()
        else:
            _trace = _trace + (self.entity_id,)
       
        # Some small utility functions 
        def format_accounts(accounts):
            """Select wanted fields from list of accounts as returned by list_members"""
            if get_entity_name:
                filter = lambda account: (account[1], account[2])
            else:
                filter = lambda account: account[1]    
            return Set(map(filter, accounts))
        
        # A temporary object for expanding groups, used by expand_groups
        group = Group(self._db)
        def expand_groups(groups):
            """Expands a list of groups as returned by Group.list_members."""
            accounts = Set()
            for (t, group_id) in groups:
                group.clear()
                group.find(group_id)
                group_members = group.get_members(_trace,
                                            spread=spread,
                                            get_entity_name=get_entity_name)
                accounts.update(group_members)
            return accounts
            
        member_accounts = self.list_members(get_entity_name=get_entity_name,
                                    spread=spread,
                                    member_type=self.const.entity_account)
        # select wanted fields
        member_accounts = [format_accounts(accounts) for accounts in member_accounts]
        member_groups = self.list_members(member_type=self.const.entity_group)

        # Expand and get all member-accounts
        member_groups = map(expand_groups, member_groups)

        # merge group accounts into account sets
        map(lambda (accounts, groups): accounts.update(groups),  
            zip(member_accounts, member_groups))

        # And unpack direct members
        (unions, intersects, differences) = member_accounts

        # we begin with all the union people
        all_accounts = Set(unions)
        # and if anything intersects - intersect it
        if intersects:
            all_accounts.intersection_update(intersects)
        # same for difference - only apply it if there's anyone   
        if differences:
            all_accounts.difference_update(differences)
        return all_accounts

    def list_all(self, spread=None):
        """Lists all groups (of given ``spread``).

        DEPRECATED: use search() instead

        """
        return self.search(filter_spread=spread)

    def search(self, filter_spread=None, filter_name=None, filter_desc=None,
               exclude_expired=False):
        """Retrieves a list of groups filtered by the given criterias.
           (list of tuples (id, name, desc)).
           If no criteria is given, all groups are returned.
           ``filter_name`` and ``filter_desc`` should be strings if
           given, wildcards * and ? are expanded for "any chars" and
           "one char".""" 
            
        def prep_string(value):
            value = value.replace("*", "%")
            value = value.replace("?", "_")
            value = value.lower()
            return value
            
        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=group_info] gi")
        tables.append("[:table schema=cerebrum name=entity_name] en")
        where.append("en.entity_id=gi.group_id")
        where.append("en.value_domain=:vdomain")
        
        if filter_spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("gi.group_id=es.entity_id")
            where.append("es.entity_type=:etype")
            # Support both integers (id-s) and strings. Strings could be
            # with wildcards
            try: 
                filter_spread = int(filter_spread)
            except (TypeError, ValueError):
                # match code_str
                filter_spread = prep_string(filter_spread)
                tables.append("[:table schema=cerebrum name=spread_code] sc")
                where.append("es.spread=sc.code")
                where.append("LOWER(sc.code_str) LIKE :filterspread")
            else:    
                # Go for the simple int version
                where.append("es.spread=:filterspread")

        if exclude_expired:
            where.append("(gi.expire_date IS NULL OR gi.expire_date > [:now])")

        if filter_name is not None:
            filter_name = prep_string(filter_name)
            where.append("LOWER(en.entity_name) LIKE :filtername")

        if filter_desc is not None:
            filter_desc = prep_string(filter_desc)
            where.append("LOWER(gi.description) LIKE :filterdesc")
            
        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)
            
        return self.query("""
        SELECT DISTINCT gi.group_id AS group_id, 
               en.entity_name AS name,  
               gi.description AS description
        FROM %s %s""" % (', '.join(tables), where_str), 
            {'filterspread': filter_spread, 'etype': int(self.const.entity_group),
             'filtername': filter_name, 'filterdesc': filter_desc,
             'vdomain': int(self.const.group_namespace)})


    def list_all_test(self, spread=None):
	""" Will be removed """
        return self.list_all_grp(spread=spread)

    def list_all_grp(self, spread=None):
	where = ""
	if spread is not None:
	    spreads = '(' + ' OR '.join(['es.spread=' + str(x) for x in spread]) + ')'
	    where = """gi, [:table schema=cerebrum name=entity_spread] es
	    WHERE gi.group_id=es.entity_id AND es.entity_type=[:get_constant name=entity_group] 
		AND %s""" % spreads
	return self.query("""
	SELECT DISTINCT group_id
	FROM [:table schema=cerebrum name=group_info]
	%s""" % where)


