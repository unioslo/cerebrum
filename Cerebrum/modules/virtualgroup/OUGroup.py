# -*- coding: utf-8 -*-
#
# Copyright 2016-2019 University of Oslo, Norway
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
Virtual groups based on the OU structure
=========================================

Use: Add OUGroup to the CLASS_GROUP and OUGroupConstants to CLASS_CLCONSTANTS

General design
---------------

We use the tables

* person_affiliation_source
* account_type
* ou_info

In general, an OUGroup is defined by

* OU,
* perspective,
* affiliation,
* source, and
* status.

The general idea is to have a relation ou_group with a one-to-many
mapping with another relation containing person affiliation code,
and affiliation status code.

Listing the group members will become a search for matching rows in
person_aff_source. Groups may be recursive in two ways: Meta groups,
and expanded. If meta group, we will look for other groups with identical
information, but with certain other OUs (looking at OU perspective).
Expanded groups are listed by taking all persons in OU or sub OU.

Person aff source
--------------------

:person_id: Person
:ou_id: OU
:affiliation: aff (PersonAffiliationCode)
:source_system: source
:status: status (PersonAffStatusCode)

"""

import collections
from Cerebrum.Utils import argument_to_sql, Factory, prepare_string
from .Group import VirtualGroup, populator
from Cerebrum.Entity import Entity
from Cerebrum.Person import Person
from Cerebrum.Account import Account
from Cerebrum.Errors import NotFoundError


__version__ = "1.0"  # mod_virtualgroup_ou


class OUGroup(VirtualGroup):
    """Virtual group based on the OUs

    All virtual groups are defined by a ou_id, connected to the ou_structure.
    Members of the group are those having an affiliation.

    Affiliations are defined by

    * affiliation code
    * affiliation status code
    * authoritative system code

    If one or more is NULL, then it means *any*.

    Virtual groups can be recursive:

    * nonrecursive: only members with direct affiliation in OU
    * recursive: Members with affiliation in OU, and matching virtual
                 groups in sub-OU
    * flattened: Members with affiliation in OU or sub-OU.

    The latter two needs a perspective code to be set.

    Finally a member type exists:
    * person: The persons with affs are members
    * primary: The primary account of the persons are listed
    * accounts: All accounts with corresponding account_types
                are listed (if the owner has correct affs)
    """
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('ou_id', 'affiliation', 'affiliation_source',
                      'affiliation_status', 'recursion', 'ou_perspective',
                      'member_type')

    def find(self, group_id):
        """Connect object to group with ``group_id`` in database."""
        super(OUGroup, self).find(group_id)
        if self.virtual_group_type != self.const.vg_ougroup:
            self.__in_db = False
            self.__updated = []
            return
        (self.ou_id, self.affiliation, self.affiliation_source,
         self.affiliation_status, self.recursion, self.ou_perspective,
         self.member_type) = \
            self.query_1("""
        SELECT vgo.ou_id, vgo.affiliation, vgo.affiliation_source,
               vgo.affiliation_status, vgo.recursion, vgo.ou_perspective,
               vgo.member_type
        FROM [:table schema=cerebrum name=virtual_group_ou] vgo
        LEFT OUTER JOIN
             [:table schema=cerebrum name=entity_name] en
        ON
          vgo.group_id = en.entity_id AND
          en.value_domain = :domain
        WHERE
          vgo.group_id=:g_id""",
                         {'g_id': group_id,
                          'domain': int(self.const.group_namespace)})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def clear(self):
        super(OUGroup, self).clear()
        self.clear_class(OUGroup)
        self.__updated = []

    @populator('ougroup', 'virtual_ou_group')
    def populate_virtual_ou_group(self,
                                  ou_id=None,
                                  affiliation=None,
                                  affiliation_source=None,
                                  affiliation_status=None,
                                  recursion=None,
                                  ou_perspective=None,
                                  member_type=None,
                                  *rest, **kw):
        """Populate this virtual group instance"""
        if ou_id is None:
            raise RuntimeError("OU group without ou_id")
        if not (affiliation or affiliation_source or affiliation_status):
            raise RuntimeError("Must have at least one affiliation matcher")
        if not ou_perspective:
            if recursion in (self.const.virtual_group_ou_recursive,
                             self.const.virtual_group_ou_flattened):
                raise RuntimeError("Must have perspective when not flat")
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times")
        except AttributeError:
            self.__in_db = False
        self.ou_id = ou_id
        self.affiliation = affiliation
        self.affiliation_source = affiliation_source
        self.affiliation_status = affiliation_status
        self.recursion = recursion
        self.ou_perspective = ou_perspective
        self.member_type = member_type

    def delete(self):
        """Delete virtual group"""
        if self.__in_db:
            self.execute("""
                DELETE FROM [:table schema=cerebrum name=virtual_group_ou]
                WHERE group_id = :group_id""",
                         {'group_id': self.entity_id})
        super(OUGroup, self).delete()

    def __eq__(self, other):
        assert isinstance(other, VirtualGroup)
        if (getattr(self, 'virtual_group_type', None) !=
                self.const.vg_ougroup):
            return super(OUGroup, self).__eq__(other)
        if (getattr(other, 'virtual_group_type', None) ==
                self.const.vg_ougroup
                and self.ou_id == other.ou_id
                and self.affiliation == other.affiliation
                and self.affiliation_status == other.affiliation_status
                and self.affiliation_source == other.affiliation_source
                and self.recursion == other.recursion
                and self.ou_perspective == other.ou_perspective
                and self.member_type == other.member_type):
            return super(OUGroup, self).__eq__(other)
        return False

    def write_db(self):
        super(OUGroup, self).write_db()
        if self.virtual_group_type != self.const.vg_ougroup:
            return
        try:
            is_new = not self.__in_db
        except AttributeError:
            return
        if not self.__updated:
            return
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=virtual_group_ou]
                         (group_id, ou_id,
                          affiliation, affiliation_status, affiliation_source,
                          recursion, ou_perspective, member_type)
            VALUES (:group_id, :ou_id, :affiliation, :affiliation_status,
                    :affiliation_source, :recursion, :ou_perspective,
                    :member_type)""",
                         {'group_id': self.entity_id,
                          'ou_id': self.ou_id,
                          'affiliation': self.affiliation,
                          'affiliation_status': self.affiliation_status,
                          'affiliation_source': self.affiliation_source,
                          'recursion': self.recursion,
                          'ou_perspective': self.ou_perspective,
                          'member_type': self.member_type})
            for member in self.list_members(self.entity_id, indirect=False):
                self._db.log_change(self.entity_id,
                                    self.clconst.group_add,
                                    member['member_id'])
        else:
            args = dict(zip(self.__updated,
                            [getattr(self, x) for x in self.__updated]))
            args['group_id'] = self.entity_id
            self.execute("""
            UPDATE [:table schema=cerebrum name=virtual_group_ou]
                         SET {}
            WHERE group_id = :group_id""".format(" ,".join(
                ["{arg} = :{arg}".format(arg=x) for x in self.__updated])),
                args)
        del self.__in_db
        self.__in_db = True
        self.__updated = []

    def has_member(self, member_id):
        if self.virtual_group_type == self.const.vg_ougroup:
            return list(self.list_members(self.entity_id,
                                          filter_members=member_id))
        return super(OUGroup, self).has_member(member_id)

    def convert(self,
                virtual_group_type='ougroup',
                ou_id=None,
                affiliation=None,
                affiliation_source=None,
                affiliation_status=None,
                recursion=None,
                ou_perspective=None,
                member_type=None):
        """ Upgrade an existing standard group to ou group """
        try:
            existing_members = super(OUGroup, self).search_members(
                self.entity_id)
        except NotFoundError:
            pass
        if existing_members:
            RuntimeError("Group {} has members; can't convert"
                         .format(self.group_name))

        super(OUGroup, self).convert(virtual_group_type)
        self.ou_id = ou_id
        self.affiliation = affiliation
        self.affiliation_source = affiliation_source
        self.affiliation_status = affiliation_status
        self.recursion = recursion
        self.ou_perspective = ou_perspective
        self.member_type = member_type

    def search(self,
               group_id=None,
               member_id=None,
               indirect_members=False,
               spread=None,
               name=None,
               group_type=None,
               description=None,
               filter_expired=True,
               creator_id=None,
               expired_only=False):
        """Search for ou groups.
        See Group.search for parameter definitions.
        """
        # Sanity check: if indirect members is specified, then at least we
        # need one id to go on.
        if indirect_members:
            assert member_id is not None
            if isinstance(member_id, (list, tuple, set)):
                assert member_id

        # Sanity check: it is probably a bad idea to allow specifying both.
        assert not (member_id and group_id)

        ret = super(OUGroup, self).search(
            group_id=group_id,
            member_id=member_id,
            indirect_members=indirect_members,
            spread=spread,
            name=name,
            group_type=group_type,
            description=description,
            filter_expired=filter_expired,
            creator_id=creator_id,
            expired_only=expired_only)

        if member_id is None:
            return ret

        def get_entity_type(entity_id):
            ent = Entity(self._db)
            ent.find(entity_id)
            return ent.entity_type

        def get_group_type(entity_id):
            try:
                return self.query_1(
                    """SELECT virtual_group_type FROM
                    [:table schema=cerebrum name=virtual_group_info]
                    WHERE group_id = :gid""", {'gid': entity_id})
            except NotFoundError:
                return self.const.vg_normal_group

        def get_ou_perspective(entity_id):
            return self.query_1(
                """SELECT ou_perspective FROM
                    [:table schema=cerebrum name=virtual_group_ou]
                    WHERE group_id = :gid""", {'gid': entity_id})

        binds = {
            'vdomain': self.const.group_namespace
        }
        wheres = []
        tables = []

        if group_id is not None:
            filter_groups = []
            if isinstance(group_id, collections.Iterable):
                for gid in group_id:
                    if get_group_type(gid) == self.const.vg_ougroup:
                        filter_groups.append(gid)
            elif get_group_type(gid) == self.const.vg_ougroup:
                filter_groups.append(gid)
            if not filter_groups:
                return ret
            wheres.append(argument_to_sql(filter_groups, 'group_id', binds,
                                          int))

        objs = {}
        affected_groups = set()

        def fget(name):
            ret = objs.get(name)
            if ret is None:
                ret = Factory.get(name)(self._db)
                objs[name] = ret
            return ret

        def handle_person(mid, mtype=self.const.virtual_group_ou_person):
            # nonlocal ftw!
            pe = fget('Person')
            for row in pe.list_affiliations(person_id=mid,
                                            include_deleted=False):
                affected_groups.update(
                    map(lambda x: x['group_id'],
                        self.list_ou_groups_for(
                            affiliation=row['affiliation'],
                            status=row['status'],
                            ou_id=row['ou_id'],
                            member_types=mtype,
                            source=row['source_system'],
                            indirect=indirect_members)))

        def handle_account(mid):
            ac = fget('Account')
            pe = fget('Person')
            ac.find(mid)
            for row in ac.get_account_types():
                affected_groups.update(
                    map(lambda x: x['group_id'],
                        self.list_ou_groups_for(
                            affiliation=row['affiliation'],
                            ou_id=row['ou_id'],
                            member_types=self.const.
                            virtual_group_ou_accounts,
                            indirect=indirect_members)))
            try:
                pe.find(ac.owner_id)
                if ac.entity_id == pe.get_primary_account():
                    handle_person(ac.owner_id,
                                  self.const.virtual_group_ou_primary)
            except Exception:
                pass
            pe.clear()
            ac.clear()

        def handle_virtual_group(mid):
            gr = fget('Group')
            gr.find(mid)
            if (gr.virtual_group_type == self.const.vg_ougroup and
                    gr.recursion == self.const.virtual_group_ou_recursive):
                affected_groups.update(
                    [x['group_id'] for x in self.list_ou_groups_for(
                        affiliation=gr.affiliation,
                        status=gr.affiliation_status,
                        ou_id=gr.ou_id,
                        member_types=gr.member_type,
                        source=gr.affiliation_source)
                        if get_ou_perspective(x['group_id']) ==
                        gr.ou_perspective])
            gr.clear()
        dp = {
            self.const.entity_person: handle_person,
            self.const.entity_account: handle_account,
            self.const.entity_group: handle_virtual_group,
        }
        if not isinstance(member_id, collections.Iterable):
            member_id = [member_id]

        for mid in member_id:
            et = get_entity_type(mid)
            if et in dp:
                dp[et](mid)

        affected_groups.difference_update(member_id)
        if not affected_groups:
            return ret
        if affected_groups and indirect_members:
            ret.extend(super(OUGroup, self).search(
                group_id=group_id,
                member_id=affected_groups,
                indirect_members=indirect_members,
                spread=spread,
                description=description,
                filter_expired=filter_expired,
                creator_id=creator_id,
                expired_only=expired_only))
            return ret

        wheres.append(argument_to_sql(affected_groups, 'group_id', binds, int))
        if spread:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            wheres.append("gi.group_id = es.entity_id")
            wheres.append(argument_to_sql(spread, 'es.spread', binds, int))

        if name is not None:
            name = prepare_string(name)
            wheres.append("(LOWER(en.entity_name) LIKE :name)")
            binds["name"] = name

        if description is not None:
            description = prepare_string(description)
            wheres.append("(LOWER(gi.description) LIKE :description)")
            binds["description"] = description

        if filter_expired:
            wheres.append(
                "(gi.expire_date IS NULL OR gi.expire_date > [:now])")

        if creator_id is not None:
            wheres.append(
                argument_to_sql(creator_id, "gi.creator_id", binds, int))

        if expired_only:
            wheres.append(
                "(gi.expire_date IS NOT NULL AND gi.expire_date < [:now])")

        where_str = ""
        if wheres:
            where_str = "WHERE " + " AND ".join(wheres)

        tables_str = ""
        if tables:
            tables_str = ", " + ", ".join(tables)

        query = """SELECT DISTINCT gi.group_id AS group_id,
                                   en.entity_name AS name,
                                   gi.description AS description,
                                   gi.visibility AS visibility,
                                   gi.creator_id AS creator_id,
                                   ei.created_at AS created_at,
                                   gi.expire_date AS expire_date
                FROM [:table schema=cerebrum name=group_info] gi
                LEFT OUTER JOIN
                     [:table schema=cerebrum name=entity_name] en
                ON
                    en.entity_id = gi.group_id AND en.value_domain = :vdomain
                LEFT OUTER JOIN
                     [:table schema=cerebrum name=entity_info] ei
                ON
                    ei.entity_id = gi.group_id
                {tables}
                {where}
                    """.format(tables=tables_str, where=where_str)
        ret.extend(self.query(query, binds, fetchall=True))
        return ret

    def list_ou_groups_for(self, ou_id, affiliation=None, status=None,
                           source=None, member_types=None, indirect=True):
        """List matching OU groups.
        All params match members of virtual_group_ou, except
        :type indirect: bool
        :param indirect: Follow indirection (for recursive groups)
        :return: List of dbrows with group_id
        """
        wheres = []
        binds = {
            'rec_recursive': self.const.virtual_group_ou_recursive,
            'rec_flat': self.const.virtual_group_ou_flattened,
            'rec_no': self.const.virtual_group_ou_nonrecursive,
            'ou_id': ou_id
        }
        if affiliation:
            wheres.append("(affiliation IS NULL OR {})".format(
                argument_to_sql(affiliation, 'vgo.affiliation', binds, int)))
        if status:
            wheres.append("(affiliation_status IS NULL OR {})".format(
                argument_to_sql(status, 'vgo.affiliation_status', binds, int)))
        if source:
            wheres.append("(affiliation_source IS NULL OR {})".format(
                argument_to_sql(source, 'vgo.affiliation_source',
                                binds, int)))
        if member_types:
            wheres.append(argument_to_sql(member_types, 'vgo.member_type',
                                          binds, int))
        if wheres:
            wheres = 'AND ' + ' AND '.join(wheres)
        else:
            wheres = ''

        if indirect:
            indirect = """
            UNION
            SELECT op.*, vgo.*
            FROM ou_structure op, virtual_group_ou vgo, ous
            WHERE op.ou_id = ous.parent_id and vgo.ou_id = op.ou_id and
              op.perspective = vgo.ou_perspective and
              vgo.recursion = ous.recursion and
              (vgo.affiliation is null and ous.affiliation is null or
               vgo.affiliation = ous.affiliation) and
              (vgo.affiliation_status is null and ous.affiliation_status is null
               or vgo.affiliation_status = ous.affiliation_status) and
              vgo.member_type = ous.member_type
            """
        else:
            indirect = ''

        return self.query("""
        WITH RECURSIVE ous AS (
        SELECT op.*, vgo.*
        FROM ou_structure op, virtual_group_ou vgo
        WHERE op.ou_id = :ou_id and vgo.ou_id = op.ou_id and
              op.perspective = vgo.ou_perspective
              and recursion = :rec_recursive
              {wheres}
              {indirect}),
        ous_flat AS (
        SELECT op.*
        FROM ou_structure op
        WHERE ou_id = :ou_id
        UNION
        SELECT op.*
        FROM ous LEFT JOIN ou_structure op ON ous.parent_id = op.ou_id
        AND ous.perspective = op.perspective)

        SELECT group_id
        FROM ous

        UNION

        SELECT group_id
        FROM virtual_group_ou vgo, ous_flat of
        WHERE vgo.ou_id = of.ou_id AND recursion = :rec_flat {wheres}

        UNION

        SELECT group_id
        FROM virtual_group_ou vgo
        WHERE ou_id = :ou_id AND recursion = :rec_no {wheres}
        """.format(wheres=wheres, indirect=indirect), binds)

    def list_members(self, group_id, indirect=False, spread=None,
                     member_spread=None, member_names=False,
                     filter_members=None):
        """Group API list_members.

        See Group.list_members for parameter definitions"""

        spread = None
        if spread:
            binds = {'id': group_id}
            res = self.query("""SELECT *
                             FROM [:table schema=cerebrum name=entity_spread]
                             WHERE entity_id = :id AND {}"""
                             .format(argument_to_sql(spread, 'spread', binds,
                                                     int)),
                             binds)
            if not res:
                return []
        grow = self.query_1("""
            SELECT vgi.*, gn.entity_name, ou_perspective,
                    affiliation, affiliation_source,
                    affiliation_status, recursion, ou_id,
                    member_type
            FROM [:table schema=cerebrum name=virtual_group_ou] vgo
            LEFT JOIN [:table schema=cerebrum name=entity_name] gn
                      ON vgo.group_id = gn.entity_id
            LEFT JOIN group_info vgi
                      ON vgo.group_id = vgi.group_id
            WHERE vgo.group_id = :id""", {'id': group_id})
        rec = grow['recursion']
        recursive = ''
        ous = ''
        extra_sql = ''
        qparams = {
            'group_name': grow['entity_name'],
            'description': grow['description'],
            'expire_date': grow['expire_date'],
            'creator_id': grow['creator_id'],
            'group_id': grow['group_id'],
            'perspective': grow['ou_perspective'],
            'ou_id': grow['ou_id'],
            'affiliation': grow['affiliation'],
            'affiliation_source': grow['affiliation_source'],
            'affsource': grow['affiliation_source'],
            'affiliation_status': grow['affiliation_status'],
            'affstatus': grow['affiliation_status'],
            'recursion': rec,
        }
        group_fields = []
        extra_where = []
        extra_tables = []
        # the indirect flag will only carry meaning for recursive groups,
        # if true, we will list out subgroups, else include sub groups,
        # thus creating a meta group feeling.
        if rec == self.const.virtual_group_ou_recursive:
            if indirect:
                # List all ou groups matching this, and add their
                # members recursively
                if spread:
                    s = ', [:table schema=cerebrum name=entity_spread] oes'
                    extra_where.extend([argument_to_sql(spread, 'oes.spread',
                                                        qparams, int),
                                        'oes.entity_id = vgo.group_id'])
                else:
                    s = ''
                ous = """
                UNION SELECT op.ou_id, op.perspective, op.parent_id,
                             vgo.group_id
                      FROM ous, [:table schema=cerebrum name=ou_structure] op,
                      [:table schema=cerebrum name=virtual_group_ou] vgo
                      {spread}
                WHERE
                     op.parent_id = ous.ou_id
                     AND op.perspective = :perspective
                     AND ous.perspective = vgo.ou_perspective
                     AND op.ou_id = vgo.ou_id
                     AND vgo.member_type = :memtype
                     AND vgo.recursion = :recursion
                     AND {{ous_where}}
                """.format(spread=s)
                recursive = 'RECURSIVE'
            else:
                extra_sql = """
                UNION
                SELECT {extra_sql_fields}
                FROM virtual_group_ou vgo LEFT JOIN ou_structure op
                     ON vgo.ou_id = op.ou_id AND
                     vgo.ou_perspective = op.perspective
                     {extra_tables}
                WHERE op.parent_id = :ou_id AND
                      vgo.recursion = :recursion AND
                      vgo.member_type = :memtype AND
                {extra_sql_where}
                """
                group_fields = [':group_id as group_id',
                                ':group_name as group_name',
                                ':description as description',
                                ':group_member_type as member_type',
                                ':expire_date as expire2',
                                ':creator_id as creator_id',
                                'NULL as expire_date',
                                'vgo.ou_id as ou_id',
                                'vgo.group_id as member_id',
                                ]
                qparams['group_member_type'] = self.const.entity_group
        elif rec == self.const.virtual_group_ou_flattened:
            recursive = 'RECURSIVE'
            ous = """
                UNION SELECT op.ou_id, op.perspective, op.parent_id,
                             :group_id
                FROM ou_structure op, ous
                WHERE op.parent_id = ous.ou_id AND op.perspective =
                ous.perspective"""

        tables = ['ous',
                  '[:table schema=cerebrum name=virtual_group_ou] vg '
                  'LEFT JOIN [:table schema=cerebrum name=entity_name] vgn '
                  'ON vg.group_id = vgn.entity_id '
                  'LEFT JOIN entity_quarantine eq '
                  'ON vg.ou_id=eq.entity_id']
        fields = ['ous.group_id as group_id',
                  'vgn.entity_name as group_name',
                  ':description as description',
                  ':member_type as member_type',
                  ':expire_date as expire2',
                  ':creator_id as creator_id',
                  ':expire_date as expire_date',
                  'ous.ou_id as ou_id']
        wheres = ['ous.ou_id = vg.ou_id',
                  '(eq.entity_id IS NULL OR '
                  'eq.start_date > [:now] OR '
                  'eq.end_date <= [:now])']

        mt = grow['member_type']
        if mt in (self.const.virtual_group_ou_person,
                  self.const.virtual_group_ou_primary):
            tables.extend(['[:table schema=cerebrum '
                           'name=person_affiliation_source] pas'])
            if grow['affiliation']:
                wheres.extend(['pas.affiliation = :affiliation',
                               'pas.affiliation = vg.affiliation'])
                extra_where.append('vgo.affiliation = :affiliation')
            else:
                extra_where.append('vgo.affiliation IS NULL')
            if grow['affiliation_status']:
                wheres.extend(['pas.status = :affiliation_status',
                               'pas.status = vg.affiliation_status'])
                extra_where.append('vgo.affiliation_status = '
                                   ':affiliation_status')
            else:
                extra_where.append('vgo.affiliation_status IS NULL')
            if grow['affiliation_source']:
                wheres.extend(['pas.source_system = :affsource',
                               'pas.source_system = vg.affiliation_source'])
                extra_where.append('vgo.affiliation_source = '
                                   ':affsource')
            else:
                extra_where.append('vgo.affiliation_source IS NULL')

            wheres.extend(['pas.ou_id = ous.ou_id',
                           '(pas.deleted_date IS NULL '
                           'OR pas.deleted_date > [:now])'])
        if mt == self.const.virtual_group_ou_person:
            memtype = self.const.entity_person
            memid = 'pas.person_id'
        elif mt == self.const.virtual_group_ou_primary:
            memtype = self.const.entity_account
            memid = """
            (SELECT ai.account_id as member_id
            FROM [:table schema=cerebrum name=account_type] at
            LEFT JOIN [:table schema=cerebrum name=account_info] ai
                      USING (account_id)
            WHERE at.person_id = pas.person_id AND
                  (ai.expire_date IS NULL OR
                   ai.expire_date > [:now])
            ORDER BY at.priority LIMIT 1)"""
            # memid = 'member.person_id'
        elif mt == self.const.virtual_group_ou_accounts:
            memtype = self.const.entity_account
            tables.extend(['account_type at'])
            memid = 'at.account_id'
            wheres.extend(['at.ou_id = ous.ou_id',
                           'at.affiliation = :affiliation'])
            extra_where.append('vgo.affiliation = :affiliation')

        fields.append('{} AS member_id'.format(memid))
        qparams['member_type'] = memtype
        qparams['memtype'] = mt

        if member_spread:
            tmp = '[:table schema=cerebrum name=entity_spread] mes'
            tables.append(tmp)
            extra_tables.append(tmp)
            tmp = argument_to_sql(member_spread, 'mes.spread', qparams, int)
            wheres.extend(['mes.entity_id = {}'.format(memid), tmp])
            if not indirect and rec == self.const.virtual_group_ou_recursive:
                extra_where.extend(['mes.entity_id = vgo.group_id', tmp])

        if member_names or filter_members:
            tmp = '[:table schema=cerebrum name=entity_name] men'
            tables.append(tmp)
            extra_tables.append(tmp)
            wheres.append('men.entity_id = {}'.format(memid))
            if not indirect and rec == self.const.virtual_group_ou_recursive:
                extra_where.append('men.entity_id = vgo.group_id')
            fields.append('men.entity_name AS member_name')
            group_fields.append('men.entity_name AS member_name')

        if filter_members:
            wheres.append(argument_to_sql(
                filter_members, 'men.entity_id', qparams, int))
            if not indirect and rec == self.const.virtual_group_ou_recursive:
                extra_where.append(argument_to_sql(filter_members,
                                                   'vgo.group_id', qparams,
                                                   int))

        if extra_sql:
            extra_tables_str = ''
            if extra_tables:
                extra_tables_str = ', ' + ', '.join(extra_tables)
            extra_sql = extra_sql.format(
                extra_sql_fields=', '.join(group_fields),
                extra_sql_where=' AND '.join(extra_where),
                extra_tables=extra_tables_str)
        query = """
        WITH {recursive} ous(ou_id, perspective, parent_id, group_id) AS (
        VALUES (CAST(:ou_id as numeric), CAST(:perspective AS numeric),
          CAST(NULL AS numeric), CAST(:group_id as numeric))
          {ous}
        )

        SELECT DISTINCT ON (member_id) {fields}
        FROM {tables}
        WHERE {wheres}
        {extra_sql}
        """.format(recursive=recursive, ous=ous.format(
            ous_where=' AND '.join(extra_where)), fields=', '.join(fields),
            tables=', '.join(tables), wheres=' AND '.join(wheres),
            extra_sql=extra_sql)
        return self.query(query, qparams)

    def search_members(self,
                       group_id=None,
                       spread=None,
                       member_id=None,
                       member_type=None,
                       indirect_members=False,
                       member_spread=None,
                       member_filter_expired=True,
                       include_member_entity_name=False):
        """Group API search members. See Cerebrum.Group.Group.search_members"""
        def get_entity_type(entity_id):
            ent = Entity(self._db)
            ent.find(entity_id)
            return ent.entity_type

        def get_vgtype(entity_id):
            try:
                return self.query_1(
                    """SELECT virtual_group_type FROM
                    [:table schema=cerebrum name=virtual_group_info]
                    WHERE group_id = :gid""", {'gid': entity_id})
            except NotFoundError:
                return self.const.vg_normal_group

        def get_ou_perspective(entity_id):
            return self.query_1(
                """SELECT ou_perspective FROM
                    [:table schema=cerebrum name=virtual_group_ou]
                    WHERE group_id = :gid""", {'gid': entity_id})
        sgroups = None
        dosuper = True
        if group_id:
            if isinstance(group_id, collections.Iterable):
                sgroups = filter(lambda x: get_vgtype(x) !=
                                 self.const.vg_ougroup, group_id)
                group_id = set(group_id)
                group_id.difference_update(sgroups)
                dosuper = sgroups
            else:
                if get_vgtype(group_id) != self.const.vg_ougroup:
                    sgroups = group_id
                    group_id = set()
                else:
                    dosuper = False
                    sgroups = ()
                    group_id = set([group_id])
        if dosuper:
            for entry in super(OUGroup, self).search_members(
                    group_id=sgroups,
                    spread=spread,
                    member_id=member_id,
                    member_type=member_type,
                    indirect_members=indirect_members,
                    member_spread=member_spread,
                    member_filter_expired=member_filter_expired,
                    include_member_entity_name=include_member_entity_name):
                # Py3 yield from ftw!
                yield entry
                if (group_id is not None and indirect_members and
                        entry['member_type'] == self.const.entity_group and
                        get_vgtype(entry['member_id']) ==
                        self.const.vg_ougroup):
                    group_id.add(entry['member_id'])

        # TODO: Don't ignore member type. Since ou groups only have one
        # member type, I have ignored it, but it should be filtered?
        # Member filter expired checks account info for ordinary groups.
        # Always on.

        if member_type is not None and not isinstance(member_type,
                                                      collections.Iterable):
            member_type = (member_type, )

        if indirect_members:
            if group_id is not None:
                if not isinstance(group_id, collections.Iterable):
                    group_id = (group_id, )
                for gid in group_id:
                    for entry in self.list_members(
                            gid, indirect=True,
                            spread=spread,
                            member_names=include_member_entity_name,
                            member_spread=member_spread):
                        if (member_type is None
                                or entry['member_type'] in member_type):
                            yield entry
                return
            else:  # member_id
                # find all groups affected and add as member id
                if not isinstance(member_id, collections.Iterable):
                    member_id = set((member_id, ))
                else:
                    member_id = set(member_id)
                objs = {}
                affected_groups = set()

                def fget(name):
                    ret = objs.get(name)
                    if ret is None:
                        ret = Factory.get(name)(self._db)
                        objs[name] = ret
                    return ret

                def handle_person(mid,
                                  mtype=self.const.virtual_group_ou_person):
                    # nonlocal ftw!
                    pe = fget('Person')
                    for row in pe.list_affiliations(person_id=mid,
                                                    include_deleted=False):
                        affected_groups.update(
                            map(lambda x: x['group_id'],
                                self.list_ou_groups_for(
                                    affiliation=row['affiliation'],
                                    status=row['status'],
                                    ou_id=row['ou_id'],
                                    member_types=mtype,
                                    source=row['source_system'],
                                    indirect=indirect_members)))

                def handle_account(mid):
                    ac = fget('Account')
                    pe = fget('Person')
                    ac.find(mid)
                    for row in ac.get_account_types():
                        affected_groups.update(
                            map(lambda x: x['group_id'],
                                self.list_ou_groups_for(
                                    affiliation=row['affiliation'],
                                    ou_id=row['ou_id'],
                                    member_types=self.const.
                                    virtual_group_ou_accounts,
                                    indirect=indirect_members)))
                    try:
                        pe.find(ac.owner_id)
                        if ac.entity_id == pe.get_primary_account():
                            handle_person(mid,
                                          self.const.virtual_group_ou_primary)
                    except Exception:
                        pass
                    pe.clear()
                    ac.clear()

                def handle_virtual_group(mid):
                    gr = fget('Group')
                    gr.find(mid)
                    if (gr.virtual_group_type == self.const.vg_ougroup and
                            gr.recursion ==
                            self.const.virtual_group_ou_recursive):
                        affected_groups.update(
                            [x['group_id'] for x in self.list_ou_groups_for(
                                affiliation=gr.affiliation,
                                status=gr.affiliation_status,
                                ou_id=gr.ou_id,
                                member_types=gr.member_type,
                                source=gr.affiliation_source)
                                if get_ou_perspective(x['group_id']) ==
                                gr.ou_perspective
                                and x['group_id'] not in member_id])
                dp = {
                    self.const.entity_person: handle_person,
                    self.const.entity_account: handle_account,
                    self.const.entity_group: handle_virtual_group,
                }
                for mid in member_id:
                    et = get_entity_type(mid)
                    if et in dp:
                        dp[et](mid)

                if affected_groups:
                    tmp = include_member_entity_name
                    for entry in super(OUGroup, self).search_members(
                            spread=spread,
                            member_id=affected_groups,
                            member_type=member_type,
                            indirect_members=indirect_members,
                            member_spread=member_spread,
                            member_filter_expired=member_filter_expired,
                            include_member_entity_name=tmp):
                        # Py3 yield from ftw!
                        yield entry
                group_id = affected_groups
        if group_id is not None:
            # list direct members of group
            if not isinstance(group_id, collections.Iterable):
                group_id = (group_id, )
            for gid in group_id:
                for entry in self.list_members(
                        gid,
                        spread=spread,
                        filter_members=member_id,
                        member_names=include_member_entity_name,
                        member_spread=member_spread):
                    if (member_type is None
                            or entry['member_type'] in member_type):
                        yield entry
            return

    def get_extensions(self):
        exts = super(OUGroup, self).get_extensions()
        if self.virtual_group_type == self.const.vg_ougroup:
            return exts + ['OUGroup']
        else:
            return exts


class PersonOuGroup(Person):
    """Update affiliation changes with group membership changes."""
    def add_affiliation(self, ou_id, affiliation, source, status,
                        deleted_date=None, precedence=None):
        """Add or update affiliation"""
        c, s, p = super(PersonOuGroup, self).add_affiliation(ou_id,
                                                             affiliation,
                                                             source,
                                                             status,
                                                             deleted_date,
                                                             precedence)
        if c:
            gr = Factory.get('Group')(self._db)
            myid = self.entity_id
            pertyp = self.const.virtual_group_ou_person
            acctyp = self.const.virtual_group_ou_primary
            new = gr.list_ou_groups_for(
                ou_id=ou_id, affiliation=affiliation, status=status,
                source=source, member_types=pertyp, indirect=False)
            new = set((x['group_id'] for x in new))
            try:
                ac = self.get_primary_account()
                anew = gr.list_ou_groups_for(
                    ou_id=ou_id, affiliation=affiliation, status=status,
                    source=source, member_types=acctyp, indirect=False)
                anew = set((x['group_id'] for x in anew))
            except Exception:
                ac = None
                anew = set()
            if c == 'add':
                adds = new
                aadds = anew
                rems = arems = ()
            elif c == 'mod' and s != status:
                old = gr.list_ou_groups_for(
                    ou_id=ou_id, affiliation=affiliation, status=status,
                    source=source, member_types=pertyp, indirect=False)
                old = set((x['group_id'] for x in old))
                adds = new - old
                rems = old - new
                if ac:
                    aold = gr.list_ou_groups_for(
                        ou_id=ou_id, affiliation=affiliation, status=status,
                        source=source, member_types=acctyp, indirect=False)
                    aold = set((x['group_id'] for x in aold))
                    aadds = anew - aold
                    arems = aold - anew
                else:
                    aadds = arems = ()
            else:
                return c, s, p
            for i in adds:
                self._db.log_change(i, self.clconst.group_add, myid)
            for i in aadds:
                self._db.log_change(i, self.clconst.group_add, ac)
            for i in rems:
                self._db.log_change(i, self.clconst.group_rem, myid)
            for i in arems:
                self._db.log_change(i, self.clconst.group_rem, ac)
        return c, s, p

    def __delete_affiliation(self, ou_id, affiliation, source, status):
        """Register group_rem for deleted aff"""
        myid = self.entity_id
        gr = Factory.get('Group')(self._db)
        for row in gr.list_ou_groups_for(
                ou_id=ou_id, affiliation=affiliation, status=status,
                source=source, indirect=False,
                member_types=self.const.virtual_group_ou_person):
            self._db.log_change(row['group_id'], self.clconst.group_rem, myid)

        for row in gr.list_ou_groups_for(
                ou_id=ou_id, affiliation=affiliation, status=status,
                source=source, indirect=False,
                member_types=self.const.virtual_group_ou_person):
            self._db.log_change(row['group_id'], self.clconst.group_rem, myid)
        try:
            myid = self.get_primary_account()
            for row in gr.list_ou_groups_for(
                    ou_id=ou_id, affiliation=affiliation, status=status,
                    source=source, indirect=False,
                    member_types=self.const.virtual_group_ou_primary):
                self._db.log_change(row['group_id'],
                                    self.clconst.group_rem,
                                    myid)
        except Exception:
            pass

    def delete_affiliation(self, ou_id, affiliation, source):
        """Remove member from virtual groups"""
        status, deleted = self.query_1(
            """SELECT status, deleted
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE person_id = :pid AND ou_id = :ou AND affiliation = :aff
                  AND source_system = :src""",
            {'pid': self.entity_id, 'ou': ou_id, 'aff': affiliation,
             'src': source})
        super(PersonOuGroup, self).delete_affiliation(ou_id, affiliation,
                                                      source)
        if deleted is None:
            self.__delete_affiliation(ou_id, affiliation, source, status)

    def nuke_affiliation(self, ou_id, affiliation, source, status):
        """Remove member from virtual groups"""
        super(PersonOuGroup, self).nuke_affiliation(ou_id, affiliation,
                                                    source, status)
        self.__delete_affiliation(ou_id, affiliation, source, status)


class AccountOuGroup(Account):
    """Mixin to handle OU groups for Accounts"""

    def __new_primary_account(self, old, new):
        """If new primary account, move memberships of primary groups"""
        pe = Factory.get('Person')(self._db)
        gr = Factory.get('Group')(self._db)
        grids = set()
        for aff in pe.list_affiliations(person_id=self.owner_id):
            for gid in gr.list_ou_groups_for(
                    ou_id=aff['ou_id'], affiliation=aff['affiliation'],
                    source=aff['source_system'], status=aff['status'],
                    indirect=False,
                    member_types=self.const.virtual_group_ou_primary):
                grids.add(gid['group_id'])
        for grid in grids:
            self._db.log_change(grid, self.clconst.group_rem, old)
            self._db.log_change(grid, self.clconst.group_add, new)

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Add or update account type -> add group memberships?"""
        lst = self.get_account_types(all_persons_types=True)
        ret = super(AccountOuGroup, self).set_account_type(ou_id, affiliation,
                                                           priority)
        if ret is None:
            return ret
        status, pri = ret
        oldprim = lst[0]['account_id']
        if status == 'add':
            if oldprim != self.entity_id and pri < lst[0]['priority']:
                self.__new_primary_account(oldprim, self.entity_id)
            myid = self.entity_id
            gr = Factory.get('Group')(self._db)
            new = gr.list_ou_groups_for(
                ou_id=ou_id, affiliation=affiliation, indirect=False,
                member_types=self.const.virtual_group_ou_accounts)
            for grp in new:
                self._db.log_change(grp['group_id'],
                                    self.clconst.group_add,
                                    myid)
        elif oldprim != self.entity_id and pri < lst[0]['priority']:
            self.__new_primary_account(oldprim, self.entity_id)
        elif (oldprim == self.entity_id and ou_id == lst[0]['ou_id'] and
              affiliation == lst[0]['affiliation']and len(lst) > 1 and
              lst[1]['account_id'] != oldprim and lst[1]['priority'] < pri):
            self.__new_primary_account(oldprim, lst[1]['account_id'])
        return ret

    def del_account_type(self, ou_id, affiliation):
        """Del account type -> remove group membership"""
        lst = self.get_account_types(all_persons_types=True)
        oldprim = lst[0]['account_id']
        ret = super(AccountOuGroup, self).del_account_type(ou_id, affiliation)
        if (oldprim == self.entity_id and ou_id == lst[0]['ou_id'] and
                affiliation == lst[0]['affiliation']):
            if len(lst) == 1:
                pass
                # self.__new_primary_account(oldprim, None)?
            elif lst[1]['account_id'] != oldprim:
                self.__new_primary_account(oldprim, lst[1]['account_id'])
        myid = self.entity_id
        gr = Factory.get('Group')(self._db)
        rem = gr.list_ou_groups_for(
            ou_id=ou_id, affiliation=affiliation, indirect=False,
            member_types=self.const.virtual_group_ou_accounts)
        for grp in rem:
            self._db.log_change(grp['group_id'], self.clconst.group_rem, myid)
        return ret

    def del_ac_types(self):
        """Delete account types -> remove group memberships"""
        lst = self.get_account_types(all_persons_types=True)
        ret = super(AccountOuGroup, self).del_ac_types()
        if not lst:
            return
        myid = self.entity_id
        if myid == lst[0]['account_id']:
            notfound = True
            for i in lst:
                if i['account_id'] != myid:
                    self.__new_primary_account(myid, i['account_id'])
                    notfound = False
                    break
            if notfound:
                pass
                # self.__new_primary_account(myid, None)?
        gr = Factory.get('Group')(self._db)
        for ac in lst:
            if ac['account_id'] == myid:
                rem = gr.list_ou_groups_for(
                    ou_id=ac['ou_id'], affiliation=ac['affiliation'],
                    indirect=False,
                    member_types=self.const.virtual_group_ou_accounts)
                for grp in rem:
                    self._db.log_change(grp['group_id'],
                                        self.clconst.group_rem,
                                        myid)
        return ret
