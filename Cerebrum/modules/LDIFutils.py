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


def cereconf2utf(*args):
    """Fetch VARIABLE [with DEFAULT] from cereconf, and translate to UTF-8."""
    return _deep_text2utf(getattr(cereconf, *args))

def _deep_text2utf(obj):
    if isinstance(obj, str):
        return iso2utf(obj)
    if isinstance(obj, unicode):
        return obj.encode('utf-8')
    if isinstance(obj, (tuple, list)):
        return type(obj)(map(_deep_text2utf, obj))
    if isinstance(obj, dict):
        return dict([(_deep_text2utf(x), _deep_text2utf(obj[x])) for x in obj])
    return obj


_ldap_base_dn = (getattr(cereconf, 'LDAP_BASE_DN', None)
                 # Previous name of LDAP_BASE_DN variable
                 or cereconf.LDAP_BASE)

def get_tree_dn(tree_name, *default_arg):
    """Get dn of tree_name (cereconf.LDAP_<tree_name>_DN).

    Will be abolished in favor of simply using cereconf.LDAP_<tree_name>_DN.
    The function is used for backwards compatibility because the cereconf
    variable could previously be just the value of an OU."""
    dn = getattr(cereconf, tree_name.join(('LDAP_', '_DN')), *default_arg)
    if dn and '=' not in dn:
        dn = "ou=%s,%s" % (dn, _ldap_base_dn)
    return dn


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
    entry = dict(cereconf2utf('LDAP_CONTAINER_ATTRS', {}))
    entry.update(attrs)
    entry.update(cereconf2utf('LDAP_%s_ATTRS' % tree_name, {}))
    return entry_string(get_tree_dn(tree_name), entry)


def add_ldif_file(outfile, filename):
    """Write to OUTFILE the LDIF file FILENAME, unless FILENAME is false."""
    if filename:
        # Test for isabs() so cereconf.LDAP_DUMP_DIR is not required to
        # be set.  (It is a poor variable name for where to fetch an input
        # file.  However, so far we have no need for yet another variable.)
        if not os.path.isabs(filename):
            filename = os.path.join(cereconf.LDAP_DUMP_DIR, filename)
        outfile.write(file(filename, 'r').read().strip("\n") + "\n\n")


def iso2utf(s):
    """Convert iso8859-1 to utf-8."""
    return unicode(s, 'iso-8859-1').encode('utf-8')

def utf2iso(s):
    """Not in use for the moment, remove this line if used """
    """Convert utf-8 to iso8859-1"""
    return unicode(s, 'utf-8').encode('iso-8859-1')


# Match an 8-bit string which is not an utf-8 string
_iso_re = re.compile("[\300-\377](?![\200-\277])|(?<![\200-\377])[\200-\277]")

# Match an 8-bit string
_is_eightbit = re.compile('[\200-\377]').search

def some2utf(str):
    """Unreliable hack: Convert either iso8859-1 or utf-8 to utf-8."""
    if _iso_re.search(str):
        str = unicode(str, 'iso8859-1').encode('utf-8')
    return str

def some2iso(str):
    """Unreliable hack: Convert either iso8859-1 or utf-8 to iso8859-1."""
    if _is_eightbit(str) and not _iso_re.search(str):
        str = unicode(str, 'utf-8').encode('iso8859-1')
    return str


_normalize_trans = string.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + string.whitespace.replace(" ", ""),
    "abcdefghijklmnopqrstuvwxyz" + " " * (len(string.whitespace) - 1))

# Match multiple spaces
_multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

# Match one or more spaces
_space_re = re.compile('[%s]+' % string.whitespace)

def normalize_phone(phone):
    """Normalize phone/fax numbers for comparison of LDAP values."""
    return phone.translate(_normalize_trans, " -")
 
def normalize_string(str):
    """Normalize strings for comparison of LDAP values."""
    str = _multi_space_re.sub(' ', str.translate(_normalize_trans)).strip()
    # Note: _normalize_trans lowercases ASCII letters.
    if _is_eightbit(str):
        str = unicode(str, 'utf-8').lower().encode('utf-8')
    return str

def normalize_caseExactString(str):
    """Normalize case-sensitive strings for comparison of LDAP values."""
    return _space_re.sub(' ', str).strip()

def normalize_IA5String(str):
    """Normalize case-sensitive ASCII strings for comparison of LDAP values."""
    return _multi_space_re.sub(' ', str.translate(_normalize_trans)).strip()


# Return true if the parameter is valid for the LDAP syntax printableString;
# including telephone and fax numbers.
verify_printableString = re.compile(r"[-a-zA-Z0-9'()+,.=/:? ]+\Z").match

# Return true if the parameter is valid for the LDAP syntax IA5String (ASCII):
# mail, dc, gecos, homeDirectory, loginShell, memberUid, memberNisNetgroup.
verify_IA5String = re.compile("[\0-\x7e]*\\Z").match

def attr_lines(name, strings, normalize = None, verify = None, raw = False):
    """ Not in use for the moment, remove this line if used """
    ret = []
    done = {}

    # Make each attribute name and value - but only one of
    # each value, compared by attribute syntax ('normalize')
    for s in strings:
        if not raw:
            # Clean up the string: remove surrounding and multiple whitespace
            s = _multi_space_re.sub(' ', s.strip())

        # Skip the value if it is not valid according to its LDAP syntax
        if s == '' or (verify and not verify(s)):
            continue

        # Check if value has already been made (or equivalent by normalize)
        if normalize:
            norm = normalize(s)
        else:
            norm = s
        if done.has_key(norm):
            continue
        done[norm] = True

        # Encode as base64 if necessary, otherwise as plain text
        if _need_base64(s):
            ret.append(":: ".join((name, _base64encode(s))))
        else:
            ret.append("%s: %s\n" % (name, s))
    return ret

# arch-tag: 9544a041-07cb-4494-92ea-c8dc82c9808a
