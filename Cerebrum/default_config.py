# Copyright 2002, 2003 University of Oslo, Norway
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
# TBD: Having both 'DATABASE_DRIVER' and 'CLASS_DATABASE' seems to
#      invite confusion; we should choose one.
DATABASE_DRIVER = "PostgreSQL"


# Files containing the authentication data needed for database access
# are kept in this directory.
DB_AUTH_DIR = '/etc/cerebrum'

# Name of the SQL database
CEREBRUM_DATABASE_NAME = None

CEREBRUM_DATABASE_CONNECT_DATA = {'user': None,
                                  'table_owner': None}

DEFAULT_GECOS_NAME="name_full"
AUTH_CRYPT_METHODS = ("auth_type_md5",)
PERSON_NAME_SS_ORDER = ("system_lt", "system_fs")

LOG_CONFIG_FILE = "/etc/cerebrum/logconfig.ini"

DEFAULT_GROUP_NAMESPACE = 'group_names'
DEFAULT_ACCOUNT_NAMESPACE = 'account_names'

DEFAULT_OU = None   # Used by bofh "account affadd" if OU is not set

# When gecos for a posix user is None, we look for the person name by
# evaluating source systems in in this order
POSIX_GECOS_SOURCE_ORDER = ("system_lt", "system_fs")
POSIX_HOME_TEMPLATE_DIR = "/local/etc/newusertemplates"
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

# Specify the class this installation should use when working with
# various entities.
#

# The specification has the format [modulename/classname].  To use
# multiple constant classes, list them

CLASS_OU = ['Cerebrum.OU/OU']
CLASS_PERSON = ['Cerebrum.Person/Person']
CLASS_ACCOUNT = ['Cerebrum.Account/Account']
CLASS_GROUP = ['Cerebrum.Group/Group']
CLASS_CONSTANTS = ['Cerebrum.Constants/Constants']

CLASS_CL_CONSTANTS = ['Cerebrum.modules.CLConstants/CLConstants']

CLASS_DBDRIVER = ['Cerebrum.Database/PostgreSQL']
CLASS_DATABASE = ['Cerebrum.CLDatabase/CLDatabase']
# To enable logging, use this:
#CLASS_CHANGELOG = ['Cerebrum.modules.ChangeLog/ChangeLog']
CLASS_CHANGELOG = ['Cerebrum.ChangeLog/ChangeLog']

# Path to templates for passweb.py et. al.
TEMPLATE_DIR='/path'
# URL to bofh server
BOFH_URL='http://127.0.0.1:8000'

# Toggle debugging various parts of the code.
# Comparing two Entity (or subclass) instances:
DEBUG_COMPARE = False

# Active directory specific settings.

AD_SERVER_HOST = 'bastard'
AD_SERVER_PORT = 1681
AD_DOMAIN = 'WinNT://WINTEST'
AD_LDAP= 'DC=wintest,DC=uio,DC=no'
AD_SOURCE_SEARCH_ORDER = ('system_ureg','system_lt','system_fs')
AD_PASSWORD = 'hallo\n'
AD_LOST_AND_FOUND = 'lost-n-found'
AD_DONT_TOUCH = ('Group Policy Creator Owners','DnsUpdateProxy','Tivoli_Admin_Privileges','Domain Guests','Domain Admins','Domain Users','Cert Publishers','Domain Controllers','Domain Computers','Administrator','Guest','tmersrvd','krbtgt','TsInternetUser')
#Necesary if groups and users have different namespaces in Cerebrum.
AD_GROUP_POSTFIX = '-gruppe'
AD_HOME_DRIVE = 'M'
AD_PASSWORD_EXPIRE = '0'
AD_CANT_CHANGE_PW = '0'

