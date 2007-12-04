#!/usr/bin/python2.3
#
# kadm5.py - Remote administration of Kerberos Administration Servers
# Copyright (C) 2004 Mark R. Roach
#
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA      02111-1307      USA

import os
from ctypes import *

KRB_FLAVOR_MIT = 1
KRB_FLAVOR_HEIMDAL = 2

# kerberos library names for mit and heimdal kerberos
MIT_KRB5 = 'libkrb5.so.3'
HEIMDAL_KRB5 = 'libkrb5.so.17'

# library names for adm5clnt libraries
MIT_ADM5CLNT = 'libkadm5clnt.so.5' 
MIT_ADM5SRV = 'libkadm5srv.so.5'
HEIMDAL_ADM5CLNT = 'libkadm5clnt.so.4'
HEIMDAL_ADM5SRV = '/usr/lib/libkadm5srv.so.7'
#libkadm5clnt = CDLL('libkadm5clnt.so.5')

# On this system int32 == c_int, will have to check
# if that is true on all systems (probably not)
INT32 = c_int
INT16 = c_short
UINT32 = c_uint
KRB5_UI_4 = c_uint


class KRB5_CONST(object):
    def __init__(self):
        #/* Attributes */
        self.KDB_DISALLOW_POSTDATED =   0x00000001
        self.KDB_DISALLOW_FORWARDABLE =  0x00000002
        self.KDB_DISALLOW_TGT_BASED =    0x00000004
        self.KDB_DISALLOW_RENEWABLE =    0x00000008
        self.KDB_DISALLOW_PROXIABLE =    0x00000010
        self.KDB_DISALLOW_DUP_SKEY =     0x00000020
        self.KDB_DISALLOW_ALL_TIX =      0x00000040
        self.KDB_REQUIRES_PRE_AUTH =     0x00000080
        self.KDB_REQUIRES_HW_AUTH =      0x00000100
        self.KDB_REQUIRES_PWCHANGE =     0x00000200
        self.KDB_DISALLOW_SVR =          0x00001000
        self.KDB_PWCHANGE_SERVICE =      0x00002000
        self.KDB_SUPPORT_DESMD5 =        0x00004000
        self.KDB_NEW_PRINC =             0x00008000

        self.CC_BADNAME =               (-1765328245L)
        self.CC_UNKNOWN_TYPE =          (-1765328244L)
        self.CC_NOTFOUND =              (-1765328243L)
        self.CC_END =                   (-1765328242L)

        self.TC_OPENCLOSE = 0x1

        class KEY_SALT_TUPLE(Structure):
            _fields_ = [('ks_enctype', INT32),
                        ('ks_salttype', INT32)]
        self.KEY_SALT_TUPLE = KEY_SALT_TUPLE
        self.P_KEY_SALT_TUPLE = POINTER(KEY_SALT_TUPLE)
        
        class DATA(Structure):
            _fields_ = [('magic', INT32),
                        ('length', c_uint),
                        ('data', c_char_p)]
        self.DATA = DATA
        self.P_DATA = POINTER(DATA)
      
        class PRINCIPAL_DATA(Structure):
            _fields_ = [('magic',   INT32),
                        ('realm',   self.DATA),
                        ('data',    self.P_DATA),
                        ('length',  INT32),
                        ('type',    INT32)]
        self.PRINCIPAL_DATA = PRINCIPAL_DATA
        self.PRINCIPAL = POINTER(PRINCIPAL_DATA)

        class KEYBLOCK(Structure):
            _fields_ = [('magic',   INT32),
                        ('enctype', INT32),
                        ('length',  c_uint),
                        ('contents', c_char_p)]
        self.KEYBLOCK = KEYBLOCK

        class TICKET_TIMES(Structure):
            _fields_ = [('authtime',    INT32),
                        ('starttime',   INT32),
                        ('endtime',     INT32),
                        ('renew_till',  INT32)]
        self.TICKET_TIMES = TICKET_TIMES

        class CREDS(Structure):
            _fields_ = [('magic',   INT32),
                        ('client',  self.PRINCIPAL),
                        ('server',  self.PRINCIPAL),
                        ('keyblock', self.KEYBLOCK),
                        ('times', self.TICKET_TIMES),
                        ('is_skey', c_uint),
                        ('flags',   INT32),
                        ('addresses', c_void_p),
                        ('ticket',  self.DATA),
                        ('second_ticket',   self.DATA),
                        ('authdata',    c_void_p)]
        self.CREDS = CREDS

class KADM5_CONST(object):

    flavor = KRB_FLAVOR_MIT
    
    _KRB5 = KRB5_CONST()

    API_VERSION_MASK = 0x12345700
    API_VERSION_1 =    API_VERSION_MASK|0x01
    API_VERSION_2 =    API_VERSION_MASK|0x02
    STRUCT_VERSION_MASK =      0x12345600
    STRUCT_VERSION_1 = STRUCT_VERSION_MASK|0x01
    STRUCT_VERSION =   STRUCT_VERSION_1

    CONFIG_REALM =             0x000001
    CONFIG_DBNAME =            0x000002
    CONFIG_MKEY_NAME =         0x000004
    CONFIG_MAX_LIFE =          0x000008
    CONFIG_MAX_RLIFE =         0x000010
    CONFIG_EXPIRATION =        0x000020
    CONFIG_FLAGS =             0x000040
    CONFIG_ADMIN_KEYTAB =      0x000080
    CONFIG_STASH_FILE =        0x000100
    CONFIG_ENCTYPE =           0x000200
    CONFIG_ADBNAME =           0x000400
    CONFIG_ADB_LOCKFILE =      0x000800
    CONFIG_PROFILE =           0x001000
    CONFIG_ACL_FILE =          0x002000
    CONFIG_KADMIND_PORT =      0x004000
    CONFIG_ENCTYPES =          0x008000
    CONFIG_ADMIN_SERVER =      0x010000
    CONFIG_DICT_FILE =         0x020000
    CONFIG_MKEY_FROM_KBD =     0x040000
    CONFIG_KPASSWD_PORT =      0x080000

    CC_END =              336760974
    TC_OPENCLOSE =        0x00000001

    PRINCIPAL_NORMAL_MASK = 0x01ffff

    ADMIN_SERVICE =    "kadmin/admin"
    CHANGEPW_SERVICE = "kadmin/changepw"
    HIST_PRINCIPAL =   "kadmin/history"

    PRINCIPAL =         0x000001
    PRINC_EXPIRE_TIME = 0x000002
    PW_EXPIRATION =    0x000004
    LAST_PWD_CHANGE =  0x000008
    ATTRIBUTES =       0x000010
    MAX_LIFE =         0x000020
    MOD_TIME =         0x000040
    MOD_NAME =         0x000080
    KVNO =             0x000100
    MKVNO =            0x000200
    AUX_ATTRIBUTES =   0x000400
    POLICY =           0x000800
    POLICY_CLR =       0x001000
    #/* version 2 masks */
    MAX_RLIFE =        0x002000
    LAST_SUCCESS =     0x004000
    LAST_FAILED =      0x008000
    FAIL_AUTH_COUNT =  0x010000
    KEY_DATA =         0x020000
    TL_DATA =          0x040000
    
    class CONFIG_PARAMS(Structure):
        _fields_ = [('mask',            c_long),
                    ('realm',           c_char_p),
                    ('profile',         c_char_p),
                    ('kadmind_port',    c_int),
                    ('kpasswd_port',    c_int),
                    ('admin_server',    c_char_p),
                    ('dbname',          c_char_p),
                    ('admin_dbname',    c_char_p),
                    ('admin_lockfile',  c_char_p),
                    ('admin_keytab',    c_char_p),
                    ('acl_file',        c_char_p),
                    ('dict_file',       c_char_p),
                    ('mkey_from_kbd',   c_int),
                    ('stash_file',      c_char_p),
                    ('mkey_name',       c_char_p),
                    ('enctype',         INT32),
                    ('max_life',        INT32),
                    ('max_rlife',       INT32),
                    ('expiration',      INT32),
                    ('flags',           INT32),
                    ('keysalts',        c_void_p),  #P_KRB5_KEY_SALT_TUPLE),
                    ('num_keysalts',    INT32)]
    P_CONFIG_PARAMS = POINTER(CONFIG_PARAMS)

    def __init__(self):
        class PRINCIPAL_ENT_REC(Structure):
            _fields_ = [('principal',       self._KRB5.PRINCIPAL),
                        ('princ_expire_time', INT32),
                        ('last_pw_change',  INT32),
                        ('pw_expiration',   INT32),
                        ('max_life',        INT32),
                        ('mod_name',        self._KRB5.PRINCIPAL),
                        ('mod_date',        INT32),
                        ('attributes',       INT32),
                        ('kvno',            c_uint),
                        ('mkvno',           c_uint),
                        ('policy',          c_char_p),
                        ('aux_attributes',  c_long),
                        ('max_renewable_life',  INT32),
                        ('last_success',    INT32),
                        ('last_failed',     INT32),
                        ('fail_auth_count', INT32),
                        ('n_key_data',      INT16),
                        ('n_tl_data',       INT16),
                        ('tl_data',         c_void_p),
                        ('key_data',        c_void_p)]
        self.PRINCIPAL_ENT_REC = PRINCIPAL_ENT_REC
                    
    class POLICY_ENT_REC(Structure):
        _fields_ = [('policy', c_char_p),
                    ('pw_min_life', c_long),
                    ('pw_max_life', c_long),
                    ('pw_min_length', c_long),
                    ('pw_min_classes', c_long),
                    ('pw_history_num', c_long),
                    ('policy_refcnt', c_long)]

class KRB5_HEIMDAL_CONST(object):
    def __init__(self):
        self.KDB_DISALLOW_POSTDATED =    0x00000001
        self.KDB_DISALLOW_FORWARDABLE =  0x00000002
        self.KDB_DISALLOW_TGT_BASED =    0x00000004
        self.KDB_DISALLOW_RENEWABLE =    0x00000008
        self.KDB_DISALLOW_PROXIABLE =    0x00000010
        self.KDB_DISALLOW_DUP_SKEY =     0x00000020
        self.KDB_DISALLOW_ALL_TIX =      0x00000040
        self.KDB_REQUIRES_PRE_AUTH =     0x00000080
        self.KDB_REQUIRES_HW_AUTH =      0x00000100
        self.KDB_REQUIRES_PWCHANGE =     0x00000200
        self.KDB_DISALLOW_SVR =          0x00001000
        self.KDB_PWCHANGE_SERVICE =      0x00002000
        self.KDB_SUPPORT_DESMD5 =        0x00004000
        self.KDB_NEW_PRINC =             0x00008000
        self.CC_END =                    336760974
        self.TC_OPENCLOSE =             0x00000001

        class NameString(Structure):
            _fields_ = [('len', c_int),
                        ('val', c_char_p)]

        class PRINCIPALNAME(Structure):
            _fields_ = [('name_type', c_int),
                        ('name_string', NameString)]
        self.PRINCIPALNAME = PRINCIPALNAME
        
        class PRINCIPAL_DATA(Structure):
            _fields_ = [('name', self.PRINCIPALNAME),
                        ('realm', c_char_p)]

        self.PRINCIPAL_DATA = PRINCIPAL_DATA
        self.PRINCIPAL = POINTER(self.PRINCIPAL_DATA)

        class DATA(Structure):
            _fields_ = [('length', c_int),
                        ('data',  c_void_p)]
        self.DATA = DATA
        self.P_DATA = POINTER(self.DATA)

        class KEYBLOCK(Structure):
            _fields_ = [('keytype', c_int),
                        ('keyvalue', c_void_p)]
        self.KEYBLOCK = KEYBLOCK

        class TIMES(Structure):
            _fields_ = [('authtime', INT32),
                        ('starttime', INT32),
                        ('endtime',   INT32),
                        ('renew_till', INT32)]
        self.TIMES = TIMES

        class AUTHDATA(Structure):
            _fields_ = [('len', INT32),
                        ('val', c_void_p)]
        self.AUTHDATA = AUTHDATA

        class ADDRESS(Structure):
            _fields_ = [('addr_type', c_int),
                        ('address', c_void_p)]
        self.ADDRESS = ADDRESS

        class ADDRESSES(Structure):
            _fields_ = [('len',     c_uint),
                        ('val',     POINTER(self.ADDRESS))]
        self.ADDRESSES = ADDRESSES

        class CREDS(Structure):
            _fields_ = [('client', c_void_p),
                        ('server', c_void_p),
                        ('session', self.KEYBLOCK),
                        ('times',  self.TIMES),
                        ('ticket', self.DATA),
                        ('second_ticket', self.DATA),
                        ('authdata',      self.AUTHDATA),
                        ('addresses',     self.ADDRESSES),
                        ('flags',         INT32)]

        self.CREDS = CREDS 

        self.PROMPT_TYPE_PASSWORD           = 0x1,
        self.PROMPT_TYPE_NEW_PASSWORD       = 0x2,
        self.PROMPT_TYPE_NEW_PASSWORD_AGAIN = 0x3,
        self.PROMPT_TYPE_PREAUTH            = 0x4

        class PROMPT(Structure):
            _fields_ = [('prompt', c_char_p),
                        ('hidden', c_int),
                        ('reply', self.P_DATA),
                        ('type', c_int)]
                        
        self.PROMPTER_FCT = CFUNCTYPE(c_void_p, INT32, c_void_p,
                                      c_char_p, c_char_p, c_int, 
                                      POINTER(PROMPT))

class KADM5_HEIMDAL_CONST(object):

    flavor = KRB_FLAVOR_HEIMDAL

    _KRB5 = KRB5_HEIMDAL_CONST()

    API_VERSION_2 = c_ulong(2)
    STRUCT_VERSION = c_ulong(0)

    CONFIG_REALM =                     (1 << 0)
    CONFIG_PROFILE =                   (1 << 1)
    CONFIG_KADMIND_PORT =              (1 << 2)
    CONFIG_ADMIN_SERVER =              (1 << 3)
    CONFIG_DBNAME =                    (1 << 4)
    CONFIG_ADBNAME =                   (1 << 5)
    CONFIG_ADB_LOCKFILE =              (1 << 6)
    CONFIG_ACL_FILE =                  (1 << 7)
    CONFIG_DICT_FILE =                 (1 << 8)
    CONFIG_ADMIN_KEYTAB =              (1 << 9)
    CONFIG_MKEY_FROM_KEYBOARD =        (1 << 10)
    CONFIG_STASH_FILE =                (1 << 11)
    CONFIG_MKEY_NAME =                 (1 << 12)
    CONFIG_ENCTYPE =                   (1 << 13)
    CONFIG_MAX_LIFE =                  (1 << 14)
    CONFIG_MAX_RLIFE =                 (1 << 15)
    CONFIG_EXPIRATION =                (1 << 16)
    CONFIG_FLAGS =                     (1 << 17)
    CONFIG_ENCTYPES =                  (1 << 18)

    CC_END =                    336760974
    TC_OPENCLOSE =             0x00000001

    PRINCIPAL =        0x000001
    PRINC_EXPIRE_TIME = 0x000002
    PW_EXPIRATION =    0x000004
    LAST_PWD_CHANGE =  0x000008
    ATTRIBUTES =       0x000010
    MAX_LIFE =         0x000020
    MOD_TIME =         0x000040
    MOD_NAME =         0x000080
    KVNO =             0x000100
    MKVNO =            0x000200
    AUX_ATTRIBUTES =   0x000400
    POLICY =           0x000800
    POLICY_CLR =       0x001000
    MAX_RLIFE =        0x002000
    LAST_SUCCESS =     0x004000
    LAST_FAILED =      0x008000
    FAIL_AUTH_COUNT =  0x010000
    KEY_DATA =         0x020000
    TL_DATA =          0x040000

    PRINCIPAL_NORMAL_MASK = (~(KEY_DATA | TL_DATA))


    ADMIN_SERVICE =    "kadmin/admin"
    CHANGEPW_SERVICE = "kadmin/changepw"
    HIST_PRINCIPAL =   "kadmin/history"

    
    class CONFIG_PARAMS(Structure):
        _fields_ = [('mask', c_uint),
                    ('realm', c_char_p),
                    ('kadmind_port', c_int),
                    ('admin_server', c_char_p),
                    ('dbname', c_char_p),
                    ('acl_file', c_char_p),
                    ('stash_file', c_char_p)]

    P_CONFIG_PARAMS = POINTER(CONFIG_PARAMS)
    def __init__(self):
        class PRINCIPAL_ENT_REC(Structure):
            _fields_ = [('principal',       self._KRB5.PRINCIPAL),
                        ('princ_expire_time', INT32),
                        ('last_pw_change',  INT32),
                        ('pw_expiration',   INT32),
                        ('max_life',        INT32),
                        ('mod_name',        self._KRB5.PRINCIPAL),
                        ('mod_date',        INT32),
                        ('attributes',       INT32),
                        ('kvno',            c_uint),
                        ('mkvno',           c_uint),
                        ('policy',          c_char_p),
                        ('aux_attributes',  UINT32),
                        ('max_renewable_life',  INT32),
                        ('last_success',    INT32),
                        ('last_failed',     INT32),
                        ('fail_auth_count', INT32),
                        ('n_key_data',      INT16),
                        ('n_tl_data',       INT16),
                        ('tl_data',         c_void_p),
                        ('key_data',        c_void_p)]
        self.PRINCIPAL_ENT_REC = PRINCIPAL_ENT_REC
                    
    class POLICY_ENT_REC(Structure):
        _fields_ = [('policy', c_char_p),
                    ('pw_min_life', UINT32),
                    ('pw_max_life', UINT32),
                    ('pw_min_length', UINT32),
                    ('pw_min_classes', UINT32),
                    ('pw_history_num', UINT32),
                    ('policy_refcnt', UINT32)]

# define global cdll and constants objects
libkrb5 = None
libkadm5 = None
constants = None
error = None

def init_libs(flavor=KRB_FLAVOR_MIT, local = False):
    global libkrb5
    global libkadm5
    global constants
    global error
 
    if (flavor == KRB_FLAVOR_HEIMDAL):
        from ceresync.backend import heimdal_error
        error = heimdal_error
        if (local):
            libkrb5 = CDLL (HEIMDAL_KRB5)
	    libkadm5 = CDLL (HEIMDAL_ADM5SRV)
	    constants = KADM5_HEIMDAL_CONST()
        else:
           
            libkrb5 = CDLL (HEIMDAL_KRB5)
            libkadm5 = CDLL (HEIMDAL_ADM5CLNT)
            constants = KADM5_HEIMDAL_CONST()

    elif (flavor == KRB_FLAVOR_MIT):
        from ceresync.backend import mit_error
        error = mit_error
        if (local):
            libkrb5 = CDLL (MIT_KRB5)
            libkadm5 = CDLL (MIT_ADM5SRV)
            constants = KADM5_CONST()
        else:
            libkrb5 = CDLL (MIT_KRB5)
            libkadm5 = CDLL (MIT_ADM5CLNT)
            constants = KADM5_CONST()

def check_kadm_error(rc, message="An unknown kadm error ocurred"):
    if (rc == 0):
        return None
    elif error.errors.has_key(str(rc)):
        raise error.errors[str(rc)]
    else:
        raise Exception, message


class KADM5(object):
    """Represents a connection to a Kerberos admin server"""

    def __init__(self):

        self.params = constants.CONFIG_PARAMS()
        self.context = c_void_p(None)

        rc = libkrb5.krb5_init_context(byref(self.context))
        if (rc != 0):
            raise Exception, "Error while initializing the krb5 library"

        #rc = libkadm5.kadm5_get_config_params(self.context, c_char_p(None), c_char_p(None), byref(self.params), byref(self.params))

        #check_kadm_error(rc, "Error while initializing the kadmin library: %d" % (rc))

    
    def connect(self, server=None, realm=None, princ=None, password=None, port=None, local=False):

        context = self.context
        if (not realm):
            def_realm = c_char_p()
            rc = libkrb5.krb5_get_default_realm(context, byref(def_realm))
            check_kadm_error(rc, "Unable to determine the default realm: %s" % (rc))
            self.def_realm = def_realm.value
            self.realm = def_realm.value
        else:
            self.def_realm = realm
            self.realm = realm

        cache = c_void_p(None)
        rc = libkrb5.krb5_cc_default(self.context, byref(cache))
        if (rc != 0):
            raise Exception, "Error getting default cache."

        if (not princ and not local):
            user = os.environ.get('USER')
            if (not user):
                user = os.getlogin()
            princ = '%s/admin@%s' % (user, self.def_realm)

        elif (princ and not '@' in princ):
            princ = '%s@%s' % (princ, self.def_realm)

        params = self.params
        params = constants.CONFIG_PARAMS()

        params.mask = 0

        self.server = server

        if (self.realm):
            params.realm = self.realm
            params.mask |= constants.CONFIG_REALM

        if (self.server):
            params.admin_server = server
            params.mask |= constants.CONFIG_ADMIN_SERVER

        handle = c_void_p(None)

        if (constants.flavor == KRB_FLAVOR_HEIMDAL):
			if not local:
				krb5 = KRB5()
				principals = krb5.klist()
				if not princ in principals:
					print "%s is not in your credentials cache" % (princ)
					raise Exception, "%s is not in your credentials cache" % (princ)

        if (local):
		    rc = libkadm5.kadm5_init_with_password_ctx(
						   self.context,
						   constants.ADMIN_SERVICE,
						   c_char_p(None),
						   constants.ADMIN_SERVICE,
						   byref(params),
						   0, 0,
						   byref(handle))

        elif constants.flavor == KRB_FLAVOR_HEIMDAL:
            cache = c_void_p(None)
            rc = libkrb5.krb5_cc_default(self.context, byref(cache))
            check_kadm_error(rc, "Error getting default cache.")

            rc = libkadm5.kadm5_init_with_creds(
                        c_char_p(princ),
                        cache,
                        constants.ADMIN_SERVICE,
                        byref(params),
                        constants.STRUCT_VERSION,
                        constants.API_VERSION_2,
                        byref(handle))
        else:
            rc = libkadm5.kadm5_init_with_password(
					       c_char_p(princ), 
                           c_char_p(password),
                           constants.ADMIN_SERVICE,
                           byref(params),
                           constants.STRUCT_VERSION,
                           constants.API_VERSION_2,
                           byref(handle))
        check_kadm_error(rc, "Error connecting to admin server: %d" % (rc))
        self.handle = handle

        rc = libkrb5.krb5_cc_set_flags(self.context, cache, constants._KRB5.TC_OPENCLOSE)
        check_kadm_error(rc, "Error while closing ccache")


    def ListPrincipals(self):
        """List all principal names"""

        princs = POINTER(c_char_p)()
        count = c_int(0)

        rc = libkadm5.kadm5_get_principals(self.handle, c_char_p("*"), 
                                               byref(princs), byref(count))
        check_kadm_error(rc, "Failed to get list of principals: %d" % (rc))

        ret = []
        for i in range(count.value):
            ret.append(str(princs[i]))

        #libkadm5.kadm5_free_name_list(self.handle, princs, count)

        return ret

    def GetPrincipal(self, princname):
        """Get information about a particular principal"""

        context = c_void_p(None)
        ent = constants.PRINCIPAL_ENT_REC()
        princ = constants._KRB5.PRINCIPAL()
        principal = c_char_p()
        mod_name = c_char_p()
        

        rc = libkrb5.krb5_init_context(byref(context))
        check_kadm_error(rc, "Error while initializing the krb5 library")

        try:

            rc = libkrb5.krb5_parse_name(context, princname, byref(princ))
            check_kadm_error(rc, "Error parsing principal: %d" % (rc))

            rc = libkadm5.kadm5_get_principal(self.handle, princ, byref(ent), constants.PRINCIPAL_NORMAL_MASK)
            check_kadm_error(rc, "Error retrieving principal: %d" % (rc))

            rc = libkrb5.krb5_unparse_name(context, ent.principal, byref(principal))
            check_kadm_error(rc, "Error unparsing principal: %d" % (rc))

            rc = libkrb5.krb5_unparse_name(context, ent.mod_name, byref(mod_name))
            check_kadm_error(rc, "Error unparsing mod_name: %d" % (rc))

            ret = {}
            ret['principal'] = principal.value
            ret['princ_expire_time'] = ent.princ_expire_time
            ret['last_pw_change'] = ent.last_pw_change
            ret['pw_expiration'] = ent.pw_expiration
            ret['max_life'] = ent.max_life
            ret['max_renewable_life'] = ent.max_renewable_life
            ret['mod_name'] = mod_name.value
            ret['kvno'] = ent.kvno
            ret['mod_date'] = ent.mod_date
            ret['last_success'] = ent.last_success
            ret['last_failed'] = ent.last_failed
            ret['fail_auth_count'] = ent.fail_auth_count
            ret['policy'] = ent.policy
            ret['attributes'] = ent.attributes

            return ret
        finally:
            libkrb5.krb5_free_context(context)

    def SetPassword(self, princname, password):
        context = c_void_p(None)
        princ = constants._KRB5.PRINCIPAL()

        rc = libkrb5.krb5_init_context(byref(context))
        check_kadm_error(rc, "Error while initializing the krb5 library")

        try:

            rc = libkrb5.krb5_parse_name(context, princname, byref(princ))

            if (rc != 0):
                raise Exception, "Error parsing principal."
            
            rc = libkadm5.kadm5_chpass_principal(self.handle, princ, password)

            check_kadm_error(rc, "Unable to change password.")

        finally:
            libkrb5.krb5_free_context(context)

    def CreatePrincipal(self, princname, password = None, options = None):
        """Create a new principal optionally specifying a password and options"""

        context = c_void_p(None)
        princ = constants.PRINCIPAL_ENT_REC()
        #principal = c_char_p()
        defpol = constants.POLICY_ENT_REC()
        mask = 0
        #randkey = 0

        if (options is None):
            options = {}

        rc = libkrb5.krb5_init_context(byref(context))
        check_kadm_error(rc, "Error while initializing the krb5 library")

        try:

            rc = libkrb5.krb5_parse_name(context, c_char_p(princname), byref(princ.principal))
            check_kadm_error(rc, "Error parsing principal.")

            # Get the default policy
            if (constants.flavor == KRB_FLAVOR_MIT):
                rc = libkadm5.kadm5_get_policy(self.handle, "default", byref(defpol))
                
                if (rc != 0):
                    print "Warning, no policy set"
                else:
                    princ.policy = "default"
                    mask |= constants.POLICY
                    libkadm5.kadm5_free_policy_ent(self.handle, byref(defpol))
                
            for key in options.keys():
                if key == 'princ_expire_time':
                    princ.princ_expire_time = options[key]
                    mask |= constants.PRINC_EXPIRE_TIME
                elif key == 'pw_expiration':
                    princ.pw_expiration = options[key]
                    mask |= constants.PW_EXPIRATION
                elif key == 'max_life':
                    princ.max_life = options[key]
                    mask |= constants.MAX_LIFE
                elif key == 'max_renewable_life':
                    princ.max_renewable_life = options[key]
                    mask |= constants.MAX_RLIFE
                elif key == 'kvno':
                    princ.kvno = options[key]
                    mask |= constants.KVNO
                elif key == 'policy':
                    princ.policy = options[key]
                    mask |= constants.POLICY
                elif key == 'attributes':
                    princ.attributes = options[key]
                    mask |= constants.ATTRIBUTES

            if (password is None):
                #randkey = 1
                print "using random password"
                password = KRB5().generate_random_key()
                #mask |= constants.ATTRIBUTES
                #princ.attributes |= constants._KRB5.KDB_DISALLOW_ALL_TIX


            # Create the principal
            mask |= constants.PRINCIPAL
            rc = libkadm5.kadm5_create_principal(self.handle, byref(princ), mask, password)
            
            check_kadm_error(rc, "Error creating principal: %d" % (rc))
  
        finally:
            libkrb5.krb5_free_context(context)
            
    def DeletePrincipal(self, princname):
        context = c_void_p(None)
        princ = constants._KRB5.PRINCIPAL()
        principal = c_char_p()
        mod_name = c_char_p()
        

        rc = libkrb5.krb5_init_context(byref(context))
        check_kadm_error(rc, "Error while initializing the krb5 library")
       
        try:

            rc = libkrb5.krb5_parse_name(context, princname, byref(princ))

            check_kadm_error(rc, "Error parsing principal.")

        finally:
            libkrb5.krb5_free_context(context)

        rc = libkadm5.kadm5_delete_principal(self.handle, princ)
        check_kadm_error(rc, "Error deleting principal: %d" % (rc))


class KRB5(object):
    def __init__(self):

        self.context = c_void_p(None)
        rc = libkrb5.krb5_init_context(byref(self.context))

        check_kadm_error(rc, "Error while initializing the krb5 library")

    def generate_random_key(self):
        key = []
        for i in range(1024 / 8):
            k = c_char_p('0' * 8)
            libkrb5.krb5_generate_random_block(k, 8)
            key.append(k.value)
        return ''.join(key)

    def klist(self):
        cache = c_void_p(None)
        princ = constants._KRB5.PRINCIPAL()
        principal = c_char_p()
        cur = c_void_p()
        creds = constants._KRB5.CREDS()
        
        principal_names = []
        
        rc = libkrb5.krb5_cc_default(self.context, byref(cache))
        check_kadm_error(rc, "Error getting default cache.")

        rc = libkrb5.krb5_cc_set_flags(self.context, cache, 0)
        check_kadm_error(rc, "Error while setting cache flags")

        rc = libkrb5.krb5_cc_get_principal(self.context, cache, byref(princ))
        check_kadm_error(rc, "Error retrieving principal name: %d" % (rc))
        
        rc = libkrb5.krb5_unparse_name(self.context, princ, byref(principal))
        check_kadm_error(rc, "Error unparsing principal name: %d" % (rc))

        principal_names.append(principal.value)

        rc = libkrb5.krb5_cc_start_seq_get(self.context, cache, byref(cur))
        check_kadm_error(rc, "Error while starting to retrieve tickets.")

        while 0:
            code = libkrb5.krb5_cc_next_cred(self.context, cache, 
                    byref(cur), byref(creds))
            if (code == constants._KRB5.CC_END):
                rc = libkrb5.krb5_cc_end_seq_get(self.context, cache, byref(cur))
                check_kadm_error(rc, "Error while finishing ticket retrieval.")
                rc = libkrb5.krb5_cc_set_flags(self.context, cache, constants._KRB5.TC_OPENCLOSE)
                check_kadm_error(rc, "Error while closing ccache")
                break
            elif (code != 0):
                break
            try:
                name = c_char_p()
                rc = libkrb5.krb5_unparse_name(self.context, creds.client, byref(name))
                if (rc != 0):
                    continue
                if not (name.value in principal_names):
                    principal_names.append(str(name.value))
            finally:
                libkrb5.krb5_free_cred_contents(self.context, byref(creds))
                
        return principal_names

if __name__ == '__main__':
    import sys
    from pprint import pprint

    if not len(sys.argv) == 5:
        print "Usage: kadm5.py admin_server realm principal password"
        sys.exit(1)
    host, realm, princ, password = sys.argv[1:]
    print host, realm
    k = KADM5(host, realm, princ, password)

    print '**** Listing principals:'
    princs = k.ListPrincipals()
    pprint(princs)

    print '\n**** Displaying info for first 3 principals'
    for p in princs[:3]:
        print "Principal: %s" % (p)
        pprint(k.GetPrincipal(p))

