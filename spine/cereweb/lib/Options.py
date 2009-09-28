# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import os
import ConfigParser
from gettext import gettext as _

import config

class Options(ConfigParser.ConfigParser):
    """User-specific options for cereweb.
    
    Reads the options from file, and stores options which differ
    from the default-values in the database.

    Adds type and help-text to the classic ConfigParser, which is
    used when displaying the options form for the user. To add
    help-text to an section or an option add it as an option with
    the key <name>_help. Type is handled the same way and available
    types are, but not limited to, checkbox, int, boolean.
    """
    
    def __init__(self, user):
        ConfigParser.ConfigParser.__init__(self)
        self.user = user
        self.load()

    def load(self):
        """Read options from file and database.

        Default options are stored on file, and options which differ from
        them are stored in the database.
        """
        ConfigParser.ConfigParser.read(self, config.option_template)
        ConfigParser.ConfigParser.read(self, config.option_config)
        
    def read():
        raise Exception('Use load to read from file and db.')
        
    def write():
        raise Exception('Default-values are readonly, use save to write to db.')
