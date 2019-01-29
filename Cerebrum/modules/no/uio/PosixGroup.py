# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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

from Cerebrum.modules import PosixGroup


class PosixGroupUiOMixin(PosixGroup.PosixGroup):
    """This mixin overrides PosixGroup for the UiO instance"""

    def demote_posix(self):
        """Remove UiO specific spreads when demoting a PosixGroup."""
        # Make sure the super functionality runs without problems before
        # removing spreads
        ret = self.__super.demote_posix()
        self.delete_spread(self.const.spread_ifi_nis_fg)
        self.delete_spread(self.const.spread_uio_nis_fg)
        return ret
