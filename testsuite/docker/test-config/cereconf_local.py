#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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
from Cerebrum.default_config import *

CEREBRUM_DATABASE_NAME = os.getenv('DB_NAME')
CEREBRUM_DATABASE_CONNECT_DATA['user'] = os.getenv('DB_USER')
CEREBRUM_DATABASE_CONNECT_DATA['table_owner'] = os.getenv('DB_USER')
CEREBRUM_DATABASE_CONNECT_DATA['host'] = os.getenv('DB_HOST')
CEREBRUM_DATABASE_CONNECT_DATA['table_owner'] = os.getenv('DB_USER')
CEREBRUM_DDL_DIR = '/src/design'
DB_AUTH_DIR = '/db-auth'
LOGGING_CONFIGFILE = os.path.join(os.getenv('TEST_CONFIG_DIR'),
                                  'logging.ini')