# Copyright 2002 University of Oslo, Norway
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

"""Default Cerebrum installation settings.  Overrides go in cereconf.py."""

# The name of the DB-API 2.0 driver class.  Supported values is
# "Oracle" and "PostgreSQL"
DATABASE_DRIVER = "Oracle"

# Files containing the authentication data needed for database access
# are kept in this directory.
DB_AUTH_DIR = '/etc/cerebrum'

# Name of the SQL database
CEREBRUM_DATABASE_NAME = None

CEREBRUM_DATABASE_CONNECT_DATA = { 'user' : None }

DEFAULT_GECOS_NAME="name_full"
AUTH_CRYPT_METHODS = ("auth_type_md5",)
PERSON_NAME_SS_ORDER = ("system_lt", "system_fs")

LOG_CONFIG_FILE = "/etc/cerebrum/logconfig.ini"

DEFAULT_GROUP_NAMESPACE = 'group_names'
DEFAULT_ACCOUNT_NAMESPACE = 'account_names'

# When gecos for a posix user is None, we look for the person name by
# evaluating source systems in in this order
POSIX_GECOS_SOURCE_ORDER = ("system_lt", "system_fs")

# Temporary switch until someone can figure out why mktime won't work
# with year < 1970 on some systems.  Must NOT be set on production
# systems.
ENABLE_MKTIME_WORKAROUND=0

# If m2crypto is installed, set this to 1 to use ssl
ENABLE_BOFHD_CRYPTO=0

# Makedb will create an initial Group and an Account.  These are
# needed for initial population of the database, as the database model
# requires that accounts and groups have creator_ids/owner_ids.
INITIAL_GROUPNAME = "bootstrap_group"
INITIAL_ACCOUNTNAME = "bootstrap_account"

# To use site-specific constants:
# CONSTANTS_MODULE="Cerebrum.modules.no.uio.Constants"
