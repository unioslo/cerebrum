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

"""
Active Directory Service Interfaces (ADSI) errors.

The ADSI interface can return different error codes. These constants map
the known errors to readable human text and catchable Python exception.
    

"""

import types
import pythoncom
import wrapper

# Error constants taken from
# "Win32 Error codes for ADSI"
# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/adsi/adsi/win32_error_codes_for_adsi.asp

adsi_errors = (
	(0L, "LDAP_SUCCESS", "NO_ERROR", "Operation succeeded."),
	(0x80070005L, "LDAP_INSUFFICIENT_RIGHTS", "ERROR_ACCESS_DENIED", "User has insufficient access rights."),
	(0x80070008L, "LDAP_NO_MEMORY", "ERROR_NOT_ENOUGH_MEMORY", "System is out of memory."),
	(0x8007001fL, "LDAP_OTHER", "ERROR_GEN_FAILURE", "Unknown error."),
	(0x800700eaL, "LDAP_PARTIAL_RESULTS", "ERROR_MORE_DATA", "Partial results and referrals received."),
	(0x800700eaL, "LDAP_MORE_RESULTS_TO_RETURN", "ERROR_MORE_DATA", "More results are to be returned."),
	(0x800704c7L, "LDAP_USER_CANCELLED", "ERROR_CANCELLED", "User cancelled the operation."),
	(0x800704c9L, "LDAP_CONNECT_ERROR", "ERROR_CONNECTION_REFUSED", "Cannot establish the connection."),
	(0x8007052eL, "LDAP_INVALID_CREDENTIALS", "ERROR_LOGON_FAILURE", "Supplied credential is invalid."),
	(0x800705b4L, "LDAP_TIMEOUT", "ERROR_TIMEOUT", "Search timed out."),
	(0x80071392L, "LDAP_ALREADY_EXISTS", "ERROR_OBJECT_ALREADY_EXISTS", "Object already exists."),
	(0x8007200aL, "LDAP_NO_SUCH_ATTRIBUTE", "ERROR_DS_NO_ATTRIBUTE_OR_VALUE", "Requested attribute does not exist."),
	(0x8007200bL, "LDAP_INVALID_SYNTAX", "ERROR_DS_INVALID_ATTRIBUTE_SYNTAX", "Syntax is invalid."),
	(0x8007200cL, "LDAP_UNDEFINED_TYPE", "ERROR_DS_ATTRIBUTE_TYPE_UNDEFINED", "Type not defined."),
	(0x8007200dL, "LDAP_ATTRIBUTE_OR_VALUE_EXISTS", "ERROR_DS_ATTRIBUTE_OR_VALUE_EXISTS", "Attribute exists or the value has been assigned."),
	(0x8007200eL, "LDAP_BUSY", "ERROR_DS_BUSY", "Server is busy."),
	(0x8007200fL, "LDAP_UNAVAILABLE", "ERROR_DS_UNAVAILABLE", "Server is not available."),
	(0x80072014L, "LDAP_OBJECT_CLASS_VIOLATION", "ERROR_DS_OBJ_CLASS_VIOLATION", "Object class violation."),
	(0x80072015L, "LDAP_NOT_ALLOWED_ON_NONLEAF", "ERROR_DS_CANT_ON_NON_LEAF", "Operation is not allowed on a non- leaf object."),
	(0x80072016L, "LDAP_NOT_ALLOWED_ON_RDN", "ERROR_DS_CANT_ON_RDN", "Operation is not allowed on an RDN."),
	(0x80072017L, "LDAP_NO_OBJECT_CLASS_MODS", "ERROR_DS_CANT_MOD_OBJ_CLASS", "Cannot modify object class."),
	(0x80072020L, "LDAP_OPERATIONS_ERROR", "ERROR_DS_OPERATIONS_ERROR", "Operation error occurred."),
	(0x80072021L, "LDAP_PROTOCOL_ERROR", "ERROR_DS_PROTOCOL_ERROR", "Protocol error occurred."),
	(0x80072022L, "LDAP_TIMELIMIT_EXCEEDED", "ERROR_DS_TIMELIMIT_EXCEEDED", "Exceeded time limit."),
	(0x80072023L, "LDAP_SIZELIMIT_EXCEEDED", "ERROR_DS_SIZELIMIT_EXCEEDED", "Exceeded size limit."),
	(0x80072024L, "LDAP_ADMIN_LIMIT_EXCEEDED", "ERROR_DS_ADMIN_LIMIT_EXCEEDED", "Exceeded administration limit on the server."),
	(0x80072025L, "LDAP_COMPARE_FALSE", "ERROR_DS_COMPARE_FALSE", "Compare yielded FALSE."),
	(0x80072026L, "LDAP_COMPARE_TRUE", "ERROR_DS_COMPARE_TRUE", "Compare yielded TRUE."),
	(0x80072027L, "LDAP_AUTH_METHOD_NOT_SUPPORTED", "ERROR_DS_AUTH_METHOD_NOT_SUPPORTED", "The authentication method is not supported."),
	(0x80072028L, "LDAP_STRONG_AUTH_REQUIRED", "ERROR_DS_STRONG_AUTH_REQUIRED", "Strong authentication is required."),
	(0x80072029L, "LDAP_INAPPROPRIATE_AUTH", "ERROR_DS_INAPPROPRIATE_AUTH", "Authentication is inappropriate."),
	(0x8007202aL, "LDAP_AUTH_UNKNOWN", "ERROR_DS_AUTH_UNKNOWN", "Unknown authentication error occurred."),
	(0x8007202bL, "LDAP_REFERRAL", "ERROR_DS_REFERRAL", "Cannot resolve referral."),
	(0x8007202cL, "LDAP_UNAVAILABLE_CRIT_EXTENSION", "ERROR_DS_UNAVAILABLE_CRIT_EXTENSION", "Critical extension is unavailable."),
	(0x8007202dL, "LDAP_CONFIDENTIALITY_REQUIRED", "ERROR_DS_CONFIDENTIALITY_REQUIRED", "Confidentiality is required."),
	(0x8007202eL, "LDAP_INAPPROPRIATE_MATCHING", "ERROR_DS_INAPPROPRIATE_MATCHING", "There was an inappropriate matching."),
	(0x8007202fL, "LDAP_CONSTRAINT_VIOLATION", "ERROR_DS_CONSTRAINT_VIOLATION", "There was a constrain violation."),
	(0x80072030L, "LDAP_NO_SUCH_OBJECT", "ERROR_DS_NO_SUCH_OBJECT", "Object does not exist."),
	(0x80072031L, "LDAP_ALIAS_PROBLEM", "ERROR_DS_ALIAS_PROBLEM", "Alias is invalid."),
	(0x80072032L, "LDAP_INVALID_DN_SYNTAX", "ERROR_DS_INVALID_DN_SYNTAX", "Distinguished name has an invalid syntax."),
	(0x80072033L, "LDAP_IS_LEAF", "ERROR_DS_IS_LEAF", "The object is a leaf."),
	(0x80072034L, "LDAP_ALIAS_DEREF_PROBLEM", "ERROR_DS_ALIAS_DEREF_PROBLEM", "Cannot dereference the alias."),
	(0x80072035L, "LDAP_UNWILLING_TO_PERFORM", "ERROR_DS_UNWILLING_TO_PERFORM", "Server cannot perform operation."),
	(0x80072036L, "LDAP_LOOP_DETECT", "ERROR_DS_LOOP_DETECT", "Loop was detected."),
	(0x80072037L, "LDAP_NAMING_VIOLATION", "ERROR_DS_NAMING_VIOLATION", "There was a naming violation."),
	(0x80072038L, "LDAP_RESULTS_TOO_LARGE", "ERROR_DS_OBJECT_RESULTS_TOO_LARGE", "Results set is too large."),
	(0x80072039L, "LDAP_AFFECTS_MULTIPLE_DSAS", "ERROR_DS_AFFECTS_MULTIPLE_DSAS", "Multiple directory service agents are affected."),
	(0x8007203aL, "LDAP_SERVER_DOWN", "ERROR_DS_SERVER_DOWN", "Cannot contact the LDAP server."),
	(0x8007203bL, "LDAP_LOCAL_ERROR", "ERROR_DS_LOCAL_ERROR", "Local error occurred."),
	(0x8007203cL, "LDAP_ENCODING_ERROR", "ERROR_DS_ENCODING_ERROR", "Encoding error occurred."),
	(0x8007203dL, "LDAP_DECODING_ERROR", "ERROR_DS_DECODING_ERROR", "Decoding error occurred."),
	(0x8007203eL, "LDAP_FILTER_ERROR", "ERROR_DS_FILTER_UNKNOWN", "The search filter is bad."),
	(0x8007203fL, "LDAP_PARAM_ERROR", "ERROR_DS_PARAM_ERROR", "A bad parameter was passed to a function."),
	(0x80072040L, "LDAP_NOT_SUPPORTED", "ERROR_DS_NOT_SUPPORTED", "Feature not supported."),
	(0x80072041L, "LDAP_NO_RESULTS_RETURNED", "ERROR_DS_NO_RESULTS_RETURNED", "Results are not returned."),
	(0x80072042L, "LDAP_CONTROL_NOT_FOUND", "ERROR_DS_CONTROL_NOT_FOUND", "Control was not found."),
	(0x80072043L, "LDAP_CLIENT_LOOP", "ERROR_DS_CLIENT_LOOP", "Client loop was detected."),
	(0x80072044L, "LDAP_REFERRAL_LIMIT_EXCEEDED", "ERROR_DS_REFERRAL_LIMIT_EXCEEDED", "Exceeded referral limit."),
)

# ADSI 2.0 has some seperate codes. I don't know what "2.0" is.
adsi20_errors = (
	(0L, "LDAP_SUCCESS", "NO_ERROR", "Operation succeeded."),
	(0x80070002L, "LDAP_NO_SUCH_OBJECT", "ERROR_FILE_NOT_FOUND", "Object does not exist."),
	(0x80070005L, "LDAP_AUTH_METHOD_NOT_SUPPORTED", "ERROR_ACCESS_DENIED", "Authentication method not supported."),
	(0x80070005L, "LDAP_STRONG_AUTH_REQUIRED", "ERROR_ACCESS_DENIED", "Requires strong authentication."),
	(0x80070005L, "LDAP_INAPPROPRIATE_AUTH", "ERROR_ACCESS_DENIED", "Inappropriate authentication."),
	(0x80070005L, "LDAP_INSUFFICIENT_RIGHTS", "ERROR_ACCESS_DENIED", "User has insufficient access rights."),
	(0x80070005L, "LDAP_AUTH_UNKNOWN", "ERROR_ACCESS_DENIED", "Unknown authentication error occurred."),
	(0x80070008L, "LDAP_NO_MEMORY", "ERROR_NOT_ENOUGH_MEMORY", "System is out of memory."),
	(0x8007001FL, "LDAP_OTHER", "ERROR_GEN_FAILURE", "Unknown error occurred."),
	(0x8007001FL, "LDAP_LOCAL_ERROR", "ERROR_GEN_FAILURE", "Local error occurred."),
	(0x80070037L, "LDAP_UNAVAILABLE", "ERROR_DEV_NOT_EXIST", "Server is not available."),
	(0x8007003AL, "LDAP_SERVER_DOWN", "ERROR_BAD_NET_RESP", "Cannot contact the LDAP server."),
	(0x8007003BL, "LDAP_ENCODING_ERROR", "ERROR_UNEXP_NET_ERR", "Encoding error occurred."),
	(0x8007003BL, "LDAP_DECODING_ERROR", "ERROR_UNEXP_NET_ERR", "Decoding error occurred."),
	(0x80070044L, "LDAP_ADMIN_LIMIT_EXCEEDED", "ERROR_TOO_MANY_NAMES", "Exceeded administration limit on the server."),
	(0x80070056L, "LDAP_INVALID_CREDENTIALS", "ERROR_INVALID_PASSWORD", "Invalid credential."),
	(0x80070057L, "LDAP_INVALID_DN_SYNTAX", "ERROR_INVALID_PARAMETER", "Distinguished name has an invalid syntax."),
	(0x80070057L, "LDAP_NAMING_VIOLATION", "ERROR_INVALID_PARAMETER", "Naming violation."),
	(0x80070057L, "LDAP_OBJECT_CLASS_VIOLATION", "ERROR_INVALID_PARAMETER", "Object class violation."),
	(0x80070057L, "LDAP_FILTER_ERROR", "ERROR_INVALID_PARAMETER", "Search filter is bad."),
	(0x80070057L, "LDAP_PARAM_ERROR", "ERROR_INVALID_PARAMETER", "Bad parameter was passed to a routine."),
	(0x8007006EL, "LDAP_OPERATIONS_ERROR", "ERROR_OPEN_FAILED", "Operation error occurred."),
	(0x8007007AL, "LDAP_RESULTS_TOO_LARGE", "ERROR_INSUFFICIENT_BUFFER", "Results set is too large."),
	(0x8007007BL, "LDAP_INVALID_SYNTAX", "ERROR_INVALID_NAME", "Invalid syntax."),
	(0x8007007CL, "LDAP_PROTOCOL_ERROR", "ERROR_INVALID_LEVEL", "Protocol error."),
	(0x800700B7L, "LDAP_ALREADY_EXISTS", "ERROR_ALREADY_EXISTS", "Object already exists."),
	(0x800700EAL, "LDAP_PARTIAL_RESULTS", "ERROR_MORE_DATA", "Partial results and referrals received."),
	(0x800700EAL, "LDAP_BUSY", "ERROR_BUSY", "Server is busy."),
	(0x800703EBL, "LDAP_UNWILLING_TO_PERFORM", "ERROR_CAN_NOT_COMPLETE", "Server cannot perform operation."),
	(0x8007041DL, "LDAP_TIMEOUT", "ERROR_SERVICE_REQUEST_TIMEOUT", "Search timed out."),
	(0x800704B8L, "LDAP_COMPARE_FALSE", "ERROR_EXTENDED_ERROR", "Compare yielded FALSE."),
	(0x800704B8L, "LDAP_COMPARE_TRUE", "ERROR_EXTENDED_ERROR", "Compare yielded TRUE."),
	(0x800704B8L, "LDAP_REFERRAL", "ERROR_EXTENDED_ERROR", "Cannot resolve referral."),
	(0x800704B8L, "LDAP_UNAVAILABLE_CRIT_EXTENSION", "ERROR_EXTENDED_ERROR", "Critical extension is unavailable."),
	(0x800704B8L, "LDAP_NO_SUCH_ATTRIBUTE", "ERROR_EXTENDED_ERROR", "Requested attribute does not exist."),
	(0x800704B8L, "LDAP_UNDEFINED_TYPE", "ERROR_EXTENDED_ERROR", "Type is not defined."),
	(0x800704B8L, "LDAP_INAPPROPRIATE_MATCHING", "ERROR_EXTENDED_ERROR", "There was an inappropriate matching."),
	(0x800704B8L, "LDAP_CONSTRAINT_VIOLATION", "ERROR_EXTENDED_ERROR", "There was a constrain violation."),
	(0x800704B8L, "LDAP_ATTRIBUTE_OR_VALUE_EXISTS", "ERROR_EXTENDED_ERROR", "The attribute exists or the value has been assigned."),
	(0x800704B8L, "LDAP_ALIAS_PROBLEM", "ERROR_EXTENDED_ERROR", "Alias is invalid."),
	(0x800704B8L, "LDAP_IS_LEAF", "ERROR_EXTENDED_ERROR", "Object is a leaf."),
	(0x800704B8L, "LDAP_ALIAS_DEREF_PROBLEM", "ERROR_EXTENDED_ERROR", "Cannot dereference the alias."),
	(0x800704B8L, "LDAP_LOOP_DETECT", "ERROR_EXTENDED_ERROR", "Loop was detected."),
	(0x800704B8L, "LDAP_NOT_ALLOWED_ON_NONLEAF", "ERROR_EXTENDED_ERROR", "Operation is not allowed on a non-leaf object."),
	(0x800704B8L, "LDAP_NOT_ALLOWED_ON_RDN", "ERROR_EXTENDED_ERROR", "Operation is not allowed on RDN."),
	(0x800704B8L, "LDAP_NO_OBJECT_CLASS_MODS", "ERROR_EXTENDED_ERROR", "Cannot modify object class."),
	(0x800704B8L, "LDAP_AFFECTS_MULTIPLE_DSAS", "ERROR_EXTENDED_ERROR", "Multiple directory service agents are affected."),
	(0x800704C7L, "LDAP_USER_CANCELLED", "ERROR_CANCELLED", "User has cancelled the operation."),
	(0x80070718L, "LDAP_TIMELIMIT_EXCEEDED", "ERROR_NOT_ENOUGH_QUOTA", "Exceeded time limit."),
	(0x80070718L, "LDAP_SIZELIMIT_EXCEEDED", "ERROR_NOT_ENOUGH_QUOTA", "Exceeded size limit."),
)

# "Generic ADSI Error codes"
# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/adsi/adsi/common_errors.asp
# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/iissdk/html/41a3cf90-db11-4dd6-94dd-bc8a7cdfa8f9.asp
# Standard COM errors
# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/biztalks/htm/lat_sdk_errmsg_hjku.asp
generic_errors = (
# Standard COM errors
    (0x80005008L, None, "E_ADS_BAD_PARAMETER", "One or more input parameters are invalid."),
    (0x80005000L, None, "E_ADS_BAD_PATHNAME", "An invalid ADSI pathname was passed."),
    (0x8000500CL, None, "E_ADS_CANT_CONVERT_DATATYPE", "The data type cannot be converted to/from a native DS data type"),
    (0x80005010L, None, "E_ADS_COLUMN_NOT_SET", "The specified column in the ADSI was not set."),
    (0x80005003L, None, "E_ADS_INVALID_COMPUTER_OBJECT", "An unknown ADSI computer object was requested."),
    (0x80005001L, None, "E_ADS_INVALID_DOMAIN_OBJECT", "An unknown ADSI domain object was requested."),
    (0x80005014L, None, "E_ADS_INVALID_FILTER", "The specified search filter is invalid."),
    (0x80005002L, None, "E_ADS_INVALID_USER_OBJECT", "An unknown ADSI user object was requested."),
    (0x8000500EL, None, "E_ADS_OBJECT_EXISTS", "The ADSI object exists."),
    (0x80005009L, None, "E_ADS_OBJECT_UNBOUND", "The specified ADSI object is not bound to a remote resource"),
    (0x80005007L, None, "E_ADS_PROPERTY_INVALID", "The specified ADSI property is invalid"),
    (0x8000500BL, None, "E_ADS_PROPERTY_MODIFIED", "The specified ADSI object has been modified."),
    (0x8000500DL, None, "E_ADS_PROPERTY_NOT_FOUND", "The property cannot be found in the cache"),
    (0x8000500AL, None, "E_ADS_PROPERTY_NOT_MODIFIED", "The specified ADSI object has not been modified"),
    (0x80005005L, None, "E_ADS_PROPERTY_NOT_SET", "The specified ADSI property was not set"),
    (0x80005006L, None, "E_ADS_PROPERTY_NOT_SUPPORTED", "The specified ADSI property is not supported."),
    (0x8000500FL, None, "E_ADS_SCHEMA_VIOLATION", "The attempted action violates the directory service schema rules."),
    (0x80005004L, None, "E_ADS_UNKNOWN_OBJECT", "An unknown ADSI object was requested."),
    (0x00005011L, None, "S_ADS_ERRORSOCCURRED", "During a query, one or more errors occurred."),
    (0x00005013L, None, "S_ADS_NOMORE_COLUMNS", "The search operation has reached the last column for the current row."),
    (0x00005012L, None, "S_ADS_NOMORE_ROWS", "The search operation has reached the last row."),
)

# Standard COM errors
# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/biztalks/htm/lat_sdk_errmsg_hjku.asp
com_errors = (
#    (0x00000000L, None, "S_OK", "Operation succeeded"),
    (0x00000001L, None, "S_FALSE", "Success, but non-standard"),
    (0x8000FFFFL, None, "E_UNEXPECTED", "Catastrophic failure error"),
    (0x80004001L, None, "E_NOTIMPL", "Not implemented"),
    (0x8007000EL, None, "E_OUTOFMEMORY", "Out of memory"),
    (0x80070057L, None, "E_INVALIDARG", "One or more arguments are not valid"),
    (0x80004002L, None, "E_NOINTERFACE", "Interface not supported"),
    (0x80004003L, None, "E_POINTER", "Pointer not valid"),
    (0x80006006L, None, "E_HANDLE", "Handle not valid"),
    (0x80004004L, None, "E_ABORT", "Operation aborted"),
    (0x80004005L, None, "E_FAIL", "Unspecified error"),
    (0x80007005L, None, "E_ACCESSDENIED", "General Access denied"),
    (0x800401E5L, None, "MK_E_NOOBJECT", "Object could not be found"),
)

class ADSIException(pythoncom.com_error):
    """Base exception for Active Directory errors.
       Required attributes:
         errno -- Windows error number
         hex -- errno in standard hex notation
         ldap -- LDAP error name 
         win32 -- win32 error name
         descr -- Human readable error
    """
    def __str__(self):
        args = Exception.__str__(self)
        if args:
            return self.__doc__ + ": " + args
        return self.__doc__

class UnknownError(ADSIException):
    """Unknown ADSI error"""
    # To be subclassed for the specific errno
    # example:
    #   raise generate_unknown(-1827827)

def generate_unknown(err, msg="Unknown ADSI Error"):
    """Generates on the fly a subclass of UnknownError with the given
    win32 error code and optional message"""
    class SomeException(UnknownError):
        errno = err
        hex = hex32(err)
        ldap = ""
        win32 = ""
        descr = msg
    SomeException.__doc__ = msg      
    SomeException.__name__ = "UnknownError"
    return SomeException
       
def i32(x): 
    """Converts a long (for instance 0x80005000L) to a signed 32-bit-int.
    >>> i32(0x80005000L)
    -2147463168
    """
    # x > 0x80000000L should be negative, such that:
    # i32(0x80000000L) -> -2147483648L 
    # i32(0x80000001L) -> -2147483647L   etc.
    return (x&0x80000000L and -2*0x40000000 or 0) + int(x&0x7fffffff)

def hex32(x):
    """Converts a 32-bit int (possibly signed) to a 32-bit hex string.
    >>> hex32(-2147463168)
    "0x80005000"
    """ 
    if x < 0:
        x += 2*0x80000000L
    return "0x%08x" % x

    
def win32_name_to_python(win_name):
    """Converts an error name from win32 style to Python style.
    For instance, "ERROR_ACCESS_DENIED" -> "AccessDeniedError"
    """
    # Generate a CamelCaseException name
    # (but avoid "DS" -> "Ds" by using some ugly code)
    name = []
    for word in win_name.split("_"):
        if word.upper() in ("ERROR", "ERR", "E", "MK", "S"):
            continue
        if word not in ("ADS", "DS"):
            word = word.capitalize()
        name.append(word)    
    if win_name.startswith("S_"):
        name.append("Success")
    else:    
        name.append("Error")
    return "".join(name)

# Mapping from errno to exception
errors = {}      

# Process error constants and generate Python exception classes
for errno, ldap, win32, descr in adsi_errors+adsi20_errors+generic_errors+com_errors:
    # Convert errno to 32-bit-signed-int
    errno = i32(errno)
    name = win32_name_to_python(win32)
        
    if errno in errors:
        # Just an alias for the same exception
        globals()[name] = errors[errno]
        continue

    # Generate the class
    class SomeException(ADSIException):
        errno = errno
        hex = hex32(errno)
        ldap = ldap
        win32 = win32
        descr = descr.rstrip(".")
        __doc__ = "%s (%s)" % (descr, hex)

    SomeException.__name__ = name
    errors[errno] = SomeException
    # export exception through module
    globals()[name] = SomeException


def convertComError(exception):
    """Converts an pythoncom.com_error exception to the appropriate
       ADSIException.
    """
    if isinstance(exception, ADSIException):
        # avoid double-conversion
        return exception
    # Not quite sure of all these different errnos.. so we'll just try
    # to convert each of them.
    hr, msg, exc, arg = exception
    if hr in errors:
        return errors[hr]
    if not exc:
        return generate_unknown(hr, msg)
    wcode, source, text, helpFile, helpId, scode = exc
    errno = scode or wcode
    if errno in errors:
        return errors[errno]
    return generate_unknown(errno, text or msg)

class WrapMeta(type):
    def __new__(cls, name, bases, dict):
        for name,method in dict.items():
            if not callable(method):
                continue
            dict[name] = cls.metawrap(name, method)
        return type.__new__(cls, name, bases, dict)
        
    def metawrap(name, fun):
        def metawrapper(self, *args, **kwargs):
            try:
                res = fun(self, *args, **kwargs)
            except pythoncom.com_error, e:
                # Find out object name
                if name in ("__getattr__", "__getattribute__"):
                    wrapname = self.__wrap_name__ + args[0]
                else:
                    wrapname = self.__wrap_name__   
                raise convertComError(e), wrapname
            return res
        return metawrapper       
    metawrap = staticmethod(metawrap)

def wrapComError(obj):
    return wrapper.wrap(obj, meta=WrapMeta)

# Delete temporary variables that should not be exported
del adsi_errors,adsi20_errors,errno,ldap,win32,descr,SomeException
del generic_errors,com_errors
