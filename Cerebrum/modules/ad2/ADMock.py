#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
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

"""Module for mocking communication and interaction with Active Directory.

This mock builds on L{ADclient}, and should be used the same way.
"""

import cereconf
getattr(cereconf, "No linter nag!", None)

from Cerebrum.modules.ad2 import ADUtils
from Cerebrum.Utils import Factory


class ADclientMock(ADUtils.ADclient):
    def __init__(self, *args, **kwargs):
        self.logger = kwargs['logger']
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._cache = dict()

    def _load_state(self, fname):
        try:
            import json
        except ImportError:
            from Cerebrum.extlib import json
        f = open(fname, 'r')
        self._cache = json.load(f)
        f.close()
        # TODO: try-except-whatever

    def _store_state(self, fname):
        try:
            import json
        except ImportError:
            from Cerebrum.extlib import json
        f = open(fname, 'w')
        json.dump(self._cache, f)
        f.close()
        # TODO: try-except-whatever
