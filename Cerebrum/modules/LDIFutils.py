# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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


"""Various utilities for building LDIF files from Cerebrum data.
It will be rewritten later.  Maybe it should use the ldif module."""


import re
import string
import os.path
from binascii import \
     b2a_hex as _str2hex, a2b_hex as _hex2str, b2a_base64 as _base64encode

import cereconf
from Cerebrum import Errors as _Errors, Utils as _Utils

_dummy = object()


def ldapconf(tree, attr, default=_dummy, utf8=True):
    """Return cereconf.LDAP_<tree>[<attr>] with default, translated to UTF-8.

    Fetch cereconf.LDAP_<tree>[<attr>], or LDAP[<attr>] if <tree> is None.
    If <default> is given, it is used if the setting is absent or None.
    If <utf8>, the result is converted to UTF-8, recursing through tuples,
    lists and dict values, but not dict keys.  If <utf8> is a type or list
    of types, only values with or inside these types are converted.
    """
    var = tree is None and 'LDAP' or 'LDAP_' + tree
    val = getattr(cereconf, var).get(attr, default)
    if val is _dummy:
        raise _Errors.PoliteException("cereconf.%s['%s'] is not set"
                                      % (var, attr))
    if val is None and default is not _dummy:
        val = default
    if utf8:
        val = _deep_text2utf(val, utf8)
    return val

def _deep_text2utf(obj, utf8):
    if utf8 == True:
        if isinstance(obj, str):
            return iso2utf(obj)
        if isinstance(obj, unicode):
            return obj.encode('utf-8')
    elif isinstance(obj, utf8):
        return _deep_text2utf(obj, True)
    if isinstance(obj, (tuple, list)):
        return type(obj)([_deep_text2utf(x, utf8) for x in obj])
    if isinstance(obj, dict):
        return dict([(x, _deep_text2utf(obj[x], utf8)) for x in obj])
    return obj


# Match an escaped character in a DN; group 1 will match the character.
dn_escaped_re = re.compile('\\\\([0-9a-fA-F]{2}|[<>,;+"#\\\\=\\s])')

def unescape_match(match):
    """Unescape the hex-escaped character in <match object>.group(1).

    Used e.g. with dn_escaped_re.sub(unescape_match, <attr value in DN>)."""
    escaped = match.group(1)
    if len(escaped) == 1:
        return escaped
    else:
        return _hex2str(escaped)

# Match a character which must be escaped in a DN.
dn_escape_re = re.compile('\\A[\\s#]|["+,;<>\\\\=\0\r\n]|\\s\\Z')

def hex_escape_match(match):
    """Return the '\\hex' representation of a match object for a character.

    Used e.g. with dn_escape_re.sub(hex_escape_match, <attr value>)."""
    return '\\' + _str2hex(match.group())


# Return true if the attr.value parameter must be base64-encoded in LDIF.
_need_base64 = re.compile('\\A[\\s:<]|[\0\r\n]|\\s\\Z').search

def entry_string(dn, attrs, add_rdn = True):
    """Return a string with an LDIF entry with the specified DN and ATTRS.

    If <add_rdn>, add the values in the rdn to the attributes if necessary."""
    if add_rdn:
        for ava in dn.split(',', 1)[0].split('+'):
            ava = ava.split('=', 1)
            ava[1] = dn_escaped_re.sub(unescape_match, ava[1])
            old = attrs.get(ava[0])
            if old:
                norm = normalize_string(ava[1])
                for val in old:
                    if normalize_string(val) == norm:
                        break
                else:
                    attrs[ava[0]] = (ava[1],) + tuple(old)
            else:
                attrs[ava[0]] = (ava[1],)
    need_b64 = _need_base64
    if need_b64(dn):
        result = ["dn:: ", _base64encode(dn)]
    else:
        result = ["dn: ", dn, "\n"]
    extend = result.extend
    attrs = attrs.items()
    attrs.sort()         # not necessary, but minimizes changes in file
    for attr, vals in attrs:
        for val in vals:
            if need_b64(val):
                extend((attr, ":: ", _base64encode(val)))
            else:
                extend((attr, ": ", val, "\n"))
    result.append("\n")
    return "".join(result)

def container_entry_string(tree_name, attrs = {}):
    """Return a string with an LDIF entry for the specified container entry."""
    entry = dict(ldapconf(None, 'container_attrs', {}))
    entry.update(attrs)
    entry.update(ldapconf(tree_name, 'attrs', {}))
    return entry_string(ldapconf(tree_name, 'dn'), entry)


def ldif_outfile(tree, filename=None, default=None, explicit_default=False,
                 max_change=None):
    """(Open and) return LDIF outfile for <tree>.

    Use <filename> if specified,
    otherwise cereconf.LDAP_<tree>['file'] unless <explicit_default>,
    otherwise return <default> (an open filehandle) if that is not None.
    (explicit_default should be set if <default> was opened from a
    <filename> argument and not from cereconf.LDAP*['file'].)

    When opening a file, use SimilarSizeWriter where close() fails if
    the resulting file has changed more than <max_change>, or
    cereconf.LDAP_<tree>['max_change'], or cereconf.LDAP['max_change'].
    If max_change is unset or >= 100, just open the file normally.
    """
    if not (filename or explicit_default):
        filename = getattr(cereconf, 'LDAP_' + tree).get('file')
        if filename:
            filename = os.path.join(cereconf.LDAP['dump_dir'], filename)
    if filename:
        if max_change is None:
            max_change = ldapconf(tree, 'max_change',
                                  ldapconf(None, 'max_change', 100))
        if max_change < 100:
            f = _Utils.SimilarSizeWriter(filename, 'w')
            f.set_size_change_limit(max_change)
        else:
            f = file(filename, 'w')
        return f
    if default:
        return default
    raise _Errors.PoliteException(
        "Outfile not specified and LDAP_%s['file'] not set" % (tree,))

def end_ldif_outfile(tree, outfile, default_file=None):
    """Finish the <tree> part of <outfile>.  Close it if != <default_file>."""
    append_file = getattr(cereconf, 'LDAP_' + tree).get('append_file')
    if append_file:
        # Test for isabs() so cereconf.LDAP['dump_dir'] is not required to
        # be set.  (It is a poor variable name for where to fetch an input
        # file.  However, so far we have no need for yet another variable.)
        if not os.path.isabs(append_file):
            append_file = os.path.join(cereconf.LDAP['dump_dir'], append_file)
        outfile.write(file(append_file, 'r').read().strip("\n") + "\n\n")
    if outfile is not default_file:
        outfile.close()


def map_spreads(spreads, return_type=None):
    """Convert a spread-name/code or sequence of such to an int or list.

    See Cerebrum.modules.LDIFutils.map_constants() for further details.
    """
    return map_constants('_SpreadCode', spreads, return_type)

def map_constants(constname, values, return_type=None):
    """Convert a constant-name/code or sequence of such to an int or list.

    constname is a Constants.py subclass of _CerebrumCode, e.g. '_SpreadCode'.
    The input values may be Constants.py names or Cerebrum names/codes.
    if return_type is None, return an int if 1 value, a list otherwise.
    If return_type is int or list, return that type, but fail if
    return_type is int and there is not exactly one input value.
    """
    arg = values
    if values is not None:
        if not isinstance(values, (list, tuple)):
            values = (values,)
        values = map(_decode_const, (constname,) * len(values), values)
        if return_type is not list and len(values) == 1:
            values = values[0]
    if return_type is int and not isinstance(values, (int, long)):
        raise _Errors.PoliteException("Expected 1 %s: %r" % (constname, arg))
    return values

_const = _Constants = None

def _decode_const(constname, value):
    global _const, _Constants
    try:
        return int(value)
    except ValueError:
        if not _const:
            from Cerebrum import Constants as _Constants
            _const = _Utils.Factory.get('Constants')(
                _Utils.Factory.get('Database')())
        try:
            return int(getattr(_const, value))
        except AttributeError:
            try:
                return int(getattr(_Constants, constname)(value))
            except _Errors.NotFoundError:
                raise _Errors.PoliteException("Invalid %s: %r"
                                              % (constname, value))


# Match an 8-bit string
_is_eightbit = re.compile('[\200-\377]').search

_normalize_trans = string.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + string.whitespace.replace(" ", ""),
    "abcdefghijklmnopqrstuvwxyz" + " " * (len(string.whitespace) - 1))

# Match multiple spaces
_multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

# Match one or more spaces
_space_re = re.compile('[%s]+' % string.whitespace)


def iso2utf(s):
    """Convert iso8859-1 to utf-8."""
    if _is_eightbit(s):
        return unicode(s, 'iso-8859-1').encode('utf-8')
    return s


def normalize_phone(phone):
    """Normalize phone/fax numbers for comparison of LDAP values."""
    return phone.translate(_normalize_trans, " -")

def normalize_string(s):
    """Normalize strings for comparison of LDAP values."""
    s = _multi_space_re.sub(' ', s.translate(_normalize_trans)).strip()
    # Note: _normalize_trans lowercases ASCII letters.
    if _is_eightbit(s):
        s = unicode(s, 'utf-8').lower().encode('utf-8')
    return s

def normalize_caseExactString(s):
    """Normalize case-sensitive strings for comparison of LDAP values."""
    return _space_re.sub(' ', s).strip()

def normalize_IA5String(s):
    """Normalize case-sensitive ASCII strings for comparison of LDAP values."""
    return _multi_space_re.sub(' ', s.translate(_normalize_trans)).strip()


# Return true if the parameter is valid for the LDAP syntax printableString;
# including telephone and fax numbers.
verify_printableString = re.compile(r"[-a-zA-Z0-9'()+,.=/:? ]+\Z").match

# Return true if the parameter is valid for the LDAP syntax IA5String (ASCII):
# mail, dc, gecos, homeDirectory, loginShell, memberUid, memberNisNetgroup.
verify_IA5String = re.compile("[\0-\x7e]*\\Z").match

class ldif_parser(object):
    """
    Use the python-ldap's ldif.LDIFParser(). Redirect handle routine
    to local routine. Input is file and following parameter are optionals: 
    ignored_attr_types(=None), max_entries(=0), process_url_schemes(=None), 
    line_sep(='\n').
    """

    def __init__(self,inputfile,
		ignored_attr_types=None,
		max_entries=0,
		process_url_schemes=None,
		line_sep='\n'):
	try:
            import ldif
	except ImportError:
	    raise _Errors.PoliteException("Missing ldif-modul from python-ldap")
        self._ldif = ldif.LDIFParser(inputfile,ignored_attr_types,max_entries,
					process_url_schemes,line_sep)
        self._ldif.handle = self.handle
	self.res_dict = {}

    def handle(self,dn,entry):
	""" Load into a dict"""
	self.res_dict[dn] = entry

    def parse(self):
	self._ldif.parse()
	return(self.res_dict)


# arch-tag: 9544a041-07cb-4494-92ea-c8dc82c9808a
