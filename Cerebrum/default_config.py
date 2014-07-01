# -*- coding: iso-8859-1 -*-
# Copyright 2002-2012 University of Oslo, Norway
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
                                  'table_owner': None,
                                  'host': None}
# Default bind name for Cerebrum
CEREBRUM_SERVER_IP = ""

AUTH_CRYPT_METHODS = ("MD5-crypt",)

# List of full path filenames to files containing non-allowed
# passwords.
PASSWORD_DICTIONARIES = ()

# List full path filenames to files containing words used to
# produce passphrases
PASSPHRASE_DICTIONARIES = ()

# Look for things like person name by evaluating source systems in in
# this order
SYSTEM_LOOKUP_ORDER = ("system_manual",)
#  Generate a full-name to display in this order
NAME_LOOKUP_ORDER = (("name_full",),
                     ("name_first", "name_last"))
DEFAULT_GECOS_NAME = "name_full"

ENTITY_TYPE_NAMESPACE = {'account': 'account_names',
                         'group': 'group_names',
                         'host': 'host_names'}

# Tuple of value_domain_code code_strs that denies update_entity_name
NAME_DOMAINS_THAT_DENY_CHANGE = ()

DEFAULT_OU = None   # Used by bofh "account affadd" if OU is not set
POSIX_HOME_TEMPLATE_DIR = "/local/etc/newusertemplates"
POSIX_USERMOD_SCRIPTDIR = "/etc/cerebrum"

DEBUG_HOSTLIST = None
"""If set, a list of hostnames which are safe to run commands on
during debugging."""

# Used by run_privileged_command.py:
CREATE_USER_SCRIPT = '/local/etc/reguser/mkhomedir'
MVUSER_SCRIPT = '/cerebrum/sbin/mvuser'
RMUSER_SCRIPT = '/cerebrum/sbin/aruser'
ARCHIVE_MAIL_SCRIPT = '/cerebrum/sbin/archivemail'
DIST_NOTESID_SCRIPT = '/cerebrum/sbin/dist_NotesID.pl'
LEGAL_BATCH_MOVE_TIMES = '20:00-08:00'
MAILMAN_SCRIPT = None
SYMPA_SCRIPT = None
CONVERT_MAILCONFIG_SCRIPT = None
MVMAIL_SCRIPT = None
SUBSCRIBE_SCRIPT = None
RSH_CMD = '/local/bin/ssh'

# Temporary switch until someone can figure out why mktime won't work
# with year < 1970 on some systems.  Must NOT be set on production
# systems.
ENABLE_MKTIME_WORKAROUND = 0

# If m2crypto is installed, set this to 1 to use ssl
ENABLE_BOFHD_CRYPTO = 0

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

CLASS_ENTITY = ['Cerebrum.Entity/Entity']
CLASS_OU = ['Cerebrum.OU/OU']
CLASS_PERSON = ['Cerebrum.Person/Person']
CLASS_ACCOUNT = ['Cerebrum.Account/Account']
CLASS_GROUP = ['Cerebrum.Group/Group']
CLASS_HOST = ['Cerebrum.Disk/Host']
CLASS_DISK = ['Cerebrum.Disk/Disk']
CLASS_CONSTANTS = [
    'Cerebrum.Constants/Constants',
    'Cerebrum.Constants/ExampleConstants']

CLASS_CL_CONSTANTS = ['Cerebrum.modules.CLConstants/CLConstants']

CLASS_DBDRIVER = ['Cerebrum.Database/PostgreSQL']
CLASS_DATABASE = ['Cerebrum.CLDatabase/CLDatabase']
#CLASS_DATABASE = ['Cerebrum.CLDatabase/ELDatabase', 'Cerebrum.CLDatabase/CLDatabase']

# exchange-relatert-jazz
# define and enable Factory for DistributionGroup-objects, 
# override localy if needed.
CLASS_DISTRIBUTION_GROUP=['Cerebrum.modules.exchange.v2013.ExchangeGroups/DistributionGroup']

# To enable logging, use this:
# CLASS_CHANGELOG = ['Cerebrum.modules.ChangeLog/ChangeLog']
CLASS_CHANGELOG = ['Cerebrum.ChangeLog/ChangeLog']
CLASS_EVENTLOG = ['Cerebrum.EventLog/EventLog']

# Plain Email-backend generation.
# UiO has it's own. Enable it with
# CLASS_EMAILLDAP = ['Cerebrum.modules.no.uio.EmailLDAP/EmailLDAPUiOMixin']
CLASS_EMAILLDAP = ['Cerebrum.modules.EmailLDAP/EmailLDAP']

# Posix extensions of Account/Group
CLASS_POSIX_USER = ['Cerebrum.modules.PosixUser/PosixUser']
CLASS_POSIX_GROUP = ['Cerebrum.modules.PosixGroup/PosixGroup']

# Hpc module
CLASS_MACHINE = ['Cerebrum.modules.Hpc/Machine']
CLASS_PROJECT = ['Cerebrum.modules.Hpc/Project']
CLASS_ALLOCATION = ['Cerebrum.modules.Hpc/Allocation']
CLASS_ALLOCATION_PERIOD = ['Cerebrum.modules.Hpc/AllocationPeriod']

# OUs that have no parent, typically the ones at the top of any
# OU-tree. Note that OU ids are strings, and therefore any ids listed
# here need to be strings too.
OUS_WITHOUT_PARENT = []

# Which module(s) to use as ClientAPI
# (use Cerebrum.Utils.Factory.get_module("ClientAPI")
MODULE_CLIENTAPI = ['Cerebrum.client.BofhModel']

# URL to bofh server
BOFH_URL = 'http://127.0.0.1:8000'

# Toggle debugging various parts of the code.
# Comparing two Entity (or subclass) instances:
DEBUG_COMPARE = False

# GroupUioMixin limits max # of groupmemberships in groups with
# these spreads
NIS_SPREADS = ()

# process_students and other scripts uses this constant to detect that the user
# should become a posix-user
POSIX_SPREAD_CODES = ()

# if an account is given spread to a spesific target system, try to synchronize
# group memberships in that system (used by bofhd)
GROUP_SYNC_SPREADS = ()

# Spreads that are legal for entries in account_home
HOME_SPREADS = ()

# Assign home in this spread if no other spread is given
DEFAULT_HOME_SPREAD = None
# If your CLASS_ACCOUNT includes
#   Cerebrum.modules.AccountExtras/AutoPriorityAccountMixin
# you must override this value in your cereconf.py.  The purpose of
# the structure is to specify the default (affiliation, status) ->
# (pri_min, pri_max) ranges for new account_type rows.  See the mixin
# class for information on the proper structure of the value.
ACCOUNT_PRIORITY_RANGES = None

# Utils.SimilarSizeWriter default values

# Checks should be not be globally disabled.
SIMILARSIZE_CHECK_DISABLED = False

# Set to a value less than one for more restrictive checks,
# a value more than on for more lenient checks.
# Default is to use the values from clients without modifications.
SIMILARSIZE_LIMIT_MULTIPLIER = 1.0

# What encoding the database data is encoded in. This must be set to be able to
# decode the data to Unicode, which is needed in some exports. If the database
# contains data in other encodings, an attempt of unicodifying it would raise
# exceptions when special characters occur, like ���. Note that this is not used
# everywhere - It started with the AD sync, but should be expanded to other jobs
# too.
#
# If you want to change the encoding, you would need to:
# 1. Make sure that all functionality that puts data into the database respects
#    the set encoding.
# 2. Migrate the database by re-encode the data to the new encoding, if it's not
#    automatically taken care of by the database.
ENCODING = 'ISO-8859-1'

# Active directory specific settings.

AD_SERVER_HOST = 'bastard'
AD_SERVER_PORT = 1681
AD_DOMAIN = 'WinNT://WINTEST'
AD_LDAP = 'DC=wintest,DC=uio,DC=no'
AD_SOURCE_SEARCH_ORDER = (
    'system_ureg',
    'system_sap',
    'system_fs',
    'system_lt')
AD_PASSWORD = 'hallo\n'
AD_LOST_AND_FOUND = 'lost-n-found'
# A value og '0' represents cn=Users,value -1 uses OU in AD_LDAP_PATH.
AD_DEFAULT_OU = '0'
AD_DEFAULT_GROUP_OU = 'OU=grupper'
AD_DEFAULT_USER_OU = 'OU=brukere'
AD_CERE_ROOT_OU_ID = '682'
AD_DONT_TOUCH = ('Group Policy Creator Owners',
                 'DnsUpdateProxy',
                 'Tivoli_Admin_Privileges',
                 'Domain Guests',
                 'Domain Admins',
                 'Domain Users',
                 'Cert Publishers',
                 'Domain Controllers',
                 'Domain Computers',
                 'Administrator',
                 'Guest',
                 'tmersrvd',
                 'krbtgt',
                 'TsInternetUser')
# Necessary if groups and users have different namespaces in Cerebrum.
AD_GROUP_POSTFIX = '-gruppe'
# Default values is sAMAccountName, distinguishedName
AD_ATTRIBUTES = ("displayName", "homeDrive", "homeDirectory")
# Must always have ACCOUNTDISABLE.
AD_ACCOUNT_CONTROL = {'ACCOUNTDISABLE': True, 'DONT_EXPIRE_PASSWORD': True}
AD_HOME_DRIVE = 'M:'
AD_PASSWORD_EXPIRE = '0'
AD_CANT_CHANGE_PW = '0'
AD_PW_EXCEPTION = 'process_students'
AD_PW_EXCEPTION_OU = 'cerebrum_pw_exception'
AD_DO_NOT_TOUCH = 'Cerebrum_dont_touch'
AD_STUNNEL = False
AD_STUNNEL_CONF = '/local/sbin/stunnel.conf'
AD_DEFAULT_SYNC = ''
AD_ACCOUNT_SPREADS = None
AD_TRAIT_TYPES = None
AD_DOMAIN_ADMIN_USER = 'cerebrum'
# Exchange-related variables
#
# exchange-related-jazz
# account exchange spread, accounts with this spread are exported to
# exchange. override localy.
EXCHANGE_ACCOUNT_SPREAD=""
# exchange-related-jazz
# at creation of primary address for dist-groups this short prefix 
# will be attached to the chosen name, override localy
# 
DISTGROUP_PRIMARY_ADDR_PREFIX=""
#
# default domain for distribution groups, override localy
# 
DISTGROUP_DEFAULT_DOMAIN=""
#
# distribution group spread, override localy
EXCHANGE_GROUP_SPREAD=None
#
# distribution group default admin list in exchange, override localy
DISTGROUP_DEFAULT_ADMIN=""
#
# list all valid homeMDBs for the given instance, max nr og users per MDB as follows:
# EXCHANGE_HOMEMDB_VALID = {'homeMDB01': 200,
#                           'homeMDB02': 800,
#                           ...}
EXCHANGE_HOMEMDB_VALID = {}
# list homeMDBs per affiliation as follows:
# EXCHANGE_HOMEMDB = {'ANSATT': (homeMDB01, homeMDB02...),
#                     'MANUELL': (homeMDB03, homeMDB04...)}
EXCHANGE_HOMEMDB_PER_AFFILIATION = {}
# Active Directory file server settings, used at UiA only for the time
# being (Jazz, 2012-05-23)
AD_OTHERS_FILEGROUPS = []
AD_STUDENT_FILEGROUPS = []


# Novell eDirectory settings.
NW_LDAPHOST = 'www.nldap.com'
NW_LDAPPORT = 389
# Every letter in NW_LDAP_ROOT is case-sensitive
NW_LDAP_ROOT = 'ou=HiST,ou=user,o=NOVELL'
NW_SOURCE_SEARCH_ORDER = ('system_fs',)
NW_CERE_ROOT_OU_ID = 6
NW_DEFAULT_OU_ID = 13
NW_ADMINUSER = 'cn=xxxxyyyyy,ou=HiST,ou=user,o=NOVELL'
NW_PASSWORD = 'pass-here'
NW_LOST_AND_FOUND = 'ou=lost-n-found'
# Necessary if groups and users have different namespaces in Cerebrum.
NW_GROUP_POSTFIX = '-gruppe'
NW_PASSWORD_EXPIRE = 'FALSE'
NW_CAN_CHANGE_PW = 'FALSE'
NW_GROUP_SPREAD = ('spread_novell_group',)
# Printer quota variables
NW_INITIALQUOTA = 0
NW_FREEQUOTA = 0

# Notes-spesifikke variable.
NOTES_SERVER_HOST = 'devel01.uio.no'
NOTES_SERVER_PORT = 2000
NOTES_PASSWORD = 'test\n'
NOTES_DEFAULT_OU = 'andre'
NOTES_OU_SUFFIX = []

# UA spesific variables
UA_FTP_HOST = 'uaftp.uio.no'
UA_FTP_UNAME = 'uname'

# You should set this variable to the location of your logging ini file
LOGGING_CONFIGFILE = None

QUARANTINE_RULES = {}
# QUARANTINE_RULES = {
#   'system': {'lock': 1, 'shell': '/local/etc/shells/nologin.system'}
# }

# A list of quarantines that are only handled automatically. The given
# quarantines are not allowed to be modified manually, not even temporarily
# disabling them. This is usable e.g. for guest-quarantines.
QUARANTINE_STRICTLY_AUTOMATIC = ()

# A list of quarantines that are handled automatically. The given quarantines
# are not allowed to be set or removed manually, but it is allowed to
# temporarily disable them. This is usable e.g. for
# inactive-student-quarantines. Superusers might be able to modify them,
# depending on the instance's policies.
QUARANTINE_AUTOMATIC = ()

# List of quarantine-rule names where LDAP Person/FEIDE should ignore 'lock'
QUARANTINE_FEIDE_NONLOCK = ()

CEREBRUM_DDL_DIR = "../share/cerebrum/design"
BOFHD_SUPERUSER_GROUP = INITIAL_GROUPNAME
BOFHD_STUDADM_GROUP = BOFHD_SUPERUSER_GROUP
BOFHD_FNR_ACCESS_GROUP = None
BOFHD_SU_CAN_SPECIFY_PASSWORDS = False
# Should contain mapping lang: [('template-prefix', 'tpl-type)...]
BOFHD_TEMPLATES = {}
BOFHD_MOTD_FILE = None
BOFHD_NEW_USER_SPREADS = []
BOFHD_NEW_GROUP_SPREADS = []
# maximum number of rows returned from person_find and group_list_expanded
BOFHD_MAX_MATCHES = 250
# maximum number of rows returned from access_list_alterable
BOFHD_MAX_MATCHES_ACCESS = 250
BOFHD_CHECK_DISK_SPREAD = None
BOFHD_CLIENTS = {'jbofh': '0.0.3'}
# Max number of seconds a client can have a socket stuck in recv/send
BOFHD_CLIENT_SOCKET_TIMEOUT = None
# authoritative source system (typically administrative
# systems/registers used by an organization)
BOFHD_AUTH_SYSTEMS = ("system_manual",)
# The name of the OpSet for use as moderator of groups, e.g.
# 'Group-owner' or 'groupmod-priv'.
BOFHD_AUTH_GROUPMODERATOR = None
# Directory for templates
TEMPLATE_DIR = None
# Location of locks used by bofhd-request processing system
BOFHD_REQUEST_LOCK_DIR = '/cerebrum/var/log/cerebrum/.lock-%d'
# Quarantines that do not lead to denial of access to bofhd
BOFHD_NONLOCK_QUARANTINES = ()
BOFHD_QUARANTINE_DISABLE_LIMIT = None  # days a quarantine can be disabled

# INDIGO-/CWEB-related bofhd settings, only used by bofhd_go_cmds
# Auth. system that contains the info on people considered 'active'
INDIGO_ACTIVE_SOURCE_SYSTEM = 'system'
# Auth. levels
INDIGO_AUTH_LEVEL = {'superuser': 50,
                     'operator':  30,
                     'other':      0}

# What spreads which should be tagged as 'auto' in bofhds spread_list
GROUP_REQUESTS_AUTOSPREADS = ()

# List of valid values for toplevel mountpoints for disks. Checked
# when disks are added. None = no check performed
VALID_DISK_TOPLEVELS = None

# Configure commands needed to send processed templates to printer
PRINT_LATEX_CMD = None
PRINT_DVIPS_CMD = None
PRINT_DVIPDF_CMD = None
PRINT_LPR_CMD = None
PRINT_PRINTER = None
PRINT_BARCODE = None

# Used for sending e-mail
SMTP_HOST = 'localhost'

# Logdir for AutoStud jobs
AUTOADMIN_LOG_DIR = '.'     # Set to a place where only 'cerebrum' has write access

# decide whether autostud should produce letters for students with address
# registered (if =True letters are produced)
AUTOADMIN_MAKE_ABROAD_LETTERS = False

# directory where the letter templates used by proc_stud are found
AUTOADMIN_PRINT_LETTER_DIRECTORY = 'no_NO/letter'

# Default message for
AUTOADMIN_WELCOME_SMS = 'Welcome\nYour username is: %(username)s'

# The default directory for where the data from FS is put. This could be used by
# jobs that needs to get many of the XML files with data from FS. If this is not
# defined, you need to specify the absolute path to each XML file.
FS_DATADIR = None

# Sets the number of days after a student is considered not active anymore,
# before the STUDENT affiliation gets removed. This is not the correct way of
# solving the problem with students loosing their affiliations too quick - a
# alumni solution would be preferred, but requires more work, so this is a quick
# way out. The default value, 0, removes the affiliations at once after the end
# date for the student.
# Note: The instance' import_FS script must be updated to handle this, this is
# mainly implemented for UiO (and UiA).
FS_STUDENT_REMOVE_AFF_GRACE_DAYS = 0

# make autostud use studentnr as uname
USE_STUDENTNR_AS_UNAME = False
# Socket used to query the job-runner server, should not be writeable by
# untrusted users
JOB_RUNNER_SOCKET = "/tmp/jr-socket"

JOB_RUNNER_LOG_DIR = '.'   # Set to a place where only 'cerebrum' has write access
JOB_RUNNER_MAX_PARALELL_JOBS = 3
# Warn if job-runner has been paused for more than N seconds, every N second
JOB_RUNNER_PAUSE_WARN = 3600 * 12

# Used by Cerebrum/no/Stedkode.py
DEFAULT_INSTITUSJONSNR = None

# INSTITUTION_DOMAIN_NAME: The DNS domain name your institution
# prefers to use for identifying itself on the internet.
#
# For FEIDE-enabled institutions, this setting specifies the domain
# name that will be used for qualifying its eduPersonPrincipalName
# attributes, as described in the "FEIDE Object Class Specification".
#
# Note that you MUST override this setting in your cereconf.py; the
# default value given here will parse as a domain name, but is
# guaranteed (by RFC 2606) to never actually appear in DNS.
#
# Example: At the University of Oslo in Norway, this setting should be
# "uio.no".
INSTITUTION_DOMAIN_NAME = "my-institution.example"

# We might need to use a separate domain name for LMS
# INSTITUTION_DOMAIN_NAME_LMS = "my-lms-institution.example"
INSTITUTION_DOMAIN_NAME_LMS = None

# The Email module's algorithm for determining a user's "default"
# email domain needs a default.  This should be a string, naming fully
# qualified domain name that is registered in the installation's
# 'email_domain' table.
EMAIL_DEFAULT_DOMAIN = None

# If your CLASS_ACCOUNT uses Email/AccountEmailQuotaMixin you have to
# set this variable in your cereconf.py. The purpose of this structure
# is to set default email_quota values based on affiliation in an
# {'AFFILIATION': value}, where value is an int ({'*': values} is
# considered default quota value)
EMAIL_HARD_QUOTA = None

# Warn user when mailbox is email_quota_warn percent full, i.e. if
# EMAIL_SOFT_QUOTA = 90 the users with EMAIL_HARD_QUOTA = 200 should
# be warned when the mailbox contains 180 MiB.  Cerebrum leaves this
# checking to the mail server, and only exports the information to
# LDAP.
EMAIL_SOFT_QUOTA = 90

# Some Cerebrum instances communicate with Cyrus via registered requests in
# bofhd_request-table in Cerebrum, while others don't. This variable decides
# whether a request should be added or not {True/False}
EMAIL_ADD_QUOTA_REQUEST = False

# When an email_target is created default spam settings should be
# registered. Keys must be _EmailTargetCode code strings.
# example:
# EMAIL_DEFAULT_SPAM_SETTINGS = {'account':
#                                ('standard_spam', 'spamfolder'),}
EMAIL_DEFAULT_SPAM_SETTINGS = {}

# When an email_target is created default filters should be
# registered. Keys must be _EmailTargetCode code strings.
# example:
# EMAIL_DEFAULT_FILTERS = {'account': ('greylist',),}
EMAIL_DEFAULT_FILTERS = {}


# When an account is deleted, the e-mail addresses associated with its
# target will be set to expire some time in the future.  When an
# account is resurrected, any expire dates on its addresses are
# removed.  The value is in days.  The expire date is only set on a
# transition from "account" to "deleted" status or vice versa.
# If this value is set to False, no changes are made.
EMAIL_EXPIRE_ADDRESSES = 180

# contrib/no/uio/process_bofhd_requests.py needs a list of servers to
# pass off to cereconf.IMAPSYNC_SCRIPT.
PROC_BOFH_REQ_MOVE_SERVERS = []

# Base reference for URLs on webpages
WEBROOT = "/"

# Used when pgp-encrypting passwords:
PGPPROG = '/usr/bin/gpg'
PGPID = "enter your string here"
PGP_DEC_OPTS = ['--batch', '--decrypt', '--quiet']
PGP_DEC_OPTS_PASSPHRASE = ['--passphrase-fd', "0"]
# ['--recipient', id, '--default-key', id] is appended to PGP_ENC_OPTS
PGP_ENC_OPTS = ['--encrypt', '--armor', '--batch', '--quiet']

# List of systems for Cerebrum.modules.AuthPGP
# keys = systemname (max 12 chars [a-z_])
# values = PGP key id string, "0x98f382f1"
# Example: AUTH_PGP = {
#    "offline": "0x8f382f1",
#    "ad_ntnu_no": "0x82f1821d",
# }
AUTH_PGP = {}

# Realm for HA1 md5 crypt, used by const.auth_type_ha1_md5
AUTH_HA1_REALM = ""

#
# LDAP stuff
#
# Configure these cereconf variables with <variable>.update(<dict>) rather
# than <variable> = <dict>, in case the dicts in default_config are extended
# later.  For optional dict members, None is equivalent to an absent value.
#

# Generation of LDIF/POSIX files
CLASS_ORGLDIF = ['Cerebrum.modules.OrgLDIF/OrgLDIF']
CLASS_POSIXLDIF = ['Cerebrum.modules.PosixLDIF/PosixLDIF']
CLASS_POSIXEXPORT = ['Cerebrum.modules.PosixExport/PosixExport']

# General LDAP info
LDAP = {
    # LDAP server used for LDAP quick-sync?
    #'server': "ldap.example.com",

    # Default directory in which to write LDIF files
    'dump_dir': "/cerebrum/dumps/LDAP/",

    # If set, default attributes for all LDAP_*['dn'] objects except ORG. Each
    # attribute is added if the object does not already have that attribute:
    #'container_attrs': {"objectClass": ("top", "uioUntypedObject")},

    # Constants.py varname of source system with phone and fax for people and
    # organization, plus postal and street addresses for people.
    #'contact_source_system': 'system_foobar',

    # Mapping used to rewrite domains in e-mail addresses:
    # {"domain returned from Cerebrum": "real domain", ...}.
    # This variable should be renamed.  Used in the Email module.
    'rewrite_email_domain': {},

    # Sequence of Constants.py varnames for OpenLDAP userPassword values.
    'auth_methods': ('auth_type_md5_crypt',),

    # To support future formats of userPassword (smd5, glibc etc)
    # and authPassword. Support priority of hash'es inside list.
    # Example with "libc" md5 hash "{crypt}$1$salt$digest
    'auth_attr': {'userPassword': [('MD5-crypt', '{crypt}%s'), ]},

    # Whether to insert 'ou/title;lang-<language>' attributes in org.dump.
    # False with multiple 'pref_languages' likely makes little sense, since
    # each attr only gets values from its 1st found preferred language.
    'output_languages': True,

    # Languages (2-letter ISO 639-1 codes) by preference.  Required, e.g.:
    'pref_languages': ('nb', 'nn', 'en'),

    # Default 'max_change' for the LDAP_<tree>s
    'max_change': 10,
}

# The following LDAP_<tree name> dicts describe LDAP dumps for <tree name>,
# or dumps rooted at that name.
#
# Some common attributes:
# 'dn':          If set, create this tree or object, and with this top DN.
# 'attrs':       Dict of {attribute name: (list of values)} for the top object.
# 'file':        Default filename in LDAP['dump_dir'] (not used tree is dumped
#                with if parent tree and parent 'file' default was not used).
# 'max_change':  Maximum percent change of the size of the LDIF outfile since
#                last run.  With a larger change, an error is reported and the
#                file if not updated.  Default LDAP['max_change'].
#                If max_change is None or >= 100, just open the file normally.
# 'append_file': If set, the name of an LDIF file to append to this tree.
# 'spread':      If set, a spread or sequence of spreads for this LDAP tree,
#                as either Constants.py names or Cerebrum code strings/numbers.
#                Applies to USER, NETGROUP, FILEGROUP, MAIL (max one spread)
#                and PERSON.

# Generated by generate_org_ldif.py:  Organization object, org.units, persons.

# Note that LDAP_ORG['attrs'] differs from other ['attrs']:
# It must at least contain
# - "objectClass" that allows the RDN of LDAP_ORG['dn'] (often "dcObject"),
# - "o" (variants of the organization's name),
# - preferably "eduOrgLegalName" (organization's legal corporate name).
# Generate_org_ldif.py adds objectClasses organization, eduOrg and norEduOrg.
# It also takes the phone, fax, postal addres and street address, if those
# are not set in LDAP_ORG['attrs'], from the LDAP_ORG['ou_id'] org.unit.
# Example LDAP_ORG['attrs'] = {
#    "objectClass":       ("dcObject", "labeledURIObject"),
#    "o":                 ("Our fine Organization", "OfO"),
#    "eduOrgLegalName":   ("Our fine Organization A/S",),
#    "telephoneNumber":   ("+47-12345678",),
#    "labeledURI":        ("http://www.ofo.no/",)}
LDAP_ORG = {                            # Top object and common settings
    'file': "organization.ldif",

    # Top level DN of LDAP tree.  Should normally have the following value:
    #'dn': "dc=" + INSTITUTION_DOMAIN_NAME.replace(".", ",dc=")

    # If one org.unit in Cerebrum actually represents the organization, set
    # this variable to its ou_id, or to 'base' to have Cerebrum deduce the
    # root OU from the org.unit structure.  This OU is excluded from LDAP,
    # instead phone numbers etc. from it are included in the LDAP_ORG['dn']
    # object.  Other root OUs, if any, are put below LDAP_OU['dn'] as usual.
    'ou_id': None,
}

# Tree with org.units, from generate_org_ldif.py.
LDAP_OU = {
    # Base of tree of organizational units.  Can be == LDAP_ORG['dn'].
    #'dn': "cn=organization," + LDAP_ORG['dn'],

    # If not None, make a fake org.unit "ou=<LDAP_OU['dummy_name']>"
    # below LDAP_OU['dn'].  It becomes the parent entry of any person
    # or alias below entries that would otherwise end up just below
    # LDAP_OU['dn'] instead of under some org.unit.
    #'dummy_name': "--",
    'dummy_attrs': {"description": ("Other organizational units",)}

    # Name of source system with perspective of org.unit structure.
    #'ou_perspective': "FOOBAR",
}

# Tree with people, from generate_org_ldif.py.
LDAP_PERSON = {
    # If the DN is == LDAP_OU['dn'], people are placed below their
    # primary org.units in the organization tree.  Otherwise, they are
    # placed in a flat structure below LDAP_PERSON['dn'].  Attributes
    # from object class eduPerson will refer to their org.units.
    #'dn': "cn=people," + LDAP_ORG['dn'],


    # Which address types to give persons: POST and/or STREET
    'address_types': ['POST', 'STREET'],

    # Whether to give the organization tree alias entries for persons.
    # Disabled by default:  Aliases defeat indexing in OpenLDAP since the
    # server does not index a value "through" an alias, so a search which
    # has aliasing turned on must examine all aliases that are in scope.
    'aliases': False,

    # ACI (Access control information) attributes for (in)visible persons.
    # With OpenLDAP-2.1.4 or later, one can e.g. configure with --enable-aci,
    # put something like this in slapd.conf:
    #   access  to dn.children=<LDAP_PERSON['dn']>  by self read  by aci read
    # so a person without OpenLDAPaci only will be visible to that person,
    # and then give this ACI to persons who should be visible:
    #   "attrs_visible": {
    # "OpenLDAPaci": ("1.1#entry#grant;c,r,s,x;[all],[entry]#public#",)},
    # A simpler variant is to use "access to ... filter=(foo=bar) ..."
    # in slapd.conf, and set attrs_(in)visible to {'foo': ('bar',)}.
    'attrs_visible': {},
    'attrs_invisible': {},

    # Constants.py varname for spread to select persons, or None.
    'spread': None,

    # Constants.py varname of source system(s) of affiliations, or None.
    'affiliation_source_system': None,

    # Selectors for person-entries:
    # Each selector is evaluated for a person with some (affiliation,status)es.
    # A selector can be a simple-selector (below), or a dict
    #   {"affiliation": {"status": simple-selector,
    # True:     simple-selector, ...}, # True means wildcard
    # True:   {True:            simple-selector, ...}, # True means wildcard
    # Shorthand for ' "affiliation": {True: simple-selector} ':
    #    "affiliation": simple-selector}.
    # For each (aff., status), the first existing simple-selector is used of
    # selector[aff.][status], selector[aff.][True] and selector[True][True].
    # Each affiliation or status can be a tuple of several values.
    #
    # A list selector evaluates to a list of the selected values for the
    # affiliations it is applied to.  Each simple-selector is a list of values.
    #
    # A boolean selector evaluates to True or False.  Each simple-selector is
    # a bool, a tuple ('group', "name of group with members to selected"),
    # or a tuple ('not', simple-selector).
    #
    # Example:
    # 'affiliation_selector': {
    # Select all employees and affiliates:
    #     ("EMPLOYEE", "AFFILIATE"): True,
    # Select active students except members of group 'no-LDAP-student':
    #     "STUDENT": {"active": ('not', ('group', "no-LDAP-student"))}},
    #
    # Boolean selector: Persons and their affiliations to include in LDAP.
    # Select the affiliations to use for generating a person-entry.
    # (Even the other selectors only use these affiliations.)
    # The person is excluded from LDAP if no affiliations are left.
    #'affiliation_selector': True,
    #
    # Boolean selector: Persons who should be visible in LDAP.
    'visible_selector': True,
    #
    # Boolean selector: Persons to get postal address, phone, work title, etc.
    #'contact_selector': True,
    #
    # List selector: eduPersonAffiliation attribute values for the person.
    'eduPersonAffiliation_selector': [],
    # List selector: eduPersonPrimaryAffiliation attribute values for the
    # person. Each element should have the str of an affiliation as the key,
    # and contain a dict with its statuses, what priority they have and what
    # attribute they should be set to in the LDIF. Example:
    #
    #   'ANSATT': {'tekadm': (100, 'employee'),
    #              'vitenskapelig': (50, 'faculty')}
    #
    # Note that only the affiliations set to True in 'affiliation_selector'
    # needs to be defined in eduPersonPrimaryAffiliation.
    'eduPersonPrimaryAffiliation_selector': {},

    # Path to the file containing a pickle of entitlements mapped to person IDs.
    # The file itself should be created by an external cron job.
    # Entitlements are used in Norway to specify and later publish in LDAP-tree
    # some extra information in about person roles and admissions 
    # at the institution.
    #
    # This parameter acts simultaneously as a switch: empty path value means the
    # publication of entitlements in LDIF is turned off (default behaviour).
    'entitlements_pickle_file' : '',
}

# Generated by generate_posix_ldif.py:  Posix users, filegroups and netgroups.

LDAP_POSIX = {                          # Top object and common settings
    'file': "posix.ldif",

    # Note: LDAP_POSIX['dn'] should not be set if it is == LDAP_ORG['dn']
    # and one uses generate_org_ldif.py to make that entry.
    #'dn': "cn=system," + LDAP_ORG['dn'],
}

# Suggested DNs: "cn=<users,filegroups,netgroups>," + LDAP_POSIX['dn']
LDAP_USER = {}
LDAP_FILEGROUP = {}
LDAP_NETGROUP = {}

# Generated by generate_subnet_ldif.py: Subnet ranges.
# Note: Reads Python comments in cereconf_dns.py for LDAP description fields.
LDAP_SUBNETS = {
    'file': 'subnets.ldif',

    # Extra attribute types and object classes to allow IP address ranges
    # converted to integers (as with inet_addr). Not defined in RFC 2307.
    #   Should have LDAP syntax Integer and EQUALITY + ORDERING rules so
    #   one can search for the subnets which contain a given IP address
    #   with filter (&(startType<=IPaddr)(endType>=IPaddr)).
    #   With OpenLDAP 2.4, an 'eq' index for an attribute with Integer
    #   syntax also works for inequality filters (<=, >=).
    # Default = no extra classes and just write a range as comments:
    #'rangeSchema': (startType, endType, (object classes,)):
    'rangeSchema': ("#addrRangeStart", "#addrRangeEnd", ()),
}

# Generated by generate_mail_ldif.py:
# E-mail information, to be used by the mail system.
LDAP_MAIL = {
    'file': "mail-db.ldif",

    #'dn': "cn=mail," + LDAP_ORG['dn'],
}

# Generated by generate_mail_dns_ldif.py:
# Host and domain names, to be used for e-mail delivery.
LDAP_MAIL_DNS = {
    'file': "mail-dns.ldif",

    #'dn': "cn=mail-dns," + LDAP_ORG['dn'],

    # Only consider hosts which have these hosts as lowest priority
    # MX record and also are A records.
    #'mx_hosts': ("some-host", ...),

    # Treat these hosts as if they have A records.
    'extra_a_hosts': (),

    # 'dig' command used to fetch information from DNS.
    'dig_cmd': "/usr/bin/dig %s. @%s. axfr",

    # Sequence of sequence of arguments to LDAP_MAIL_DNS['dig_cmd'].  The
    # command is run once for each argument sequence. The results are combined.
    #'dig_args': ((domain, name server), (domain, name server), ...),
}

# Default settings of the previous names of these variables;
# retained for the time being for backwards compatibility.
LDAP_DUMP_DIR = '/cerebrum/dumps/LDAP/'
LDAP_ORG_FILE = 'organization.ldif'
LDAP_POSIX_FILE = 'posix.ldif'
LDAP_ALIASES = False
LDAP_ORG_ROOT = None
LDAP_DUMMY_OU_ATTRS = {'description': ('Other organizational units',)}
LDAP_PERSON_SPREAD = None
LDAP_PERSON_AFFILIATION_SOURCE_SYSTEM = None
LDAP_VISIBLE_PERSON_SELECTOR = True
LDAP_EDUPERSONAFFILIATION_SELECTOR = []
LDAP_VISIBLE_PERSON_ATTRS = {}
LDAP_REWRITE_EMAIL_DOMAIN = {}
LDAP_ORG_ADD_LDIF_FILE = LDAP_POSIX_ADD_LDIF_FILE = None
LDAP_MAIL_DNS_EXTRA_A_HOSTS = ()
LDAP_MAIL_DNS_DIG_CMD = "/usr/bin/dig %s. @%s. axfr"
LDAP_MAIL_DNS_MAX_CHANGE = 10

# DNS
DNS_EMAIL_REGEXP = r'^[-+=a-z0-9_.]+@[a-z0-9_-]+[-a-z0-9_.]*\.[a-z]{2,3}$'
# Default number of adresses to reserve at start of a
# subnet. Additionally, if any addresses are reserved, broadcast
# (last) address is reserved too. If no entry, max value from
# dictionary is used.
DEFAULT_RESERVED_BY_NET_SIZE = {
    25: 10,
    26: 3,
    27: 3,
    28: 3,
    29: 3,
    30: 0,
    31: 0,
    32: 0,
}

# The default DNS zone to use for bofhd commands and others. Must reference to a
# Cerebrum constant of type DnsZoneCode:
DNS_DEFAULT_ZONE = 'uio'

DEFAULT_RESERVED_BY_IPv6_NET_SIZE = {64: 4}
DEFAULT_IPv6_SUBNET_ALLOCATION_START = 0x256

# Suppress the force-option for unknown IPv6 subnets.
# This needs to be done if an instance does not have any subnets defined.
# TODO: Remove this at an appropriate time!
DNS_HOST_A_ADD_ACCEPT_MISSING_IPV6_SUBNET = False

# Location of documentation concerning import of subnets for DNS.
# Added to mails sent when errors occur.
DNS_SUBNETIMPORT_ERRORDOC_URL = None

# STATISTICS
# Various settings used by statistics-programs Lists most significant
# affiliation to least significant, using their numeric codes.
AFFILIATIONS_BY_PRIORITY = []
# String used to represent the group that can't be connected to any
# affiliations.
NO_AFFILIATION = "(NONE)"
# File that contains explanatory info about the statistics, that is
# included in the report generated by the program
STATISTICS_EXPLANATION_TEMPLATE = ""

# CACHING
# Some testing requires that the constants do not save their int-value when
# looked up.  Disable CACHE_CONSTANTS when running these tests.
CACHE_CONSTANTS = True

# Needed by contrib/file_clean.py
DELETE_FILES = []
ARCHIVE_FILES = []

# Vars needed by Ephorte module
EPHORTE_ADMINS = ""
EPHORTE_SO_SKO = []
EPHORTE_NIKK_SKO = []
EPHORTE_UIO_ROOT_SKO = ''
EPHORTE_MAIL_WARNINGS = ""
EPHORTE_MAIL_WARNINGS2 = ""
EPHORTE_MAIL_TIME = []
EPHORTE_DEFAULT_PERM = ''
EPHORTE_DEFAULT_OLD_PERM = ''
EPHORTE_EGNE_SAKER_SKO = ''
EPHORTE_NEW2OLD_PERMISSIONS = {}
EPHORTE_OLD2NEW_PERMISSIONS = {}

# Oracle default DB driver
DB_DRIVER_ORACLE = "cx_Oracle"


#
# Automatic group creation based on employment information
# Syntax: 'affiliation-or-status': 'group-prefix
# affiliation-or-status is a PersonAffiliation/PersonAffStatus
# group-prefix is a string which will be the prefix of the auto-generated
# groups.
# E.g. {'affiliation_status_ansatt_tekadm': 'ansatt-tekadm'}
#
AUTOMATIC_GROUPS = {}

# Prefixes that define which groups should be added as members of meta-groups.
# E.g. ['ansatt', 'tilknyttet']
AUTOMATIC_GROUP_POPULATE_META_PREFIX = []

# Prefix to description mapping for automatic groups.
# E.g. {"ansatt": "Tilsatte ved %s",
#       "meta-ansatt":
#           "Tilsatte ved %s og underordnede organisatoriske enheter",}
AUTOMATIC_GROUP_LEGAL_PREFIXES = {}


# Mapping of affiliations and groups, used for automatic group membership
# based on person affiliations.
# Syntax: 'AFFILIATION': 'group'
# The variable is overwritten by local cereconf.py and used by
# update_affiliation_groups.py (contrib).
# Initiated by UiA Dec 2012, implemented Jan 2013.
AFFILIATION_GROUPS = {}


#
# SMS gateway
#
SMS_URL = ''
# The "system", used by the gateway at logon
SMS_SYSTEM = ''
# The username for authentication at the gateway
SMS_USER = ''
# A regex whitelist of numbers. The SMSSender will only send to phone numbers
# that pass one of these regexes. Default value: Eight digit number.
SMS_ACCEPT_REGEX = (r'^\d{8}$', )

#
# Certificates
#

# The private key used by Cerebrum's server(s).
SSL_PRIVATE_KEY_FILE = '/cerebrum/var/password/cerebrum_key.priv'
# Cerebrum's server(s) x509 certificate.
SSL_CERTIFICATE_FILE = '/cerebrum/var/certs/cerebrum.pem'

#
# The Individuation daemon
# A soap-daemon for users to change password, e.g. by SMS.
#

# The port number where an Individuation daemon should run
INDIVIDUATION_SERVICE_PORT = 0
# To where the Individuation daemon should log
INDIVIDUATION_SERVICE_LOGFILE = None
# The local individuation instance to use
INDIVIDUATION_INSTANCE = 'Cerebrum.modules.cis.Individuation/Individuation'

# The number of attempts before a user gets blocked from the service
INDIVIDUATION_ATTEMPTS = 10
# For how long a blocked user will stay blocked
INDIVIDUATION_ATTEMPTS_BLOCK_PERIOD = 3600  # in seconds
# The lifetime of one time passwords sent by SMS
# Remember that some countries have slow mobile networks
INDIVIDUATION_TOKEN_LIFETIME = 60  # Minutes
# The number of characters in a one time passwords sent by SMS
INDIVIDUATION_TOKEN_LENGTH = 8
# The format of the message
INDIVIDUATION_SMS_MESSAGE = "Your one time password:\n%s\nCerebrum"
# The number of times a token can be checked before it's invalidated
INDIVIDUATION_TOKEN_ATTEMPTS = 10
# The location of the certificate(s) for which is accepted as the signer of
# the client's certificate. Defaults to Cerebrum's own server certificate. If
# chains are needed, you need to supply a list of all the needed certificates.
# If you specify a directory, you first need to run `cacertdir_rehash` on it,
# to create hashed symlinks to the certificates, otherwize they will be
# ignored. This script is a wrapper for creating files named by:
#   openssl x509 -noout -subject_hash -in cert.pem
# Note that the hashes might vary between OpenSSL versions.
INDIVIDUATION_CLIENT_CA = SSL_CERTIFICATE_FILE

# A whitelist of sha-1 fingerprints for accepted client certificates. Note
# that the certificate has to be signed by one of the CAs in
# INDIVIDUATION_CLIENT_CA as well before it is accepted. Also note that every
# certificate that is used in a certificate chain has to be whitelisted, which
# includes the CAs certificates. To get the sha1 fingerprint of a certificate,
# one can use the command:
#
#   openssl x509 -in certificate.pem -noout -fingerprint -sha1
#
# Fingerprints can, in theory, be hacked through collision attacks. Use sha256
# in the future to minimize this risk.
INDIVIDUATION_CLIENT_FINGERPRINTS = ()

# Quarantines that is accepted for password changes. Quarantines not in this
# list blocks the user from changing password.
INDIVIDUATION_ACCEPTED_QUARANTINES = ('quarantine_svakt_passord',
                                      'quarantine_autopassord')
# The number of days a deleted affiliation will still be considered active for
# the password service. This is to let people that has just quit, or is wrongly
# registered, to be able to use the service a short time after.
INDIVIDUATION_AFF_GRACE_PERIOD = 7  # in days

# Configuration for each source system and its phone types that is accepted for
# sending SMS. The keys are the name of the source system, the values are:
#
#  - priority: In what order the system should be used. Only the person's
#    affiliations from the highest priority is used, the rest is ignored. This
#    is used for the scenario where employees which also studies should not be
#    able to use the phone number registered in the student system for setting
#    new passwords. The HR system should then have priority 1, while the student
#    system is at 2. If a person then have an affiliation from the HR system,
#    the student system is then ignored.
#
#    To let employees be able to use their student registrations, the HR and
#    student systems should have the same priority.
#
#  - types: The contact types that should be used from the given system. The
#    dict contains of the contact types as keys, while the content might
#    contain:
#
#     - delay: (default: 0) Sets the number of days that numbers from this
#       system will be "quarantined" for use in the password service. This is to
#       slow down attacks where a user is compromised and the phone number is
#       changed - the attacker would then have to wait some time before they can
#       use the phone number for getting the password.
#
INDIVIDUATION_PHONE_TYPES = {}
# Example: {
#   'system_sap': {
#       'priority': 1,
#       'types': {
#           'contact_mobile_phone':   {},
#           'contact_private_mobile': {},
#       },
#   },
#   'system_fs':  {
#       'priority': 1,
#       'types': {
#           'contact_mobile_phone':   {'delay': 7},
#           'contact_private_mobile': {'delay': 7},
#       },
#   },

# Groups that should be reserved from the password service. Bofhd's superuser
# group is automatically included here.
INDIVIDUATION_PASW_RESERVED = (INITIAL_GROUPNAME,)

# A mapping of building codes to their addresses. Used by the ldif export.
BUILDING_CODES = {}

#
# Guest accounts
#

# Note that these configuration variables should be put in their own file,
# guestconfig.py, in the same location as cereconf.py.

# The maximum number of days a guest account can live. The set expire date for
# guest accounts can not be longer than this. It is, however, possible to set it
# lower than this.
GUEST_MAX_DAYS = 30

# The different types of guests. This is a dict where each element is a type
# with the different settings for the given type of guest accounts. The dict's
# keys are the guest group that the account should be added to. Possible
# variables:
#
#  - prefix -   Prefix for the usernames. Used when creating guest accounts.
#               Must be set.
#  - spreads -  A list of spreads to add to the guest account at creation.
#               Optional.
#
# Example:
#  {'gueststudent':  {'prefix': 'guests-',
#                     'spread': ('stud_account@AD',),},
#   'guestemployee': {'prefix': 'guesta-',
#                     'spread': ('account@AD',),},
GUEST_TYPES = {}

# The default GUEST_TYPES choice. This will be presented as the default choice
# when using 'guest create' and then giving arguments interactively.
GUEST_TYPES_DEFAULT = ''

# The group that stands as the 'owner' of the guest accounts. Note that this is
# the owner group, and not the 'responsible' for the guest, which is a different
# thing which is stored in a trait.
GUEST_OWNER_GROUP = 'guestaccounts'

# The maximum number of simultaneously active guest accounts a given person
# could create. Superusers are still able to create more than this.
GUEST_MAX_PER_PERSON = 100

# The message that should be sent to guest accounts that are registered with a
# mobile phone number. Some input variables are needed, like 'username',
# 'password' and 'expire' with the expire date, formated like YYYY-MM-DD.
GUEST_WELCOME_SMS = ('Welcome.\n'
                     'Your username is: %(username)s\n'
                     'Your password is: %(password)s\n'
                     'The account will expire at %(expire)s')

# The maximum length of the username of guest accounts. Used to restrict the
# length of usernames when generating them, to conform with limits of some
# systems
GUEST_MAX_LENGTH_USERNAME = 20


# This switch decides if users are allowed to supply a phone number to send SMS
# to, in bofhd commands that sends SMS-es.
# At its current state, it's a kill switch for the mobile number-parameter
# of UiA's bofhd-command 'user send_welcome_sms'.
BOFHD_ALLOW_MANUAL_MOBILE = False


# These variables define the UID- and GID-ranges reserved for allocation by
# PosixUser and PosixGroup. They should either be empty (as below), or should
# look something like:
# UID_RESERVED_RANGE = ((5, 10), (20, 25), (30, 35),)
# GID_RESERVED_RANGE = ((40, 42), (89, 92),)
# In the example above, UIDs 5,6,7,8,9,10,20,21,22,23,24,25,30,31,32,33,34,35
# will not be alloced. For the GIDs, 40,41,42,89,90,91,92 will not be alloced.
UID_RESERVED_RANGE = tuple()
GID_RESERVED_RANGE = tuple()
