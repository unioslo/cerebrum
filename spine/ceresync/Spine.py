#!/usr/bin/env python
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

import sys
sys.path.append('../../')
import cerebrum_path

import SpineClient
import config

def new_session():
    return SpineClient.SpineClient(config.url, config.use_ssl, config.ssl_ca_file, config.ssl_key_file, config.ssl_password, idl_path=config.idl_path).connect().login(config.username, config.password)

# arch-tag: 9118fd96-47f8-11da-95bf-ecce98ae9def
