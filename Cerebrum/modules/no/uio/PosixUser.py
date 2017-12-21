#!/user/bin/env python
# -*- coding: iso-8859-1 -*-
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

from contextlib import contextmanager

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.auth import (BofhdAuthOpSet,
                                         BofhdAuthOpTarget,
                                         BofhdAuthRole)


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

    def _find_personal_group(self, account_id):
        """Find a group (either a PosixGroup or a regular Group) with the
        personal_dfg trait. If a regular Group is found, promote it to
        a PosixGroup. Auto-promoting is necessary due to the fact that
        a previously demoted user that is promoted back to a PosixUser,
        probably already has a personal group that was also demoted at
        the same time as the user, and we want to reuse this group.
        Since this function will only be called under the creation (populate)
        of a PosixUser, or while updating an existing PosixUser, it is safe
        to assume that we would like to automatically re-promote the user's
        personal group as well if it hasn't been done yet.
        """
        pg = Factory.get('PosixGroup')(self._db)
        trait = list(pg.list_traits(target_id=account_id,
                                    code=self.const.trait_personal_dfg))
        if trait:
            group_id = trait[0]['entity_id']
            try:
                pg.find(group_id)
                return pg
            except Errors.NotFoundError:
                gr = Factory.get('Group')(self._db)
                gr.find(group_id)
                pg.clear()
                pg.populate(parent=gr)
                pg.write_db()
                return pg
        return None

    def find_personal_group(self):
        """ Find a posix group marked by the trait_personal_dfg trait.

        @return PosixGroup or None.
        """
        if not getattr(self, 'entity_id'):
            return None
        return self._find_personal_group(self.entity_id)

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

        if gid_id is None:
            personal_dfg = None
            if parent:
                personal_dfg = self._find_personal_group(parent.entity_id)
            if personal_dfg is None:
                # No dfg, we need to create it
                self.__create_dfg = creator_id
            else:
                self.pg = personal_dfg
                gid_id = self.pg.entity_id

        return self.__super.populate(posix_uid, gid_id, gecos,
                                     shell, name, owner_type, owner_id,
                                     np_type, creator_id, expire_date, parent)

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
            creator_id,
            self.const.group_visibility_all,
            personal_dfg_name,
            'Personal file group for {}'.format(self.account_name))

        # Intermediate write, to get an entity_id
        group.write_db()

        yield group

        group.populate_trait(self.const.trait_personal_dfg,
                             target_id=self.entity_id)

        group.write_db()

    def map_user_spreads_to_pg(self, group=None):
        """ Maps user's spreads to personal group. """
        super(PosixUserUiOMixin, self).map_user_spreads_to_pg()
        if group is None:
            group = self.find_personal_group()
            if group is None or not group.has_extension('PosixGroup'):
                return
        mapping = [(int(self.const.spread_uio_nis_user),
                    int(self.const.spread_uio_nis_fg)),
                   (int(self.const.spread_uio_ad_account),
                    int(self.const.spread_uio_ad_group)),
                   (int(self.const.spread_ifi_nis_user),
                    int(self.const.spread_ifi_nis_fg)), ]
        user_spreads = [int(r['spread']) for r in self.get_spread()]
        group_spreads = [int(r['spread']) for r in group.get_spread()]
        for uspr, gspr in mapping:
            if uspr in user_spreads and gspr not in group_spreads:
                group.add_spread(gspr)
            if gspr in group_spreads and uspr not in user_spreads:
                group.delete_spread(gspr)

    def _set_owner_of_group(self, group):
        op_target = BofhdAuthOpTarget(self._db)
        if not op_target.list(entity_id=group.entity_id, target_type='group'):
            op_target.populate(group.entity_id, 'group')
            op_target.write_db()
            op_set = BofhdAuthOpSet(self._db)
            op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
            role = BofhdAuthRole(self._db)
            role.grant_auth(self.entity_id,
                            op_set.op_set_id,
                            op_target.op_target_id)

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
                self._set_owner_of_group(personal_fg)
                self.pg = personal_fg
        finally:
            self.map_user_spreads_to_pg()
