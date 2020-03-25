#!/user/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2012 University of Oslo, Norway
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
import six
import collections

from contextlib import contextmanager

from Cerebrum import Errors
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser


class PosixUserUiOMixin(PosixUser.PosixUser):
    """This mixin overrides PosixUser for the UiO instance, and automatically
    creates a personal file group for each user created. It also makes sure
    the group is deleted when POSIX is demoted for a user.

    """

    # NOTE: This mixin depends on mod_entity_trait, allthough it's not in the
    # MRO explicitly

    __read_attr__ = ('__create_dfg', )

    def __init__(self, database):
        self.pg = Factory.get('PosixGroup')(database)
        self.__super.__init__(database)
        self.user2group_spread = {
            int(self.const.spread_uio_nis_user):
                int(self.const.spread_uio_nis_fg),
            int(self.const.spread_ifi_nis_user):
                int(self.const.spread_ifi_nis_fg),
        }

    def delete_posixuser(self):
        """Demotes this PosixUser to a normal Account. Overridden to also
        demote the PosixUser's file group to a normal group, as long as it is
        the account's personal group.

        """
        ret = self.__super.delete_posixuser()

        pg = self.find_personal_group()
        if pg is not None:
            for row in pg.get_spread():
                pg.delete_spread(int(row['spread']))
            pg.write_db()
            if pg.has_extension('PosixGroup'):
                pg.demote_posix()
        return ret

    def clear(self):
        """Also clear the PosixGroup."""
        self.pg.clear()
        try:
            del self.__create_dfg
        except AttributeError:
            pass
        return self.__super.clear()

    def add_spread(self, *args, **kwargs):
        """Override with UiO specific behaviour."""
        ret = self.__super.add_spread(*args, **kwargs)
        self.map_user_spreads_to_pg()
        return ret

    def delete_spread(self, *args, **kwargs):
        """Override with UiO specific behaviour."""
        ret = self.__super.delete_spread(*args, **kwargs)
        self.map_user_spreads_to_pg()
        return ret

    def populate(self, posix_uid, gid_id, gecos, shell,
                 name=None, owner_type=None, owner_id=None, np_type=None,
                 creator_id=None, expire_date=None, parent=None):
        """Populate PosixUser instance's attributes without database access.
        Note that the given L{gid_id} is ignored, the account's personal file
        group is used anyways. The personal group's entity_id will be fetched
        at L{write_db}.

        Note that the gid_id could be forced by explicitly setting pu.gid_id
        after populate. The module would then respect this at write_db.

        """
        # TODO: Fix __xerox__ so that it fails if passed 'None', remove this
        # assertion, and move super.populate up here.
        assert name or parent, "Need to either specify name or parent"

        if not creator_id:
            creator_id = parent.entity_id

        ret = self.__super.populate(posix_uid, gid_id, gecos,
                                    shell, name, owner_type, owner_id,
                                    np_type, creator_id, expire_date, parent)

        if self.gid_id is None:
            personal_dfg = None
            if parent:
                personal_dfg = self.find_personal_group()
            if personal_dfg is None:
                # No dfg, we need to create it
                self.__create_dfg = creator_id
            else:
                self.pg = personal_dfg
                self.gid_id = self.pg.entity_id

        return ret

    @contextmanager
    def _new_personal_group(self, creator_id):
        group = Factory.get('PosixGroup')(self._db)

        def get_available_dfg_name(basename):
            group = Factory.get('Group')(self._db)

            def alternatives(base):
                # base -> base, base1, base2, ... base9
                yield base
                if len(base) >= 8:
                    base = base[:-1]
                for i in range(1, 10):
                    yield base + str(i)

            for name in alternatives(basename):
                try:
                    group.find_by_name(name)
                    group.clear()
                    continue
                except Errors.NotFoundError:
                    return name
            # TODO: Better exception?
            raise Errors.NotFoundError(
                "Unable to find a group name for {!s}".format(basename))

        # Find any group previously marked as this users personal group.
        personal_dfg_name = get_available_dfg_name(self.account_name)

        group.populate(
            creator_id=creator_id,
            visibility=self.const.group_visibility_all,
            name=personal_dfg_name,
            description='Personal file group for {}'.format(self.account_name),
            group_type=self.const.group_type_personal,
        )

        # Intermediate write, to get an entity_id
        group.write_db()

        yield group

        group.populate_trait(self.const.trait_personal_dfg,
                             target_id=self.entity_id)

        group.write_db()

    def promote_personal_group(self, pg, group_id):
        gr = Factory.get('Group')(self._db)
        gr.find(group_id)
        pg.clear()
        pg.populate(parent=gr)
        pg.write_db()

    def match_spreads(self, group_id, account=None):
        """Compare the spreads of an account with the spreads of a group

        :return: Spreads of the group which matches those of the user
        """
        user = account or self
        gr = Factory.get('Group')(self._db)
        gr.find(group_id)
        group_spreads = {s[0] for s in gr.get_spread()}
        return group_spreads.intersection(
            {self.user2group_spread[s[0]] for s in user.get_spread() if
             s[0] in self.user2group_spread}
        )

    def choose_personal_group(self, group_ids):
        """Choose the most suitable personal group of the candidates given"""
        # 1. Check if one of the groups is the PosixUser's default group
        if self.gid_id is not None and self.gid_id in group_ids:
            return self.gid_id
        # 2. Check which group has the most spreads matching the user's spreads
        matches = collections.defaultdict(list)
        for group_id in group_ids:
            matches[len(self.match_spreads(group_id))].append(
                group_id
            )
        best_matching_groups = matches[max(matches)]
        if len(best_matching_groups) == 1:
            return best_matching_groups[0]
        # 3. Check which group has the same name as the user
        gr = Factory.get('Group')(self._db)
        for group_id in best_matching_groups:
            gr.clear()
            gr.find(group_id)
            if gr.group_name == self.account_name:
                return gr.entity_id
        # 4. Might as well pick the first one
        return best_matching_groups[0]

    def maybe_promote_group(self, group_id):
        """Promote the group to a posix group if it isn't one already"""
        pg = Factory.get('PosixGroup')(self._db)
        try:
            pg.find(group_id)
        except Errors.NotFoundError:
            self.promote_personal_group(pg, group_id)
        return pg

    def find_personal_group(self):
        """Retrieve the personal file group of an existing PosixUser"""
        traits = list(self.list_traits(target_id=self.entity_id,
                                       code=self.const.trait_personal_dfg))
        if len(traits) == 0:
            return None
        if len(traits) == 1:
            return self.maybe_promote_group(traits[0]['entity_id'])
        group_id = self.choose_personal_group([t['entity_id'] for t in traits])
        return self.maybe_promote_group(group_id)

    def map_user_spreads_to_pg(self, group=None):
        """ Maps user's spreads to personal group. """
        super(PosixUserUiOMixin, self).map_user_spreads_to_pg()
        if group is None:
            group = self.find_personal_group()
            if group is None:
                return 
        user_spreads = [int(r['spread']) for r in self.get_spread()]
        group_spreads = [int(r['spread']) for r in group.get_spread()]
        for uspr, gspr in six.iteritems(self.user2group_spread):
            if uspr in user_spreads and gspr not in group_spreads:
                group.add_spread(gspr)
            if gspr in group_spreads and uspr not in user_spreads:
                group.delete_spread(gspr)

    def write_db(self):
        try:
            creator_id = self.__create_dfg
            del self.__create_dfg
        except AttributeError:
            self.__super.write_db()
        else:
            with self._new_personal_group(creator_id) as personal_fg:
                self.gid_id = personal_fg.entity_id
                self.__super.write_db()
                roles = GroupRoles(self._db)
                roles.add_admin_to_group(self.entity_id, personal_fg.entity_id)
                self.pg = personal_fg
        finally:
            self.map_user_spreads_to_pg()
