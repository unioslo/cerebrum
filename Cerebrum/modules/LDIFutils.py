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


"""Module with various utilities for building LDIF files from Cerebrum data.
It will be rewritten later; it or its callers should use the ldif module."""


import re, string
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
        return type(obj)([_deep_text2utf(x) for x in obj])
    if isinstance(obj, dict):
        return dict([(_deep_text2utf(x), _deep_text2utf(obj[x])) for x in obj])
    return obj


_tree_dn_re = re.compile(r'\A[-.\w]+=')

def get_tree_dn(tree_name, *default_arg):
    """Get dn of tree_name (cereconf.LDAP_<tree_name>_DN).

    Will be abolished in favor of simply using cereconf.LDAP_<tree_name>_DN.
    The function is used for backwards compatibility because the cereconf
    variable could previously be just the value of an OU."""
    dn = getattr(cereconf, 'LDAP_%s_DN' % tree_name, *default_arg)
    if dn and not _tree_dn_re.match(dn):
        dn = "ou=%s,%s" % (dn, (getattr(cereconf, 'LDAP_BASE_DN', None)
                                # Previous name of LDAP_BASE_DN variable
                                or cereconf.LDAP_BASE))
    return dn

# Match an escaped character in a DN
dn_escaped_re = re.compile(r'\\([0-9a-zA-Z]{2}|[ \#,+\"\\<>\;])')

def unescape_match(group):
    """Return the actual character for a match group for an escaped character.
    Used e.g. with dn_escaped_re.sub(unescape_match, dn_ava_string)."""
    quoted = group()
    if len(quoted) == 1:
        return quoted
    else:
        return int(quoted, 16)

dn_escape_re = re.compile('\\A\\s|[#"+,;<>\\\\=\0]|\\s\\Z')

def hex_escape_match(match):
    """Return the \\hex representation of a match group for a character.
    Used e.g. with dn_escape_re.sub(hex_escape_match, attr_value)."""
    return r'\%02X' % ord(match.group())

def entry_string(dn, attrs, add_rdn = True):
    """Return a string with an LDIF entry with the specified DN and ATTRS.
    **Does not currently base64-encode values when necessary.**
    If ADD_RDN, add the values in the RDN to the attributes if necessary."""
    if add_rdn:
        for ava in dn.split(',')[0].split('+'):
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
    attrs = attrs.items()
    attrs.sort()         # not necessary, but minimizes changes in file
    attrs = [": ".join((attr, val))
             for attr, vals in attrs
             for val in vals]
    attrs.insert(0, "dn: " + dn)
    attrs.append("\n")
    return "\n".join(attrs)

def container_entry_string(tree_name, attrs = {}):
    """Return a string with an LDIF entry for the specified container entry."""
    attrs = dict(cereconf2utf('LDAP_CONTAINER_ATTRS'))
    attrs.update(attrs)
    attrs.update(cereconf2utf('LDAP_%s_ATTRS' % tree_name, {}))
    return entry_string(get_tree_dn(tree_name), attrs)


def add_ldif_file(outfile, filename):
    """Write to OUTFILE the LDIF file FILENAME, unless FILENAME is false."""
    if filename:
        # Removed 'try: / except IOError: pass / else:' around file()
        if not re.match(r'^\.*/', filename):
            filename = cereconf.LDAP_DUMP_DIR + '/' + filename
        outfile.write(file(filename, 'r').read().strip() + "\n\n")


def iso2utf(s):
    """Convert iso8859-1 to utf-8"""
    utf_str = unicode(s,'iso-8859-1').encode('utf-8')
    return utf_str

def utf2iso(s):
    """Not in use for the moment, remove this line if used """
    """Convert utf-8 to iso8859-1"""
    iso_str = unicode(s,'utf-8').encode('iso-8859-1')
    return iso_str


# Match an 8-bit string which is not an utf-8 string
_iso_re = re.compile("[\300-\377](?![\200-\277])|(?<![\200-\377])[\200-\277]")

# Match an 8-bit string
_eightbit_re = re.compile('[\200-\377]')

def some2utf(str):
    """Unreliable hack: Convert either iso8859-1 or utf-8 to utf-8"""
    if _iso_re.search(str):
        str = unicode(str, 'iso8859-1').encode('utf-8')
    return str

def some2iso(str):
    """Unreliable hack: Convert either iso8859-1 or utf-8 to iso8859-1"""
    if _eightbit_re.search(str) and not _iso_re.search(str):
        str = unicode(str, 'utf-8').encode('iso8859-1')
    return str


_normalize_trans = string.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + string.whitespace.replace(" ", ""),
    "abcdefghijklmnopqrstuvwxyz" + " " * (len(string.whitespace) - 1))

# Match multiple spaces
_multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

def normalize_phone(phone):
    """Normalize phone/fax numbers for LDAP"""
    return phone.translate(_normalize_trans, " -")
 
def normalize_string(str):
    """Normalize strings for LDAP"""
    str = _multi_space_re.sub(' ', str.translate(_normalize_trans)).strip()
    # Note: _normalize_trans lowercases ASCII letters.
    if _eightbit_re.search(str):
        str = unicode(str, 'utf-8').lower().encode('utf-8')
    return str


# Match attributes with the printableString LDAP syntax
printablestring_re = re.compile(r"\A[-a-zA-Z0-9'()+,.=/:? ]+\Z")

def verify_printableString(str):
    """Not in use for the moment, remove this line if used """
    """Return true if STR is valid for the LDAP syntax printableString"""
    return printablestring_re.match(str)


# Match an attribute value which in LDIF must be base64-encoded
_need_base64_re = re.compile('^\\s|[\0\r\n]|\\s$')

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
        if _need_base64_re.search(s):
            ret.append("%s:: %s\n" % (name, (base64.encodestring(s)
                                             .replace("\n", ''))))
        else:
            ret.append("%s: %s\n" % (name, s))
    return ret
