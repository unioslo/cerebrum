# -*- coding: iso-8859-1 -*-
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

# Files containing the authentication data needed for database access
# are kept in this directory.
DB_AUTH_DIR = '/etc/cerebrum'

# Name of the SQL database
CEREBRUM_DATABASE_NAME = None

CEREBRUM_DATABASE_CONNECT_DATA = {'user': None,
                                  'table_owner': None}

AUTH_CRYPT_METHODS = ("auth_type_md5_crypt",)

# List of full path filenames to files containing non-allowed
# passwords.
PASSWORD_DICTIONARIES = ()

# Look for things like person name by evaluating source systems in in
# this order
SYSTEM_LOOKUP_ORDER = ("system_manual",)
#  Generate a full-name to display in this order
NAME_LOOKUP_ORDER = (("name_full",),
                     ("name_first", "name_last"))
DEFAULT_GECOS_NAME="name_full"

DEFAULT_GROUP_NAMESPACE = 'group_names'
DEFAULT_ACCOUNT_NAMESPACE = 'account_names'

DEFAULT_OU = None   # Used by bofh "account affadd" if OU is not set
POSIX_HOME_TEMPLATE_DIR = "/local/etc/newusertemplates"
POSIX_USERMOD_SCRIPTDIR = "/etc/cerebrum"
CREATE_USER_SCRIPT= '/local/etc/reguser/mkhomedir'
MVUSER_SCRIPT = '/cerebrum/sbin/mvuser'
RMUSER_SCRIPT = '/cerebrum/sbin/aruser'
RSH_CMD = '/local/bin/ssh'

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
INITIAL_ACCOUNTNAME_PASSWORD = "change_on_install"

# Specify the class this installation should use when working with
# various entities.
#

# The specification has the format [modulename/classname].  To use
# multiple constant classes, list them

CLASS_OU = ['Cerebrum.OU/OU']
CLASS_PERSON = ['Cerebrum.Person/Person']
CLASS_ACCOUNT = ['Cerebrum.Account/Account']
CLASS_GROUP = ['Cerebrum.Group/Group']
CLASS_CONSTANTS = ['Cerebrum.Constants/Constants', 'Cerebrum.Constants/ExampleConstants']

CLASS_CL_CONSTANTS = ['Cerebrum.modules.CLConstants/CLConstants']

CLASS_DBDRIVER = ['Cerebrum.Database/PostgreSQL']
CLASS_DATABASE = ['Cerebrum.CLDatabase/CLDatabase']
# To enable logging, use this:
#CLASS_CHANGELOG = ['Cerebrum.modules.ChangeLog/ChangeLog']
CLASS_CHANGELOG = ['Cerebrum.ChangeLog/ChangeLog']

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
#A value og '0' represents cn=Users,value -1 uses OU in AD_LDAP_PATH.
AD_DEFAULT_OU = '0'
AD_CERE_ROOT_OU_ID = '682'
AD_DONT_TOUCH = ('Group Policy Creator Owners','DnsUpdateProxy','Tivoli_Admin_Privileges','Domain Guests','Domain Admins','Domain Users','Cert Publishers','Domain Controllers','Domain Computers','Administrator','Guest','tmersrvd','krbtgt','TsInternetUser')
#Necesary if groups and users have different namespaces in Cerebrum.
AD_GROUP_POSTFIX = '-gruppe'
AD_HOME_DRIVE = 'M'
AD_PASSWORD_EXPIRE = '0'
AD_CANT_CHANGE_PW = '0'


#Notes spesifikke variable.
NOTES_SERVER_HOST = 'devel01.uio.no'
NOTES_SERVER_PORT = 2000
NOTES_PASSWORD = 'test\n'
NOTES_DEFAULT_OU = 'andre'
NOTES_SOURCE_SEARCH_ORDER = ('system_ureg','system_lt','system_fs')

# You should set this variable to the location of your logging ini file
LOGGING_CONFIGFILE = None

QUARANTINE_RULES = {}
# QUARANTINE_RULES = {
#   'system': {'lock': 1, 'shell': '/local/etc/shells/nologin.system'}
# }

CEREBRUM_DDL_DIR="../share/doc/cerebrum/design"
BOFHD_SUPERUSER_GROUP=INITIAL_GROUPNAME
BOFHD_STUDADM_GROUP=BOFHD_SUPERUSER_GROUP
# Should contain mapping lang: [('template-prefix', 'tpl-type)...]
BOFHD_TEMPLATES={}
# Directory for templates
TEMPLATE_DIR=None

# Configure commands needed to send processed templates to printer
PRINT_LATEX_CMD=None
PRINT_DVIPS_CMD=None
PRINT_LPR_CMD=None
PRINT_PRINTER=None
PRINT_BARCODE=None

# Logdir for AutoStud jobs
AUTOADMIN_LOG_DIR='.'     # Set to a place where only 'cerebrum' has write access
# Socket used to query the job-runner server, should not be writeable by untrusted users
JOB_RUNNER_SOCKET="/tmp/jr-socket"

JOB_RUNNER_LOG_DIR='.'   # Set to a place where only 'cerebrum' has write access
