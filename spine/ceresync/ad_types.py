# -*- coding: mbcs -*-
# Created by makepy.py version 0.4.8
# By python version 2.3.4 (#53, May 25 2004, 21:17:02) [MSC v.1200 32 bit (Intel)]
# From type library 'activeds.tlb'
# On Mon Jan 31 17:48:12 2005
"""Active DS Type Library"""
makepy_version = '0.4.8'
python_version = 0x20304f0

import win32com.client.CLSIDToClass, pythoncom
import win32com.client.util
from pywintypes import IID
from win32com.client import Dispatch

# The following 3 lines may need tweaking for the particular server
# Candidates are pythoncom.Missing and pythoncom.Empty
defaultNamedOptArg=pythoncom.Empty
defaultNamedNotOptArg=pythoncom.Empty
defaultUnnamedArg=pythoncom.Empty

CLSID = IID('{97D25DB0-0363-11CF-ABC4-02608C9E7553}')
MajorVersion = 1
MinorVersion = 0
LibraryFlags = 8
LCID = 0x0

class constants:
	ADS_UF_ACCOUNTDISABLE         =0x2        # from enum ADS_USER_FLAG
	ADS_UF_DONT_EXPIRE_PASSWD     =0x10000    # from enum ADS_USER_FLAG
	ADS_UF_DONT_REQUIRE_PREAUTH   =0x400000   # from enum ADS_USER_FLAG
	ADS_UF_ENCRYPTED_TEXT_PASSWORD_ALLOWED=0x80       # from enum ADS_USER_FLAG
	ADS_UF_HOMEDIR_REQUIRED       =0x8        # from enum ADS_USER_FLAG
	ADS_UF_INTERDOMAIN_TRUST_ACCOUNT=0x800      # from enum ADS_USER_FLAG
	ADS_UF_LOCKOUT                =0x10       # from enum ADS_USER_FLAG
	ADS_UF_MNS_LOGON_ACCOUNT      =0x20000    # from enum ADS_USER_FLAG
	ADS_UF_NORMAL_ACCOUNT         =0x200      # from enum ADS_USER_FLAG
	ADS_UF_NOT_DELEGATED          =0x100000   # from enum ADS_USER_FLAG
	ADS_UF_PASSWD_CANT_CHANGE     =0x40       # from enum ADS_USER_FLAG
	ADS_UF_PASSWD_NOTREQD         =0x20       # from enum ADS_USER_FLAG
	ADS_UF_PASSWORD_EXPIRED       =0x800000   # from enum ADS_USER_FLAG
	ADS_UF_SCRIPT                 =0x1        # from enum ADS_USER_FLAG
	ADS_UF_SERVER_TRUST_ACCOUNT   =0x2000     # from enum ADS_USER_FLAG
	ADS_UF_SMARTCARD_REQUIRED     =0x40000    # from enum ADS_USER_FLAG
	ADS_UF_TEMP_DUPLICATE_ACCOUNT =0x100      # from enum ADS_USER_FLAG
	ADS_UF_TRUSTED_FOR_DELEGATION =0x80000    # from enum ADS_USER_FLAG
	ADS_UF_TRUSTED_TO_AUTHENTICATE_FOR_DELEGATION=0x1000000  # from enum ADS_USER_FLAG
	ADS_UF_USE_DES_KEY_ONLY       =0x200000   # from enum ADS_USER_FLAG
	ADS_UF_WORKSTATION_TRUST_ACCOUNT=0x1000     # from enum ADS_USER_FLAG
	ADSTYPE_BACKLINK              =0x12       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_BOOLEAN               =0x6        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_CASEIGNORE_LIST       =0xd        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_CASE_EXACT_STRING     =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_CASE_IGNORE_STRING    =0x3        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_DN_STRING             =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_DN_WITH_BINARY        =0x1b       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_DN_WITH_STRING        =0x1c       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_EMAIL                 =0x18       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_FAXNUMBER             =0x17       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_HOLD                  =0x14       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_INTEGER               =0x7        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_INVALID               =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_LARGE_INTEGER         =0xa        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_NETADDRESS            =0x15       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_NT_SECURITY_DESCRIPTOR=0x19       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_NUMERIC_STRING        =0x5        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_OBJECT_CLASS          =0xc        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_OCTET_LIST            =0xe        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_OCTET_STRING          =0x8        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_PATH                  =0xf        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_POSTALADDRESS         =0x10       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_PRINTABLE_STRING      =0x4        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_PROV_SPECIFIC         =0xb        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_REPLICAPOINTER        =0x16       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_TIMESTAMP             =0x11       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_TYPEDNAME             =0x13       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_UNKNOWN               =0x1a       # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADSTYPE_UTC_TIME              =0x9        # from enum __MIDL___MIDL_itf_ads_0000_0001
	ADS_AUTH_RESERVED             =-2147483648 # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_FAST_BIND                 =0x20       # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_NO_AUTHENTICATION         =0x10       # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_PROMPT_CREDENTIALS        =0x8        # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_READONLY_SERVER           =0x4        # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_SECURE_AUTHENTICATION     =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_SERVER_BIND               =0x200      # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_USE_DELEGATION            =0x100      # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_USE_ENCRYPTION            =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_USE_SEALING               =0x80       # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_USE_SIGNING               =0x40       # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_USE_SSL                   =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0018
	ADS_STATUS_INVALID_SEARCHPREF =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0019
	ADS_STATUS_INVALID_SEARCHPREFVALUE=0x2        # from enum __MIDL___MIDL_itf_ads_0000_0019
	ADS_STATUS_S_OK               =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0019
	ADS_DEREF_ALWAYS              =0x3        # from enum __MIDL___MIDL_itf_ads_0000_0020
	ADS_DEREF_FINDING             =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0020
	ADS_DEREF_NEVER               =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0020
	ADS_DEREF_SEARCHING           =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0020
	ADS_SCOPE_BASE                =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0021
	ADS_SCOPE_ONELEVEL            =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0021
	ADS_SCOPE_SUBTREE             =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0021
	ADSIPROP_ADSIFLAG             =0xc        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_ASYNCHRONOUS         =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_ATTRIBTYPES_ONLY     =0x4        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_CACHE_RESULTS        =0xb        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_CHASE_REFERRALS      =0x9        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_DEREF_ALIASES        =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_PAGED_TIME_LIMIT     =0x8        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_PAGESIZE             =0x7        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_SEARCH_SCOPE         =0x5        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_SIZE_LIMIT           =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_SORT_ON              =0xa        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_TIMEOUT              =0x6        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSIPROP_TIME_LIMIT           =0x3        # from enum __MIDL___MIDL_itf_ads_0000_0022
	ADSI_DIALECT_LDAP             =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0023
	ADSI_DIALECT_SQL              =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0023
	ADS_CHASE_REFERRALS_ALWAYS    =0x60       # from enum __MIDL___MIDL_itf_ads_0000_0024
	ADS_CHASE_REFERRALS_EXTERNAL  =0x40       # from enum __MIDL___MIDL_itf_ads_0000_0024
	ADS_CHASE_REFERRALS_NEVER     =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0024
	ADS_CHASE_REFERRALS_SUBORDINATE=0x20       # from enum __MIDL___MIDL_itf_ads_0000_0024
	ADS_SEARCHPREF_ASYNCHRONOUS   =0x0        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_ATTRIBTYPES_ONLY=0x4        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_ATTRIBUTE_QUERY=0xf        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_CACHE_RESULTS  =0xb        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_CHASE_REFERRALS=0x9        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_DEREF_ALIASES  =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_DIRSYNC        =0xc        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_DIRSYNC_FLAG   =0x11       # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_EXTENDED_DN    =0x12       # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_PAGED_TIME_LIMIT=0x8        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_PAGESIZE       =0x7        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_SEARCH_SCOPE   =0x5        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_SECURITY_MASK  =0x10       # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_SIZE_LIMIT     =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_SORT_ON        =0xa        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_TIMEOUT        =0x6        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_TIME_LIMIT     =0x3        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_TOMBSTONE      =0xd        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_SEARCHPREF_VLV            =0xe        # from enum __MIDL___MIDL_itf_ads_0000_0025
	ADS_PASSWORD_ENCODE_CLEAR     =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0026
	ADS_PASSWORD_ENCODE_REQUIRE_SSL=0x0        # from enum __MIDL___MIDL_itf_ads_0000_0026
	ADS_PROPERTY_APPEND           =0x3        # from enum __MIDL___MIDL_itf_ads_0000_0027
	ADS_PROPERTY_CLEAR            =0x1        # from enum __MIDL___MIDL_itf_ads_0000_0027
	ADS_PROPERTY_DELETE           =0x4        # from enum __MIDL___MIDL_itf_ads_0000_0027
	ADS_PROPERTY_UPDATE           =0x2        # from enum __MIDL___MIDL_itf_ads_0000_0027
	ADS_SYSTEMFLAG_ATTR_IS_CONSTRUCTED=0x4        # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_ATTR_NOT_REPLICATED=0x1        # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_CONFIG_ALLOW_LIMITED_MOVE=0x10000000 # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_CONFIG_ALLOW_MOVE=0x20000000 # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_CONFIG_ALLOW_RENAME=0x40000000 # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_CR_NTDS_DOMAIN =0x2        # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_CR_NTDS_NC     =0x1        # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_DISALLOW_DELETE=-2147483648 # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_DOMAIN_DISALLOW_MOVE=0x4000000  # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_SYSTEMFLAG_DOMAIN_DISALLOW_RENAME=0x8000000  # from enum __MIDL___MIDL_itf_ads_0130_0001
	ADS_GROUP_TYPE_DOMAIN_LOCAL_GROUP=0x4        # from enum __MIDL___MIDL_itf_ads_0136_0001
	ADS_GROUP_TYPE_GLOBAL_GROUP   =0x2        # from enum __MIDL___MIDL_itf_ads_0136_0001
	ADS_GROUP_TYPE_LOCAL_GROUP    =0x4        # from enum __MIDL___MIDL_itf_ads_0136_0001
	ADS_GROUP_TYPE_SECURITY_ENABLED=-2147483648 # from enum __MIDL___MIDL_itf_ads_0136_0001
	ADS_GROUP_TYPE_UNIVERSAL_GROUP=0x8        # from enum __MIDL___MIDL_itf_ads_0136_0001
	ADS_RIGHT_ACCESS_SYSTEM_SECURITY=0x1000000  # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_ACTRL_DS_LIST       =0x4        # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DELETE              =0x10000    # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_CONTROL_ACCESS   =0x100      # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_CREATE_CHILD     =0x1        # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_DELETE_CHILD     =0x2        # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_DELETE_TREE      =0x40       # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_LIST_OBJECT      =0x80       # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_READ_PROP        =0x10       # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_SELF             =0x8        # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_DS_WRITE_PROP       =0x20       # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_GENERIC_ALL         =0x10000000 # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_GENERIC_EXECUTE     =0x20000000 # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_GENERIC_READ        =-2147483648 # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_GENERIC_WRITE       =0x40000000 # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_READ_CONTROL        =0x20000    # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_SYNCHRONIZE         =0x100000   # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_WRITE_DAC           =0x40000    # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_RIGHT_WRITE_OWNER         =0x80000    # from enum __MIDL___MIDL_itf_ads_0158_0001
	ADS_ACETYPE_ACCESS_ALLOWED    =0x0        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_ALLOWED_CALLBACK=0x9        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_ALLOWED_CALLBACK_OBJECT=0xb        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_ALLOWED_OBJECT=0x5        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_DENIED     =0x1        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_DENIED_CALLBACK=0xa        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_DENIED_CALLBACK_OBJECT=0xc        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_ACCESS_DENIED_OBJECT=0x6        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_ALARM_CALLBACK=0xe        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_ALARM_CALLBACK_OBJECT=0x10       # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_ALARM_OBJECT=0x8        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_AUDIT      =0x2        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_AUDIT_CALLBACK=0xd        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_AUDIT_CALLBACK_OBJECT=0xf        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACETYPE_SYSTEM_AUDIT_OBJECT=0x7        # from enum __MIDL___MIDL_itf_ads_0158_0002
	ADS_ACEFLAG_FAILED_ACCESS     =0x80       # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_ACEFLAG_INHERITED_ACE     =0x10       # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_ACEFLAG_INHERIT_ACE       =0x2        # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_ACEFLAG_INHERIT_ONLY_ACE  =0x8        # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_ACEFLAG_NO_PROPAGATE_INHERIT_ACE=0x4        # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_ACEFLAG_SUCCESSFUL_ACCESS =0x40       # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_ACEFLAG_VALID_INHERIT_FLAGS=0x1f       # from enum __MIDL___MIDL_itf_ads_0158_0003
	ADS_FLAG_INHERITED_OBJECT_TYPE_PRESENT=0x2        # from enum __MIDL___MIDL_itf_ads_0158_0004
	ADS_FLAG_OBJECT_TYPE_PRESENT  =0x1        # from enum __MIDL___MIDL_itf_ads_0158_0004
	ADS_SD_CONTROL_SE_DACL_AUTO_INHERITED=0x400      # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_DACL_AUTO_INHERIT_REQ=0x100      # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_DACL_DEFAULTED=0x8        # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_DACL_PRESENT=0x4        # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_DACL_PROTECTED=0x1000     # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_GROUP_DEFAULTED=0x2        # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_OWNER_DEFAULTED=0x1        # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_SACL_AUTO_INHERITED=0x800      # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_SACL_AUTO_INHERIT_REQ=0x200      # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_SACL_DEFAULTED=0x20       # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_SACL_PRESENT=0x10       # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_SACL_PROTECTED=0x2000     # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_CONTROL_SE_SELF_RELATIVE=0x8000     # from enum __MIDL___MIDL_itf_ads_0158_0005
	ADS_SD_REVISION_DS            =0x4        # from enum __MIDL___MIDL_itf_ads_0158_0006
	ADS_NAME_TYPE_1779            =0x1        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_CANONICAL       =0x2        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_CANONICAL_EX    =0xa        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_DISPLAY         =0x4        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_DOMAIN_SIMPLE   =0x5        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_ENTERPRISE_SIMPLE=0x6        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_GUID            =0x7        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_NT4             =0x3        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_SERVICE_PRINCIPAL_NAME=0xb        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_SID_OR_SID_HISTORY_NAME=0xc        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_UNKNOWN         =0x8        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_TYPE_USER_PRINCIPAL_NAME=0x9        # from enum __MIDL___MIDL_itf_ads_0159_0001
	ADS_NAME_INITTYPE_DOMAIN      =0x1        # from enum __MIDL___MIDL_itf_ads_0159_0002
	ADS_NAME_INITTYPE_GC          =0x3        # from enum __MIDL___MIDL_itf_ads_0159_0002
	ADS_NAME_INITTYPE_SERVER      =0x2        # from enum __MIDL___MIDL_itf_ads_0159_0002
	ADS_OPTION_MUTUAL_AUTH_STATUS =0x4        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_PAGE_SIZE          =0x2        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_PASSWORD_METHOD    =0x7        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_PASSWORD_PORTNUMBER=0x6        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_QUOTA              =0x5        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_REFERRALS          =0x1        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_SECURITY_MASK      =0x3        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_OPTION_SERVERNAME         =0x0        # from enum __MIDL___MIDL_itf_ads_0173_0001
	ADS_SECURITY_INFO_DACL        =0x4        # from enum __MIDL___MIDL_itf_ads_0173_0002
	ADS_SECURITY_INFO_GROUP       =0x2        # from enum __MIDL___MIDL_itf_ads_0173_0002
	ADS_SECURITY_INFO_OWNER       =0x1        # from enum __MIDL___MIDL_itf_ads_0173_0002
	ADS_SECURITY_INFO_SACL        =0x8        # from enum __MIDL___MIDL_itf_ads_0173_0002
	ADS_SETTYPE_DN                =0x4        # from enum __MIDL___MIDL_itf_ads_0174_0001
	ADS_SETTYPE_FULL              =0x1        # from enum __MIDL___MIDL_itf_ads_0174_0001
	ADS_SETTYPE_PROVIDER          =0x2        # from enum __MIDL___MIDL_itf_ads_0174_0001
	ADS_SETTYPE_SERVER            =0x3        # from enum __MIDL___MIDL_itf_ads_0174_0001
	ADS_FORMAT_LEAF               =0xb        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_PROVIDER           =0xa        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_SERVER             =0x9        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_WINDOWS            =0x1        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_WINDOWS_DN         =0x3        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_WINDOWS_NO_SERVER  =0x2        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_WINDOWS_PARENT     =0x4        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_X500               =0x5        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_X500_DN            =0x7        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_X500_NO_SERVER     =0x6        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_FORMAT_X500_PARENT        =0x8        # from enum __MIDL___MIDL_itf_ads_0174_0002
	ADS_DISPLAY_FULL              =0x1        # from enum __MIDL___MIDL_itf_ads_0174_0003
	ADS_DISPLAY_VALUE_ONLY        =0x2        # from enum __MIDL___MIDL_itf_ads_0174_0003
	ADS_ESCAPEDMODE_DEFAULT       =0x1        # from enum __MIDL___MIDL_itf_ads_0174_0004
	ADS_ESCAPEDMODE_OFF           =0x3        # from enum __MIDL___MIDL_itf_ads_0174_0004
	ADS_ESCAPEDMODE_OFF_EX        =0x4        # from enum __MIDL___MIDL_itf_ads_0174_0004
	ADS_ESCAPEDMODE_ON            =0x2        # from enum __MIDL___MIDL_itf_ads_0174_0004
	ADS_PATH_FILE                 =0x1        # from enum __MIDL___MIDL_itf_ads_0179_0001
	ADS_PATH_FILESHARE            =0x2        # from enum __MIDL___MIDL_itf_ads_0179_0001
	ADS_PATH_REGISTRY             =0x3        # from enum __MIDL___MIDL_itf_ads_0179_0001
	ADS_SD_FORMAT_HEXSTRING       =0x3        # from enum __MIDL___MIDL_itf_ads_0179_0002
	ADS_SD_FORMAT_IID             =0x1        # from enum __MIDL___MIDL_itf_ads_0179_0002
	ADS_SD_FORMAT_RAW             =0x2        # from enum __MIDL___MIDL_itf_ads_0179_0002
	CC_CDECL                      =0x1        # from enum tagCALLCONV
	CC_FASTCALL                   =0x0        # from enum tagCALLCONV
	CC_FPFASTCALL                 =0x5        # from enum tagCALLCONV
	CC_MACPASCAL                  =0x3        # from enum tagCALLCONV
	CC_MAX                        =0x9        # from enum tagCALLCONV
	CC_MPWCDECL                   =0x7        # from enum tagCALLCONV
	CC_MPWPASCAL                  =0x8        # from enum tagCALLCONV
	CC_MSCPASCAL                  =0x2        # from enum tagCALLCONV
	CC_PASCAL                     =0x2        # from enum tagCALLCONV
	CC_STDCALL                    =0x4        # from enum tagCALLCONV
	CC_SYSCALL                    =0x6        # from enum tagCALLCONV
	DESCKIND_FUNCDESC             =0x1        # from enum tagDESCKIND
	DESCKIND_IMPLICITAPPOBJ       =0x4        # from enum tagDESCKIND
	DESCKIND_MAX                  =0x5        # from enum tagDESCKIND
	DESCKIND_NONE                 =0x0        # from enum tagDESCKIND
	DESCKIND_TYPECOMP             =0x3        # from enum tagDESCKIND
	DESCKIND_VARDESC              =0x2        # from enum tagDESCKIND
	FUNC_DISPATCH                 =0x4        # from enum tagFUNCKIND
	FUNC_NONVIRTUAL               =0x2        # from enum tagFUNCKIND
	FUNC_PUREVIRTUAL              =0x1        # from enum tagFUNCKIND
	FUNC_STATIC                   =0x3        # from enum tagFUNCKIND
	FUNC_VIRTUAL                  =0x0        # from enum tagFUNCKIND
	INVOKE_FUNC                   =0x1        # from enum tagINVOKEKIND
	INVOKE_PROPERTYGET            =0x2        # from enum tagINVOKEKIND
	INVOKE_PROPERTYPUT            =0x4        # from enum tagINVOKEKIND
	INVOKE_PROPERTYPUTREF         =0x8        # from enum tagINVOKEKIND
	SYS_MAC                       =0x2        # from enum tagSYSKIND
	SYS_WIN16                     =0x0        # from enum tagSYSKIND
	SYS_WIN32                     =0x1        # from enum tagSYSKIND
	SYS_WIN64                     =0x3        # from enum tagSYSKIND
	TKIND_ALIAS                   =0x6        # from enum tagTYPEKIND
	TKIND_COCLASS                 =0x5        # from enum tagTYPEKIND
	TKIND_DISPATCH                =0x4        # from enum tagTYPEKIND
	TKIND_ENUM                    =0x0        # from enum tagTYPEKIND
	TKIND_INTERFACE               =0x3        # from enum tagTYPEKIND
	TKIND_MAX                     =0x8        # from enum tagTYPEKIND
	TKIND_MODULE                  =0x2        # from enum tagTYPEKIND
	TKIND_RECORD                  =0x1        # from enum tagTYPEKIND
	TKIND_UNION                   =0x7        # from enum tagTYPEKIND
	VAR_CONST                     =0x2        # from enum tagVARKIND
	VAR_DISPATCH                  =0x3        # from enum tagVARKIND
	VAR_PERINSTANCE               =0x0        # from enum tagVARKIND
	VAR_STATIC                    =0x1        # from enum tagVARKIND

from win32com.client import DispatchBaseClass
class IADs(DispatchBaseClass):
	CLSID = IID('{FD8256D0-FD15-11CE-ABC4-02608C9E7553}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
	}

class IADsADSystemInfo(DispatchBaseClass):
	CLSID = IID('{5BB11929-AFD1-11D2-9CB9-0000F87A369E}')
	coclass_clsid = IID('{50B6327F-AFD1-11D2-9CB9-0000F87A369E}')

	def GetAnyDCName(self):
		# Result is a Unicode object - return as-is for this version of Python
		return self._oleobj_.InvokeTypes(11, LCID, 1, (8, 0), (),)

	def GetDCSiteName(self, szServer=defaultNamedNotOptArg):
		# Result is a Unicode object - return as-is for this version of Python
		return self._oleobj_.InvokeTypes(12, LCID, 1, (8, 0), ((8, 1),),szServer)

	def GetTrees(self):
		return self._ApplyTypes_(14, 1, (12, 0), (), 'GetTrees', None,)

	def RefreshSchemaCache(self):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ComputerName": (3, 2, (8, 0), (), "ComputerName", None),
		"DomainDNSName": (6, 2, (8, 0), (), "DomainDNSName", None),
		"DomainShortName": (5, 2, (8, 0), (), "DomainShortName", None),
		"ForestDNSName": (7, 2, (8, 0), (), "ForestDNSName", None),
		"IsNativeMode": (10, 2, (11, 0), (), "IsNativeMode", None),
		"PDCRoleOwner": (8, 2, (8, 0), (), "PDCRoleOwner", None),
		"SchemaRoleOwner": (9, 2, (8, 0), (), "SchemaRoleOwner", None),
		"SiteName": (4, 2, (8, 0), (), "SiteName", None),
		"UserName": (2, 2, (8, 0), (), "UserName", None),
	}
	_prop_map_put_ = {
	}

class IADsAccessControlEntry(DispatchBaseClass):
	CLSID = IID('{B4F3A14C-9BDD-11D0-852C-00C04FD8D503}')
	coclass_clsid = IID('{B75AC000-9BDD-11D0-852C-00C04FD8D503}')

	_prop_map_get_ = {
		"AccessMask": (2, 2, (3, 0), (), "AccessMask", None),
		"AceFlags": (4, 2, (3, 0), (), "AceFlags", None),
		"AceType": (3, 2, (3, 0), (), "AceType", None),
		"Flags": (5, 2, (3, 0), (), "Flags", None),
		"InheritedObjectType": (7, 2, (8, 0), (), "InheritedObjectType", None),
		"ObjectType": (6, 2, (8, 0), (), "ObjectType", None),
		"Trustee": (8, 2, (8, 0), (), "Trustee", None),
	}
	_prop_map_put_ = {
		"AccessMask": ((2, LCID, 4, 0),()),
		"AceFlags": ((4, LCID, 4, 0),()),
		"AceType": ((3, LCID, 4, 0),()),
		"Flags": ((5, LCID, 4, 0),()),
		"InheritedObjectType": ((7, LCID, 4, 0),()),
		"ObjectType": ((6, LCID, 4, 0),()),
		"Trustee": ((8, LCID, 4, 0),()),
	}

class IADsAccessControlList(DispatchBaseClass):
	CLSID = IID('{B7EE91CC-9BDD-11D0-852C-00C04FD8D503}')
	coclass_clsid = IID('{B85EA052-9BDD-11D0-852C-00C04FD8D503}')

	def AddAce(self, pAccessControlEntry=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(5, LCID, 1, (24, 0), ((9, 1),),pAccessControlEntry)

	def CopyAccessList(self):
		ret = self._oleobj_.InvokeTypes(7, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'CopyAccessList', None, UnicodeToString=0)
		return ret

	def RemoveAce(self, pAccessControlEntry=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(6, LCID, 1, (24, 0), ((9, 1),),pAccessControlEntry)

	_prop_map_get_ = {
		"AceCount": (4, 2, (3, 0), (), "AceCount", None),
		"AclRevision": (3, 2, (3, 0), (), "AclRevision", None),
	}
	_prop_map_put_ = {
		"AceCount": ((4, LCID, 4, 0),()),
		"AclRevision": ((3, LCID, 4, 0),()),
	}
	def __iter__(self):
		"Return a Python iterator for this object"
		ob = self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),())
		return win32com.client.util.Iterator(ob)
	def _NewEnum(self):
		"Create an enumerator from this object"
		return win32com.client.util.WrapEnum(self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),()),None)
	def __getitem__(self, index):
		"Allow this class to be accessed as a collection"
		if not self.__dict__.has_key('_enum_'):
			self.__dict__['_enum_'] = self._NewEnum()
		return self._enum_.__getitem__(index)

class IADsAcl(DispatchBaseClass):
	CLSID = IID('{8452D3AB-0869-11D1-A377-00C04FB950DC}')
	coclass_clsid = None

	def CopyAcl(self):
		ret = self._oleobj_.InvokeTypes(5, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'CopyAcl', None, UnicodeToString=0)
		return ret

	_prop_map_get_ = {
		"Privileges": (4, 2, (3, 0), (), "Privileges", None),
		"ProtectedAttrName": (2, 2, (8, 0), (), "ProtectedAttrName", None),
		"SubjectName": (3, 2, (8, 0), (), "SubjectName", None),
	}
	_prop_map_put_ = {
		"Privileges": ((4, LCID, 4, 0),()),
		"ProtectedAttrName": ((2, LCID, 4, 0),()),
		"SubjectName": ((3, LCID, 4, 0),()),
	}

class IADsBackLink(DispatchBaseClass):
	CLSID = IID('{FD1302BD-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{FCBF906F-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"ObjectName": (3, 2, (8, 0), (), "ObjectName", None),
		"RemoteID": (2, 2, (3, 0), (), "RemoteID", None),
	}
	_prop_map_put_ = {
		"ObjectName": ((3, LCID, 4, 0),()),
		"RemoteID": ((2, LCID, 4, 0),()),
	}

class IADsCaseIgnoreList(DispatchBaseClass):
	CLSID = IID('{7B66B533-4680-11D1-A3B4-00C04FB950DC}')
	coclass_clsid = IID('{15F88A55-4680-11D1-A3B4-00C04FB950DC}')

	_prop_map_get_ = {
		"CaseIgnoreList": (2, 2, (12, 0), (), "CaseIgnoreList", None),
	}
	_prop_map_put_ = {
		"CaseIgnoreList": ((2, LCID, 4, 0),()),
	}

class IADsClass(DispatchBaseClass):
	CLSID = IID('{C8F93DD0-4AE0-11CF-9E73-00AA004A5691}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	# Result is of type IADsCollection
	def Qualifiers(self):
		ret = self._oleobj_.InvokeTypes(25, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Qualifiers', '{72B945E0-253B-11CF-A988-00AA006BC149}', UnicodeToString=0)
		return ret

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Abstract": (18, 2, (11, 0), (), "Abstract", None),
		"AuxDerivedFrom": (27, 2, (12, 0), (), "AuxDerivedFrom", None),
		"Auxiliary": (26, 2, (11, 0), (), "Auxiliary", None),
		"CLSID": (16, 2, (8, 0), (), "CLSID", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Container": (22, 2, (11, 0), (), "Container", None),
		"Containment": (21, 2, (12, 0), (), "Containment", None),
		"DerivedFrom": (20, 2, (12, 0), (), "DerivedFrom", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"HelpFileContext": (24, 2, (3, 0), (), "HelpFileContext", None),
		"HelpFileName": (23, 2, (8, 0), (), "HelpFileName", None),
		"MandatoryProperties": (19, 2, (12, 0), (), "MandatoryProperties", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"NamingProperties": (30, 2, (12, 0), (), "NamingProperties", None),
		"OID": (17, 2, (8, 0), (), "OID", None),
		"OptionalProperties": (29, 2, (12, 0), (), "OptionalProperties", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PossibleSuperiors": (28, 2, (12, 0), (), "PossibleSuperiors", None),
		"PrimaryInterface": (15, 2, (8, 0), (), "PrimaryInterface", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
		"Abstract": ((18, LCID, 4, 0),()),
		"AuxDerivedFrom": ((27, LCID, 4, 0),()),
		"Auxiliary": ((26, LCID, 4, 0),()),
		"CLSID": ((16, LCID, 4, 0),()),
		"Container": ((22, LCID, 4, 0),()),
		"Containment": ((21, LCID, 4, 0),()),
		"DerivedFrom": ((20, LCID, 4, 0),()),
		"HelpFileContext": ((24, LCID, 4, 0),()),
		"HelpFileName": ((23, LCID, 4, 0),()),
		"MandatoryProperties": ((19, LCID, 4, 0),()),
		"NamingProperties": ((30, LCID, 4, 0),()),
		"OID": ((17, LCID, 4, 0),()),
		"OptionalProperties": ((29, LCID, 4, 0),()),
		"PossibleSuperiors": ((28, LCID, 4, 0),()),
	}

class IADsCollection(DispatchBaseClass):
	CLSID = IID('{72B945E0-253B-11CF-A988-00AA006BC149}')
	coclass_clsid = None

	def Add(self, bstrName=defaultNamedNotOptArg, vItem=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(4, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vItem)

	def GetObject(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(6, 1, (12, 0), ((8, 1),), 'GetObject', None,bstrName)

	def Remove(self, bstrItemToBeRemoved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(5, LCID, 1, (24, 0), ((8, 1),),bstrItemToBeRemoved)

	_prop_map_get_ = {
	}
	_prop_map_put_ = {
	}
	def __iter__(self):
		"Return a Python iterator for this object"
		ob = self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),())
		return win32com.client.util.Iterator(ob)
	def _NewEnum(self):
		"Create an enumerator from this object"
		return win32com.client.util.WrapEnum(self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),()),None)
	def __getitem__(self, index):
		"Allow this class to be accessed as a collection"
		if not self.__dict__.has_key('_enum_'):
			self.__dict__['_enum_'] = self._NewEnum()
		return self._enum_.__getitem__(index)

class IADsComputer(DispatchBaseClass):
	CLSID = IID('{EFE3CC70-1D9F-11CF-B1F3-02608C9E7553}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"ComputerID": (16, 2, (8, 0), (), "ComputerID", None),
		"Department": (24, 2, (8, 0), (), "Department", None),
		"Description": (19, 2, (8, 0), (), "Description", None),
		"Division": (23, 2, (8, 0), (), "Division", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Location": (20, 2, (8, 0), (), "Location", None),
		"MemorySize": (31, 2, (8, 0), (), "MemorySize", None),
		"Model": (28, 2, (8, 0), (), "Model", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"NetAddresses": (17, 2, (12, 0), (), "NetAddresses", None),
		"OperatingSystem": (26, 2, (8, 0), (), "OperatingSystem", None),
		"OperatingSystemVersion": (27, 2, (8, 0), (), "OperatingSystemVersion", None),
		"Owner": (22, 2, (8, 0), (), "Owner", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PrimaryUser": (21, 2, (8, 0), (), "PrimaryUser", None),
		"Processor": (29, 2, (8, 0), (), "Processor", None),
		"ProcessorCount": (30, 2, (8, 0), (), "ProcessorCount", None),
		"Role": (25, 2, (8, 0), (), "Role", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Site": (18, 2, (8, 0), (), "Site", None),
		"StorageCapacity": (32, 2, (8, 0), (), "StorageCapacity", None),
	}
	_prop_map_put_ = {
		"Department": ((24, LCID, 4, 0),()),
		"Description": ((19, LCID, 4, 0),()),
		"Division": ((23, LCID, 4, 0),()),
		"Location": ((20, LCID, 4, 0),()),
		"MemorySize": ((31, LCID, 4, 0),()),
		"Model": ((28, LCID, 4, 0),()),
		"NetAddresses": ((17, LCID, 4, 0),()),
		"OperatingSystem": ((26, LCID, 4, 0),()),
		"OperatingSystemVersion": ((27, LCID, 4, 0),()),
		"Owner": ((22, LCID, 4, 0),()),
		"PrimaryUser": ((21, LCID, 4, 0),()),
		"Processor": ((29, LCID, 4, 0),()),
		"ProcessorCount": ((30, LCID, 4, 0),()),
		"Role": ((25, LCID, 4, 0),()),
		"StorageCapacity": ((32, LCID, 4, 0),()),
	}

class IADsComputerOperations(DispatchBaseClass):
	CLSID = IID('{EF497680-1D9F-11CF-B1F3-02608C9E7553}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	def Shutdown(self, bReboot=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(34, LCID, 1, (24, 0), ((11, 1),),bReboot)

	def Status(self):
		ret = self._oleobj_.InvokeTypes(33, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Status', None, UnicodeToString=0)
		return ret

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
	}

class IADsContainer(DispatchBaseClass):
	CLSID = IID('{001677D0-FD16-11CE-ABC4-02608C9E7553}')
	coclass_clsid = None

	def CopyHere(self, SourceName=defaultNamedNotOptArg, NewName=defaultNamedNotOptArg):
		ret = self._oleobj_.InvokeTypes(8, LCID, 1, (9, 0), ((8, 1), (8, 1)),SourceName, NewName)
		if ret is not None:
			ret = Dispatch(ret, 'CopyHere', None, UnicodeToString=0)
		return ret

	def Create(self, ClassName=defaultNamedNotOptArg, RelativeName=defaultNamedNotOptArg):
		ret = self._oleobj_.InvokeTypes(6, LCID, 1, (9, 0), ((8, 1), (8, 1)),ClassName, RelativeName)
		if ret is not None:
			ret = Dispatch(ret, 'Create', None, UnicodeToString=0)
		return ret

	def Delete(self, bstrClassName=defaultNamedNotOptArg, bstrRelativeName=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(7, LCID, 1, (24, 0), ((8, 1), (8, 1)),bstrClassName, bstrRelativeName)

	def GetObject(self, ClassName=defaultNamedNotOptArg, RelativeName=defaultNamedNotOptArg):
		ret = self._oleobj_.InvokeTypes(5, LCID, 1, (9, 0), ((8, 1), (8, 1)),ClassName, RelativeName)
		if ret is not None:
			ret = Dispatch(ret, 'GetObject', None, UnicodeToString=0)
		return ret

	def MoveHere(self, SourceName=defaultNamedNotOptArg, NewName=defaultNamedNotOptArg):
		ret = self._oleobj_.InvokeTypes(9, LCID, 1, (9, 0), ((8, 1), (8, 1)),SourceName, NewName)
		if ret is not None:
			ret = Dispatch(ret, 'MoveHere', None, UnicodeToString=0)
		return ret

	_prop_map_get_ = {
		"Count": (2, 2, (3, 0), (), "Count", None),
		"Filter": (3, 2, (12, 0), (), "Filter", None),
		"Hints": (4, 2, (12, 0), (), "Hints", None),
	}
	_prop_map_put_ = {
		"Filter": ((3, LCID, 4, 0),()),
		"Hints": ((4, LCID, 4, 0),()),
	}
	def __iter__(self):
		"Return a Python iterator for this object"
		ob = self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),())
		return win32com.client.util.Iterator(ob)
	def _NewEnum(self):
		"Create an enumerator from this object"
		return win32com.client.util.WrapEnum(self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),()),None)
	def __getitem__(self, index):
		"Allow this class to be accessed as a collection"
		if not self.__dict__.has_key('_enum_'):
			self.__dict__['_enum_'] = self._NewEnum()
		return self._enum_.__getitem__(index)
	#This class has Count() property - allow len(ob) to provide this
	def __len__(self):
		return self._ApplyTypes_(*(2, 2, (3, 0), (), "Count", None))
	#This class has a __len__ - this is needed so 'if object:' always returns TRUE.
	def __nonzero__(self):
		return True

class IADsDNWithBinary(DispatchBaseClass):
	CLSID = IID('{7E99C0A2-F935-11D2-BA96-00C04FB6D0D1}')
	coclass_clsid = IID('{7E99C0A3-F935-11D2-BA96-00C04FB6D0D1}')

	_prop_map_get_ = {
		"BinaryValue": (2, 2, (12, 0), (), "BinaryValue", None),
		"DNString": (3, 2, (8, 0), (), "DNString", None),
	}
	_prop_map_put_ = {
		"BinaryValue": ((2, LCID, 4, 0),()),
		"DNString": ((3, LCID, 4, 0),()),
	}

class IADsDNWithString(DispatchBaseClass):
	CLSID = IID('{370DF02E-F934-11D2-BA96-00C04FB6D0D1}')
	coclass_clsid = IID('{334857CC-F934-11D2-BA96-00C04FB6D0D1}')

	_prop_map_get_ = {
		"DNString": (3, 2, (8, 0), (), "DNString", None),
		"StringValue": (2, 2, (8, 0), (), "StringValue", None),
	}
	_prop_map_put_ = {
		"DNString": ((3, LCID, 4, 0),()),
		"StringValue": ((2, LCID, 4, 0),()),
	}

class IADsDeleteOps(DispatchBaseClass):
	CLSID = IID('{B2BD0902-8878-11D1-8C21-00C04FD8D503}')
	coclass_clsid = None

	def DeleteObject(self, lnFlags=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(2, LCID, 1, (24, 0), ((3, 1),),lnFlags)

	_prop_map_get_ = {
	}
	_prop_map_put_ = {
	}

class IADsDomain(DispatchBaseClass):
	CLSID = IID('{00E4C220-FD16-11CE-ABC4-02608C9E7553}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"AutoUnlockInterval": (22, 2, (3, 0), (), "AutoUnlockInterval", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"IsWorkgroup": (15, 2, (11, 0), (), "IsWorkgroup", None),
		"LockoutObservationInterval": (23, 2, (3, 0), (), "LockoutObservationInterval", None),
		"MaxBadPasswordsAllowed": (19, 2, (3, 0), (), "MaxBadPasswordsAllowed", None),
		"MaxPasswordAge": (18, 2, (3, 0), (), "MaxPasswordAge", None),
		"MinPasswordAge": (17, 2, (3, 0), (), "MinPasswordAge", None),
		"MinPasswordLength": (16, 2, (3, 0), (), "MinPasswordLength", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PasswordAttributes": (21, 2, (3, 0), (), "PasswordAttributes", None),
		"PasswordHistoryLength": (20, 2, (3, 0), (), "PasswordHistoryLength", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
		"AutoUnlockInterval": ((22, LCID, 4, 0),()),
		"LockoutObservationInterval": ((23, LCID, 4, 0),()),
		"MaxBadPasswordsAllowed": ((19, LCID, 4, 0),()),
		"MaxPasswordAge": ((18, LCID, 4, 0),()),
		"MinPasswordAge": ((17, LCID, 4, 0),()),
		"MinPasswordLength": ((16, LCID, 4, 0),()),
		"PasswordAttributes": ((21, LCID, 4, 0),()),
		"PasswordHistoryLength": ((20, LCID, 4, 0),()),
	}

class IADsEmail(DispatchBaseClass):
	CLSID = IID('{97AF011A-478E-11D1-A3B4-00C04FB950DC}')
	coclass_clsid = IID('{8F92A857-478E-11D1-A3B4-00C04FB950DC}')

	_prop_map_get_ = {
		"Address": (3, 2, (8, 0), (), "Address", None),
		"Type": (2, 2, (3, 0), (), "Type", None),
	}
	_prop_map_put_ = {
		"Address": ((3, LCID, 4, 0),()),
		"Type": ((2, LCID, 4, 0),()),
	}

class IADsFaxNumber(DispatchBaseClass):
	CLSID = IID('{A910DEA9-4680-11D1-A3B4-00C04FB950DC}')
	coclass_clsid = IID('{A5062215-4681-11D1-A3B4-00C04FB950DC}')

	_prop_map_get_ = {
		"Parameters": (3, 2, (12, 0), (), "Parameters", None),
		"TelephoneNumber": (2, 2, (8, 0), (), "TelephoneNumber", None),
	}
	_prop_map_put_ = {
		"Parameters": ((3, LCID, 4, 0),()),
		"TelephoneNumber": ((2, LCID, 4, 0),()),
	}

class IADsFileService(DispatchBaseClass):
	CLSID = IID('{A89D1900-31CA-11CF-A98A-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Dependencies": (26, 2, (12, 0), (), "Dependencies", None),
		"Description": (33, 2, (8, 0), (), "Description", None),
		"DisplayName": (16, 2, (8, 0), (), "DisplayName", None),
		"ErrorControl": (22, 2, (3, 0), (), "ErrorControl", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"HostComputer": (15, 2, (8, 0), (), "HostComputer", None),
		"LoadOrderGroup": (23, 2, (8, 0), (), "LoadOrderGroup", None),
		"MaxUserCount": (34, 2, (3, 0), (), "MaxUserCount", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Path": (20, 2, (8, 0), (), "Path", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"ServiceAccountName": (24, 2, (8, 0), (), "ServiceAccountName", None),
		"ServiceAccountPath": (25, 2, (8, 0), (), "ServiceAccountPath", None),
		"ServiceType": (18, 2, (3, 0), (), "ServiceType", None),
		"StartType": (19, 2, (3, 0), (), "StartType", None),
		"StartupParameters": (21, 2, (8, 0), (), "StartupParameters", None),
		"Version": (17, 2, (8, 0), (), "Version", None),
	}
	_prop_map_put_ = {
		"Dependencies": ((26, LCID, 4, 0),()),
		"Description": ((33, LCID, 4, 0),()),
		"DisplayName": ((16, LCID, 4, 0),()),
		"ErrorControl": ((22, LCID, 4, 0),()),
		"HostComputer": ((15, LCID, 4, 0),()),
		"LoadOrderGroup": ((23, LCID, 4, 0),()),
		"MaxUserCount": ((34, LCID, 4, 0),()),
		"Path": ((20, LCID, 4, 0),()),
		"ServiceAccountName": ((24, LCID, 4, 0),()),
		"ServiceAccountPath": ((25, LCID, 4, 0),()),
		"ServiceType": ((18, LCID, 4, 0),()),
		"StartType": ((19, LCID, 4, 0),()),
		"StartupParameters": ((21, LCID, 4, 0),()),
		"Version": ((17, LCID, 4, 0),()),
	}

class IADsFileServiceOperations(DispatchBaseClass):
	CLSID = IID('{A02DED10-31CA-11CF-A98A-00AA006BC149}')
	coclass_clsid = None

	def Continue(self):
		return self._oleobj_.InvokeTypes(31, LCID, 1, (24, 0), (),)

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Pause(self):
		return self._oleobj_.InvokeTypes(30, LCID, 1, (24, 0), (),)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	# Result is of type IADsCollection
	def Resources(self):
		ret = self._oleobj_.InvokeTypes(36, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Resources', '{72B945E0-253B-11CF-A988-00AA006BC149}', UnicodeToString=0)
		return ret

	# Result is of type IADsCollection
	def Sessions(self):
		ret = self._oleobj_.InvokeTypes(35, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Sessions', '{72B945E0-253B-11CF-A988-00AA006BC149}', UnicodeToString=0)
		return ret

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	def SetPassword(self, bstrNewPassword=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(32, LCID, 1, (24, 0), ((8, 1),),bstrNewPassword)

	def Start(self):
		return self._oleobj_.InvokeTypes(28, LCID, 1, (24, 0), (),)

	def Stop(self):
		return self._oleobj_.InvokeTypes(29, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Status": (27, 2, (3, 0), (), "Status", None),
	}
	_prop_map_put_ = {
	}

class IADsFileShare(DispatchBaseClass):
	CLSID = IID('{EB6DCAF0-4B83-11CF-A995-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"CurrentUserCount": (15, 2, (3, 0), (), "CurrentUserCount", None),
		"Description": (16, 2, (8, 0), (), "Description", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"HostComputer": (17, 2, (8, 0), (), "HostComputer", None),
		"MaxUserCount": (19, 2, (3, 0), (), "MaxUserCount", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Path": (18, 2, (8, 0), (), "Path", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
		"Description": ((16, LCID, 4, 0),()),
		"HostComputer": ((17, LCID, 4, 0),()),
		"MaxUserCount": ((19, LCID, 4, 0),()),
		"Path": ((18, LCID, 4, 0),()),
	}

class IADsGroup(DispatchBaseClass):
	CLSID = IID('{27636B00-410F-11CF-B1FF-02608C9E7553}')
	coclass_clsid = None

	def Add(self, bstrNewItem=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(18, LCID, 1, (24, 0), ((8, 1),),bstrNewItem)

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def IsMember(self, bstrMember=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(17, LCID, 1, (11, 0), ((8, 1),),bstrMember)

	# Result is of type IADsMembers
	def Members(self):
		ret = self._oleobj_.InvokeTypes(16, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Members', '{451A0030-72EC-11CF-B03B-00AA006E0975}', UnicodeToString=0)
		return ret

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def Remove(self, bstrItemToBeRemoved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(19, LCID, 1, (24, 0), ((8, 1),),bstrItemToBeRemoved)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Description": (15, 2, (8, 0), (), "Description", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
		"Description": ((15, LCID, 4, 0),()),
	}

class IADsHold(DispatchBaseClass):
	CLSID = IID('{B3EB3B37-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{B3AD3E13-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"Amount": (3, 2, (3, 0), (), "Amount", None),
		"ObjectName": (2, 2, (8, 0), (), "ObjectName", None),
	}
	_prop_map_put_ = {
		"Amount": ((3, LCID, 4, 0),()),
		"ObjectName": ((2, LCID, 4, 0),()),
	}

class IADsLargeInteger(DispatchBaseClass):
	CLSID = IID('{9068270B-0939-11D1-8BE1-00C04FD8D503}')
	coclass_clsid = IID('{927971F5-0939-11D1-8BE1-00C04FD8D503}')

	_prop_map_get_ = {
		"HighPart": (2, 2, (3, 0), (), "HighPart", None),
		"LowPart": (3, 2, (3, 0), (), "LowPart", None),
	}
	_prop_map_put_ = {
		"HighPart": ((2, LCID, 4, 0),()),
		"LowPart": ((3, LCID, 4, 0),()),
	}

class IADsLocality(DispatchBaseClass):
	CLSID = IID('{A05E03A2-EFFE-11CF-8ABC-00C04FD8D503}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Description": (15, 2, (8, 0), (), "Description", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"LocalityName": (16, 2, (8, 0), (), "LocalityName", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PostalAddress": (17, 2, (8, 0), (), "PostalAddress", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"SeeAlso": (18, 2, (12, 0), (), "SeeAlso", None),
	}
	_prop_map_put_ = {
		"Description": ((15, LCID, 4, 0),()),
		"LocalityName": ((16, LCID, 4, 0),()),
		"PostalAddress": ((17, LCID, 4, 0),()),
		"SeeAlso": ((18, LCID, 4, 0),()),
	}

class IADsMembers(DispatchBaseClass):
	CLSID = IID('{451A0030-72EC-11CF-B03B-00AA006E0975}')
	coclass_clsid = None

	_prop_map_get_ = {
		"Count": (2, 2, (3, 0), (), "Count", None),
		"Filter": (3, 2, (12, 0), (), "Filter", None),
	}
	_prop_map_put_ = {
		"Filter": ((3, LCID, 4, 0),()),
	}
	def __iter__(self):
		"Return a Python iterator for this object"
		ob = self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),())
		return win32com.client.util.Iterator(ob)
	def _NewEnum(self):
		"Create an enumerator from this object"
		return win32com.client.util.WrapEnum(self._oleobj_.InvokeTypes(-4,LCID,2,(13, 10),()),None)
	def __getitem__(self, index):
		"Allow this class to be accessed as a collection"
		if not self.__dict__.has_key('_enum_'):
			self.__dict__['_enum_'] = self._NewEnum()
		return self._enum_.__getitem__(index)
	#This class has Count() property - allow len(ob) to provide this
	def __len__(self):
		return self._ApplyTypes_(*(2, 2, (3, 0), (), "Count", None))
	#This class has a __len__ - this is needed so 'if object:' always returns TRUE.
	def __nonzero__(self):
		return True

class IADsNameTranslate(DispatchBaseClass):
	CLSID = IID('{B1B272A3-3625-11D1-A3A4-00C04FB950DC}')
	coclass_clsid = IID('{274FAE1F-3626-11D1-A3A4-00C04FB950DC}')

	def Get(self, lnFormatType=defaultNamedNotOptArg):
		# Result is a Unicode object - return as-is for this version of Python
		return self._oleobj_.InvokeTypes(5, LCID, 1, (8, 0), ((3, 1),),lnFormatType)

	def GetEx(self, lnFormatType=defaultNamedNotOptArg):
		return self._ApplyTypes_(7, 1, (12, 0), ((3, 1),), 'GetEx', None,lnFormatType)

	def Init(self, lnSetType=defaultNamedNotOptArg, bstrADsPath=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(2, LCID, 1, (24, 0), ((3, 1), (8, 1)),lnSetType, bstrADsPath)

	def InitEx(self, lnSetType=defaultNamedNotOptArg, bstrADsPath=defaultNamedNotOptArg, bstrUserID=defaultNamedNotOptArg, bstrDomain=defaultNamedNotOptArg, bstrPassword=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(3, LCID, 1, (24, 0), ((3, 1), (8, 1), (8, 1), (8, 1), (8, 1)),lnSetType, bstrADsPath, bstrUserID, bstrDomain, bstrPassword)

	def Set(self, lnSetType=defaultNamedNotOptArg, bstrADsPath=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(4, LCID, 1, (24, 0), ((3, 1), (8, 1)),lnSetType, bstrADsPath)

	def SetEx(self, lnFormatType=defaultNamedNotOptArg, pVar=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(6, LCID, 1, (24, 0), ((3, 1), (12, 1)),lnFormatType, pVar)

	_prop_map_get_ = {
	}
	_prop_map_put_ = {
		"ChaseReferral": ((1, LCID, 4, 0),()),
	}

class IADsNamespaces(DispatchBaseClass):
	CLSID = IID('{28B96BA0-B330-11CF-A9AD-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"DefaultContainer": (1, 2, (8, 0), (), "DefaultContainer", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
		"DefaultContainer": ((1, LCID, 4, 0),()),
	}

class IADsNetAddress(DispatchBaseClass):
	CLSID = IID('{B21A50A9-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{B0B71247-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"Address": (3, 2, (12, 0), (), "Address", None),
		"AddressType": (2, 2, (3, 0), (), "AddressType", None),
	}
	_prop_map_put_ = {
		"Address": ((3, LCID, 4, 0),()),
		"AddressType": ((2, LCID, 4, 0),()),
	}

class IADsO(DispatchBaseClass):
	CLSID = IID('{A1CD2DC6-EFFE-11CF-8ABC-00C04FD8D503}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Description": (15, 2, (8, 0), (), "Description", None),
		"FaxNumber": (19, 2, (8, 0), (), "FaxNumber", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"LocalityName": (16, 2, (8, 0), (), "LocalityName", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PostalAddress": (17, 2, (8, 0), (), "PostalAddress", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"SeeAlso": (20, 2, (12, 0), (), "SeeAlso", None),
		"TelephoneNumber": (18, 2, (8, 0), (), "TelephoneNumber", None),
	}
	_prop_map_put_ = {
		"Description": ((15, LCID, 4, 0),()),
		"FaxNumber": ((19, LCID, 4, 0),()),
		"LocalityName": ((16, LCID, 4, 0),()),
		"PostalAddress": ((17, LCID, 4, 0),()),
		"SeeAlso": ((20, LCID, 4, 0),()),
		"TelephoneNumber": ((18, LCID, 4, 0),()),
	}

class IADsOU(DispatchBaseClass):
	CLSID = IID('{A2F733B8-EFFE-11CF-8ABC-00C04FD8D503}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"BusinessCategory": (21, 2, (8, 0), (), "BusinessCategory", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Description": (15, 2, (8, 0), (), "Description", None),
		"FaxNumber": (19, 2, (8, 0), (), "FaxNumber", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"LocalityName": (16, 2, (8, 0), (), "LocalityName", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PostalAddress": (17, 2, (8, 0), (), "PostalAddress", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"SeeAlso": (20, 2, (12, 0), (), "SeeAlso", None),
		"TelephoneNumber": (18, 2, (8, 0), (), "TelephoneNumber", None),
	}
	_prop_map_put_ = {
		"BusinessCategory": ((21, LCID, 4, 0),()),
		"Description": ((15, LCID, 4, 0),()),
		"FaxNumber": ((19, LCID, 4, 0),()),
		"LocalityName": ((16, LCID, 4, 0),()),
		"PostalAddress": ((17, LCID, 4, 0),()),
		"SeeAlso": ((20, LCID, 4, 0),()),
		"TelephoneNumber": ((18, LCID, 4, 0),()),
	}

class IADsObjectOptions(DispatchBaseClass):
	CLSID = IID('{46F14FDA-232B-11D1-A808-00C04FD8D5A8}')
	coclass_clsid = None

	def GetOption(self, lnOption=defaultNamedNotOptArg):
		return self._ApplyTypes_(2, 1, (12, 0), ((3, 1),), 'GetOption', None,lnOption)

	def SetOption(self, lnOption=defaultNamedNotOptArg, vValue=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(3, LCID, 1, (24, 0), ((3, 1), (12, 1)),lnOption, vValue)

	_prop_map_get_ = {
	}
	_prop_map_put_ = {
	}

class IADsOctetList(DispatchBaseClass):
	CLSID = IID('{7B28B80F-4680-11D1-A3B4-00C04FB950DC}')
	coclass_clsid = IID('{1241400F-4680-11D1-A3B4-00C04FB950DC}')

	_prop_map_get_ = {
		"OctetList": (2, 2, (12, 0), (), "OctetList", None),
	}
	_prop_map_put_ = {
		"OctetList": ((2, LCID, 4, 0),()),
	}

class IADsOpenDSObject(DispatchBaseClass):
	CLSID = IID('{DDF2891E-0F9C-11D0-8AD4-00C04FD8D503}')
	coclass_clsid = None

	def OpenDSObject(self, lpszDNName=defaultNamedNotOptArg, lpszUserName=defaultNamedNotOptArg, lpszPassword=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		ret = self._oleobj_.InvokeTypes(1, LCID, 1, (9, 0), ((8, 1), (8, 1), (8, 1), (3, 1)),lpszDNName, lpszUserName, lpszPassword, lnReserved)
		if ret is not None:
			ret = Dispatch(ret, 'OpenDSObject', None, UnicodeToString=0)
		return ret

	_prop_map_get_ = {
	}
	_prop_map_put_ = {
	}

class IADsPath(DispatchBaseClass):
	CLSID = IID('{B287FCD5-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{B2538919-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"Path": (4, 2, (8, 0), (), "Path", None),
		"Type": (2, 2, (3, 0), (), "Type", None),
		"VolumeName": (3, 2, (8, 0), (), "VolumeName", None),
	}
	_prop_map_put_ = {
		"Path": ((4, LCID, 4, 0),()),
		"Type": ((2, LCID, 4, 0),()),
		"VolumeName": ((3, LCID, 4, 0),()),
	}

class IADsPathname(DispatchBaseClass):
	CLSID = IID('{D592AED4-F420-11D0-A36E-00C04FB950DC}')
	coclass_clsid = IID('{080D0D78-F421-11D0-A36E-00C04FB950DC}')

	def AddLeafElement(self, bstrLeafElement=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(7, LCID, 1, (24, 0), ((8, 1),),bstrLeafElement)

	def CopyPath(self):
		ret = self._oleobj_.InvokeTypes(9, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'CopyPath', None, UnicodeToString=0)
		return ret

	def GetElement(self, lnElementIndex=defaultNamedNotOptArg):
		# Result is a Unicode object - return as-is for this version of Python
		return self._oleobj_.InvokeTypes(6, LCID, 1, (8, 0), ((3, 1),),lnElementIndex)

	def GetEscapedElement(self, lnReserved=defaultNamedNotOptArg, bstrInStr=defaultNamedNotOptArg):
		# Result is a Unicode object - return as-is for this version of Python
		return self._oleobj_.InvokeTypes(10, LCID, 1, (8, 0), ((3, 1), (8, 1)),lnReserved, bstrInStr)

	def GetNumElements(self):
		return self._oleobj_.InvokeTypes(5, LCID, 1, (3, 0), (),)

	def RemoveLeafElement(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def Retrieve(self, lnFormatType=defaultNamedNotOptArg):
		# Result is a Unicode object - return as-is for this version of Python
		return self._oleobj_.InvokeTypes(4, LCID, 1, (8, 0), ((3, 1),),lnFormatType)

	def Set(self, bstrADsPath=defaultNamedNotOptArg, lnSetType=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(2, LCID, 1, (24, 0), ((8, 1), (3, 1)),bstrADsPath, lnSetType)

	def SetDisplayType(self, lnDisplayType=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(3, LCID, 1, (24, 0), ((3, 1),),lnDisplayType)

	_prop_map_get_ = {
		"EscapedMode": (11, 2, (3, 0), (), "EscapedMode", None),
	}
	_prop_map_put_ = {
		"EscapedMode": ((11, LCID, 4, 0),()),
	}

class IADsPostalAddress(DispatchBaseClass):
	CLSID = IID('{7ADECF29-4680-11D1-A3B4-00C04FB950DC}')
	coclass_clsid = IID('{0A75AFCD-4680-11D1-A3B4-00C04FB950DC}')

	_prop_map_get_ = {
		"PostalAddress": (2, 2, (12, 0), (), "PostalAddress", None),
	}
	_prop_map_put_ = {
		"PostalAddress": ((2, LCID, 4, 0),()),
	}

class IADsPrintJob(DispatchBaseClass):
	CLSID = IID('{32FB6780-1ED0-11CF-A988-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Description": (20, 2, (8, 0), (), "Description", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"HostPrintQueue": (15, 2, (8, 0), (), "HostPrintQueue", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Notify": (24, 2, (8, 0), (), "Notify", None),
		"NotifyPath": (25, 2, (8, 0), (), "NotifyPath", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Priority": (21, 2, (3, 0), (), "Priority", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Size": (234, 2, (3, 0), (), "Size", None),
		"StartTime": (22, 2, (7, 0), (), "StartTime", None),
		"TimeSubmitted": (18, 2, (7, 0), (), "TimeSubmitted", None),
		"TotalPages": (19, 2, (3, 0), (), "TotalPages", None),
		"UntilTime": (23, 2, (7, 0), (), "UntilTime", None),
		"User": (16, 2, (8, 0), (), "User", None),
		"UserPath": (17, 2, (8, 0), (), "UserPath", None),
	}
	_prop_map_put_ = {
		"Description": ((20, LCID, 4, 0),()),
		"Notify": ((24, LCID, 4, 0),()),
		"NotifyPath": ((25, LCID, 4, 0),()),
		"Priority": ((21, LCID, 4, 0),()),
		"StartTime": ((22, LCID, 4, 0),()),
		"UntilTime": ((23, LCID, 4, 0),()),
	}

class IADsPrintJobOperations(DispatchBaseClass):
	CLSID = IID('{9A52DB30-1ECF-11CF-A988-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Pause(self):
		return self._oleobj_.InvokeTypes(30, LCID, 1, (24, 0), (),)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def Resume(self):
		return self._oleobj_.InvokeTypes(31, LCID, 1, (24, 0), (),)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"PagesPrinted": (28, 2, (3, 0), (), "PagesPrinted", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Position": (29, 2, (3, 0), (), "Position", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Status": (26, 2, (3, 0), (), "Status", None),
		"TimeElapsed": (27, 2, (3, 0), (), "TimeElapsed", None),
	}
	_prop_map_put_ = {
		"Position": ((29, LCID, 4, 0),()),
	}

class IADsPrintQueue(DispatchBaseClass):
	CLSID = IID('{B15160D0-1226-11CF-A985-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"BannerPage": (25, 2, (8, 0), (), "BannerPage", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Datatype": (17, 2, (8, 0), (), "Datatype", None),
		"DefaultJobPriority": (23, 2, (3, 0), (), "DefaultJobPriority", None),
		"Description": (19, 2, (8, 0), (), "Description", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Location": (20, 2, (8, 0), (), "Location", None),
		"Model": (16, 2, (8, 0), (), "Model", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"NetAddresses": (27, 2, (12, 0), (), "NetAddresses", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PrintDevices": (26, 2, (12, 0), (), "PrintDevices", None),
		"PrintProcessor": (18, 2, (8, 0), (), "PrintProcessor", None),
		"PrinterPath": (15, 2, (8, 0), (), "PrinterPath", None),
		"Priority": (24, 2, (3, 0), (), "Priority", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"StartTime": (21, 2, (7, 0), (), "StartTime", None),
		"UntilTime": (22, 2, (7, 0), (), "UntilTime", None),
	}
	_prop_map_put_ = {
		"BannerPage": ((25, LCID, 4, 0),()),
		"Datatype": ((17, LCID, 4, 0),()),
		"DefaultJobPriority": ((23, LCID, 4, 0),()),
		"Description": ((19, LCID, 4, 0),()),
		"Location": ((20, LCID, 4, 0),()),
		"Model": ((16, LCID, 4, 0),()),
		"NetAddresses": ((27, LCID, 4, 0),()),
		"PrintDevices": ((26, LCID, 4, 0),()),
		"PrintProcessor": ((18, LCID, 4, 0),()),
		"PrinterPath": ((15, LCID, 4, 0),()),
		"Priority": ((24, LCID, 4, 0),()),
		"StartTime": ((21, LCID, 4, 0),()),
		"UntilTime": ((22, LCID, 4, 0),()),
	}

class IADsPrintQueueOperations(DispatchBaseClass):
	CLSID = IID('{124BE5C0-156E-11CF-A986-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Pause(self):
		return self._oleobj_.InvokeTypes(29, LCID, 1, (24, 0), (),)

	# Result is of type IADsCollection
	def PrintJobs(self):
		ret = self._oleobj_.InvokeTypes(28, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'PrintJobs', '{72B945E0-253B-11CF-A988-00AA006BC149}', UnicodeToString=0)
		return ret

	def Purge(self):
		return self._oleobj_.InvokeTypes(31, LCID, 1, (24, 0), (),)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def Resume(self):
		return self._oleobj_.InvokeTypes(30, LCID, 1, (24, 0), (),)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Status": (27, 2, (3, 0), (), "Status", None),
	}
	_prop_map_put_ = {
	}

class IADsProperty(DispatchBaseClass):
	CLSID = IID('{C8F93DD3-4AE0-11CF-9E73-00AA004A5691}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	# Result is of type IADsCollection
	def Qualifiers(self):
		ret = self._oleobj_.InvokeTypes(22, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Qualifiers', '{72B945E0-253B-11CF-A988-00AA006BC149}', UnicodeToString=0)
		return ret

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"MaxRange": (19, 2, (3, 0), (), "MaxRange", None),
		"MinRange": (20, 2, (3, 0), (), "MinRange", None),
		"MultiValued": (21, 2, (11, 0), (), "MultiValued", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"OID": (17, 2, (8, 0), (), "OID", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Syntax": (18, 2, (8, 0), (), "Syntax", None),
	}
	_prop_map_put_ = {
		"MaxRange": ((19, LCID, 4, 0),()),
		"MinRange": ((20, LCID, 4, 0),()),
		"MultiValued": ((21, LCID, 4, 0),()),
		"OID": ((17, LCID, 4, 0),()),
		"Syntax": ((18, LCID, 4, 0),()),
	}

class IADsPropertyEntry(DispatchBaseClass):
	CLSID = IID('{05792C8E-941F-11D0-8529-00C04FD8D503}')
	coclass_clsid = IID('{72D3EDC2-A4C4-11D0-8533-00C04FD8D503}')

	def Clear(self):
		return self._oleobj_.InvokeTypes(1, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsType": (3, 2, (3, 0), (), "ADsType", None),
		"ControlCode": (4, 2, (3, 0), (), "ControlCode", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Values": (5, 2, (12, 0), (), "Values", None),
	}
	_prop_map_put_ = {
		"ADsType": ((3, LCID, 4, 0),()),
		"ControlCode": ((4, LCID, 4, 0),()),
		"Name": ((2, LCID, 4, 0),()),
		"Values": ((5, LCID, 4, 0),()),
	}

class IADsPropertyList(DispatchBaseClass):
	CLSID = IID('{C6F602B6-8F69-11D0-8528-00C04FD8D503}')
	coclass_clsid = None

	def GetPropertyItem(self, bstrName=defaultNamedNotOptArg, lnADsType=defaultNamedNotOptArg):
		return self._ApplyTypes_(6, 1, (12, 0), ((8, 1), (3, 1)), 'GetPropertyItem', None,bstrName, lnADsType)

	def Item(self, varIndex=defaultNamedNotOptArg):
		return self._ApplyTypes_(0, 1, (12, 0), ((12, 1),), 'Item', None,varIndex)

	def Next(self):
		return self._ApplyTypes_(3, 1, (12, 0), (), 'Next', None,)

	def PurgePropertyList(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	def PutPropertyItem(self, varData=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(7, LCID, 1, (24, 0), ((12, 1),),varData)

	def Reset(self):
		return self._oleobj_.InvokeTypes(5, LCID, 1, (24, 0), (),)

	def ResetPropertyItem(self, varEntry=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), ((12, 1),),varEntry)

	def Skip(self, cElements=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(4, LCID, 1, (24, 0), ((3, 1),),cElements)

	_prop_map_get_ = {
		"PropertyCount": (2, 2, (3, 0), (), "PropertyCount", None),
	}
	_prop_map_put_ = {
	}
	# Default method for this class is 'Item'
	def __call__(self, varIndex=defaultNamedNotOptArg):
		return self._ApplyTypes_(0, 1, (12, 0), ((12, 1),), '__call__', None,varIndex)

	# str(ob) and int(ob) will use __call__
	def __unicode__(self, *args):
		try:
			return unicode(self.__call__(*args))
		except pythoncom.com_error:
			return repr(self)
	def __str__(self, *args):
		return str(self.__unicode__(*args))
	def __int__(self, *args):
		return int(self.__call__(*args))

class IADsPropertyValue(DispatchBaseClass):
	CLSID = IID('{79FA9AD0-A97C-11D0-8534-00C04FD8D503}')
	coclass_clsid = IID('{7B9E38B0-A97C-11D0-8534-00C04FD8D503}')

	def Clear(self):
		return self._oleobj_.InvokeTypes(1, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsType": (2, 2, (3, 0), (), "ADsType", None),
		"Boolean": (8, 2, (3, 0), (), "Boolean", None),
		"CaseExactString": (4, 2, (8, 0), (), "CaseExactString", None),
		"CaseIgnoreString": (5, 2, (8, 0), (), "CaseIgnoreString", None),
		"DNString": (3, 2, (8, 0), (), "DNString", None),
		"Integer": (9, 2, (3, 0), (), "Integer", None),
		"LargeInteger": (12, 2, (9, 0), (), "LargeInteger", None),
		"NumericString": (7, 2, (8, 0), (), "NumericString", None),
		"OctetString": (10, 2, (12, 0), (), "OctetString", None),
		"PrintableString": (6, 2, (8, 0), (), "PrintableString", None),
		"SecurityDescriptor": (11, 2, (9, 0), (), "SecurityDescriptor", None),
		"UTCTime": (13, 2, (7, 0), (), "UTCTime", None),
	}
	_prop_map_put_ = {
		"ADsType": ((2, LCID, 4, 0),()),
		"Boolean": ((8, LCID, 4, 0),()),
		"CaseExactString": ((4, LCID, 4, 0),()),
		"CaseIgnoreString": ((5, LCID, 4, 0),()),
		"DNString": ((3, LCID, 4, 0),()),
		"Integer": ((9, LCID, 4, 0),()),
		"LargeInteger": ((12, LCID, 4, 0),()),
		"NumericString": ((7, LCID, 4, 0),()),
		"OctetString": ((10, LCID, 4, 0),()),
		"PrintableString": ((6, LCID, 4, 0),()),
		"SecurityDescriptor": ((11, LCID, 4, 0),()),
		"UTCTime": ((13, LCID, 4, 0),()),
	}

class IADsPropertyValue2(DispatchBaseClass):
	CLSID = IID('{306E831C-5BC7-11D1-A3B8-00C04FB950DC}')
	coclass_clsid = None

	def GetObjectProperty(self, lnADsType=defaultNamedNotOptArg):
		return self._ApplyTypes_(1, 1, (12, 0), ((16387, 3),), 'GetObjectProperty', None,lnADsType)

	def PutObjectProperty(self, lnADsType=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(2, LCID, 1, (24, 0), ((3, 1), (12, 1)),lnADsType, vProp)

	_prop_map_get_ = {
	}
	_prop_map_put_ = {
	}

class IADsReplicaPointer(DispatchBaseClass):
	CLSID = IID('{F60FB803-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{F5D1BADF-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"Count": (5, 2, (3, 0), (), "Count", None),
		"ReplicaAddressHints": (6, 2, (12, 0), (), "ReplicaAddressHints", None),
		"ReplicaNumber": (4, 2, (3, 0), (), "ReplicaNumber", None),
		"ReplicaType": (3, 2, (3, 0), (), "ReplicaType", None),
		"ServerName": (2, 2, (8, 0), (), "ServerName", None),
	}
	_prop_map_put_ = {
		"Count": ((5, LCID, 4, 0),()),
		"ReplicaAddressHints": ((6, LCID, 4, 0),()),
		"ReplicaNumber": ((4, LCID, 4, 0),()),
		"ReplicaType": ((3, LCID, 4, 0),()),
		"ServerName": ((2, LCID, 4, 0),()),
	}
	#This class has Count() property - allow len(ob) to provide this
	def __len__(self):
		return self._ApplyTypes_(*(5, 2, (3, 0), (), "Count", None))
	#This class has a __len__ - this is needed so 'if object:' always returns TRUE.
	def __nonzero__(self):
		return True

class IADsResource(DispatchBaseClass):
	CLSID = IID('{34A05B20-4AAB-11CF-AE2C-00AA006EBFB9}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"LockCount": (18, 2, (3, 0), (), "LockCount", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Path": (17, 2, (8, 0), (), "Path", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"User": (15, 2, (8, 0), (), "User", None),
		"UserPath": (16, 2, (8, 0), (), "UserPath", None),
	}
	_prop_map_put_ = {
	}

class IADsSecurityDescriptor(DispatchBaseClass):
	CLSID = IID('{B8C787CA-9BDD-11D0-852C-00C04FD8D503}')
	coclass_clsid = IID('{B958F73C-9BDD-11D0-852C-00C04FD8D503}')

	def CopySecurityDescriptor(self):
		ret = self._oleobj_.InvokeTypes(12, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'CopySecurityDescriptor', None, UnicodeToString=0)
		return ret

	_prop_map_get_ = {
		"Control": (3, 2, (3, 0), (), "Control", None),
		"DaclDefaulted": (9, 2, (11, 0), (), "DaclDefaulted", None),
		"DiscretionaryAcl": (8, 2, (9, 0), (), "DiscretionaryAcl", None),
		"Group": (6, 2, (8, 0), (), "Group", None),
		"GroupDefaulted": (7, 2, (11, 0), (), "GroupDefaulted", None),
		"Owner": (4, 2, (8, 0), (), "Owner", None),
		"OwnerDefaulted": (5, 2, (11, 0), (), "OwnerDefaulted", None),
		"Revision": (2, 2, (3, 0), (), "Revision", None),
		"SaclDefaulted": (11, 2, (11, 0), (), "SaclDefaulted", None),
		"SystemAcl": (10, 2, (9, 0), (), "SystemAcl", None),
	}
	_prop_map_put_ = {
		"Control": ((3, LCID, 4, 0),()),
		"DaclDefaulted": ((9, LCID, 4, 0),()),
		"DiscretionaryAcl": ((8, LCID, 4, 0),()),
		"Group": ((6, LCID, 4, 0),()),
		"GroupDefaulted": ((7, LCID, 4, 0),()),
		"Owner": ((4, LCID, 4, 0),()),
		"OwnerDefaulted": ((5, LCID, 4, 0),()),
		"Revision": ((2, LCID, 4, 0),()),
		"SaclDefaulted": ((11, LCID, 4, 0),()),
		"SystemAcl": ((10, LCID, 4, 0),()),
	}

class IADsSecurityUtility(DispatchBaseClass):
	CLSID = IID('{A63251B2-5F21-474B-AB52-4A8EFAD10895}')
	coclass_clsid = IID('{F270C64A-FFB8-4AE4-85FE-3A75E5347966}')

	def ConvertSecurityDescriptor(self, varSD=defaultNamedNotOptArg, lDataFormat=defaultNamedNotOptArg, lOutFormat=defaultNamedNotOptArg):
		return self._ApplyTypes_(4, 1, (12, 0), ((12, 1), (3, 1), (3, 1)), 'ConvertSecurityDescriptor', None,varSD, lDataFormat, lOutFormat)

	def GetSecurityDescriptor(self, varPath=defaultNamedNotOptArg, lPathFormat=defaultNamedNotOptArg, lFormat=defaultNamedNotOptArg):
		return self._ApplyTypes_(2, 1, (12, 0), ((12, 1), (3, 1), (3, 1)), 'GetSecurityDescriptor', None,varPath, lPathFormat, lFormat)

	def SetSecurityDescriptor(self, varPath=defaultNamedNotOptArg, lPathFormat=defaultNamedNotOptArg, varData=defaultNamedNotOptArg, lDataFormat=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(3, LCID, 1, (24, 0), ((12, 1), (3, 1), (12, 1), (3, 1)),varPath, lPathFormat, varData, lDataFormat)

	_prop_map_get_ = {
		"SecurityMask": (5, 2, (3, 0), (), "SecurityMask", None),
	}
	_prop_map_put_ = {
		"SecurityMask": ((5, LCID, 4, 0),()),
	}

class IADsService(DispatchBaseClass):
	CLSID = IID('{68AF66E0-31CA-11CF-A98A-00AA006BC149}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Dependencies": (26, 2, (12, 0), (), "Dependencies", None),
		"DisplayName": (16, 2, (8, 0), (), "DisplayName", None),
		"ErrorControl": (22, 2, (3, 0), (), "ErrorControl", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"HostComputer": (15, 2, (8, 0), (), "HostComputer", None),
		"LoadOrderGroup": (23, 2, (8, 0), (), "LoadOrderGroup", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Path": (20, 2, (8, 0), (), "Path", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"ServiceAccountName": (24, 2, (8, 0), (), "ServiceAccountName", None),
		"ServiceAccountPath": (25, 2, (8, 0), (), "ServiceAccountPath", None),
		"ServiceType": (18, 2, (3, 0), (), "ServiceType", None),
		"StartType": (19, 2, (3, 0), (), "StartType", None),
		"StartupParameters": (21, 2, (8, 0), (), "StartupParameters", None),
		"Version": (17, 2, (8, 0), (), "Version", None),
	}
	_prop_map_put_ = {
		"Dependencies": ((26, LCID, 4, 0),()),
		"DisplayName": ((16, LCID, 4, 0),()),
		"ErrorControl": ((22, LCID, 4, 0),()),
		"HostComputer": ((15, LCID, 4, 0),()),
		"LoadOrderGroup": ((23, LCID, 4, 0),()),
		"Path": ((20, LCID, 4, 0),()),
		"ServiceAccountName": ((24, LCID, 4, 0),()),
		"ServiceAccountPath": ((25, LCID, 4, 0),()),
		"ServiceType": ((18, LCID, 4, 0),()),
		"StartType": ((19, LCID, 4, 0),()),
		"StartupParameters": ((21, LCID, 4, 0),()),
		"Version": ((17, LCID, 4, 0),()),
	}

class IADsServiceOperations(DispatchBaseClass):
	CLSID = IID('{5D7B33F0-31CA-11CF-A98A-00AA006BC149}')
	coclass_clsid = None

	def Continue(self):
		return self._oleobj_.InvokeTypes(31, LCID, 1, (24, 0), (),)

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Pause(self):
		return self._oleobj_.InvokeTypes(30, LCID, 1, (24, 0), (),)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	def SetPassword(self, bstrNewPassword=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(32, LCID, 1, (24, 0), ((8, 1),),bstrNewPassword)

	def Start(self):
		return self._oleobj_.InvokeTypes(28, LCID, 1, (24, 0), (),)

	def Stop(self):
		return self._oleobj_.InvokeTypes(29, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"Status": (27, 2, (3, 0), (), "Status", None),
	}
	_prop_map_put_ = {
	}

class IADsSession(DispatchBaseClass):
	CLSID = IID('{398B7DA0-4AAB-11CF-AE2C-00AA006EBFB9}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Computer": (17, 2, (8, 0), (), "Computer", None),
		"ComputerPath": (18, 2, (8, 0), (), "ComputerPath", None),
		"ConnectTime": (19, 2, (3, 0), (), "ConnectTime", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"IdleTime": (20, 2, (3, 0), (), "IdleTime", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"User": (15, 2, (8, 0), (), "User", None),
		"UserPath": (16, 2, (8, 0), (), "UserPath", None),
	}
	_prop_map_put_ = {
	}

class IADsSyntax(DispatchBaseClass):
	CLSID = IID('{C8F93DD2-4AE0-11CF-9E73-00AA004A5691}')
	coclass_clsid = None

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"OleAutoDataType": (15, 2, (3, 0), (), "OleAutoDataType", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
	}
	_prop_map_put_ = {
		"OleAutoDataType": ((15, LCID, 4, 0),()),
	}

class IADsTimestamp(DispatchBaseClass):
	CLSID = IID('{B2F5A901-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{B2BED2EB-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"EventID": (3, 2, (3, 0), (), "EventID", None),
		"WholeSeconds": (2, 2, (3, 0), (), "WholeSeconds", None),
	}
	_prop_map_put_ = {
		"EventID": ((3, LCID, 4, 0),()),
		"WholeSeconds": ((2, LCID, 4, 0),()),
	}

class IADsTypedName(DispatchBaseClass):
	CLSID = IID('{B371A349-4080-11D1-A3AC-00C04FB950DC}')
	coclass_clsid = IID('{B33143CB-4080-11D1-A3AC-00C04FB950DC}')

	_prop_map_get_ = {
		"Interval": (4, 2, (3, 0), (), "Interval", None),
		"Level": (3, 2, (3, 0), (), "Level", None),
		"ObjectName": (2, 2, (8, 0), (), "ObjectName", None),
	}
	_prop_map_put_ = {
		"Interval": ((4, LCID, 4, 0),()),
		"Level": ((3, LCID, 4, 0),()),
		"ObjectName": ((2, LCID, 4, 0),()),
	}

class IADsUser(DispatchBaseClass):
	CLSID = IID('{3E37E320-17E2-11CF-ABC4-02608C9E7553}')
	coclass_clsid = None

	def ChangePassword(self, bstrOldPassword=defaultNamedNotOptArg, bstrNewPassword=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(68, LCID, 1, (24, 0), ((8, 1), (8, 1)),bstrOldPassword, bstrNewPassword)

	def Get(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(10, 1, (12, 0), ((8, 1),), 'Get', None,bstrName)

	def GetEx(self, bstrName=defaultNamedNotOptArg):
		return self._ApplyTypes_(12, 1, (12, 0), ((8, 1),), 'GetEx', None,bstrName)

	def GetInfo(self):
		return self._oleobj_.InvokeTypes(8, LCID, 1, (24, 0), (),)

	def GetInfoEx(self, vProperties=defaultNamedNotOptArg, lnReserved=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(14, LCID, 1, (24, 0), ((12, 1), (3, 1)),vProperties, lnReserved)

	# Result is of type IADsMembers
	def Groups(self):
		ret = self._oleobj_.InvokeTypes(66, LCID, 1, (9, 0), (),)
		if ret is not None:
			ret = Dispatch(ret, 'Groups', '{451A0030-72EC-11CF-B03B-00AA006E0975}', UnicodeToString=0)
		return ret

	def Put(self, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1), (12, 1)),bstrName, vProp)

	def PutEx(self, lnControlCode=defaultNamedNotOptArg, bstrName=defaultNamedNotOptArg, vProp=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(13, LCID, 1, (24, 0), ((3, 1), (8, 1), (12, 1)),lnControlCode, bstrName, vProp)

	def SetInfo(self):
		return self._oleobj_.InvokeTypes(9, LCID, 1, (24, 0), (),)

	def SetPassword(self, NewPassword=defaultNamedNotOptArg):
		return self._oleobj_.InvokeTypes(67, LCID, 1, (24, 0), ((8, 1),),NewPassword)

	_prop_map_get_ = {
		"ADsPath": (5, 2, (8, 0), (), "ADsPath", None),
		"AccountDisabled": (37, 2, (11, 0), (), "AccountDisabled", None),
		"AccountExpirationDate": (38, 2, (7, 0), (), "AccountExpirationDate", None),
		"BadLoginAddress": (53, 2, (8, 0), (), "BadLoginAddress", None),
		"BadLoginCount": (54, 2, (3, 0), (), "BadLoginCount", None),
		"Class": (3, 2, (8, 0), (), "Class", None),
		"Department": (122, 2, (8, 0), (), "Department", None),
		"Description": (15, 2, (8, 0), (), "Description", None),
		"Division": (19, 2, (8, 0), (), "Division", None),
		"EmailAddress": (60, 2, (8, 0), (), "EmailAddress", None),
		"EmployeeID": (20, 2, (8, 0), (), "EmployeeID", None),
		"FaxNumber": (16, 2, (12, 0), (), "FaxNumber", None),
		"FirstName": (22, 2, (8, 0), (), "FirstName", None),
		"FullName": (23, 2, (8, 0), (), "FullName", None),
		"GUID": (4, 2, (8, 0), (), "GUID", None),
		"GraceLoginsAllowed": (41, 2, (3, 0), (), "GraceLoginsAllowed", None),
		"GraceLoginsRemaining": (42, 2, (3, 0), (), "GraceLoginsRemaining", None),
		"HomeDirectory": (61, 2, (8, 0), (), "HomeDirectory", None),
		"HomePage": (120, 2, (8, 0), (), "HomePage", None),
		"IsAccountLocked": (43, 2, (11, 0), (), "IsAccountLocked", None),
		"Languages": (62, 2, (12, 0), (), "Languages", None),
		"LastFailedLogin": (58, 2, (7, 0), (), "LastFailedLogin", None),
		"LastLogin": (56, 2, (7, 0), (), "LastLogin", None),
		"LastLogoff": (57, 2, (7, 0), (), "LastLogoff", None),
		"LastName": (25, 2, (8, 0), (), "LastName", None),
		"LoginHours": (45, 2, (12, 0), (), "LoginHours", None),
		"LoginScript": (64, 2, (8, 0), (), "LoginScript", None),
		"LoginWorkstations": (46, 2, (12, 0), (), "LoginWorkstations", None),
		"Manager": (26, 2, (8, 0), (), "Manager", None),
		"MaxLogins": (47, 2, (3, 0), (), "MaxLogins", None),
		"MaxStorage": (48, 2, (3, 0), (), "MaxStorage", None),
		"Name": (2, 2, (8, 0), (), "Name", None),
		"NamePrefix": (114, 2, (8, 0), (), "NamePrefix", None),
		"NameSuffix": (115, 2, (8, 0), (), "NameSuffix", None),
		"OfficeLocations": (28, 2, (12, 0), (), "OfficeLocations", None),
		"OtherName": (27, 2, (8, 0), (), "OtherName", None),
		"Parent": (6, 2, (8, 0), (), "Parent", None),
		"PasswordExpirationDate": (49, 2, (7, 0), (), "PasswordExpirationDate", None),
		"PasswordLastChanged": (59, 2, (7, 0), (), "PasswordLastChanged", None),
		"PasswordMinimumLength": (50, 2, (3, 0), (), "PasswordMinimumLength", None),
		"PasswordRequired": (51, 2, (11, 0), (), "PasswordRequired", None),
		"Picture": (65, 2, (12, 0), (), "Picture", None),
		"PostalAddresses": (30, 2, (12, 0), (), "PostalAddresses", None),
		"PostalCodes": (31, 2, (12, 0), (), "PostalCodes", None),
		"Profile": (63, 2, (8, 0), (), "Profile", None),
		"RequireUniquePassword": (52, 2, (11, 0), (), "RequireUniquePassword", None),
		"Schema": (7, 2, (8, 0), (), "Schema", None),
		"SeeAlso": (117, 2, (12, 0), (), "SeeAlso", None),
		"TelephoneHome": (32, 2, (12, 0), (), "TelephoneHome", None),
		"TelephoneMobile": (33, 2, (12, 0), (), "TelephoneMobile", None),
		"TelephoneNumber": (34, 2, (12, 0), (), "TelephoneNumber", None),
		"TelephonePager": (17, 2, (12, 0), (), "TelephonePager", None),
		"Title": (36, 2, (8, 0), (), "Title", None),
	}
	_prop_map_put_ = {
		"AccountDisabled": ((37, LCID, 4, 0),()),
		"AccountExpirationDate": ((38, LCID, 4, 0),()),
		"Department": ((122, LCID, 4, 0),()),
		"Description": ((15, LCID, 4, 0),()),
		"Division": ((19, LCID, 4, 0),()),
		"EmailAddress": ((60, LCID, 4, 0),()),
		"EmployeeID": ((20, LCID, 4, 0),()),
		"FaxNumber": ((16, LCID, 4, 0),()),
		"FirstName": ((22, LCID, 4, 0),()),
		"FullName": ((23, LCID, 4, 0),()),
		"GraceLoginsAllowed": ((41, LCID, 4, 0),()),
		"GraceLoginsRemaining": ((42, LCID, 4, 0),()),
		"HomeDirectory": ((61, LCID, 4, 0),()),
		"HomePage": ((120, LCID, 4, 0),()),
		"IsAccountLocked": ((43, LCID, 4, 0),()),
		"Languages": ((62, LCID, 4, 0),()),
		"LastName": ((25, LCID, 4, 0),()),
		"LoginHours": ((45, LCID, 4, 0),()),
		"LoginScript": ((64, LCID, 4, 0),()),
		"LoginWorkstations": ((46, LCID, 4, 0),()),
		"Manager": ((26, LCID, 4, 0),()),
		"MaxLogins": ((47, LCID, 4, 0),()),
		"MaxStorage": ((48, LCID, 4, 0),()),
		"NamePrefix": ((114, LCID, 4, 0),()),
		"NameSuffix": ((115, LCID, 4, 0),()),
		"OfficeLocations": ((28, LCID, 4, 0),()),
		"OtherName": ((27, LCID, 4, 0),()),
		"PasswordExpirationDate": ((49, LCID, 4, 0),()),
		"PasswordMinimumLength": ((50, LCID, 4, 0),()),
		"PasswordRequired": ((51, LCID, 4, 0),()),
		"Picture": ((65, LCID, 4, 0),()),
		"PostalAddresses": ((30, LCID, 4, 0),()),
		"PostalCodes": ((31, LCID, 4, 0),()),
		"Profile": ((63, LCID, 4, 0),()),
		"RequireUniquePassword": ((52, LCID, 4, 0),()),
		"SeeAlso": ((117, LCID, 4, 0),()),
		"TelephoneHome": ((32, LCID, 4, 0),()),
		"TelephoneMobile": ((33, LCID, 4, 0),()),
		"TelephoneNumber": ((34, LCID, 4, 0),()),
		"TelephonePager": ((17, LCID, 4, 0),()),
		"Title": ((36, LCID, 4, 0),()),
	}

class IADsWinNTSystemInfo(DispatchBaseClass):
	CLSID = IID('{6C6D65DC-AFD1-11D2-9CB9-0000F87A369E}')
	coclass_clsid = IID('{66182EC4-AFD1-11D2-9CB9-0000F87A369E}')

	_prop_map_get_ = {
		"ComputerName": (3, 2, (8, 0), (), "ComputerName", None),
		"DomainName": (4, 2, (8, 0), (), "DomainName", None),
		"PDC": (5, 2, (8, 0), (), "PDC", None),
		"UserName": (2, 2, (8, 0), (), "UserName", None),
	}
	_prop_map_put_ = {
	}

from win32com.client import CoClassBaseClass
# This CoClass is known by the name 'ADSystemInfo'
class ADSystemInfo(CoClassBaseClass): # A CoClass
	CLSID = IID('{50B6327F-AFD1-11D2-9CB9-0000F87A369E}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsADSystemInfo,
	]
	default_interface = IADsADSystemInfo

# This CoClass is known by the name 'ADsSecurityUtility'
class ADsSecurityUtility(CoClassBaseClass): # A CoClass
	CLSID = IID('{F270C64A-FFB8-4AE4-85FE-3A75E5347966}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsSecurityUtility,
	]
	default_interface = IADsSecurityUtility

# This CoClass is known by the name 'AccessControlEntry'
class AccessControlEntry(CoClassBaseClass): # A CoClass
	CLSID = IID('{B75AC000-9BDD-11D0-852C-00C04FD8D503}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsAccessControlEntry,
	]
	default_interface = IADsAccessControlEntry

# This CoClass is known by the name 'AccessControlList'
class AccessControlList(CoClassBaseClass): # A CoClass
	CLSID = IID('{B85EA052-9BDD-11D0-852C-00C04FD8D503}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsAccessControlList,
	]
	default_interface = IADsAccessControlList

# This CoClass is known by the name 'BackLink'
class BackLink(CoClassBaseClass): # A CoClass
	CLSID = IID('{FCBF906F-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsBackLink,
	]
	default_interface = IADsBackLink

# This CoClass is known by the name 'CaseIgnoreList'
class CaseIgnoreList(CoClassBaseClass): # A CoClass
	CLSID = IID('{15F88A55-4680-11D1-A3B4-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsCaseIgnoreList,
	]
	default_interface = IADsCaseIgnoreList

# This CoClass is known by the name 'DNWithBinary'
class DNWithBinary(CoClassBaseClass): # A CoClass
	CLSID = IID('{7E99C0A3-F935-11D2-BA96-00C04FB6D0D1}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsDNWithBinary,
	]
	default_interface = IADsDNWithBinary

# This CoClass is known by the name 'DNWithString'
class DNWithString(CoClassBaseClass): # A CoClass
	CLSID = IID('{334857CC-F934-11D2-BA96-00C04FB6D0D1}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsDNWithString,
	]
	default_interface = IADsDNWithString

# This CoClass is known by the name 'Email'
class Email(CoClassBaseClass): # A CoClass
	CLSID = IID('{8F92A857-478E-11D1-A3B4-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsEmail,
	]
	default_interface = IADsEmail

# This CoClass is known by the name 'FaxNumber'
class FaxNumber(CoClassBaseClass): # A CoClass
	CLSID = IID('{A5062215-4681-11D1-A3B4-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsFaxNumber,
	]
	default_interface = IADsFaxNumber

# This CoClass is known by the name 'Hold'
class Hold(CoClassBaseClass): # A CoClass
	CLSID = IID('{B3AD3E13-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsHold,
	]
	default_interface = IADsHold

# This CoClass is known by the name 'LargeInteger'
class LargeInteger(CoClassBaseClass): # A CoClass
	CLSID = IID('{927971F5-0939-11D1-8BE1-00C04FD8D503}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsLargeInteger,
	]
	default_interface = IADsLargeInteger

# This CoClass is known by the name 'NameTranslate'
class NameTranslate(CoClassBaseClass): # A CoClass
	CLSID = IID('{274FAE1F-3626-11D1-A3A4-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsNameTranslate,
	]
	default_interface = IADsNameTranslate

# This CoClass is known by the name 'NetAddress'
class NetAddress(CoClassBaseClass): # A CoClass
	CLSID = IID('{B0B71247-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsNetAddress,
	]
	default_interface = IADsNetAddress

# This CoClass is known by the name 'OctetList'
class OctetList(CoClassBaseClass): # A CoClass
	CLSID = IID('{1241400F-4680-11D1-A3B4-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsOctetList,
	]
	default_interface = IADsOctetList

# This CoClass is known by the name 'Path'
class Path(CoClassBaseClass): # A CoClass
	CLSID = IID('{B2538919-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsPath,
	]
	default_interface = IADsPath

# This CoClass is known by the name 'Pathname'
class Pathname(CoClassBaseClass): # A CoClass
	CLSID = IID('{080D0D78-F421-11D0-A36E-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsPathname,
	]
	default_interface = IADsPathname

# This CoClass is known by the name 'PostalAddress'
class PostalAddress(CoClassBaseClass): # A CoClass
	CLSID = IID('{0A75AFCD-4680-11D1-A3B4-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsPostalAddress,
	]
	default_interface = IADsPostalAddress

# This CoClass is known by the name 'PropertyEntry'
class PropertyEntry(CoClassBaseClass): # A CoClass
	CLSID = IID('{72D3EDC2-A4C4-11D0-8533-00C04FD8D503}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsPropertyEntry,
	]
	default_interface = IADsPropertyEntry

# This CoClass is known by the name 'PropertyValue'
class PropertyValue(CoClassBaseClass): # A CoClass
	CLSID = IID('{7B9E38B0-A97C-11D0-8534-00C04FD8D503}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsPropertyValue,
	]
	default_interface = IADsPropertyValue

# This CoClass is known by the name 'ReplicaPointer'
class ReplicaPointer(CoClassBaseClass): # A CoClass
	CLSID = IID('{F5D1BADF-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsReplicaPointer,
	]
	default_interface = IADsReplicaPointer

# This CoClass is known by the name 'SecurityDescriptor'
class SecurityDescriptor(CoClassBaseClass): # A CoClass
	CLSID = IID('{B958F73C-9BDD-11D0-852C-00C04FD8D503}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsSecurityDescriptor,
	]
	default_interface = IADsSecurityDescriptor

# This CoClass is known by the name 'TimeStamp'
class Timestamp(CoClassBaseClass): # A CoClass
	CLSID = IID('{B2BED2EB-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsTimestamp,
	]
	default_interface = IADsTimestamp

# This CoClass is known by the name 'TypedName'
class TypedName(CoClassBaseClass): # A CoClass
	CLSID = IID('{B33143CB-4080-11D1-A3AC-00C04FB950DC}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsTypedName,
	]
	default_interface = IADsTypedName

# This CoClass is known by the name 'WinNTSystemInfo'
class WinNTSystemInfo(CoClassBaseClass): # A CoClass
	CLSID = IID('{66182EC4-AFD1-11D2-9CB9-0000F87A369E}')
	coclass_sources = [
	]
	coclass_interfaces = [
		IADsWinNTSystemInfo,
	]
	default_interface = IADsWinNTSystemInfo

IADs_vtables_dispatch_ = 1
IADs_vtables_ = [
	(('Name', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('Class', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 0)),
	(('GUID', 'retval'), 4, (4, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('ADsPath', 'retval'), 5, (5, (), [(16392, 10, None, None)], 1, 2, 4, 0, 40, (3, 0, None, None), 0)),
	(('Parent', 'retval'), 6, (6, (), [(16392, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('Schema', 'retval'), 7, (7, (), [(16392, 10, None, None)], 1, 2, 4, 0, 48, (3, 0, None, None), 0)),
	(('GetInfo',), 8, (8, (), [], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
	(('SetInfo',), 9, (9, (), [], 1, 1, 4, 0, 56, (3, 0, None, None), 0)),
	(('Get', 'bstrName', 'pvProp'), 10, (10, (), [(8, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 60, (3, 0, None, None), 0)),
	(('Put', 'bstrName', 'vProp'), 11, (11, (), [(8, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 64, (3, 0, None, None), 0)),
	(('GetEx', 'bstrName', 'pvProp'), 12, (12, (), [(8, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 68, (3, 0, None, None), 0)),
	(('PutEx', 'lnControlCode', 'bstrName', 'vProp'), 13, (13, (), [(3, 1, None, None), (8, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 72, (3, 0, None, None), 0)),
	(('GetInfoEx', 'vProperties', 'lnReserved'), 14, (14, (), [(12, 1, None, None), (3, 1, None, None)], 1, 1, 4, 0, 76, (3, 0, None, None), 0)),
]

IADsADSystemInfo_vtables_dispatch_ = 1
IADsADSystemInfo_vtables_ = [
	(('UserName', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('ComputerName', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 0)),
	(('SiteName', 'retval'), 4, (4, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('DomainShortName', 'retval'), 5, (5, (), [(16392, 10, None, None)], 1, 2, 4, 0, 40, (3, 0, None, None), 0)),
	(('DomainDNSName', 'retval'), 6, (6, (), [(16392, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('ForestDNSName', 'retval'), 7, (7, (), [(16392, 10, None, None)], 1, 2, 4, 0, 48, (3, 0, None, None), 0)),
	(('PDCRoleOwner', 'retval'), 8, (8, (), [(16392, 10, None, None)], 1, 2, 4, 0, 52, (3, 0, None, None), 0)),
	(('SchemaRoleOwner', 'retval'), 9, (9, (), [(16392, 10, None, None)], 1, 2, 4, 0, 56, (3, 0, None, None), 0)),
	(('IsNativeMode', 'retval'), 10, (10, (), [(16395, 10, None, None)], 1, 2, 4, 0, 60, (3, 0, None, None), 0)),
	(('GetAnyDCName', 'pszDCName'), 11, (11, (), [(16392, 10, None, None)], 1, 1, 4, 0, 64, (3, 0, None, None), 0)),
	(('GetDCSiteName', 'szServer', 'pszSiteName'), 12, (12, (), [(8, 1, None, None), (16392, 10, None, None)], 1, 1, 4, 0, 68, (3, 0, None, None), 0)),
	(('RefreshSchemaCache',), 13, (13, (), [], 1, 1, 4, 0, 72, (3, 0, None, None), 0)),
	(('GetTrees', 'pvTrees'), 14, (14, (), [(16396, 10, None, None)], 1, 1, 4, 0, 76, (3, 0, None, None), 0)),
]

IADsAccessControlEntry_vtables_dispatch_ = 1
IADsAccessControlEntry_vtables_ = [
	(('AccessMask', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('AccessMask', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('AceType', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('AceType', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('AceFlags', 'retval'), 4, (4, (), [(16387, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('AceFlags', 'retval'), 4, (4, (), [(3, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
	(('Flags', 'retval'), 5, (5, (), [(16387, 10, None, None)], 1, 2, 4, 0, 52, (3, 0, None, None), 0)),
	(('Flags', 'retval'), 5, (5, (), [(3, 1, None, None)], 1, 4, 4, 0, 56, (3, 0, None, None), 0)),
	(('ObjectType', 'retval'), 6, (6, (), [(16392, 10, None, None)], 1, 2, 4, 0, 60, (3, 0, None, None), 0)),
	(('ObjectType', 'retval'), 6, (6, (), [(8, 1, None, None)], 1, 4, 4, 0, 64, (3, 0, None, None), 0)),
	(('InheritedObjectType', 'retval'), 7, (7, (), [(16392, 10, None, None)], 1, 2, 4, 0, 68, (3, 0, None, None), 0)),
	(('InheritedObjectType', 'retval'), 7, (7, (), [(8, 1, None, None)], 1, 4, 4, 0, 72, (3, 0, None, None), 0)),
	(('Trustee', 'retval'), 8, (8, (), [(16392, 10, None, None)], 1, 2, 4, 0, 76, (3, 0, None, None), 0)),
	(('Trustee', 'retval'), 8, (8, (), [(8, 1, None, None)], 1, 4, 4, 0, 80, (3, 0, None, None), 0)),
]

IADsAccessControlList_vtables_dispatch_ = 1
IADsAccessControlList_vtables_ = [
	(('AclRevision', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('AclRevision', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('AceCount', 'retval'), 4, (4, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('AceCount', 'retval'), 4, (4, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('AddAce', 'pAccessControlEntry'), 5, (5, (), [(9, 1, None, None)], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('RemoveAce', 'pAccessControlEntry'), 6, (6, (), [(9, 1, None, None)], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
	(('CopyAccessList', 'ppAccessControlList'), 7, (7, (), [(16393, 10, None, None)], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
	(('_NewEnum', 'retval'), -4, (-4, (), [(16397, 10, None, None)], 1, 2, 4, 0, 56, (3, 0, None, None), 1)),
]

IADsAcl_vtables_dispatch_ = 1
IADsAcl_vtables_ = [
	(('ProtectedAttrName', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('ProtectedAttrName', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('SubjectName', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('SubjectName', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('Privileges', 'retval'), 4, (4, (), [(16387, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('Privileges', 'retval'), 4, (4, (), [(3, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
	(('CopyAcl', 'ppAcl'), 5, (5, (), [(16393, 10, None, None)], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
]

IADsAggregatee_vtables_dispatch_ = 0
IADsAggregatee_vtables_ = [
	(('ConnectAsAggregatee', 'pOuterUnknown'), 1610678272, (1610678272, (), [(13, 0, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('DisconnectAsAggregatee',), 1610678273, (1610678273, (), [], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('RelinquishInterface', 'riid'), 1610678274, (1610678274, (), [(36, 0, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('RestoreInterface', 'riid'), 1610678275, (1610678275, (), [(36, 0, None, None)], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
]

IADsAggregator_vtables_dispatch_ = 0
IADsAggregator_vtables_ = [
	(('ConnectAsAggregator', 'pAggregatee'), 1610678272, (1610678272, (), [(13, 0, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('DisconnectAsAggregator',), 1610678273, (1610678273, (), [], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
]

IADsBackLink_vtables_dispatch_ = 1
IADsBackLink_vtables_ = [
	(('RemoteID', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('RemoteID', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('ObjectName', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('ObjectName', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsCaseIgnoreList_vtables_dispatch_ = 1
IADsCaseIgnoreList_vtables_ = [
	(('CaseIgnoreList', 'retval'), 2, (2, (), [(16396, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('CaseIgnoreList', 'retval'), 2, (2, (), [(12, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
]

IADsClass_vtables_dispatch_ = 1
IADsClass_vtables_ = [
	(('PrimaryInterface', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('CLSID', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('CLSID', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 88, (3, 0, None, None), 0)),
	(('OID', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('OID', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 96, (3, 0, None, None), 0)),
	(('Abstract', 'retval'), 18, (18, (), [(16395, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
	(('Abstract', 'retval'), 18, (18, (), [(11, 1, None, None)], 1, 4, 4, 0, 104, (3, 0, None, None), 0)),
	(('Auxiliary', 'retval'), 26, (26, (), [(16395, 10, None, None)], 1, 2, 4, 0, 108, (3, 0, None, None), 0)),
	(('Auxiliary', 'retval'), 26, (26, (), [(11, 1, None, None)], 1, 4, 4, 0, 112, (3, 0, None, None), 0)),
	(('MandatoryProperties', 'retval'), 19, (19, (), [(16396, 10, None, None)], 1, 2, 4, 0, 116, (3, 0, None, None), 0)),
	(('MandatoryProperties', 'retval'), 19, (19, (), [(12, 1, None, None)], 1, 4, 4, 0, 120, (3, 0, None, None), 0)),
	(('OptionalProperties', 'retval'), 29, (29, (), [(16396, 10, None, None)], 1, 2, 4, 0, 124, (3, 0, None, None), 0)),
	(('OptionalProperties', 'retval'), 29, (29, (), [(12, 1, None, None)], 1, 4, 4, 0, 128, (3, 0, None, None), 0)),
	(('NamingProperties', 'retval'), 30, (30, (), [(16396, 10, None, None)], 1, 2, 4, 0, 132, (3, 0, None, None), 0)),
	(('NamingProperties', 'retval'), 30, (30, (), [(12, 1, None, None)], 1, 4, 4, 0, 136, (3, 0, None, None), 0)),
	(('DerivedFrom', 'retval'), 20, (20, (), [(16396, 10, None, None)], 1, 2, 4, 0, 140, (3, 0, None, None), 0)),
	(('DerivedFrom', 'retval'), 20, (20, (), [(12, 1, None, None)], 1, 4, 4, 0, 144, (3, 0, None, None), 0)),
	(('AuxDerivedFrom', 'retval'), 27, (27, (), [(16396, 10, None, None)], 1, 2, 4, 0, 148, (3, 0, None, None), 0)),
	(('AuxDerivedFrom', 'retval'), 27, (27, (), [(12, 1, None, None)], 1, 4, 4, 0, 152, (3, 0, None, None), 0)),
	(('PossibleSuperiors', 'retval'), 28, (28, (), [(16396, 10, None, None)], 1, 2, 4, 0, 156, (3, 0, None, None), 0)),
	(('PossibleSuperiors', 'retval'), 28, (28, (), [(12, 1, None, None)], 1, 4, 4, 0, 160, (3, 0, None, None), 0)),
	(('Containment', 'retval'), 21, (21, (), [(16396, 10, None, None)], 1, 2, 4, 0, 164, (3, 0, None, None), 0)),
	(('Containment', 'retval'), 21, (21, (), [(12, 1, None, None)], 1, 4, 4, 0, 168, (3, 0, None, None), 0)),
	(('Container', 'retval'), 22, (22, (), [(16395, 10, None, None)], 1, 2, 4, 0, 172, (3, 0, None, None), 0)),
	(('Container', 'retval'), 22, (22, (), [(11, 1, None, None)], 1, 4, 4, 0, 176, (3, 0, None, None), 0)),
	(('HelpFileName', 'retval'), 23, (23, (), [(16392, 10, None, None)], 1, 2, 4, 0, 180, (3, 0, None, None), 0)),
	(('HelpFileName', 'retval'), 23, (23, (), [(8, 1, None, None)], 1, 4, 4, 0, 184, (3, 0, None, None), 0)),
	(('HelpFileContext', 'retval'), 24, (24, (), [(16387, 10, None, None)], 1, 2, 4, 0, 188, (3, 0, None, None), 0)),
	(('HelpFileContext', 'retval'), 24, (24, (), [(3, 1, None, None)], 1, 4, 4, 0, 192, (3, 0, None, None), 0)),
	(('Qualifiers', 'ppQualifiers'), 25, (25, (), [(16393, 10, None, "IID('{72B945E0-253B-11CF-A988-00AA006BC149}')")], 1, 1, 4, 0, 196, (3, 0, None, None), 0)),
]

IADsCollection_vtables_dispatch_ = 1
IADsCollection_vtables_ = [
	(('_NewEnum', 'ppEnumerator'), -4, (-4, (), [(16397, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('Add', 'bstrName', 'vItem'), 4, (4, (), [(8, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('Remove', 'bstrItemToBeRemoved'), 5, (5, (), [(8, 1, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('GetObject', 'bstrName', 'pvItem'), 6, (6, (), [(8, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsComputer_vtables_dispatch_ = 1
IADsComputer_vtables_ = [
	(('ComputerID', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Site', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('Description', 'retval'), 19, (19, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('Description', 'retval'), 19, (19, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('Location', 'retval'), 20, (20, (), [(16392, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('Location', 'retval'), 20, (20, (), [(8, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('PrimaryUser', 'retval'), 21, (21, (), [(16392, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('PrimaryUser', 'retval'), 21, (21, (), [(8, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('Owner', 'retval'), 22, (22, (), [(16392, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('Owner', 'retval'), 22, (22, (), [(8, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('Division', 'retval'), 23, (23, (), [(16392, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('Division', 'retval'), 23, (23, (), [(8, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
	(('Department', 'retval'), 24, (24, (), [(16392, 10, None, None)], 1, 2, 4, 0, 128, (3, 0, None, None), 0)),
	(('Department', 'retval'), 24, (24, (), [(8, 1, None, None)], 1, 4, 4, 0, 132, (3, 0, None, None), 0)),
	(('Role', 'retval'), 25, (25, (), [(16392, 10, None, None)], 1, 2, 4, 0, 136, (3, 0, None, None), 0)),
	(('Role', 'retval'), 25, (25, (), [(8, 1, None, None)], 1, 4, 4, 0, 140, (3, 0, None, None), 0)),
	(('OperatingSystem', 'retval'), 26, (26, (), [(16392, 10, None, None)], 1, 2, 4, 0, 144, (3, 0, None, None), 0)),
	(('OperatingSystem', 'retval'), 26, (26, (), [(8, 1, None, None)], 1, 4, 4, 0, 148, (3, 0, None, None), 0)),
	(('OperatingSystemVersion', 'retval'), 27, (27, (), [(16392, 10, None, None)], 1, 2, 4, 0, 152, (3, 0, None, None), 0)),
	(('OperatingSystemVersion', 'retval'), 27, (27, (), [(8, 1, None, None)], 1, 4, 4, 0, 156, (3, 0, None, None), 0)),
	(('Model', 'retval'), 28, (28, (), [(16392, 10, None, None)], 1, 2, 4, 0, 160, (3, 0, None, None), 0)),
	(('Model', 'retval'), 28, (28, (), [(8, 1, None, None)], 1, 4, 4, 0, 164, (3, 0, None, None), 0)),
	(('Processor', 'retval'), 29, (29, (), [(16392, 10, None, None)], 1, 2, 4, 0, 168, (3, 0, None, None), 0)),
	(('Processor', 'retval'), 29, (29, (), [(8, 1, None, None)], 1, 4, 4, 0, 172, (3, 0, None, None), 0)),
	(('ProcessorCount', 'retval'), 30, (30, (), [(16392, 10, None, None)], 1, 2, 4, 0, 176, (3, 0, None, None), 0)),
	(('ProcessorCount', 'retval'), 30, (30, (), [(8, 1, None, None)], 1, 4, 4, 0, 180, (3, 0, None, None), 0)),
	(('MemorySize', 'retval'), 31, (31, (), [(16392, 10, None, None)], 1, 2, 4, 0, 184, (3, 0, None, None), 0)),
	(('MemorySize', 'retval'), 31, (31, (), [(8, 1, None, None)], 1, 4, 4, 0, 188, (3, 0, None, None), 0)),
	(('StorageCapacity', 'retval'), 32, (32, (), [(16392, 10, None, None)], 1, 2, 4, 0, 192, (3, 0, None, None), 0)),
	(('StorageCapacity', 'retval'), 32, (32, (), [(8, 1, None, None)], 1, 4, 4, 0, 196, (3, 0, None, None), 0)),
	(('NetAddresses', 'retval'), 17, (17, (), [(16396, 10, None, None)], 1, 2, 4, 0, 200, (3, 0, None, None), 0)),
	(('NetAddresses', 'retval'), 17, (17, (), [(12, 1, None, None)], 1, 4, 4, 0, 204, (3, 0, None, None), 0)),
]

IADsComputerOperations_vtables_dispatch_ = 1
IADsComputerOperations_vtables_ = [
	(('Status', 'ppObject'), 33, (33, (), [(16393, 10, None, None)], 1, 1, 4, 0, 80, (3, 0, None, None), 0)),
	(('Shutdown', 'bReboot'), 34, (34, (), [(11, 1, None, None)], 1, 1, 4, 0, 84, (3, 0, None, None), 0)),
]

IADsContainer_vtables_dispatch_ = 1
IADsContainer_vtables_ = [
	(('Count', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('_NewEnum', 'retval'), -4, (-4, (), [(16397, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 1)),
	(('Filter', 'pVar'), 3, (3, (), [(16396, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Filter', 'pVar'), 3, (3, (), [(12, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('Hints', 'pvFilter'), 4, (4, (), [(16396, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('Hints', 'pvFilter'), 4, (4, (), [(12, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
	(('GetObject', 'ClassName', 'RelativeName', 'ppObject'), 5, (5, (), [(8, 1, None, None), (8, 1, None, None), (16393, 10, None, None)], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
	(('Create', 'ClassName', 'RelativeName', 'ppObject'), 6, (6, (), [(8, 1, None, None), (8, 1, None, None), (16393, 10, None, None)], 1, 1, 4, 0, 56, (3, 0, None, None), 0)),
	(('Delete', 'bstrClassName', 'bstrRelativeName'), 7, (7, (), [(8, 1, None, None), (8, 1, None, None)], 1, 1, 4, 0, 60, (3, 0, None, None), 0)),
	(('CopyHere', 'SourceName', 'NewName', 'ppObject'), 8, (8, (), [(8, 1, None, None), (8, 1, None, None), (16393, 10, None, None)], 1, 1, 4, 0, 64, (3, 0, None, None), 0)),
	(('MoveHere', 'SourceName', 'NewName', 'ppObject'), 9, (9, (), [(8, 1, None, None), (8, 1, None, None), (16393, 10, None, None)], 1, 1, 4, 0, 68, (3, 0, None, None), 0)),
]

IADsDNWithBinary_vtables_dispatch_ = 1
IADsDNWithBinary_vtables_ = [
	(('BinaryValue', 'retval'), 2, (2, (), [(16396, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('BinaryValue', 'retval'), 2, (2, (), [(12, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('DNString', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('DNString', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsDNWithString_vtables_dispatch_ = 1
IADsDNWithString_vtables_ = [
	(('StringValue', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('StringValue', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('DNString', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('DNString', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsDeleteOps_vtables_dispatch_ = 1
IADsDeleteOps_vtables_ = [
	(('DeleteObject', 'lnFlags'), 2, (2, (), [(3, 1, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
]

IADsDomain_vtables_dispatch_ = 1
IADsDomain_vtables_ = [
	(('IsWorkgroup', 'retval'), 15, (15, (), [(16395, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('MinPasswordLength', 'retval'), 16, (16, (), [(16387, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('MinPasswordLength', 'retval'), 16, (16, (), [(3, 1, None, None)], 1, 4, 4, 0, 88, (3, 0, None, None), 0)),
	(('MinPasswordAge', 'retval'), 17, (17, (), [(16387, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('MinPasswordAge', 'retval'), 17, (17, (), [(3, 1, None, None)], 1, 4, 4, 0, 96, (3, 0, None, None), 0)),
	(('MaxPasswordAge', 'retval'), 18, (18, (), [(16387, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
	(('MaxPasswordAge', 'retval'), 18, (18, (), [(3, 1, None, None)], 1, 4, 4, 0, 104, (3, 0, None, None), 0)),
	(('MaxBadPasswordsAllowed', 'retval'), 19, (19, (), [(16387, 10, None, None)], 1, 2, 4, 0, 108, (3, 0, None, None), 0)),
	(('MaxBadPasswordsAllowed', 'retval'), 19, (19, (), [(3, 1, None, None)], 1, 4, 4, 0, 112, (3, 0, None, None), 0)),
	(('PasswordHistoryLength', 'retval'), 20, (20, (), [(16387, 10, None, None)], 1, 2, 4, 0, 116, (3, 0, None, None), 0)),
	(('PasswordHistoryLength', 'retval'), 20, (20, (), [(3, 1, None, None)], 1, 4, 4, 0, 120, (3, 0, None, None), 0)),
	(('PasswordAttributes', 'retval'), 21, (21, (), [(16387, 10, None, None)], 1, 2, 4, 0, 124, (3, 0, None, None), 0)),
	(('PasswordAttributes', 'retval'), 21, (21, (), [(3, 1, None, None)], 1, 4, 4, 0, 128, (3, 0, None, None), 0)),
	(('AutoUnlockInterval', 'retval'), 22, (22, (), [(16387, 10, None, None)], 1, 2, 4, 0, 132, (3, 0, None, None), 0)),
	(('AutoUnlockInterval', 'retval'), 22, (22, (), [(3, 1, None, None)], 1, 4, 4, 0, 136, (3, 0, None, None), 0)),
	(('LockoutObservationInterval', 'retval'), 23, (23, (), [(16387, 10, None, None)], 1, 2, 4, 0, 140, (3, 0, None, None), 0)),
	(('LockoutObservationInterval', 'retval'), 23, (23, (), [(3, 1, None, None)], 1, 4, 4, 0, 144, (3, 0, None, None), 0)),
]

IADsEmail_vtables_dispatch_ = 1
IADsEmail_vtables_ = [
	(('Type', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('Type', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('Address', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Address', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsExtension_vtables_dispatch_ = 0
IADsExtension_vtables_ = [
	(('Operate', 'dwCode', 'varData1', 'varData2', 'varData3'), 1610678272, (1610678272, (), [(19, 1, None, None), (12, 1, None, None), (12, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('PrivateGetIDsOfNames', 'riid', 'rgszNames', 'cNames', 'lcid', 'rgdispid'), 1610678273, (1610678273, (), [(36, 1, None, None), (16402, 1, None, None), (3, 1, None, None), (19, 1, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('PrivateInvoke', 'dispidMember', 'riid', 'lcid', 'wFlags', 'pdispparams', 'pvarResult', 'pexcepinfo', 'puArgErr'), 1610678274, (1610678274, (), [(3, 1, None, None), (36, 1, None, None), (19, 1, None, None), (18, 1, None, None), (36, 1, None, None), (16396, 2, None, None), (36, 2, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
]

IADsFaxNumber_vtables_dispatch_ = 1
IADsFaxNumber_vtables_ = [
	(('TelephoneNumber', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('Parameters', 'retval'), 3, (3, (), [(16396, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Parameters', 'retval'), 3, (3, (), [(12, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsFileService_vtables_dispatch_ = 1
IADsFileService_vtables_ = [
	(('Description', 'retval'), 33, (33, (), [(16392, 10, None, None)], 1, 2, 4, 0, 176, (3, 0, None, None), 0)),
	(('Description', 'retval'), 33, (33, (), [(8, 1, None, None)], 1, 4, 4, 0, 180, (3, 0, None, None), 0)),
	(('MaxUserCount', 'retval'), 34, (34, (), [(16387, 10, None, None)], 1, 2, 4, 0, 184, (3, 0, None, None), 0)),
	(('MaxUserCount', 'retval'), 34, (34, (), [(3, 1, None, None)], 1, 4, 4, 0, 188, (3, 0, None, None), 0)),
]

IADsFileServiceOperations_vtables_dispatch_ = 1
IADsFileServiceOperations_vtables_ = [
	(('Sessions', 'ppSessions'), 35, (35, (), [(16393, 10, None, "IID('{72B945E0-253B-11CF-A988-00AA006BC149}')")], 1, 1, 4, 0, 104, (3, 0, None, None), 0)),
	(('Resources', 'ppResources'), 36, (36, (), [(16393, 10, None, "IID('{72B945E0-253B-11CF-A988-00AA006BC149}')")], 1, 1, 4, 0, 108, (3, 0, None, None), 0)),
]

IADsFileShare_vtables_dispatch_ = 1
IADsFileShare_vtables_ = [
	(('CurrentUserCount', 'retval'), 15, (15, (), [(16387, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Description', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('Description', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 88, (3, 0, None, None), 0)),
	(('HostComputer', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('HostComputer', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 96, (3, 0, None, None), 0)),
	(('Path', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
	(('Path', 'retval'), 18, (18, (), [(8, 1, None, None)], 1, 4, 4, 0, 104, (3, 0, None, None), 0)),
	(('MaxUserCount', 'retval'), 19, (19, (), [(16387, 10, None, None)], 1, 2, 4, 0, 108, (3, 0, None, None), 0)),
	(('MaxUserCount', 'retval'), 19, (19, (), [(3, 1, None, None)], 1, 4, 4, 0, 112, (3, 0, None, None), 0)),
]

IADsGroup_vtables_dispatch_ = 1
IADsGroup_vtables_ = [
	(('Description', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Description', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('Members', 'ppMembers'), 16, (16, (), [(16393, 10, None, "IID('{451A0030-72EC-11CF-B03B-00AA006E0975}')")], 1, 1, 4, 0, 88, (3, 0, None, None), 0)),
	(('IsMember', 'bstrMember', 'bMember'), 17, (17, (), [(8, 1, None, None), (16395, 10, None, None)], 1, 1, 4, 0, 92, (3, 0, None, None), 0)),
	(('Add', 'bstrNewItem'), 18, (18, (), [(8, 1, None, None)], 1, 1, 4, 0, 96, (3, 0, None, None), 0)),
	(('Remove', 'bstrItemToBeRemoved'), 19, (19, (), [(8, 1, None, None)], 1, 1, 4, 0, 100, (3, 0, None, None), 0)),
]

IADsHold_vtables_dispatch_ = 1
IADsHold_vtables_ = [
	(('ObjectName', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('ObjectName', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('Amount', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Amount', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsLargeInteger_vtables_dispatch_ = 1
IADsLargeInteger_vtables_ = [
	(('HighPart', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('HighPart', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('LowPart', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('LowPart', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsLocality_vtables_dispatch_ = 1
IADsLocality_vtables_ = [
	(('Description', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Description', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('LocalityName', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('LocalityName', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 18, (18, (), [(16396, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 18, (18, (), [(12, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
]

IADsMembers_vtables_dispatch_ = 1
IADsMembers_vtables_ = [
	(('Count', 'plCount'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('_NewEnum', 'ppEnumerator'), -4, (-4, (), [(16397, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 0)),
	(('Filter', 'pvFilter'), 3, (3, (), [(16396, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Filter', 'pvFilter'), 3, (3, (), [(12, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsNameTranslate_vtables_dispatch_ = 1
IADsNameTranslate_vtables_ = [
	(('ChaseReferral',), 1, (1, (), [(3, 1, None, None)], 1, 4, 4, 0, 28, (3, 0, None, None), 0)),
	(('Init', 'lnSetType', 'bstrADsPath'), 2, (2, (), [(3, 1, None, None), (8, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('InitEx', 'lnSetType', 'bstrADsPath', 'bstrUserID', 'bstrDomain', 'bstrPassword'), 3, (3, (), [(3, 1, None, None), (8, 1, None, None), (8, 1, None, None), (8, 1, None, None), (8, 1, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('Set', 'lnSetType', 'bstrADsPath'), 4, (4, (), [(3, 1, None, None), (8, 1, None, None)], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
	(('Get', 'lnFormatType', 'pbstrADsPath'), 5, (5, (), [(3, 1, None, None), (16392, 10, None, None)], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('SetEx', 'lnFormatType', 'pVar'), 6, (6, (), [(3, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
	(('GetEx', 'lnFormatType', 'pVar'), 7, (7, (), [(3, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
]

IADsNamespaces_vtables_dispatch_ = 1
IADsNamespaces_vtables_ = [
	(('DefaultContainer', 'retval'), 1, (1, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('DefaultContainer', 'retval'), 1, (1, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
]

IADsNetAddress_vtables_dispatch_ = 1
IADsNetAddress_vtables_ = [
	(('AddressType', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('AddressType', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('Address', 'retval'), 3, (3, (), [(16396, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Address', 'retval'), 3, (3, (), [(12, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsO_vtables_dispatch_ = 1
IADsO_vtables_ = [
	(('Description', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Description', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('LocalityName', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('LocalityName', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 18, (18, (), [(8, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('FaxNumber', 'retval'), 19, (19, (), [(16392, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('FaxNumber', 'retval'), 19, (19, (), [(8, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 20, (20, (), [(16396, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 20, (20, (), [(12, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
]

IADsOU_vtables_dispatch_ = 1
IADsOU_vtables_ = [
	(('Description', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Description', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('LocalityName', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('LocalityName', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 18, (18, (), [(8, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('FaxNumber', 'retval'), 19, (19, (), [(16392, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('FaxNumber', 'retval'), 19, (19, (), [(8, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 20, (20, (), [(16396, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 20, (20, (), [(12, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
	(('BusinessCategory', 'retval'), 21, (21, (), [(16392, 10, None, None)], 1, 2, 4, 0, 128, (3, 0, None, None), 0)),
	(('BusinessCategory', 'retval'), 21, (21, (), [(8, 1, None, None)], 1, 4, 4, 0, 132, (3, 0, None, None), 0)),
]

IADsObjectOptions_vtables_dispatch_ = 1
IADsObjectOptions_vtables_ = [
	(('GetOption', 'lnOption', 'pvValue'), 2, (2, (), [(3, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('SetOption', 'lnOption', 'vValue'), 3, (3, (), [(3, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
]

IADsOctetList_vtables_dispatch_ = 1
IADsOctetList_vtables_ = [
	(('OctetList', 'retval'), 2, (2, (), [(16396, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('OctetList', 'retval'), 2, (2, (), [(12, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
]

IADsOpenDSObject_vtables_dispatch_ = 1
IADsOpenDSObject_vtables_ = [
	(('OpenDSObject', 'lpszDNName', 'lpszUserName', 'lpszPassword', 'lnReserved', 'ppOleDsObj'), 1, (1, (), [(8, 1, None, None), (8, 1, None, None), (8, 1, None, None), (3, 1, None, None), (16393, 10, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
]

IADsPath_vtables_dispatch_ = 1
IADsPath_vtables_ = [
	(('Type', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('Type', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('VolumeName', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('VolumeName', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('Path', 'retval'), 4, (4, (), [(16392, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('Path', 'retval'), 4, (4, (), [(8, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
]

IADsPathname_vtables_dispatch_ = 1
IADsPathname_vtables_ = [
	(('Set', 'bstrADsPath', 'lnSetType'), 2, (2, (), [(8, 1, None, None), (3, 1, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('SetDisplayType', 'lnDisplayType'), 3, (3, (), [(3, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('Retrieve', 'lnFormatType', 'pbstrADsPath'), 4, (4, (), [(3, 1, None, None), (16392, 10, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('GetNumElements', 'plnNumPathElements'), 5, (5, (), [(16387, 10, None, None)], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
	(('GetElement', 'lnElementIndex', 'pbstrElement'), 6, (6, (), [(3, 1, None, None), (16392, 10, None, None)], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('AddLeafElement', 'bstrLeafElement'), 7, (7, (), [(8, 1, None, None)], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
	(('RemoveLeafElement',), 8, (8, (), [], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
	(('CopyPath', 'ppAdsPath'), 9, (9, (), [(16393, 10, None, None)], 1, 1, 4, 0, 56, (3, 0, None, None), 0)),
	(('GetEscapedElement', 'lnReserved', 'bstrInStr', 'pbstrOutStr'), 10, (10, (), [(3, 1, None, None), (8, 1, None, None), (16392, 10, None, None)], 1, 1, 4, 0, 60, (3, 0, None, None), 0)),
	(('EscapedMode', 'retval'), 11, (11, (), [(16387, 10, None, None)], 1, 2, 4, 0, 64, (3, 0, None, None), 0)),
	(('EscapedMode', 'retval'), 11, (11, (), [(3, 1, None, None)], 1, 4, 4, 0, 68, (3, 0, None, None), 0)),
]

IADsPostalAddress_vtables_dispatch_ = 1
IADsPostalAddress_vtables_ = [
	(('PostalAddress', 'retval'), 2, (2, (), [(16396, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('PostalAddress', 'retval'), 2, (2, (), [(12, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
]

IADsPrintJob_vtables_dispatch_ = 1
IADsPrintJob_vtables_ = [
	(('HostPrintQueue', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('User', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('UserPath', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('TimeSubmitted', 'retval'), 18, (18, (), [(16391, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('TotalPages', 'retval'), 19, (19, (), [(16387, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('Size', 'retval'), 234, (234, (), [(16387, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
	(('Description', 'retval'), 20, (20, (), [(16392, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('Description', 'retval'), 20, (20, (), [(8, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('Priority', 'retval'), 21, (21, (), [(16387, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('Priority', 'retval'), 21, (21, (), [(3, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('StartTime', 'retval'), 22, (22, (), [(16391, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('StartTime', 'retval'), 22, (22, (), [(7, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
	(('UntilTime', 'retval'), 23, (23, (), [(16391, 10, None, None)], 1, 2, 4, 0, 128, (3, 0, None, None), 0)),
	(('UntilTime', 'retval'), 23, (23, (), [(7, 1, None, None)], 1, 4, 4, 0, 132, (3, 0, None, None), 0)),
	(('Notify', 'retval'), 24, (24, (), [(16392, 10, None, None)], 1, 2, 4, 0, 136, (3, 0, None, None), 0)),
	(('Notify', 'retval'), 24, (24, (), [(8, 1, None, None)], 1, 4, 4, 0, 140, (3, 0, None, None), 0)),
	(('NotifyPath', 'retval'), 25, (25, (), [(16392, 10, None, None)], 1, 2, 4, 0, 144, (3, 0, None, None), 0)),
	(('NotifyPath', 'retval'), 25, (25, (), [(8, 1, None, None)], 1, 4, 4, 0, 148, (3, 0, None, None), 0)),
]

IADsPrintJobOperations_vtables_dispatch_ = 1
IADsPrintJobOperations_vtables_ = [
	(('Status', 'retval'), 26, (26, (), [(16387, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('TimeElapsed', 'retval'), 27, (27, (), [(16387, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('PagesPrinted', 'retval'), 28, (28, (), [(16387, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('Position', 'retval'), 29, (29, (), [(16387, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('Position', 'retval'), 29, (29, (), [(3, 1, None, None)], 1, 4, 4, 0, 96, (3, 0, None, None), 0)),
	(('Pause',), 30, (30, (), [], 1, 1, 4, 0, 100, (3, 0, None, None), 0)),
	(('Resume',), 31, (31, (), [], 1, 1, 4, 0, 104, (3, 0, None, None), 0)),
]

IADsPrintQueue_vtables_dispatch_ = 1
IADsPrintQueue_vtables_ = [
	(('PrinterPath', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('PrinterPath', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('Model', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('Model', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('Datatype', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('Datatype', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('PrintProcessor', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('PrintProcessor', 'retval'), 18, (18, (), [(8, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('Description', 'retval'), 19, (19, (), [(16392, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('Description', 'retval'), 19, (19, (), [(8, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('Location', 'retval'), 20, (20, (), [(16392, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('Location', 'retval'), 20, (20, (), [(8, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
	(('StartTime', 'retval'), 21, (21, (), [(16391, 10, None, None)], 1, 2, 4, 0, 128, (3, 0, None, None), 0)),
	(('StartTime', 'retval'), 21, (21, (), [(7, 1, None, None)], 1, 4, 4, 0, 132, (3, 0, None, None), 0)),
	(('UntilTime', 'retval'), 22, (22, (), [(16391, 10, None, None)], 1, 2, 4, 0, 136, (3, 0, None, None), 0)),
	(('UntilTime', 'retval'), 22, (22, (), [(7, 1, None, None)], 1, 4, 4, 0, 140, (3, 0, None, None), 0)),
	(('DefaultJobPriority', 'retval'), 23, (23, (), [(16387, 10, None, None)], 1, 2, 4, 0, 144, (3, 0, None, None), 0)),
	(('DefaultJobPriority', 'retval'), 23, (23, (), [(3, 1, None, None)], 1, 4, 4, 0, 148, (3, 0, None, None), 0)),
	(('Priority', 'retval'), 24, (24, (), [(16387, 10, None, None)], 1, 2, 4, 0, 152, (3, 0, None, None), 0)),
	(('Priority', 'retval'), 24, (24, (), [(3, 1, None, None)], 1, 4, 4, 0, 156, (3, 0, None, None), 0)),
	(('BannerPage', 'retval'), 25, (25, (), [(16392, 10, None, None)], 1, 2, 4, 0, 160, (3, 0, None, None), 0)),
	(('BannerPage', 'retval'), 25, (25, (), [(8, 1, None, None)], 1, 4, 4, 0, 164, (3, 0, None, None), 0)),
	(('PrintDevices', 'retval'), 26, (26, (), [(16396, 10, None, None)], 1, 2, 4, 0, 168, (3, 0, None, None), 0)),
	(('PrintDevices', 'retval'), 26, (26, (), [(12, 1, None, None)], 1, 4, 4, 0, 172, (3, 0, None, None), 0)),
	(('NetAddresses', 'retval'), 27, (27, (), [(16396, 10, None, None)], 1, 2, 4, 0, 176, (3, 0, None, None), 0)),
	(('NetAddresses', 'retval'), 27, (27, (), [(12, 1, None, None)], 1, 4, 4, 0, 180, (3, 0, None, None), 0)),
]

IADsPrintQueueOperations_vtables_dispatch_ = 1
IADsPrintQueueOperations_vtables_ = [
	(('Status', 'retval'), 27, (27, (), [(16387, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('PrintJobs', 'pObject'), 28, (28, (), [(16393, 10, None, "IID('{72B945E0-253B-11CF-A988-00AA006BC149}')")], 1, 1, 4, 0, 84, (3, 0, None, None), 0)),
	(('Pause',), 29, (29, (), [], 1, 1, 4, 0, 88, (3, 0, None, None), 0)),
	(('Resume',), 30, (30, (), [], 1, 1, 4, 0, 92, (3, 0, None, None), 0)),
	(('Purge',), 31, (31, (), [], 1, 1, 4, 0, 96, (3, 0, None, None), 0)),
]

IADsProperty_vtables_dispatch_ = 1
IADsProperty_vtables_ = [
	(('OID', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('OID', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('Syntax', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('Syntax', 'retval'), 18, (18, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('MaxRange', 'retval'), 19, (19, (), [(16387, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('MaxRange', 'retval'), 19, (19, (), [(3, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('MinRange', 'retval'), 20, (20, (), [(16387, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('MinRange', 'retval'), 20, (20, (), [(3, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('MultiValued', 'retval'), 21, (21, (), [(16395, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('MultiValued', 'retval'), 21, (21, (), [(11, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('Qualifiers', 'ppQualifiers'), 22, (22, (), [(16393, 10, None, "IID('{72B945E0-253B-11CF-A988-00AA006BC149}')")], 1, 1, 4, 0, 120, (3, 0, None, None), 0)),
]

IADsPropertyEntry_vtables_dispatch_ = 1
IADsPropertyEntry_vtables_ = [
	(('Clear',), 1, (1, (), [], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('Name', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 0)),
	(('Name', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 36, (3, 0, None, None), 0)),
	(('ADsType', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 40, (3, 0, None, None), 0)),
	(('ADsType', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 44, (3, 0, None, None), 0)),
	(('ControlCode', 'retval'), 4, (4, (), [(16387, 10, None, None)], 1, 2, 4, 0, 48, (3, 0, None, None), 0)),
	(('ControlCode', 'retval'), 4, (4, (), [(3, 1, None, None)], 1, 4, 4, 0, 52, (3, 0, None, None), 0)),
	(('Values', 'retval'), 5, (5, (), [(16396, 10, None, None)], 1, 2, 4, 0, 56, (3, 0, None, None), 0)),
	(('Values', 'retval'), 5, (5, (), [(12, 1, None, None)], 1, 4, 4, 0, 60, (3, 0, None, None), 0)),
]

IADsPropertyList_vtables_dispatch_ = 1
IADsPropertyList_vtables_ = [
	(('PropertyCount', 'plCount'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('Next', 'pVariant'), 3, (3, (), [(16396, 10, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('Skip', 'cElements'), 4, (4, (), [(3, 1, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('Reset',), 5, (5, (), [], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
	(('Item', 'varIndex', 'pVariant'), 0, (0, (), [(12, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('GetPropertyItem', 'bstrName', 'lnADsType', 'pVariant'), 6, (6, (), [(8, 1, None, None), (3, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
	(('PutPropertyItem', 'varData'), 7, (7, (), [(12, 1, None, None)], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
	(('ResetPropertyItem', 'varEntry'), 8, (8, (), [(12, 1, None, None)], 1, 1, 4, 0, 56, (3, 0, None, None), 0)),
	(('PurgePropertyList',), 9, (9, (), [], 1, 1, 4, 0, 60, (3, 0, None, None), 0)),
]

IADsPropertyValue_vtables_dispatch_ = 1
IADsPropertyValue_vtables_ = [
	(('Clear',), 1, (1, (), [], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('ADsType', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 0)),
	(('ADsType', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 36, (3, 0, None, None), 0)),
	(('DNString', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 40, (3, 0, None, None), 0)),
	(('DNString', 'retval'), 3, (3, (), [(8, 1, None, None)], 1, 4, 4, 0, 44, (3, 0, None, None), 0)),
	(('CaseExactString', 'retval'), 4, (4, (), [(16392, 10, None, None)], 1, 2, 4, 0, 48, (3, 0, None, None), 0)),
	(('CaseExactString', 'retval'), 4, (4, (), [(8, 1, None, None)], 1, 4, 4, 0, 52, (3, 0, None, None), 0)),
	(('CaseIgnoreString', 'retval'), 5, (5, (), [(16392, 10, None, None)], 1, 2, 4, 0, 56, (3, 0, None, None), 0)),
	(('CaseIgnoreString', 'retval'), 5, (5, (), [(8, 1, None, None)], 1, 4, 4, 0, 60, (3, 0, None, None), 0)),
	(('PrintableString', 'retval'), 6, (6, (), [(16392, 10, None, None)], 1, 2, 4, 0, 64, (3, 0, None, None), 0)),
	(('PrintableString', 'retval'), 6, (6, (), [(8, 1, None, None)], 1, 4, 4, 0, 68, (3, 0, None, None), 0)),
	(('NumericString', 'retval'), 7, (7, (), [(16392, 10, None, None)], 1, 2, 4, 0, 72, (3, 0, None, None), 0)),
	(('NumericString', 'retval'), 7, (7, (), [(8, 1, None, None)], 1, 4, 4, 0, 76, (3, 0, None, None), 0)),
	(('Boolean', 'retval'), 8, (8, (), [(16387, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Boolean', 'retval'), 8, (8, (), [(3, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('Integer', 'retval'), 9, (9, (), [(16387, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('Integer', 'retval'), 9, (9, (), [(3, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('OctetString', 'retval'), 10, (10, (), [(16396, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('OctetString', 'retval'), 10, (10, (), [(12, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('SecurityDescriptor', 'retval'), 11, (11, (), [(16393, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('SecurityDescriptor', 'retval'), 11, (11, (), [(9, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('LargeInteger', 'retval'), 12, (12, (), [(16393, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('LargeInteger', 'retval'), 12, (12, (), [(9, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('UTCTime', 'retval'), 13, (13, (), [(16391, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('UTCTime', 'retval'), 13, (13, (), [(7, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
]

IADsPropertyValue2_vtables_dispatch_ = 1
IADsPropertyValue2_vtables_ = [
	(('GetObjectProperty', 'lnADsType', 'pvProp'), 1, (1, (), [(16387, 3, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('PutObjectProperty', 'lnADsType', 'vProp'), 2, (2, (), [(3, 1, None, None), (12, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
]

IADsReplicaPointer_vtables_dispatch_ = 1
IADsReplicaPointer_vtables_ = [
	(('ServerName', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('ServerName', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('ReplicaType', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('ReplicaType', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('ReplicaNumber', 'retval'), 4, (4, (), [(16387, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('ReplicaNumber', 'retval'), 4, (4, (), [(3, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
	(('Count', 'retval'), 5, (5, (), [(16387, 10, None, None)], 1, 2, 4, 0, 52, (3, 0, None, None), 0)),
	(('Count', 'retval'), 5, (5, (), [(3, 1, None, None)], 1, 4, 4, 0, 56, (3, 0, None, None), 0)),
	(('ReplicaAddressHints', 'retval'), 6, (6, (), [(16396, 10, None, None)], 1, 2, 4, 0, 60, (3, 0, None, None), 0)),
	(('ReplicaAddressHints', 'retval'), 6, (6, (), [(12, 1, None, None)], 1, 4, 4, 0, 64, (3, 0, None, None), 0)),
]

IADsResource_vtables_dispatch_ = 1
IADsResource_vtables_ = [
	(('User', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('UserPath', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('Path', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('LockCount', 'retval'), 18, (18, (), [(16387, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
]

IADsSecurityDescriptor_vtables_dispatch_ = 1
IADsSecurityDescriptor_vtables_ = [
	(('Revision', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('Revision', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('Control', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Control', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('Owner', 'retval'), 4, (4, (), [(16392, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('Owner', 'retval'), 4, (4, (), [(8, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
	(('OwnerDefaulted', 'retval'), 5, (5, (), [(16395, 10, None, None)], 1, 2, 4, 0, 52, (3, 0, None, None), 0)),
	(('OwnerDefaulted', 'retval'), 5, (5, (), [(11, 1, None, None)], 1, 4, 4, 0, 56, (3, 0, None, None), 0)),
	(('Group', 'retval'), 6, (6, (), [(16392, 10, None, None)], 1, 2, 4, 0, 60, (3, 0, None, None), 0)),
	(('Group', 'retval'), 6, (6, (), [(8, 1, None, None)], 1, 4, 4, 0, 64, (3, 0, None, None), 0)),
	(('GroupDefaulted', 'retval'), 7, (7, (), [(16395, 10, None, None)], 1, 2, 4, 0, 68, (3, 0, None, None), 0)),
	(('GroupDefaulted', 'retval'), 7, (7, (), [(11, 1, None, None)], 1, 4, 4, 0, 72, (3, 0, None, None), 0)),
	(('DiscretionaryAcl', 'retval'), 8, (8, (), [(16393, 10, None, None)], 1, 2, 4, 0, 76, (3, 0, None, None), 0)),
	(('DiscretionaryAcl', 'retval'), 8, (8, (), [(9, 1, None, None)], 1, 4, 4, 0, 80, (3, 0, None, None), 0)),
	(('DaclDefaulted', 'retval'), 9, (9, (), [(16395, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('DaclDefaulted', 'retval'), 9, (9, (), [(11, 1, None, None)], 1, 4, 4, 0, 88, (3, 0, None, None), 0)),
	(('SystemAcl', 'retval'), 10, (10, (), [(16393, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('SystemAcl', 'retval'), 10, (10, (), [(9, 1, None, None)], 1, 4, 4, 0, 96, (3, 0, None, None), 0)),
	(('SaclDefaulted', 'retval'), 11, (11, (), [(16395, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
	(('SaclDefaulted', 'retval'), 11, (11, (), [(11, 1, None, None)], 1, 4, 4, 0, 104, (3, 0, None, None), 0)),
	(('CopySecurityDescriptor', 'ppSecurityDescriptor'), 12, (12, (), [(16393, 10, None, None)], 1, 1, 4, 0, 108, (3, 0, None, None), 0)),
]

IADsSecurityUtility_vtables_dispatch_ = 1
IADsSecurityUtility_vtables_ = [
	(('GetSecurityDescriptor', 'varPath', 'lPathFormat', 'lFormat', 'pVariant'), 2, (2, (), [(12, 1, None, None), (3, 1, None, None), (3, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('SetSecurityDescriptor', 'varPath', 'lPathFormat', 'varData', 'lDataFormat'), 3, (3, (), [(12, 1, None, None), (3, 1, None, None), (12, 1, None, None), (3, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('ConvertSecurityDescriptor', 'varSD', 'lDataFormat', 'lOutFormat', 'pResult'), 4, (4, (), [(12, 1, None, None), (3, 1, None, None), (3, 1, None, None), (16396, 10, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('SecurityMask', 'retval'), 5, (5, (), [(16387, 10, None, None)], 1, 2, 4, 0, 40, (3, 0, None, None), 0)),
	(('SecurityMask', 'retval'), 5, (5, (), [(3, 1, None, None)], 1, 4, 4, 0, 44, (3, 0, None, None), 0)),
]

IADsService_vtables_dispatch_ = 1
IADsService_vtables_ = [
	(('HostComputer', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('HostComputer', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
	(('DisplayName', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('DisplayName', 'retval'), 16, (16, (), [(8, 1, None, None)], 1, 4, 4, 0, 92, (3, 0, None, None), 0)),
	(('Version', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('Version', 'retval'), 17, (17, (), [(8, 1, None, None)], 1, 4, 4, 0, 100, (3, 0, None, None), 0)),
	(('ServiceType', 'retval'), 18, (18, (), [(16387, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('ServiceType', 'retval'), 18, (18, (), [(3, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('StartType', 'retval'), 19, (19, (), [(16387, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('StartType', 'retval'), 19, (19, (), [(3, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('Path', 'retval'), 20, (20, (), [(16392, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('Path', 'retval'), 20, (20, (), [(8, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
	(('StartupParameters', 'retval'), 21, (21, (), [(16392, 10, None, None)], 1, 2, 4, 0, 128, (3, 0, None, None), 0)),
	(('StartupParameters', 'retval'), 21, (21, (), [(8, 1, None, None)], 1, 4, 4, 0, 132, (3, 0, None, None), 0)),
	(('ErrorControl', 'retval'), 22, (22, (), [(16387, 10, None, None)], 1, 2, 4, 0, 136, (3, 0, None, None), 0)),
	(('ErrorControl', 'retval'), 22, (22, (), [(3, 1, None, None)], 1, 4, 4, 0, 140, (3, 0, None, None), 0)),
	(('LoadOrderGroup', 'retval'), 23, (23, (), [(16392, 10, None, None)], 1, 2, 4, 0, 144, (3, 0, None, None), 0)),
	(('LoadOrderGroup', 'retval'), 23, (23, (), [(8, 1, None, None)], 1, 4, 4, 0, 148, (3, 0, None, None), 0)),
	(('ServiceAccountName', 'retval'), 24, (24, (), [(16392, 10, None, None)], 1, 2, 4, 0, 152, (3, 0, None, None), 0)),
	(('ServiceAccountName', 'retval'), 24, (24, (), [(8, 1, None, None)], 1, 4, 4, 0, 156, (3, 0, None, None), 0)),
	(('ServiceAccountPath', 'retval'), 25, (25, (), [(16392, 10, None, None)], 1, 2, 4, 0, 160, (3, 0, None, None), 0)),
	(('ServiceAccountPath', 'retval'), 25, (25, (), [(8, 1, None, None)], 1, 4, 4, 0, 164, (3, 0, None, None), 0)),
	(('Dependencies', 'retval'), 26, (26, (), [(16396, 10, None, None)], 1, 2, 4, 0, 168, (3, 0, None, None), 0)),
	(('Dependencies', 'retval'), 26, (26, (), [(12, 1, None, None)], 1, 4, 4, 0, 172, (3, 0, None, None), 0)),
]

IADsServiceOperations_vtables_dispatch_ = 1
IADsServiceOperations_vtables_ = [
	(('Status', 'retval'), 27, (27, (), [(16387, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('Start',), 28, (28, (), [], 1, 1, 4, 0, 84, (3, 0, None, None), 0)),
	(('Stop',), 29, (29, (), [], 1, 1, 4, 0, 88, (3, 0, None, None), 0)),
	(('Pause',), 30, (30, (), [], 1, 1, 4, 0, 92, (3, 0, None, None), 0)),
	(('Continue',), 31, (31, (), [], 1, 1, 4, 0, 96, (3, 0, None, None), 0)),
	(('SetPassword', 'bstrNewPassword'), 32, (32, (), [(8, 1, None, None)], 1, 1, 4, 0, 100, (3, 0, None, None), 0)),
]

IADsSession_vtables_dispatch_ = 1
IADsSession_vtables_ = [
	(('User', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('UserPath', 'retval'), 16, (16, (), [(16392, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('Computer', 'retval'), 17, (17, (), [(16392, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('ComputerPath', 'retval'), 18, (18, (), [(16392, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('ConnectTime', 'retval'), 19, (19, (), [(16387, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('IdleTime', 'retval'), 20, (20, (), [(16387, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
]

IADsSyntax_vtables_dispatch_ = 1
IADsSyntax_vtables_ = [
	(('OleAutoDataType', 'retval'), 15, (15, (), [(16387, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('OleAutoDataType', 'retval'), 15, (15, (), [(3, 1, None, None)], 1, 4, 4, 0, 84, (3, 0, None, None), 0)),
]

IADsTimestamp_vtables_dispatch_ = 1
IADsTimestamp_vtables_ = [
	(('WholeSeconds', 'retval'), 2, (2, (), [(16387, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('WholeSeconds', 'retval'), 2, (2, (), [(3, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('EventID', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('EventID', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
]

IADsTypedName_vtables_dispatch_ = 1
IADsTypedName_vtables_ = [
	(('ObjectName', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('ObjectName', 'retval'), 2, (2, (), [(8, 1, None, None)], 1, 4, 4, 0, 32, (3, 0, None, None), 0)),
	(('Level', 'retval'), 3, (3, (), [(16387, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('Level', 'retval'), 3, (3, (), [(3, 1, None, None)], 1, 4, 4, 0, 40, (3, 0, None, None), 0)),
	(('Interval', 'retval'), 4, (4, (), [(16387, 10, None, None)], 1, 2, 4, 0, 44, (3, 0, None, None), 0)),
	(('Interval', 'retval'), 4, (4, (), [(3, 1, None, None)], 1, 4, 4, 0, 48, (3, 0, None, None), 0)),
]

IADsUser_vtables_dispatch_ = 1
IADsUser_vtables_ = [
	(('BadLoginAddress', 'retval'), 53, (53, (), [(16392, 10, None, None)], 1, 2, 4, 0, 80, (3, 0, None, None), 0)),
	(('BadLoginCount', 'retval'), 54, (54, (), [(16387, 10, None, None)], 1, 2, 4, 0, 84, (3, 0, None, None), 0)),
	(('LastLogin', 'retval'), 56, (56, (), [(16391, 10, None, None)], 1, 2, 4, 0, 88, (3, 0, None, None), 0)),
	(('LastLogoff', 'retval'), 57, (57, (), [(16391, 10, None, None)], 1, 2, 4, 0, 92, (3, 0, None, None), 0)),
	(('LastFailedLogin', 'retval'), 58, (58, (), [(16391, 10, None, None)], 1, 2, 4, 0, 96, (3, 0, None, None), 0)),
	(('PasswordLastChanged', 'retval'), 59, (59, (), [(16391, 10, None, None)], 1, 2, 4, 0, 100, (3, 0, None, None), 0)),
	(('Description', 'retval'), 15, (15, (), [(16392, 10, None, None)], 1, 2, 4, 0, 104, (3, 0, None, None), 0)),
	(('Description', 'retval'), 15, (15, (), [(8, 1, None, None)], 1, 4, 4, 0, 108, (3, 0, None, None), 0)),
	(('Division', 'retval'), 19, (19, (), [(16392, 10, None, None)], 1, 2, 4, 0, 112, (3, 0, None, None), 0)),
	(('Division', 'retval'), 19, (19, (), [(8, 1, None, None)], 1, 4, 4, 0, 116, (3, 0, None, None), 0)),
	(('Department', 'retval'), 122, (122, (), [(16392, 10, None, None)], 1, 2, 4, 0, 120, (3, 0, None, None), 0)),
	(('Department', 'retval'), 122, (122, (), [(8, 1, None, None)], 1, 4, 4, 0, 124, (3, 0, None, None), 0)),
	(('EmployeeID', 'retval'), 20, (20, (), [(16392, 10, None, None)], 1, 2, 4, 0, 128, (3, 0, None, None), 0)),
	(('EmployeeID', 'retval'), 20, (20, (), [(8, 1, None, None)], 1, 4, 4, 0, 132, (3, 0, None, None), 0)),
	(('FullName', 'retval'), 23, (23, (), [(16392, 10, None, None)], 1, 2, 4, 0, 136, (3, 0, None, None), 0)),
	(('FullName', 'retval'), 23, (23, (), [(8, 1, None, None)], 1, 4, 4, 0, 140, (3, 0, None, None), 0)),
	(('FirstName', 'retval'), 22, (22, (), [(16392, 10, None, None)], 1, 2, 4, 0, 144, (3, 0, None, None), 0)),
	(('FirstName', 'retval'), 22, (22, (), [(8, 1, None, None)], 1, 4, 4, 0, 148, (3, 0, None, None), 0)),
	(('LastName', 'retval'), 25, (25, (), [(16392, 10, None, None)], 1, 2, 4, 0, 152, (3, 0, None, None), 0)),
	(('LastName', 'retval'), 25, (25, (), [(8, 1, None, None)], 1, 4, 4, 0, 156, (3, 0, None, None), 0)),
	(('OtherName', 'retval'), 27, (27, (), [(16392, 10, None, None)], 1, 2, 4, 0, 160, (3, 0, None, None), 0)),
	(('OtherName', 'retval'), 27, (27, (), [(8, 1, None, None)], 1, 4, 4, 0, 164, (3, 0, None, None), 0)),
	(('NamePrefix', 'retval'), 114, (114, (), [(16392, 10, None, None)], 1, 2, 4, 0, 168, (3, 0, None, None), 0)),
	(('NamePrefix', 'retval'), 114, (114, (), [(8, 1, None, None)], 1, 4, 4, 0, 172, (3, 0, None, None), 0)),
	(('NameSuffix', 'retval'), 115, (115, (), [(16392, 10, None, None)], 1, 2, 4, 0, 176, (3, 0, None, None), 0)),
	(('NameSuffix', 'retval'), 115, (115, (), [(8, 1, None, None)], 1, 4, 4, 0, 180, (3, 0, None, None), 0)),
	(('Title', 'retval'), 36, (36, (), [(16392, 10, None, None)], 1, 2, 4, 0, 184, (3, 0, None, None), 0)),
	(('Title', 'retval'), 36, (36, (), [(8, 1, None, None)], 1, 4, 4, 0, 188, (3, 0, None, None), 0)),
	(('Manager', 'retval'), 26, (26, (), [(16392, 10, None, None)], 1, 2, 4, 0, 192, (3, 0, None, None), 0)),
	(('Manager', 'retval'), 26, (26, (), [(8, 1, None, None)], 1, 4, 4, 0, 196, (3, 0, None, None), 0)),
	(('TelephoneHome', 'retval'), 32, (32, (), [(16396, 10, None, None)], 1, 2, 4, 0, 200, (3, 0, None, None), 0)),
	(('TelephoneHome', 'retval'), 32, (32, (), [(12, 1, None, None)], 1, 4, 4, 0, 204, (3, 0, None, None), 0)),
	(('TelephoneMobile', 'retval'), 33, (33, (), [(16396, 10, None, None)], 1, 2, 4, 0, 208, (3, 0, None, None), 0)),
	(('TelephoneMobile', 'retval'), 33, (33, (), [(12, 1, None, None)], 1, 4, 4, 0, 212, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 34, (34, (), [(16396, 10, None, None)], 1, 2, 4, 0, 216, (3, 0, None, None), 0)),
	(('TelephoneNumber', 'retval'), 34, (34, (), [(12, 1, None, None)], 1, 4, 4, 0, 220, (3, 0, None, None), 0)),
	(('TelephonePager', 'retval'), 17, (17, (), [(16396, 10, None, None)], 1, 2, 4, 0, 224, (3, 0, None, None), 0)),
	(('TelephonePager', 'retval'), 17, (17, (), [(12, 1, None, None)], 1, 4, 4, 0, 228, (3, 0, None, None), 0)),
	(('FaxNumber', 'retval'), 16, (16, (), [(16396, 10, None, None)], 1, 2, 4, 0, 232, (3, 0, None, None), 0)),
	(('FaxNumber', 'retval'), 16, (16, (), [(12, 1, None, None)], 1, 4, 4, 0, 236, (3, 0, None, None), 0)),
	(('OfficeLocations', 'retval'), 28, (28, (), [(16396, 10, None, None)], 1, 2, 4, 0, 240, (3, 0, None, None), 0)),
	(('OfficeLocations', 'retval'), 28, (28, (), [(12, 1, None, None)], 1, 4, 4, 0, 244, (3, 0, None, None), 0)),
	(('PostalAddresses', 'retval'), 30, (30, (), [(16396, 10, None, None)], 1, 2, 4, 0, 248, (3, 0, None, None), 0)),
	(('PostalAddresses', 'retval'), 30, (30, (), [(12, 1, None, None)], 1, 4, 4, 0, 252, (3, 0, None, None), 0)),
	(('PostalCodes', 'retval'), 31, (31, (), [(16396, 10, None, None)], 1, 2, 4, 0, 256, (3, 0, None, None), 0)),
	(('PostalCodes', 'retval'), 31, (31, (), [(12, 1, None, None)], 1, 4, 4, 0, 260, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 117, (117, (), [(16396, 10, None, None)], 1, 2, 4, 0, 264, (3, 0, None, None), 0)),
	(('SeeAlso', 'retval'), 117, (117, (), [(12, 1, None, None)], 1, 4, 4, 0, 268, (3, 0, None, None), 0)),
	(('AccountDisabled', 'retval'), 37, (37, (), [(16395, 10, None, None)], 1, 2, 4, 0, 272, (3, 0, None, None), 0)),
	(('AccountDisabled', 'retval'), 37, (37, (), [(11, 1, None, None)], 1, 4, 4, 0, 276, (3, 0, None, None), 0)),
	(('AccountExpirationDate', 'retval'), 38, (38, (), [(16391, 10, None, None)], 1, 2, 4, 0, 280, (3, 0, None, None), 0)),
	(('AccountExpirationDate', 'retval'), 38, (38, (), [(7, 1, None, None)], 1, 4, 4, 0, 284, (3, 0, None, None), 0)),
	(('GraceLoginsAllowed', 'retval'), 41, (41, (), [(16387, 10, None, None)], 1, 2, 4, 0, 288, (3, 0, None, None), 0)),
	(('GraceLoginsAllowed', 'retval'), 41, (41, (), [(3, 1, None, None)], 1, 4, 4, 0, 292, (3, 0, None, None), 0)),
	(('GraceLoginsRemaining', 'retval'), 42, (42, (), [(16387, 10, None, None)], 1, 2, 4, 0, 296, (3, 0, None, None), 0)),
	(('GraceLoginsRemaining', 'retval'), 42, (42, (), [(3, 1, None, None)], 1, 4, 4, 0, 300, (3, 0, None, None), 0)),
	(('IsAccountLocked', 'retval'), 43, (43, (), [(16395, 10, None, None)], 1, 2, 4, 0, 304, (3, 0, None, None), 0)),
	(('IsAccountLocked', 'retval'), 43, (43, (), [(11, 1, None, None)], 1, 4, 4, 0, 308, (3, 0, None, None), 0)),
	(('LoginHours', 'retval'), 45, (45, (), [(16396, 10, None, None)], 1, 2, 4, 0, 312, (3, 0, None, None), 0)),
	(('LoginHours', 'retval'), 45, (45, (), [(12, 1, None, None)], 1, 4, 4, 0, 316, (3, 0, None, None), 0)),
	(('LoginWorkstations', 'retval'), 46, (46, (), [(16396, 10, None, None)], 1, 2, 4, 0, 320, (3, 0, None, None), 0)),
	(('LoginWorkstations', 'retval'), 46, (46, (), [(12, 1, None, None)], 1, 4, 4, 0, 324, (3, 0, None, None), 0)),
	(('MaxLogins', 'retval'), 47, (47, (), [(16387, 10, None, None)], 1, 2, 4, 0, 328, (3, 0, None, None), 0)),
	(('MaxLogins', 'retval'), 47, (47, (), [(3, 1, None, None)], 1, 4, 4, 0, 332, (3, 0, None, None), 0)),
	(('MaxStorage', 'retval'), 48, (48, (), [(16387, 10, None, None)], 1, 2, 4, 0, 336, (3, 0, None, None), 0)),
	(('MaxStorage', 'retval'), 48, (48, (), [(3, 1, None, None)], 1, 4, 4, 0, 340, (3, 0, None, None), 0)),
	(('PasswordExpirationDate', 'retval'), 49, (49, (), [(16391, 10, None, None)], 1, 2, 4, 0, 344, (3, 0, None, None), 0)),
	(('PasswordExpirationDate', 'retval'), 49, (49, (), [(7, 1, None, None)], 1, 4, 4, 0, 348, (3, 0, None, None), 0)),
	(('PasswordMinimumLength', 'retval'), 50, (50, (), [(16387, 10, None, None)], 1, 2, 4, 0, 352, (3, 0, None, None), 0)),
	(('PasswordMinimumLength', 'retval'), 50, (50, (), [(3, 1, None, None)], 1, 4, 4, 0, 356, (3, 0, None, None), 0)),
	(('PasswordRequired', 'retval'), 51, (51, (), [(16395, 10, None, None)], 1, 2, 4, 0, 360, (3, 0, None, None), 0)),
	(('PasswordRequired', 'retval'), 51, (51, (), [(11, 1, None, None)], 1, 4, 4, 0, 364, (3, 0, None, None), 0)),
	(('RequireUniquePassword', 'retval'), 52, (52, (), [(16395, 10, None, None)], 1, 2, 4, 0, 368, (3, 0, None, None), 0)),
	(('RequireUniquePassword', 'retval'), 52, (52, (), [(11, 1, None, None)], 1, 4, 4, 0, 372, (3, 0, None, None), 0)),
	(('EmailAddress', 'retval'), 60, (60, (), [(16392, 10, None, None)], 1, 2, 4, 0, 376, (3, 0, None, None), 0)),
	(('EmailAddress', 'retval'), 60, (60, (), [(8, 1, None, None)], 1, 4, 4, 0, 380, (3, 0, None, None), 0)),
	(('HomeDirectory', 'retval'), 61, (61, (), [(16392, 10, None, None)], 1, 2, 4, 0, 384, (3, 0, None, None), 0)),
	(('HomeDirectory', 'retval'), 61, (61, (), [(8, 1, None, None)], 1, 4, 4, 0, 388, (3, 0, None, None), 0)),
	(('Languages', 'retval'), 62, (62, (), [(16396, 10, None, None)], 1, 2, 4, 0, 392, (3, 0, None, None), 0)),
	(('Languages', 'retval'), 62, (62, (), [(12, 1, None, None)], 1, 4, 4, 0, 396, (3, 0, None, None), 0)),
	(('Profile', 'retval'), 63, (63, (), [(16392, 10, None, None)], 1, 2, 4, 0, 400, (3, 0, None, None), 0)),
	(('Profile', 'retval'), 63, (63, (), [(8, 1, None, None)], 1, 4, 4, 0, 404, (3, 0, None, None), 0)),
	(('LoginScript', 'retval'), 64, (64, (), [(16392, 10, None, None)], 1, 2, 4, 0, 408, (3, 0, None, None), 0)),
	(('LoginScript', 'retval'), 64, (64, (), [(8, 1, None, None)], 1, 4, 4, 0, 412, (3, 0, None, None), 0)),
	(('Picture', 'retval'), 65, (65, (), [(16396, 10, None, None)], 1, 2, 4, 0, 416, (3, 0, None, None), 0)),
	(('Picture', 'retval'), 65, (65, (), [(12, 1, None, None)], 1, 4, 4, 0, 420, (3, 0, None, None), 0)),
	(('HomePage', 'retval'), 120, (120, (), [(16392, 10, None, None)], 1, 2, 4, 0, 424, (3, 0, None, None), 0)),
	(('HomePage', 'retval'), 120, (120, (), [(8, 1, None, None)], 1, 4, 4, 0, 428, (3, 0, None, None), 0)),
	(('Groups', 'ppGroups'), 66, (66, (), [(16393, 10, None, "IID('{451A0030-72EC-11CF-B03B-00AA006E0975}')")], 1, 1, 4, 0, 432, (3, 0, None, None), 0)),
	(('SetPassword', 'NewPassword'), 67, (67, (), [(8, 1, None, None)], 1, 1, 4, 0, 436, (3, 0, None, None), 0)),
	(('ChangePassword', 'bstrOldPassword', 'bstrNewPassword'), 68, (68, (), [(8, 1, None, None), (8, 1, None, None)], 1, 1, 4, 0, 440, (3, 0, None, None), 0)),
]

IADsWinNTSystemInfo_vtables_dispatch_ = 1
IADsWinNTSystemInfo_vtables_ = [
	(('UserName', 'retval'), 2, (2, (), [(16392, 10, None, None)], 1, 2, 4, 0, 28, (3, 0, None, None), 0)),
	(('ComputerName', 'retval'), 3, (3, (), [(16392, 10, None, None)], 1, 2, 4, 0, 32, (3, 0, None, None), 0)),
	(('DomainName', 'retval'), 4, (4, (), [(16392, 10, None, None)], 1, 2, 4, 0, 36, (3, 0, None, None), 0)),
	(('PDC', 'retval'), 5, (5, (), [(16392, 10, None, None)], 1, 2, 4, 0, 40, (3, 0, None, None), 0)),
]

IDirectoryObject_vtables_dispatch_ = 0
IDirectoryObject_vtables_ = [
	(('GetObjectInformation', 'ppObjInfo'), 1610678272, (1610678272, (), [(16420, 2, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('GetObjectAttributes', 'pAttributeNames', 'dwNumberAttributes', 'ppAttributeEntries', 'pdwNumAttributesReturned'), 1610678273, (1610678273, (), [(16415, 1, None, None), (19, 1, None, None), (16420, 2, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('SetObjectAttributes', 'pAttributeEntries', 'dwNumAttributes', 'pdwNumAttributesModified'), 1610678274, (1610678274, (), [(36, 1, None, None), (19, 1, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('CreateDSObject', 'pszRDNName', 'pAttributeEntries', 'dwNumAttributes', 'ppObject'), 1610678275, (1610678275, (), [(31, 1, None, None), (36, 1, None, None), (19, 1, None, None), (16393, 2, None, None)], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
	(('DeleteDSObject', 'pszRDNName'), 1610678276, (1610678276, (), [(31, 1, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
]

IDirectorySchemaMgmt_vtables_dispatch_ = 0
IDirectorySchemaMgmt_vtables_ = [
	(('EnumAttributes', 'ppszAttrNames', 'dwNumAttributes', 'ppAttrDefinition', 'pdwNumAttributes'), 1610678272, (1610678272, (), [(16415, 0, None, None), (19, 0, None, None), (16420, 0, None, None), (16403, 0, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('CreateAttributeDefinition', 'pszAttributeName', 'pAttributeDefinition'), 1610678273, (1610678273, (), [(31, 0, None, None), (36, 0, None, None)], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('WriteAttributeDefinition', 'pszAttributeName', 'pAttributeDefinition'), 1610678274, (1610678274, (), [(31, 0, None, None), (36, 0, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('DeleteAttributeDefinition', 'pszAttributeName'), 1610678275, (1610678275, (), [(31, 0, None, None)], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
	(('EnumClasses', 'ppszClassNames', 'dwNumClasses', 'ppClassDefinition', 'pdwNumClasses'), 1610678276, (1610678276, (), [(16415, 0, None, None), (19, 0, None, None), (16420, 0, None, None), (16403, 0, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('WriteClassDefinition', 'pszClassName', 'pClassDefinition'), 1610678277, (1610678277, (), [(31, 0, None, None), (36, 0, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('CreateClassDefinition', 'pszClassName', 'pClassDefinition'), 1610678278, (1610678278, (), [(31, 0, None, None), (36, 0, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('DeleteClassDefinition', 'pszClassName'), 1610678279, (1610678279, (), [(31, 0, None, None)], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
]

IDirectorySearch_vtables_dispatch_ = 0
IDirectorySearch_vtables_ = [
	(('SetSearchPreference', 'pSearchPrefs', 'dwNumPrefs'), 1610678272, (1610678272, (), [(36, 1, None, None), (19, 1, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('ExecuteSearch', 'pszSearchFilter', 'pAttributeNames', 'dwNumberAttributes', 'phSearchResult'), 1610678273, (1610678273, (), [(31, 1, None, None), (16415, 1, None, None), (19, 1, None, None), (16408, 2, None, None)], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('AbandonSearch', 'phSearchResult'), 1610678274, (1610678274, (), [(16408, 1, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('GetFirstRow', 'hSearchResult'), 1610678275, (1610678275, (), [(16408, 1, None, None)], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
	(('GetNextRow', 'hSearchResult'), 1610678276, (1610678276, (), [(16408, 1, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('GetPreviousRow', 'hSearchResult'), 1610678277, (1610678277, (), [(16408, 1, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('GetNextColumnName', 'hSearchHandle', 'ppszColumnName'), 1610678278, (1610678278, (), [(16408, 1, None, None), (16415, 2, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('GetColumn', 'hSearchResult', 'szColumnName', 'pSearchColumn'), 1610678279, (1610678279, (), [(16408, 1, None, None), (31, 1, None, None), (36, 2, None, None)], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
	(('FreeColumn', 'pSearchColumn'), 1610678280, (1610678280, (), [(36, 1, None, None)], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('CloseSearchHandle', 'hSearchResult'), 1610678281, (1610678281, (), [(16408, 1, None, None)], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
]

IPrivateDispatch_vtables_dispatch_ = 0
IPrivateDispatch_vtables_ = [
	(('ADSIInitializeDispatchManager', 'dwExtensionId'), 1610678272, (1610678272, (), [(3, 1, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('ADSIGetTypeInfoCount', 'pctinfo'), 1610678273, (1610678273, (), [(16387, 2, None, None)], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('ADSIGetTypeInfo', 'itinfo', 'lcid', 'ppTInfo'), 1610678274, (1610678274, (), [(3, 1, None, None), (19, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('ADSIGetIDsOfNames', 'riid', 'rgszNames', 'cNames', 'lcid', 'rgdispid'), 1610678275, (1610678275, (), [(36, 1, None, None), (16402, 1, None, None), (3, 1, None, None), (19, 1, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
	(('ADSIInvoke', 'dispidMember', 'riid', 'lcid', 'wFlags', 'pdispparams', 'pvarResult', 'pexcepinfo', 'puArgErr'), 1610678276, (1610678276, (), [(3, 1, None, None), (36, 1, None, None), (19, 1, None, None), (18, 1, None, None), (36, 1, None, None), (16396, 2, None, None), (36, 2, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
]

IPrivateUnknown_vtables_dispatch_ = 0
IPrivateUnknown_vtables_ = [
	(('ADSIInitializeObject', 'lpszUserName', 'lpszPassword', 'lnReserved'), 1610678272, (1610678272, (), [(8, 1, None, None), (8, 1, None, None), (3, 1, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('ADSIReleaseObject',), 1610678273, (1610678273, (), [], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
]

ITypeComp_vtables_dispatch_ = 0
ITypeComp_vtables_ = [
	(('RemoteBind', 'szName', 'lHashVal', 'wFlags', 'ppTInfo', 'pDescKind', 'ppFuncDesc', 'ppVarDesc', 'ppTypeComp', 'pDummy'), 1610678272, (1610678272, (), [(31, 1, None, None), (19, 1, None, None), (18, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')"), (16387, 2, None, None), (16420, 2, None, None), (16420, 2, None, None), (16397, 2, None, "IID('{00020403-0000-0000-C000-000000000046}')"), (16403, 2, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('RemoteBindType', 'szName', 'lHashVal', 'ppTInfo'), 1610678273, (1610678273, (), [(31, 1, None, None), (19, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
]

ITypeInfo_vtables_dispatch_ = 0
ITypeInfo_vtables_ = [
	(('RemoteGetTypeAttr', 'ppTypeAttr', 'pDummy'), 1610678272, (1610678272, (), [(16420, 2, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('GetTypeComp', 'ppTComp'), 1610678273, (1610678273, (), [(16397, 2, None, "IID('{00020403-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('RemoteGetFuncDesc', 'index', 'ppFuncDesc', 'pDummy'), 1610678274, (1610678274, (), [(3, 1, None, None), (16420, 2, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('RemoteGetVarDesc', 'index', 'ppVarDesc', 'pDummy'), 1610678275, (1610678275, (), [(3, 1, None, None), (16420, 2, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
	(('RemoteGetNames', 'memid', 'rgBstrNames', 'cMaxNames', 'pcNames'), 1610678276, (1610678276, (), [(3, 1, None, None), (16392, 2, None, None), (3, 1, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('GetRefTypeOfImplType', 'index', 'pRefType'), 1610678277, (1610678277, (), [(3, 1, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('GetImplTypeFlags', 'index', 'pImplTypeFlags'), 1610678278, (1610678278, (), [(3, 1, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('LocalGetIDsOfNames',), 1610678279, (1610678279, (), [], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
	(('LocalInvoke',), 1610678280, (1610678280, (), [], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('RemoteGetDocumentation', 'memid', 'refPtrFlags', 'pBstrName', 'pBstrDocString', 'pdwHelpContext', 'pBstrHelpFile'), 1610678281, (1610678281, (), [(3, 1, None, None), (19, 1, None, None), (16392, 2, None, None), (16392, 2, None, None), (16403, 2, None, None), (16392, 2, None, None)], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
	(('RemoteGetDllEntry', 'memid', 'invkind', 'refPtrFlags', 'pBstrDllName', 'pBstrName', 'pwOrdinal'), 1610678282, (1610678282, (), [(3, 1, None, None), (3, 1, None, None), (19, 1, None, None), (16392, 2, None, None), (16392, 2, None, None), (16402, 2, None, None)], 1, 1, 4, 0, 52, (3, 0, None, None), 0)),
	(('GetRefTypeInfo', 'hreftype', 'ppTInfo'), 1610678283, (1610678283, (), [(19, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 56, (3, 0, None, None), 0)),
	(('LocalAddressOfMember',), 1610678284, (1610678284, (), [], 1, 1, 4, 0, 60, (3, 0, None, None), 0)),
	(('RemoteCreateInstance', 'riid', 'ppvObj'), 1610678285, (1610678285, (), [(36, 1, None, None), (16397, 2, None, None)], 1, 1, 4, 0, 64, (3, 0, None, None), 0)),
	(('GetMops', 'memid', 'pBstrMops'), 1610678286, (1610678286, (), [(3, 1, None, None), (16392, 2, None, None)], 1, 1, 4, 0, 68, (3, 0, None, None), 0)),
	(('RemoteGetContainingTypeLib', 'ppTLib', 'pIndex'), 1610678287, (1610678287, (), [(16397, 2, None, "IID('{00020402-0000-0000-C000-000000000046}')"), (16387, 2, None, None)], 1, 1, 4, 0, 72, (3, 0, None, None), 0)),
	(('LocalReleaseTypeAttr',), 1610678288, (1610678288, (), [], 1, 1, 4, 0, 76, (3, 0, None, None), 0)),
	(('LocalReleaseFuncDesc',), 1610678289, (1610678289, (), [], 1, 1, 4, 0, 80, (3, 0, None, None), 0)),
	(('LocalReleaseVarDesc',), 1610678290, (1610678290, (), [], 1, 1, 4, 0, 84, (3, 0, None, None), 0)),
]

ITypeLib_vtables_dispatch_ = 0
ITypeLib_vtables_ = [
	(('RemoteGetTypeInfoCount', 'pctinfo'), 1610678272, (1610678272, (), [(16387, 2, None, None)], 1, 1, 4, 0, 12, (3, 0, None, None), 0)),
	(('GetTypeInfo', 'index', 'ppTInfo'), 1610678273, (1610678273, (), [(3, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 16, (3, 0, None, None), 0)),
	(('GetTypeInfoType', 'index', 'pTKind'), 1610678274, (1610678274, (), [(3, 1, None, None), (16387, 2, None, None)], 1, 1, 4, 0, 20, (3, 0, None, None), 0)),
	(('GetTypeInfoOfGuid', 'GUID', 'ppTInfo'), 1610678275, (1610678275, (), [(36, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 24, (3, 0, None, None), 0)),
	(('RemoteGetLibAttr', 'ppTLibAttr', 'pDummy'), 1610678276, (1610678276, (), [(16420, 2, None, None), (16403, 2, None, None)], 1, 1, 4, 0, 28, (3, 0, None, None), 0)),
	(('GetTypeComp', 'ppTComp'), 1610678277, (1610678277, (), [(16397, 2, None, "IID('{00020403-0000-0000-C000-000000000046}')")], 1, 1, 4, 0, 32, (3, 0, None, None), 0)),
	(('RemoteGetDocumentation', 'index', 'refPtrFlags', 'pBstrName', 'pBstrDocString', 'pdwHelpContext', 'pBstrHelpFile'), 1610678278, (1610678278, (), [(3, 1, None, None), (19, 1, None, None), (16392, 2, None, None), (16392, 2, None, None), (16403, 2, None, None), (16392, 2, None, None)], 1, 1, 4, 0, 36, (3, 0, None, None), 0)),
	(('RemoteIsName', 'szNameBuf', 'lHashVal', 'pfName', 'pBstrLibName'), 1610678279, (1610678279, (), [(31, 1, None, None), (19, 1, None, None), (16387, 2, None, None), (16392, 2, None, None)], 1, 1, 4, 0, 40, (3, 0, None, None), 0)),
	(('RemoteFindName', 'szNameBuf', 'lHashVal', 'ppTInfo', 'rgMemId', 'pcFound', 'pBstrLibName'), 1610678280, (1610678280, (), [(31, 1, None, None), (19, 1, None, None), (16397, 2, None, "IID('{00020401-0000-0000-C000-000000000046}')"), (16387, 2, None, None), (16402, 3, None, None), (16392, 2, None, None)], 1, 1, 4, 0, 44, (3, 0, None, None), 0)),
	(('LocalReleaseTLibAttr',), 1610678281, (1610678281, (), [], 1, 1, 4, 0, 48, (3, 0, None, None), 0)),
]

RecordMap = {
	'tagTLIBATTR': '{00000000-0000-0000-0000-000000000000}',
}

CLSIDToClassMap = {
	'{334857CC-F934-11D2-BA96-00C04FB6D0D1}' : DNWithString,
	'{001677D0-FD16-11CE-ABC4-02608C9E7553}' : IADsContainer,
	'{9068270B-0939-11D1-8BE1-00C04FD8D503}' : IADsLargeInteger,
	'{274FAE1F-3626-11D1-A3A4-00C04FB950DC}' : NameTranslate,
	'{3E37E320-17E2-11CF-ABC4-02608C9E7553}' : IADsUser,
	'{B33143CB-4080-11D1-A3AC-00C04FB950DC}' : TypedName,
	'{0A75AFCD-4680-11D1-A3B4-00C04FB950DC}' : PostalAddress,
	'{6C6D65DC-AFD1-11D2-9CB9-0000F87A369E}' : IADsWinNTSystemInfo,
	'{27636B00-410F-11CF-B1FF-02608C9E7553}' : IADsGroup,
	'{C8F93DD0-4AE0-11CF-9E73-00AA004A5691}' : IADsClass,
	'{C8F93DD2-4AE0-11CF-9E73-00AA004A5691}' : IADsSyntax,
	'{C8F93DD3-4AE0-11CF-9E73-00AA004A5691}' : IADsProperty,
	'{68AF66E0-31CA-11CF-A98A-00AA006BC149}' : IADsService,
	'{72D3EDC2-A4C4-11D0-8533-00C04FD8D503}' : PropertyEntry,
	'{EF497680-1D9F-11CF-B1F3-02608C9E7553}' : IADsComputerOperations,
	'{370DF02E-F934-11D2-BA96-00C04FB6D0D1}' : IADsDNWithString,
	'{00E4C220-FD16-11CE-ABC4-02608C9E7553}' : IADsDomain,
	'{A89D1900-31CA-11CF-A98A-00AA006BC149}' : IADsFileService,
	'{F60FB803-4080-11D1-A3AC-00C04FB950DC}' : IADsReplicaPointer,
	'{A05E03A2-EFFE-11CF-8ABC-00C04FD8D503}' : IADsLocality,
	'{34A05B20-4AAB-11CF-AE2C-00AA006EBFB9}' : IADsResource,
	'{B8C787CA-9BDD-11D0-852C-00C04FD8D503}' : IADsSecurityDescriptor,
	'{B7EE91CC-9BDD-11D0-852C-00C04FD8D503}' : IADsAccessControlList,
	'{05792C8E-941F-11D0-8529-00C04FD8D503}' : IADsPropertyEntry,
	'{A02DED10-31CA-11CF-A98A-00AA006BC149}' : IADsFileServiceOperations,
	'{B3AD3E13-4080-11D1-A3AC-00C04FB950DC}' : Hold,
	'{A5062215-4681-11D1-A3B4-00C04FB950DC}' : FaxNumber,
	'{A2F733B8-EFFE-11CF-8ABC-00C04FD8D503}' : IADsOU,
	'{97AF011A-478E-11D1-A3B4-00C04FB950DC}' : IADsEmail,
	'{7E99C0A3-F935-11D2-BA96-00C04FB6D0D1}' : DNWithBinary,
	'{A1CD2DC6-EFFE-11CF-8ABC-00C04FD8D503}' : IADsO,
	'{B21A50A9-4080-11D1-A3AC-00C04FB950DC}' : IADsNetAddress,
	'{EB6DCAF0-4B83-11CF-A995-00AA006BC149}' : IADsFileShare,
	'{B75AC000-9BDD-11D0-852C-00C04FD8D503}' : AccessControlEntry,
	'{B0B71247-4080-11D1-A3AC-00C04FB950DC}' : NetAddress,
	'{B1B272A3-3625-11D1-A3A4-00C04FB950DC}' : IADsNameTranslate,
	'{72B945E0-253B-11CF-A988-00AA006BC149}' : IADsCollection,
	'{15F88A55-4680-11D1-A3B4-00C04FB950DC}' : CaseIgnoreList,
	'{1241400F-4680-11D1-A3B4-00C04FB950DC}' : OctetList,
	'{451A0030-72EC-11CF-B03B-00AA006E0975}' : IADsMembers,
	'{306E831C-5BC7-11D1-A3B8-00C04FB950DC}' : IADsPropertyValue2,
	'{124BE5C0-156E-11CF-A986-00AA006BC149}' : IADsPrintQueueOperations,
	'{7E99C0A2-F935-11D2-BA96-00C04FB6D0D1}' : IADsDNWithBinary,
	'{FCBF906F-4080-11D1-A3AC-00C04FB950DC}' : BackLink,
	'{50B6327F-AFD1-11D2-9CB9-0000F87A369E}' : ADSystemInfo,
	'{D592AED4-F420-11D0-A36E-00C04FB950DC}' : IADsPathname,
	'{C6F602B6-8F69-11D0-8528-00C04FD8D503}' : IADsPropertyList,
	'{398B7DA0-4AAB-11CF-AE2C-00AA006EBFB9}' : IADsSession,
	'{7B9E38B0-A97C-11D0-8534-00C04FD8D503}' : PropertyValue,
	'{B85EA052-9BDD-11D0-852C-00C04FD8D503}' : AccessControlList,
	'{8452D3AB-0869-11D1-A377-00C04FB950DC}' : IADsAcl,
	'{7B28B80F-4680-11D1-A3B4-00C04FB950DC}' : IADsOctetList,
	'{927971F5-0939-11D1-8BE1-00C04FD8D503}' : LargeInteger,
	'{A910DEA9-4680-11D1-A3B4-00C04FB950DC}' : IADsFaxNumber,
	'{FD8256D0-FD15-11CE-ABC4-02608C9E7553}' : IADs,
	'{79FA9AD0-A97C-11D0-8534-00C04FD8D503}' : IADsPropertyValue,
	'{66182EC4-AFD1-11D2-9CB9-0000F87A369E}' : WinNTSystemInfo,
	'{FD1302BD-4080-11D1-A3AC-00C04FB950DC}' : IADsBackLink,
	'{B2538919-4080-11D1-A3AC-00C04FB950DC}' : Path,
	'{B287FCD5-4080-11D1-A3AC-00C04FB950DC}' : IADsPath,
	'{F5D1BADF-4080-11D1-A3AC-00C04FB950DC}' : ReplicaPointer,
	'{B2BD0902-8878-11D1-8C21-00C04FD8D503}' : IADsDeleteOps,
	'{B2BED2EB-4080-11D1-A3AC-00C04FB950DC}' : Timestamp,
	'{5D7B33F0-31CA-11CF-A98A-00AA006BC149}' : IADsServiceOperations,
	'{F270C64A-FFB8-4AE4-85FE-3A75E5347966}' : ADsSecurityUtility,
	'{B2F5A901-4080-11D1-A3AC-00C04FB950DC}' : IADsTimestamp,
	'{A63251B2-5F21-474B-AB52-4A8EFAD10895}' : IADsSecurityUtility,
	'{28B96BA0-B330-11CF-A9AD-00AA006BC149}' : IADsNamespaces,
	'{080D0D78-F421-11D0-A36E-00C04FB950DC}' : Pathname,
	'{5BB11929-AFD1-11D2-9CB9-0000F87A369E}' : IADsADSystemInfo,
	'{DDF2891E-0F9C-11D0-8AD4-00C04FD8D503}' : IADsOpenDSObject,
	'{7ADECF29-4680-11D1-A3B4-00C04FB950DC}' : IADsPostalAddress,
	'{B15160D0-1226-11CF-A985-00AA006BC149}' : IADsPrintQueue,
	'{7B66B533-4680-11D1-A3B4-00C04FB950DC}' : IADsCaseIgnoreList,
	'{9A52DB30-1ECF-11CF-A988-00AA006BC149}' : IADsPrintJobOperations,
	'{B3EB3B37-4080-11D1-A3AC-00C04FB950DC}' : IADsHold,
	'{B371A349-4080-11D1-A3AC-00C04FB950DC}' : IADsTypedName,
	'{EFE3CC70-1D9F-11CF-B1F3-02608C9E7553}' : IADsComputer,
	'{8F92A857-478E-11D1-A3B4-00C04FB950DC}' : Email,
	'{B958F73C-9BDD-11D0-852C-00C04FD8D503}' : SecurityDescriptor,
	'{32FB6780-1ED0-11CF-A988-00AA006BC149}' : IADsPrintJob,
	'{46F14FDA-232B-11D1-A808-00C04FD8D5A8}' : IADsObjectOptions,
	'{B4F3A14C-9BDD-11D0-852C-00C04FD8D503}' : IADsAccessControlEntry,
}
CLSIDToPackageMap = {}
win32com.client.CLSIDToClass.RegisterCLSIDsFromDict( CLSIDToClassMap )
VTablesToPackageMap = {}
VTablesToClassMap = {
	'{FD1302BD-4080-11D1-A3AC-00C04FB950DC}' : 'IADsBackLink',
	'{05792C8E-941F-11D0-8529-00C04FD8D503}' : 'IADsPropertyEntry',
	'{32FB6780-1ED0-11CF-A988-00AA006BC149}' : 'IADsPrintJob',
	'{8452D3AB-0869-11D1-A377-00C04FB950DC}' : 'IADsAcl',
	'{7B28B80F-4680-11D1-A3B4-00C04FB950DC}' : 'IADsOctetList',
	'{124BE5C0-156E-11CF-A986-00AA006BC149}' : 'IADsPrintQueueOperations',
	'{5BB11929-AFD1-11D2-9CB9-0000F87A369E}' : 'IADsADSystemInfo',
	'{86AB4BBE-65F6-11D1-8C13-00C04FD8D503}' : 'IPrivateDispatch',
	'{A02DED10-31CA-11CF-A98A-00AA006BC149}' : 'IADsFileServiceOperations',
	'{3D35553C-D2B0-11D1-B17B-0000F87593A0}' : 'IADsExtension',
	'{B2F5A901-4080-11D1-A3AC-00C04FB950DC}' : 'IADsTimestamp',
	'{1346CE8C-9039-11D0-8528-00C04FD8D503}' : 'IADsAggregatee',
	'{97AF011A-478E-11D1-A3B4-00C04FB950DC}' : 'IADsEmail',
	'{A910DEA9-4680-11D1-A3B4-00C04FB950DC}' : 'IADsFaxNumber',
	'{FD8256D0-FD15-11CE-ABC4-02608C9E7553}' : 'IADs',
	'{A1CD2DC6-EFFE-11CF-8ABC-00C04FD8D503}' : 'IADsO',
	'{9068270B-0939-11D1-8BE1-00C04FD8D503}' : 'IADsLargeInteger',
	'{B15160D0-1226-11CF-A985-00AA006BC149}' : 'IADsPrintQueue',
	'{79FA9AD0-A97C-11D0-8534-00C04FD8D503}' : 'IADsPropertyValue',
	'{52DB5FB0-941F-11D0-8529-00C04FD8D503}' : 'IADsAggregator',
	'{7B66B533-4680-11D1-A3B4-00C04FB950DC}' : 'IADsCaseIgnoreList',
	'{9A52DB30-1ECF-11CF-A988-00AA006BC149}' : 'IADsPrintJobOperations',
	'{EB6DCAF0-4B83-11CF-A995-00AA006BC149}' : 'IADsFileShare',
	'{001677D0-FD16-11CE-ABC4-02608C9E7553}' : 'IADsContainer',
	'{89126BAB-6EAD-11D1-8C18-00C04FD8D503}' : 'IPrivateUnknown',
	'{34A05B20-4AAB-11CF-AE2C-00AA006EBFB9}' : 'IADsResource',
	'{3E37E320-17E2-11CF-ABC4-02608C9E7553}' : 'IADsUser',
	'{B1B272A3-3625-11D1-A3A4-00C04FB950DC}' : 'IADsNameTranslate',
	'{B371A349-4080-11D1-A3AC-00C04FB950DC}' : 'IADsTypedName',
	'{B7EE91CC-9BDD-11D0-852C-00C04FD8D503}' : 'IADsAccessControlList',
	'{27636B00-410F-11CF-B1FF-02608C9E7553}' : 'IADsGroup',
	'{00020401-0000-0000-C000-000000000046}' : 'ITypeInfo',
	'{00020402-0000-0000-C000-000000000046}' : 'ITypeLib',
	'{00020403-0000-0000-C000-000000000046}' : 'ITypeComp',
	'{72B945E0-253B-11CF-A988-00AA006BC149}' : 'IADsCollection',
	'{B287FCD5-4080-11D1-A3AC-00C04FB950DC}' : 'IADsPath',
	'{EFE3CC70-1D9F-11CF-B1F3-02608C9E7553}' : 'IADsComputer',
	'{398B7DA0-4AAB-11CF-AE2C-00AA006EBFB9}' : 'IADsSession',
	'{451A0030-72EC-11CF-B03B-00AA006E0975}' : 'IADsMembers',
	'{C8F93DD0-4AE0-11CF-9E73-00AA004A5691}' : 'IADsClass',
	'{C8F93DD2-4AE0-11CF-9E73-00AA004A5691}' : 'IADsSyntax',
	'{C8F93DD3-4AE0-11CF-9E73-00AA004A5691}' : 'IADsProperty',
	'{109BA8EC-92F0-11D0-A790-00C04FD8D5A8}' : 'IDirectorySearch',
	'{68AF66E0-31CA-11CF-A98A-00AA006BC149}' : 'IADsService',
	'{306E831C-5BC7-11D1-A3B8-00C04FB950DC}' : 'IADsPropertyValue2',
	'{A05E03A2-EFFE-11CF-8ABC-00C04FD8D503}' : 'IADsLocality',
	'{A2F733B8-EFFE-11CF-8ABC-00C04FD8D503}' : 'IADsOU',
	'{EF497680-1D9F-11CF-B1F3-02608C9E7553}' : 'IADsComputerOperations',
	'{7ADECF29-4680-11D1-A3B4-00C04FB950DC}' : 'IADsPostalAddress',
	'{E798DE2C-22E4-11D0-84FE-00C04FD8D503}' : 'IDirectoryObject',
	'{7E99C0A2-F935-11D2-BA96-00C04FB6D0D1}' : 'IADsDNWithBinary',
	'{5D7B33F0-31CA-11CF-A98A-00AA006BC149}' : 'IADsServiceOperations',
	'{D592AED4-F420-11D0-A36E-00C04FB950DC}' : 'IADsPathname',
	'{B21A50A9-4080-11D1-A3AC-00C04FB950DC}' : 'IADsNetAddress',
	'{75DB3B9C-A4D8-11D0-A79C-00C04FD8D5A8}' : 'IDirectorySchemaMgmt',
	'{370DF02E-F934-11D2-BA96-00C04FB6D0D1}' : 'IADsDNWithString',
	'{DDF2891E-0F9C-11D0-8AD4-00C04FD8D503}' : 'IADsOpenDSObject',
	'{00E4C220-FD16-11CE-ABC4-02608C9E7553}' : 'IADsDomain',
	'{B4F3A14C-9BDD-11D0-852C-00C04FD8D503}' : 'IADsAccessControlEntry',
	'{C6F602B6-8F69-11D0-8528-00C04FD8D503}' : 'IADsPropertyList',
	'{F60FB803-4080-11D1-A3AC-00C04FB950DC}' : 'IADsReplicaPointer',
	'{6C6D65DC-AFD1-11D2-9CB9-0000F87A369E}' : 'IADsWinNTSystemInfo',
	'{B3EB3B37-4080-11D1-A3AC-00C04FB950DC}' : 'IADsHold',
	'{A63251B2-5F21-474B-AB52-4A8EFAD10895}' : 'IADsSecurityUtility',
	'{28B96BA0-B330-11CF-A9AD-00AA006BC149}' : 'IADsNamespaces',
	'{B8C787CA-9BDD-11D0-852C-00C04FD8D503}' : 'IADsSecurityDescriptor',
	'{46F14FDA-232B-11D1-A808-00C04FD8D5A8}' : 'IADsObjectOptions',
	'{A89D1900-31CA-11CF-A98A-00AA006BC149}' : 'IADsFileService',
	'{B2BD0902-8878-11D1-8C21-00C04FD8D503}' : 'IADsDeleteOps',
}


NamesToIIDMap = {
	'IADsTypedName' : '{B371A349-4080-11D1-A3AC-00C04FB950DC}',
	'ITypeInfo' : '{00020401-0000-0000-C000-000000000046}',
	'IADsNetAddress' : '{B21A50A9-4080-11D1-A3AC-00C04FB950DC}',
	'IADsTimestamp' : '{B2F5A901-4080-11D1-A3AC-00C04FB950DC}',
	'IADsNamespaces' : '{28B96BA0-B330-11CF-A9AD-00AA006BC149}',
	'IADsO' : '{A1CD2DC6-EFFE-11CF-8ABC-00C04FD8D503}',
	'IADsObjectOptions' : '{46F14FDA-232B-11D1-A808-00C04FD8D5A8}',
	'IADsFaxNumber' : '{A910DEA9-4680-11D1-A3B4-00C04FB950DC}',
	'IADsAccessControlEntry' : '{B4F3A14C-9BDD-11D0-852C-00C04FD8D503}',
	'IADsPostalAddress' : '{7ADECF29-4680-11D1-A3B4-00C04FB950DC}',
	'IADsPropertyValue2' : '{306E831C-5BC7-11D1-A3B8-00C04FB950DC}',
	'ITypeComp' : '{00020403-0000-0000-C000-000000000046}',
	'IADsContainer' : '{001677D0-FD16-11CE-ABC4-02608C9E7553}',
	'IADsCaseIgnoreList' : '{7B66B533-4680-11D1-A3B4-00C04FB950DC}',
	'IADsComputerOperations' : '{EF497680-1D9F-11CF-B1F3-02608C9E7553}',
	'IPrivateDispatch' : '{86AB4BBE-65F6-11D1-8C13-00C04FD8D503}',
	'IADsSecurityUtility' : '{A63251B2-5F21-474B-AB52-4A8EFAD10895}',
	'IADsGroup' : '{27636B00-410F-11CF-B1FF-02608C9E7553}',
	'IADsOpenDSObject' : '{DDF2891E-0F9C-11D0-8AD4-00C04FD8D503}',
	'ITypeLib' : '{00020402-0000-0000-C000-000000000046}',
	'IDirectoryObject' : '{E798DE2C-22E4-11D0-84FE-00C04FD8D503}',
	'IADs' : '{FD8256D0-FD15-11CE-ABC4-02608C9E7553}',
	'IADsClass' : '{C8F93DD0-4AE0-11CF-9E73-00AA004A5691}',
	'IADsDeleteOps' : '{B2BD0902-8878-11D1-8C21-00C04FD8D503}',
	'IADsSecurityDescriptor' : '{B8C787CA-9BDD-11D0-852C-00C04FD8D503}',
	'IADsCollection' : '{72B945E0-253B-11CF-A988-00AA006BC149}',
	'IADsSyntax' : '{C8F93DD2-4AE0-11CF-9E73-00AA004A5691}',
	'IADsExtension' : '{3D35553C-D2B0-11D1-B17B-0000F87593A0}',
	'IADsPrintJob' : '{32FB6780-1ED0-11CF-A988-00AA006BC149}',
	'IADsServiceOperations' : '{5D7B33F0-31CA-11CF-A98A-00AA006BC149}',
	'IPrivateUnknown' : '{89126BAB-6EAD-11D1-8C18-00C04FD8D503}',
	'IADsUser' : '{3E37E320-17E2-11CF-ABC4-02608C9E7553}',
	'IADsPropertyList' : '{C6F602B6-8F69-11D0-8528-00C04FD8D503}',
	'IADsPrintJobOperations' : '{9A52DB30-1ECF-11CF-A988-00AA006BC149}',
	'IADsBackLink' : '{FD1302BD-4080-11D1-A3AC-00C04FB950DC}',
	'IADsOU' : '{A2F733B8-EFFE-11CF-8ABC-00C04FD8D503}',
	'IADsReplicaPointer' : '{F60FB803-4080-11D1-A3AC-00C04FB950DC}',
	'IADsMembers' : '{451A0030-72EC-11CF-B03B-00AA006E0975}',
	'IADsOctetList' : '{7B28B80F-4680-11D1-A3B4-00C04FB950DC}',
	'IADsPathname' : '{D592AED4-F420-11D0-A36E-00C04FB950DC}',
	'IADsPrintQueueOperations' : '{124BE5C0-156E-11CF-A986-00AA006BC149}',
	'IADsHold' : '{B3EB3B37-4080-11D1-A3AC-00C04FB950DC}',
	'IADsWinNTSystemInfo' : '{6C6D65DC-AFD1-11D2-9CB9-0000F87A369E}',
	'IADsFileService' : '{A89D1900-31CA-11CF-A98A-00AA006BC149}',
	'IADsDNWithBinary' : '{7E99C0A2-F935-11D2-BA96-00C04FB6D0D1}',
	'IADsAggregator' : '{52DB5FB0-941F-11D0-8529-00C04FD8D503}',
	'IADsPropertyEntry' : '{05792C8E-941F-11D0-8529-00C04FD8D503}',
	'IADsFileServiceOperations' : '{A02DED10-31CA-11CF-A98A-00AA006BC149}',
	'IADsPrintQueue' : '{B15160D0-1226-11CF-A985-00AA006BC149}',
	'IADsLocality' : '{A05E03A2-EFFE-11CF-8ABC-00C04FD8D503}',
	'IADsADSystemInfo' : '{5BB11929-AFD1-11D2-9CB9-0000F87A369E}',
	'IDirectorySchemaMgmt' : '{75DB3B9C-A4D8-11D0-A79C-00C04FD8D5A8}',
	'IADsLargeInteger' : '{9068270B-0939-11D1-8BE1-00C04FD8D503}',
	'IADsService' : '{68AF66E0-31CA-11CF-A98A-00AA006BC149}',
	'IADsAggregatee' : '{1346CE8C-9039-11D0-8528-00C04FD8D503}',
	'IADsPath' : '{B287FCD5-4080-11D1-A3AC-00C04FB950DC}',
	'IADsAccessControlList' : '{B7EE91CC-9BDD-11D0-852C-00C04FD8D503}',
	'IADsPropertyValue' : '{79FA9AD0-A97C-11D0-8534-00C04FD8D503}',
	'IADsResource' : '{34A05B20-4AAB-11CF-AE2C-00AA006EBFB9}',
	'IADsProperty' : '{C8F93DD3-4AE0-11CF-9E73-00AA004A5691}',
	'IADsNameTranslate' : '{B1B272A3-3625-11D1-A3A4-00C04FB950DC}',
	'IADsSession' : '{398B7DA0-4AAB-11CF-AE2C-00AA006EBFB9}',
	'IADsDomain' : '{00E4C220-FD16-11CE-ABC4-02608C9E7553}',
	'IADsComputer' : '{EFE3CC70-1D9F-11CF-B1F3-02608C9E7553}',
	'IADsAcl' : '{8452D3AB-0869-11D1-A377-00C04FB950DC}',
	'IADsFileShare' : '{EB6DCAF0-4B83-11CF-A995-00AA006BC149}',
	'IADsDNWithString' : '{370DF02E-F934-11D2-BA96-00C04FB6D0D1}',
	'IADsEmail' : '{97AF011A-478E-11D1-A3B4-00C04FB950DC}',
	'IDirectorySearch' : '{109BA8EC-92F0-11D0-A790-00C04FD8D5A8}',
}

win32com.client.constants.__dicts__.append(constants.__dict__)

