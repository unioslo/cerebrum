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


# Module with various utilities for building LDIF files from Cerebrum data.
# It will be rewritten later; it or its callers should use the ldif module.


import re, string
import cereconf


def cereconf2utf(*args):
    """Fetch VARIABLE [with DEFAULT] from cereconf, and translate to UTF-8."""
    return _deep_iso2utf(getattr(cereconf, *args))

def _deep_iso2utf(obj):
    if isinstance(obj, str):
        return iso2utf(obj)
    if isinstance(obj, (tuple, list)):
        return type(obj)([_deep_iso2utf(x) for x in obj])
    if isinstance(obj, dict):
        return dict([(_deep_iso2utf(x), _deep_iso2utf(obj[x])) for x in obj])
    return obj


def get_tree_dn(tree_name):
    """Get DN of TREE_NAME (cereconf.LDAP_<TREE_NAME>_DN).
    The cereconf variable should be a DN, but may (so far) also be
    just the value of an OU, for backwards compatibility."""

    dn = cereconf2utf('LDAP_%s_DN' % tree_name)
    if not re.match(r'^[-.\w]+=', dn):
        dn = "ou=%s,%s" % (dn, cereconf.LDAP_BASE)
    return dn


def make_entry(dn, attrs, add_rdn = True):
    """Return a string with an LDIF entry with the specified DN and ATTRS.
    **Does not currently base64-encode values when necessary.**
    If ADD_RDN, add the values in the RDN to the attribues if necessary."""
    if add_rdn:
        for ava in dn.split(',')[0].split('+'):
            ava = ava.split('=', 1)
            old = attrs.get(ava[0])
            if not old:
                attrs[ava[0]] = (ava[1],)
            elif not filter(lambda s: normalize_string(s) == ava[1], old):
                attrs[ava[0]] = (ava[1],) + tuple(old)
    keys = attrs.keys()
    keys.sort()         # not necessary, but minimizes changes in file
    return ("dn: %s\n" % dn
            + "".join(["%s: %s\n" % (attr, val)
                       for attr in keys
                       for val in attrs[attr]])
            + "\n")

def make_container_entry(tree_name, attrs = {}):
    attrs = dict(cereconf2utf('LDAP_CONTAINER_ATTRS'))
    attrs.update(attrs)
    attrs.update(cereconf2utf('LDAP_%s_ATTRS' % tree_name, {}))
    if 'top' not in attrs['objectClass']:
        attrs['objectClass'] = ('top',) + tuple(attrs['objectClass'])
    return make_entry(get_tree_dn(tree_name), attrs)


def add_ldif_file(outfile, filename, required = False):
    """Write to OUTFILE the LDIF file FILENAME, if it exists."""
    if filename:
        try:
            if not filename.startswith('/'):
                filename = cereconf.LDAP_DUMP_DIR + '/' + filename
	    lfile = file(filename, 'r')
        except IOError:
            if required:
                raise
        else:
	    outfile.write(lfile.read().strip() + "\n\n")
	    lfile.close()


def iso2utf(s):
    """Not in use for the moment, remove this line if used """
    """Convert iso8859-1 to utf-8"""
    utf_str = unicode(s,'iso-8859-1').encode('utf-8')
    return utf_str

def utf2iso(s):
    """Not in use for the moment, remove this line if used """
    """Convert utf-8 to iso8859-1"""
    iso_str = unicode(s,'utf-8').encode('iso-8859-1')
    return iso_str


# match an 8-bit string which is not an utf-8 string
_iso_re = re.compile("[\300-\377](?![\200-\277])|(?<![\200-\377])[\200-\277]")

# match an 8-bit string
_eightbit_re = re.compile('[\200-\377]')

def some2utf(str):
    """Convert either iso8859-1 or utf-8 to utf-8"""
    if _iso_re.search(str):
        str = unicode(str, 'iso8859-1').encode('utf-8')
    return str

def some2iso(str):
    """Convert either iso8859-1 or utf-8 to iso8859-1"""
    if _eightbit_re.search(str) and not _iso_re.search(str):
        str = unicode(str, 'utf-8').encode('iso8859-1')
    return str


_normalize_trans = string.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ\t\n\r\f\v",
    "abcdefghijklmnopqrstuvwxyz     ")

# match multiple spaces
_multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

def normalize_phone(phone):
    """Normalize phone/fax numbers for LDAP"""
    return phone.translate(_normalize_trans, " -")
 
def normalize_string(str):
    """Normalize strings for LDAP"""
    str = _multi_space_re.sub(' ', str.translate(_normalize_trans).strip())
    if _eightbit_re.search(str):
        str = unicode(str, 'utf-8').lower().encode('utf-8')
    return str


# Match attributes with the printableString LDAP syntax
_printablestring_re = re.compile('^[a-zA-Z0-9\'()+,\\-.=/:? ]+$')

def verify_printableString(str):
    """Not in use for the moment, remove this line if used """
    """Return true if STR is valid for the LDAP syntax printableString"""
    return _printablestring_re.match(str)


_need_base64_re = re.compile('^\\s|[\0\r\n]|\\s$')

def make_attr(name, strings, normalize = None, verify = None, raw = False):
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
    return ''.join(ret)
