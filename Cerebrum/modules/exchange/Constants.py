# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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
"""Constants specific for Exchange
"""

from Cerebrum import Constants
from Cerebrum.Constants import _EntityNameCode

class Constants(Constants.Constants):
    # exchange-relatert-jazz
    # using entity_language_name in order to support display
    # names in various languages if that should be required at 
    # some point
    dl_group_displ_name = _EntityNameCode("DL display name", 
                                    "DL-group display name",
                                    {"nb": "Fremvisningsnavn",
                                     "en": "Display Name", })
