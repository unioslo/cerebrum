# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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
"""Default Cerebrum settings for the integration against Exchange

Overrides should go in a local, instance specific file named:

    eventconf.py

Each setting should be well commented in this file, to inform developers and
sysadmin about the usage and consequences of the setting.

"""


CONFIG = dict()

# Following keys should be defined:
# domain: the resource AD domain
# server: The springboard server to use
# management_server: The server Exchange commands sould be run on
# port: Port that winrm uses
# auth_user: user that winrm auths as
# domain_admin: An account in the main AD, should at least have read access to
#   the main AD
# ex_domain_admin: The user in the resource AD, which has access to create mailboxes and stuff.

