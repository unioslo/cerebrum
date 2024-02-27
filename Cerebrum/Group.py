# -*- coding: utf-8 -*-
#
# Copyright 2002-2023 University of Oslo, Norway
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
"""
API for accessing the core group structures in Cerebrum.

Note that even though the database allows us to define groups in
``group_info`` without giving the group a name in ``entity_name``, it
would probably turn out to be a bad idea if one tried to use groups in
that fashion.  Hence, this module **requires** the caller to supply a
name when constructing a Group object.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import six

import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.Entity import (EntityName, EntityQuarantine, EntityExternalId,
                             EntitySpread, EntityNameWithLanguage)
from Cerebrum.Utils import argument_to_sql, prepare_string
from Cerebrum.utils import date_compat


Entity_class = Utils.Factory.get("Entity")


@six.python_2_unicode_compatible
class BaseGroup(EntityQuarantine, EntityExternalId,
                EntityName, EntitySpread,
                EntityNameWithLanguage, Entity_class):

    __read_attr__ = ('__in_db', 'created_at')
    __write_attr__ = ('description', 'visibility', 'creator_id',
                      'expire_date', 'group_name', 'group_type')

    def clear(self):
        super(BaseGroup, self).clear()
        self.clear_class(BaseGroup)
        self.__updated = []

    def populate(self, creator_id=None, visibility=None, name=None,
                 description=None, expire_date=None, group_type=None,
                 parent=None):
        """
        Populate group instance's attributes without database access.

        :param creator_id:
            the entity_id of an existing account.  Required for new Group
            objects.

        :param visibility:
            A valid _GroupVisibilityCode (or its int-value).  Required for new
            Group objects.

        :param name:
            A group_name for this group.  Required for new Group objects.

        :param description:
            A description for this group.  Typically something that describes
            its content or usecase.

        :param expire_date:
            Sets an expire_date for this group.

        :param group_type:
            A valid _GroupTypeCode (or its int-value).  Required for new Group
            objects.

        :param parent:
            Set to an existing entity-object to promote it.

            Normally, populate creates a new Entity and assigns group data to
            it.  If a `parent` value is given, that Entity will be re-used and
            *promoted* to a group.
        """
        if parent is not None:
            self.__xerox__(parent)
        else:
            super(BaseGroup, self).populate(
                  entity_type=self.const.entity_group)
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
        self.group_type = int(group_type)
        self.visibility = int(visibility)
        self.description = description
        self.expire_date = expire_date
        # TBD: Should this live in EntityName, and not here?  If yes,
        # the attribute should probably have a more generic name than
        # "group_name".
        self.group_name = name

    def new(self, *rest, **kw):
        """Insert a new group into the database."""
        self.populate(*rest, **kw)
        self.write_db()

    def is_expired(self):
        """Checks if group is expired"""
        expire_date = date_compat.get_date(self.expire_date)
        if expire_date is None:
            return False
        return expire_date < datetime.date.today()

    def is_empty(self):
        """Checks if group is empty"""
        for row in self.search_members(group_id=self.entity_id):
            return False
        return True

    def set_default_expire_date(self):
        """Sets the expire date of a group if a default lifetime is defined"""
        lifetime = cereconf.MANUAL_GROUP_DEFAULT_LIFETIME
        if lifetime:
            # Insanity: This value is in *hours*?
            delta = datetime.timedelta(hours=int(lifetime))
            self.expire_date = datetime.date.today() + delta

    # exchange-relatert-jazz
    # we need to be able to check group names for different
    # lengths and max length in database is 256 characters
    def illegal_name(self, name, max_length=256):
        """Return a string with error message if groupname is illegal"""
        if not name:
            return "Must specify group name"
        if len(name) > max_length:
            return "Name %s too long (%d char allowed)" % (name, max_length)
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
        super(BaseGroup, self).write_db()
        try:
            is_new = not self.__in_db
        except AttributeError:
            return
        if not self.__updated:
            return

        if 'group_name' in self.__updated:
            tmp = self.illegal_name(self.group_name)
            if tmp:
                raise self._db.IntegrityError("Illegal groupname: %s" % tmp)
        binds = {
            'description': self.description,
            'group_id': self.entity_id,
            'visibility': int(self.visibility),
            'creator_id': self.creator_id,
            'expire_date': self.expire_date,
            'group_type': int(self.group_type),
        }
        if is_new:
            binds['entity_type'] = int(self.const.entity_group),
            insert_stmt = """
              INSERT INTO [:table schema=cerebrum name=group_info] (%(tc)s)
              VALUES (%(tb)s)
            """ % {
                'tc': ", ".join(x for x in sorted(binds)),
                'tb': ", ".join(':{0}'.format(x) for x in sorted(binds)),
            }
            self.execute(insert_stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.group_create,
                                None)
            self.add_entity_name(self.const.group_namespace, self.group_name)
        else:
            original_state = self.query_1("""
              SELECT gi.description, gi.visibility, gi.creator_id,
                     gi.expire_date, gi.group_type
              FROM [:table schema=cerebrum name=group_info] gi
              WHERE gi.group_id=:group_id
            """, {
                'group_id': self.entity_id
            })

            change_params = {'old_' + k: v for k, v in
                             dict(original_state).items() if not v == binds[k]}

            if change_params:
                # True positive
                set_str = ', '.join(
                    '{0}=:{0}'.format(x) for x in binds if x != 'group_id')
                update_stmt = """
                  UPDATE [:table schema=cerebrum name=group_info]
                  SET {set_str}
                  WHERE group_id=:group_id""".format(set_str=set_str)
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.clconst.group_mod,
                                    None,
                                    change_params=change_params)
            if 'group_name' in self.__updated:
                self.update_entity_name(self.const.group_namespace,
                                        self.group_name)

        # EntityName.write_db(self, as_object)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def demote(self):
        """ Allow partial delete in mixins and subtypes.

        This function should be used by subtypes when the group should be
        kept, but the subtype-specific data should be deleted.

        E.g. 'demote posix group', to remove the posix group data, but keep the
        base group.

        :return bool: True if something was demoted.

        """
        return False

    def delete(self):
        """ Delete group and entity from database."""
        if self.__in_db:
            # Empty this group's set of members.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_member]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})

            # Empty this group's memberships.
            # IVR 2008-06-06 TBD: Is this really wise? I.e. should the caller
            # of delete() make sure that all memberships have been removed?
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_member]
            WHERE member_id=:g_id""", {'g_id': self.entity_id})

            # Remove name of group from the group namespace.
            try:
                self.delete_entity_name(self.const.group_namespace)
            except Errors.NotFoundError:
                # This group does not have a name. It is an error, but it does
                # not really matter, since the group is being removed.
                pass
            # Remove entry in table `group_info'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_info]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
            self._db.log_change(self.entity_id,
                                self.clconst.group_destroy,
                                None,
                                {'name': self.group_name})
        # Class Group is a core class; when its delete() method is
        # called, the underlying Entity object is also removed.
        self.__super.delete()

    # TBD: Do we really need __eq__ methods once all Entity subclass
    # instances properly keep track of their __updated attributes?
    def __eq__(self, other):
        assert isinstance(other, Group)
        if (self.creator_id == other.creator_id and
            self.entity_type == other.entity_type and
            self.visibility == other.visibility and
            self.group_name == other.group_name and
            self.description == other.description and
            self.group_type == other.group_type and
            # The 'created_at' attributes should only be included in
            # the comparison of it is set in both objects.
            (self.created_at is None or
             other.created_at is None or
             self.created_at == other.created_at) and
            (self.expire_date is None or
             other.expire_date is None or
             self.expire_date == other.expire_date)):
            # TBD: Should this compare member sets as well?
            return self.__super.__eq__(other)
        return False

    def find(self, group_id):
        """Connect object to group with ``group_id`` in database."""
        self.__super.find(group_id)
        (
            self.description,
            self.visibility,
            self.creator_id,
            self.expire_date,
            self.group_name,
            self.group_type,
        ) = self.query_1(
            """
              SELECT gi.description, gi.visibility, gi.creator_id,
                     gi.expire_date, en.entity_name, gi.group_type
              FROM [:table schema=cerebrum name=group_info] gi
              LEFT OUTER JOIN
                   [:table schema=cerebrum name=entity_name] en
              ON
                gi.group_id = en.entity_id AND
                en.value_domain = :value_domain
              WHERE
                gi.group_id=:group_id
            """,
            {
                'group_id': group_id,
                'value_domain': int(self.const.group_namespace),
            })
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

    def get_extensions(self):
        """ Return all the group subtypes that applies to this group.

        This method returns a list of subtypes that applies to this group.
        Subtypes should implement a base-mixin to Group that can identify and
        append the subtype to the return value of this method.

        E.g. For a group that is also PosixGroup and DistributionGroup, this
        method should return ['PosixGroup', 'DistributionGroup', ].

        :rtype: list
        :return: A list of all the subtypes that applies to this group.

        """
        # TBD: Should this return a non-empty list? Should it include 'Group'?
        return list()

    def has_extension(self, extname):
        """ Check if a group has a certain subtype associated with it.

        :param basestring extname: The extension/subtype name.

        :return bool: True if the group is a group of type extname.

        """
        return extname in self.get_extensions()

    def add_member(self, member_id):
        """Add L{member_id} to this group.

        :param int member_id:
          Member (id) to add to this group. This must be an entity
          (i.e. registered in entity_info).
        """
        # First, locate the member's type (it's silly to require the client
        # code to supply it, even though it costs one lookup extra in the
        # database).
        member_type = self.query_1("""
            SELECT entity_type
            FROM [:table schema=cerebrum name=entity_info]
            WHERE entity_id = :member_id""", {"member_id": member_id})

        # Then insert the data into the table.
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=group_member]
          (group_id, member_type, member_id)
        VALUES (:g_id, :m_type, :m_id)""",
                     {'g_id': self.entity_id,
                      'm_type': int(member_type),
                      'm_id': member_id})
        self._db.log_change(self.entity_id, self.clconst.group_add, member_id)

    def has_member(self, member_id):
        """Check whether L{member_id} is a member of this group.

        :param int member_id:
          Member (id) to check for membership.

        :return:
            A single group_member database row, or False if no membership
            exists.
        """

        # IVR 2008-06-27 TBD: Perhaps, express this in terms of search_members?
        where = ["group_id = :g_id", "member_id = :m_id"]
        binds = {'g_id': self.entity_id, 'm_id': member_id}
        try:
            return self.query_1("""
            SELECT group_id, member_type, member_id
            FROM [:table schema=cerebrum name=group_member]
            WHERE """ + " AND ".join(where), binds)
        except Errors.NotFoundError:
            return False

    def remove_member(self, member_id):
        """Remove L{member_id}'s membership from this group.

        @type member_id: int
        @param member_id:
          Member (id) to remove from this group.
        """
        return self.remove_member_from_group(member_id, self.entity_id)

    def remove_member_from_group(self, member_id, group_id):
        """Remove L{member_id}'s membership from a group.

        @type member_id: int
        @param member_id:
          Member (id) to remove from group.

        @type group_id: int
        @param group_id:
            Group (id) to remove member from
        """

        binds = {'group_id': group_id,
                 'member_id': member_id}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=group_member]
            WHERE group_id=:group_id AND
                  member_id=:member_id
          )
        """
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=group_member]
          WHERE group_id=:group_id AND
                member_id=:member_id"""
        self.execute(delete_stmt, binds)
        self._db.log_change(group_id, self.clconst.group_rem, member_id)

    def search(self,
               group_id=None,
               member_id=None,
               indirect_members=False,
               admin_id=None,
               admin_by_membership=False,
               moderator_id=None,
               moderator_by_membership=False,
               spread=None,
               name=None,
               description=None,
               group_type=None,
               filter_expired=True,
               creator_id=None,
               expired_only=False,
               fetchall=True,
               ):
        """Search for groups satisfying various filters.

        Search **for groups** where the results are filtered by a number of
        criteria. There are many filters that can be specified; the result
        returned by this method satisfies all of the filters. Not all of the
        filters are compatible (check the documentation)

        If a filter is None, it means that it will not be applied. Calling
        this method without any arguments will return all non-expired groups
        registered in group_info.

        :type group_id: int or sequence thereof or None.
        :param group_id:
          Group ids to look for. This is the most specific filter that can be
          given. With this filter, only the groups matching the specified
          id(s) will be returned.

          This filter cannot be combined with L{member_id}.

        :type member_id: int or sequence thereof or None.
        :param member_id:
          The resulting group list will be filtered by membership - only
          groups that have members specified by member_id will be returned. If
          member_id is a sequence, then a group g1 is returned if any of the
          ids in the sequence are a member of g1.

          This filter cannot be combined with L{group_id}.

        :type indirect_members: bool
        :param indirect_members:
          This parameter controls how the L{member_id} filter is applied. When
          False, only groups where L{member_id} is a/are direct member(s) will
          be returned. When True, the membership of L{member_id} does not have
          to be direct; if group g2 is a member of group g1, and member_id m1
          is a member of g2, specifying indirect_members=True will return g1
          as well as g2. Be careful, for some situations this can drastically
          increase the result size.

          This filter makes sense only when L{member_id} is set.

        :type admin_id: int or sequence thereof or None.
        :param admin_id:
          The resulting group list will be filtered by adminship - only
          groups that have admins specified by admin_id will be
          returned. If admin_id is a sequence, then a group g1 is returned
          if any of the ids in the sequence are a admin of g1.

        :type admin_by_membership: bool
        :param admin_by_membership:
          This parameter controls how the L{admin_id} filter is applied.
          When False, only groups where L{admin_id} is a/are direct
          admin(s) will be returned. When True, the adminship of
          L{admin_id} does not have to be direct; if group g2 is a
          admin of group g1, and admin_id m1 is a member of g2,
          specifying indirect_admins=True will return g1.

          This filter makes sense only when L{admin_id} is set.

        :type moderator_id: int or sequence thereof or None.
        :param moderator_id:
          The resulting group list will be filtered by moderatorship - only
          groups that have moderators specified by moderator_id will be
          returned. If moderator_id is a sequence, then a group g1 is returned
          if any of the ids in the sequence are a moderator of g1.

        :type moderator_by_membership: bool
        :param moderator_by_membership:
          This parameter controls how the L{moderator_id} filter is applied.
          When False, only groups where L{moderator_id} is a/are direct
          moderator(s) will be returned. When True, the moderatorship of
          L{moderator_id} does not have to be direct; if group g2 is a
          moderator of group g1, and moderator_id m1 is a member of g2,
          specifying indirect_moderators=True will return g1.

          This filter makes sense only when L{moderator_id} is set.

        :type spread: int or SpreadCode or sequence thereof or None.
        :param spread:
          Filter the resulting group list by spread. I.e. only groups with
          specified spread(s) will be returned.

        :type name: basestring
        :param name:
          Filter the resulting group list by name. The name may contain SQL
          wildcard characters.

        :type description: basestring
        :param description:
          Filter the resulting group list by group description. The
          description may contain SQL wildcard characters.

        :type group_type: int or GroupTypeCode or sequence thereof or None
        :param description:
          Filter the resulting group list by group type - i.e. only return
          groups with one of the given group types.

        :type filter_expired: bool
        :param filter_expired:
          Filter the resulting group list by expiration date. If set, do NOT
          return groups that have expired (i.e. have group_info.expire_date in
          the past relative to the call time).

        :type expired_only: bool
        :param expired_only:
          Filter the resulting group list by expiration date.
          If set, return ONLY groups
          that have expired_date set and expired (relative to the call time).
          N.B. filter_expired and expired_only are mutually exclusive

        :rtype: iterable (yielding rows with group information)
        :return:
          An iterable (sequence or a generator) that yields successive db-rows
          matching all of the specified filters. Regardless of the filters,
          any given group_id is guaranteed to occur at most once in the
          result. The keys available in rows are the content of the
          group_info table, supplemented with a 'name' column.  'name' will be
          None if no group name exists.
        """
        # Sanity check: if indirect members is specified, then at least we
        # need one id to go on.
        if indirect_members and not member_id:
            raise Errors.ProgrammingError(
                'Cannot use indirect_members without member_id'
            )

        if admin_by_membership and not admin_id:
            raise Errors.ProgrammingError(
                'Cannot use indirect_admins without admin_id'
            )

        if moderator_by_membership and not moderator_id:
            raise Errors.ProgrammingError(
                'Cannot use indirect_moderators without moderator_id'
            )

        # Sanity check: it is probably a bad idea to allow specifying both.
        if member_id and group_id:
            raise Errors.ProgrammingError(
                'member_id and group_id cannot be used simultaneously'
            )

        def search_transitive_closure(member_id):
            """Return all groups where member_id is/are indirect member(s).

            :type member_id: int or sequence thereof.
            :param member_id:
              We are looking for groups where L{member_id} is/are indirect
              member(s).

            :rtype: set (of group_ids (ints))
            :result:
              Set of group_ids where member_id is/are indirect members.
            """

            result = set()
            if not isinstance(member_id, (tuple, set, list)):
                member_id = (member_id,)

            # workset contains ids of the entities that are members. in each
            # iteration we are looking for direct parents of whatever is in
            # workset.
            workset = set(int(x) for x in member_id)
            while workset:
                tmp = workset
                workset = set()
                for row in self.search(member_id=tmp,
                                       indirect_members=False,
                                       # We need to be *least* restrictive
                                       # here. Final filtering will take care
                                       # of 'expiredness'.
                                       filter_expired=False):
                    group_id = int(row["group_id"])
                    if group_id in result:
                        continue
                    result.add(group_id)
                    if group_id not in workset:
                        workset.add(group_id)

            return result

        stmt = """
          SELECT DISTINCT
            gi.group_id AS group_id,
            en.entity_name AS name,
            gi.description AS description,
            gi.visibility AS visibility,
            gi.creator_id AS creator_id,
            ei.created_at AS created_at,
            gi.expire_date AS expire_date,
            gi.group_type AS group_type
          FROM
            [:table schema=cerebrum name=group_info] gi
          LEFT OUTER JOIN
            [:table schema=cerebrum name=entity_name] en
          ON
            en.entity_id = gi.group_id AND
            en.value_domain = :vdomain
          LEFT OUTER JOIN
            [:table schema=cerebrum name=entity_info] ei
          ON
            ei.entity_id = gi.group_id AND
            ei.entity_type = :entity_type
          {extra_tables}
          {where}
        """
        extra_tables = []
        where = []
        binds = {
            "vdomain": int(self.const.group_namespace),
            "entity_type": int(self.const.entity_group),
        }

        #
        # group_id filter
        if group_id is not None:
            where.append(
                argument_to_sql(group_id, "gi.group_id", binds, int))

        #
        # member_id filters (all of them)
        if member_id is not None:
            if indirect_members:
                # NB! This can be a very large group set.
                group_ids = search_transitive_closure(member_id)
                if not group_ids:
                    return []

                where.append(
                    argument_to_sql(group_ids, "gi.group_id", binds, int))
            else:
                extra_tables.append(
                    "[:table schema=cerebrum name=group_member] gm")
                where.append("(gi.group_id = gm.group_id)")
                where.append(argument_to_sql(member_id, "gm.member_id",
                                             binds, int))

        #
        # admin_id filter (all of them)
        if admin_id is not None:
            extra_tables.append("[:table schema=cerebrum name=group_admin] ga")
            where.append("(gi.group_id = ga.group_id)")

            if admin_by_membership:
                admin_ids = [admin_id]
                for group in self.search(member_id=admin_id):
                    admin_ids.append(group['group_id'])

                where.append(argument_to_sql(admin_ids, "ga.admin_id",
                                             binds, int))
            else:
                where.append(argument_to_sql(admin_id, "ga.admin_id",
                                             binds, int))

        #
        # moderator_id filter (all of them)
        if moderator_id is not None:
            extra_tables.append(
                "[:table schema=cerebrum name=group_moderator] gmod")
            where.append("(gi.group_id = gmod.group_id)")
            if moderator_by_membership:
                moderator_ids = [moderator_id]
                for group in self.search(member_id=moderator_id):
                    moderator_ids.append(group['group_id'])
                where.append(argument_to_sql(moderator_ids,
                                             "gmod.moderator_id", binds, int))
            else:
                where.append(argument_to_sql(moderator_id, "gmod.moderator_id",
                                             binds, int))

        #
        # spread filter
        if spread is not None:
            extra_tables.append(
                "[:table schema=cerebrum name=entity_spread] es")
            where.append("(gi.group_id = es.entity_id)")
            where.append(argument_to_sql(spread, "es.spread", binds, int))

        #
        # name filter
        if name is not None:
            name = prepare_string(name)
            where.append("(LOWER(en.entity_name) LIKE :name)")
            binds["name"] = name

        # description filter
        if description is not None:
            description = prepare_string(description)
            where.append("(LOWER(gi.description) LIKE :description)")
            binds["description"] = description

        #
        # group type filter
        if group_type is not None:
            where.append(
                argument_to_sql(group_type, "gi.group_type", binds, int))

        #
        # expired filter
        if filter_expired:
            where.append("(gi.expire_date IS NULL OR gi.expire_date > [:now])")

        #
        # creator_id filter
        if creator_id is not None:
            where.append(argument_to_sql(creator_id, "gi.creator_id", binds,
                                         int))

        #
        # expired_only filter
        if expired_only:
            where.append(
                "(gi.expire_date IS NOT NULL AND gi.expire_date < " "[:now])")

        prepared = stmt.format(
            extra_tables=(', ' + ', '.join(extra_tables)
                          if extra_tables else ''),
            where='WHERE ' + ' AND '.join(where) if where else '',
        )
        return self.query(prepared, binds, fetchall=fetchall)

    def search_members(self, group_id=None, spread=None,
                       member_id=None, member_type=None,
                       indirect_members=False,
                       member_spread=None,
                       member_filter_expired=True,
                       include_member_entity_name=False,
                       group_type=None):
        """Search for group *MEMBERS* satisfying certain criteria.

        This method is a complement of L{search}. While L{search} returns
        *group* information, L{search_members} returns member and membership
        information. Despite the similarity in filters, the methods have
        different objectives.

        If a filter is None, it means that it will not be applied. Calling
        this method without any argument will return all non-expired members
        of groups (i.e. a huge chunk of the group_member table). Since
        group_member is one of the largest tables, do not do that, unless you
        have a good reason.

        All filters except for L{group_id} are applied to members, rather than
        groups containing members.

        The db-rows eventually returned by this method contain at least these
        keys: group_id, group_name, member_type, member_id. There may be other
        keys as well.

        :type group_id: int or a sequence thereof or None.
        :param group_id:
          Group ids to look for. Given a group_id, only memberships in the
          specified groups will be returned. This is useful for answering
          questions like 'give a list of all members of group <bla>'. See also
          L{indirect_members}.

        :type spread: int or SpreadCode or sequence thereof or None.
        :param spread:
          Filter the resulting group list by spread. I.e. only groups with
          specified spread(s) will be returned.

        :type member_id: int or a sequence thereof or None.
        :param member_id:
          The result membership list will be filtered by member_ids - only the
          specified member_ids will be listed. This is useful for answering
          questions like 'give a list of memberships held by <entity_id>'. See
          also L{indirect_members}.

        :type member_type:
          int or an EntityType constant or a sequence thereof or None.
        :param member_type:
          The resulting membership list be filtered by member type - only the
          member entities of the specified type will be returned. This is
          useful for answering questions like 'give me a list of *group*
          members of group <bla>'.

        :type indirect_members: bool
        :param indirect_members:
          This parameter controls how 'deep' a search is performed. If True,
          we recursively expand *all* group_ids matching the rest of the
          filters.

          This filter can and must be combined either with L{group_id} or with
          L{member_id} (but not both).

          When combined with L{group_id}, the search means 'return all
          membership entries where members are direct AND indirect members of
          the specified group_id(s)'.

          When combined with L{member_id}, the search means 'return all
          membership entries where the specified members are direct AND
          indirect members'

          When False, only direct memberships are considered for all filters.

        :type member_spread: int or SpreadCode or sequence thereof or None.
        :param member_spread:
          Filter the resulting membership list by spread. I.e. only members
          with specified spread(s) will be returned.

        :type member_filter_expired: bool
        :param member_filter_expired:
          Filter the resulting membership list by expiration date. If set, do
          NOT return any rows where members have expired (i.e. have
          expire_date in the past relative to the call time).

        :type include_member_entity_name: bool or dict
        :param include_member_entity_name:
          If the members' entity_name should be included in output or not. If
          the value is a dict, it is used as a mapping of what entity_types' of
          namespaces to get the names from, otherwise it uses
          cereconf.ENTITY_TYPE_NAMESPACE.

        :rtype: generator (yielding db-rows with membership information)
        :return:
          A generator that yields successive group_member rows matching all of
          the specified filters.  Each row contains columns:
            - group_id
            - group_name
            - member_type
            - member_id
            - expire_date

          There *may* be other keys, but the caller cannot rely on that; nor
          can the caller assume that any other key will not be revoked at any
          time. expire_date may be None, the rest is always set.

          Note that if L{indirect_members} is specified, the answer may
          contain member_ids that were NOT part of the initial filters. The
          client code invoking search_members() this way should be prepared
          for such an eventuality.

          Note that if L{indirect_members} is specified, the answers may
          contain duplicate member_id keys. The client code interested in
          unique member_ids must filter the result set.
        """

        # first of all, a help function to help us look for recursive
        # memberships...
        def search_transitive_closure(start_id_set, searcher, field):
            """Collect the transitive closure of L{ids} by using the search
            strategy specified by L{searcher}.

            L{searcher} is simply a tailored self.search()-call with
            indirect_members=False.

            L{field} is the key to extract from db-rows returned by the
            L{searcher}. Occasionally we need group_id and other times
            member_id. These are the two permissible values.
            """
            result = set()
            if isinstance(start_id_set, (tuple, set, list)):
                workset = set(start_id_set)
            else:
                workset = set((start_id_set,))

            while workset:
                new_set = set([x[field] for x in searcher(workset)])
                result.update(workset)
                workset = new_set.difference(result)

            return result
        # end search_transitive_closure

        # ... then a slight sanity check. We cannot allow a combination of
        # group and member id filters combined with indirect_members (what
        # kind of meaning can be attached to specifying all three?)
        if indirect_members:
            assert not (group_id and member_id), "Illegal API usage"
            assert group_id or member_id, "Illegal API usage"

        # ... and finally, let's generate the SQL statements for all the
        # filters.

        # IVR 2008-06-12 FIXME: Unfortunately, expire_date tests are not
        # exactly pretty, to put it mildly. There are 2 tables, and we want to
        # outer join on their union. *That* is hopeless (performancewise), so
        # we take the outer joins in turn. It is not exactly pretty either,
        # but at least it is feasible.
        #
        # Once the EntityExpire module is merged in and in production, all
        # this junk can be simplified. Before modifying the expressions, make
        # sure that the the queries actually work on multiple backends.
        select = [
            "tmp1.group_id AS group_id",
            "tmp1.entity_name AS group_name",
            "tmp1.member_type AS member_type",
            "tmp1.member_id AS member_id",
        ]

        # We always grab the expiration dates, but we filter on them ONLY if
        # member_filter_expired is set.
        tables = [
            """
            ( SELECT
                gm.*,
                en.entity_name as entity_name,
                ai.expire_date as expire1
              FROM [:table schema=cerebrum name=group_member] gm
              LEFT OUTER JOIN [:table schema=cerebrum name=entity_name] en
              ON (en.entity_id = gm.group_id AND en.value_domain = :vdomain)
              LEFT OUTER JOIN [:table schema=cerebrum name=account_info] ai
              ON ai.account_id = gm.member_id
            ) AS tmp1
            LEFT OUTER JOIN [:table schema=cerebrum name=group_info] gi
            ON gi.group_id = tmp1.member_id
            """,
        ]

        binds = {"vdomain": int(self.const.group_namespace)}
        where = list()

        if group_id is not None:
            if indirect_members:
                # expand group_id to include all direct and indirect *group*
                # members of the initial set of group ids. This way we get
                # *all* indirect non-group members
                group_id = search_transitive_closure(
                    group_id,
                    lambda ids: self.search_members(
                        group_id=ids,
                        indirect_members=False,
                        member_type=self.const.entity_group,
                        member_filter_expired=False),
                    "member_id")
                indirect_members = False

            where.append(
                argument_to_sql(
                    group_id,
                    "tmp1.group_id",
                    binds,
                    int))

        if spread is not None:
            tables.append(
                """
                  JOIN [:table schema=cerebrum name=entity_spread] es2
                  ON (tmp1.group_id = es2.entity_id AND {spreads})
                """.format(spreads=argument_to_sql(spread, "es2.spread", binds,
                                                   int)))

        if member_id is not None:
            if indirect_members:
                # expand member_id to include all direct and indirect *parent*
                # groups of the initial set of member ids. This way, we reach
                # *all* parent groups starting from a given set of direct
                # members.
                member_id = search_transitive_closure(
                    member_id,
                    lambda ids: self.search(member_id=ids,
                                            indirect_members=False,
                                            filter_expired=False),
                    "group_id")
                indirect_members = False

            where.append(
                argument_to_sql(
                    member_id,
                    "tmp1.member_id",
                    binds,
                    int))

        if member_type is not None:
            where.append(
                argument_to_sql(member_type, "tmp1.member_type", binds, int))

        if member_spread is not None:
            tables.append(
                """
                  JOIN [:table schema=cerebrum name=entity_spread] es
                  ON (tmp1.member_id = es.entity_id AND {spreads})
                """.format(spreads=argument_to_sql(member_spread, "es.spread",
                                                   binds, int)))

        if member_filter_expired:
            where.append(
                """
                  (tmp1.expire1 IS NULL OR tmp1.expire1 > [:now]) AND
                  (gi.expire_date IS NULL OR gi.expire_date > [:now])
                """)

        if include_member_entity_name:
            if isinstance(include_member_entity_name, dict):
                namespaces = include_member_entity_name
            else:
                namespaces = dict(
                    (self.const.EntityType(k), self.const.ValueDomain(v))
                    for k, v in cereconf.ENTITY_TYPE_NAMESPACE.items())
            case = []
            for i, (e_type, vdomain) in enumerate(namespaces.items()):
                e_type_name = "e_type{:d}".format(i)
                vdomain_name = "vdomain{:d}".format(i)
                case.append(
                    """
                      WHEN tmp1.member_type=:{bind} THEN :{domain}
                    """.format(
                        bind=e_type_name,
                        domain=vdomain_name))
                binds.update({
                    e_type_name: e_type,
                    vdomain_name: vdomain,
                })
            select.append("mn.entity_name AS member_name")
            tables.append(
                """
                  LEFT OUTER JOIN [:table schema=cerebrum name=entity_name] mn
                  ON tmp1.member_id = mn.entity_id
                  AND mn.value_domain = CASE
                  {cases}
                  END
                """.format(cases="\n".join(case)))

        if group_type is not None:
            tables.append(
                """
                  LEFT OUTER JOIN [:table schema=cerebrum name=group_info] grp
                  ON tmp1.group_id = grp.group_id
                """
            )
            where.append(
                argument_to_sql(group_type, "grp.group_type", binds, int))

        query_str = """
          SELECT DISTINCT {columns}
          FROM {tables}
          {where}
        """.format(
            columns=', '.join(select),
            tables=' '.join(tables),
            where=('WHERE ' + ' AND '.join(where)) if where else '',
        )

        return self.query(query_str, binds)

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.group_name
        return '<unbound group>'

    def get_owned_accounts(self, filter_expired=True):
        """Get accounts owned by a group

        :param filter_expired: see list_accounts_by_owner_id method
        :return: list of db.rows with account ids
        """
        acc = Utils.Factory.get('Account')(self._db)
        return acc.list_accounts_by_owner_id(
            self.entity_id,
            owner_type=self.const.entity_group,
            filter_expired=filter_expired
        )

    def is_account_owner(self):
        """Check if the group owns any accounts

        :return: True if owner of at least one account, False if not
        """
        return bool(self.get_owned_accounts())

    def get_adminless_groups(self):
        """Returns a list of all groups that lacks an admin"""
        stmt = """
        SELECT group_id FROM group_info
        WHERE group_id NOT IN
          (
            SELECT group_id FROM group_admin
          )
        """
        return self.query(stmt)

    def get_moderatorless_groups(self):
        """Returns a list of all groups that lacks a moderator"""
        stmt = """
        SELECT group_id FROM group_info
        WHERE group_id NOT IN
          (
            SELECT group_id FROM group_moderator
          )
        """
        return self.query(stmt)

    def get_group_admins(self, group_id=None):
        binds = {'group_id': group_id}
        """Returns a list of all admins of a group"""
        stmt = """
        SELECT * FROM group_admin WHERE group_id=:group_id
        """
        return self.query(stmt, binds)

    def get_group_moderators(self, group_id=None):
        binds = {'group_id': group_id}
        """Returns a list of all moderators of a group"""
        stmt = """
        SELECT * FROM group_moderator WHERE group_id=:group_id
        """
        return self.query(stmt, binds)


class GroupRolesMixin(BaseGroup):
    def delete(self):
        # Empty this group's set of admins and moderators
        GroupRoles.remove_all(GroupRoles(self._db), self.entity_id)
        super(GroupRolesMixin, self).delete()


class Group(GroupRolesMixin, BaseGroup):
    pass
