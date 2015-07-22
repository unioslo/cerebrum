# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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
"""Module for default config settings.

All default configuration that is imported to the Cerebrum instances' config
files should exist in this directory.

Cerebrum's common configuration is mostly put into a local file named:

    cereconf.py

To avoid putting too much settings into L{cereconf}, the various Cerebrum
modules should have their own config files, if they require more than just a
few configuration variables. Examples are adconf.py and cisconf. Modules with
their own config settings should then also have their own default config file,
which should exist in this directory.
"""


def get_config(component):
    """Return instantiated config for a component.

    >>> from Cerebrum.config import get_config
    >>> conf = get_config(__name__.split('.')[-1])
    >>> MyStuff(conf)
    """
    # TODO: Snarf component name from caller?
    import json
    import os
    import cereconf
    if not os.path.exists(component):
        fname = os.path.join(cereconf.CONFIG_PATH, component)
    else:
        fname = component

    with open(fname, 'r') as f:
        return json.load(f)
