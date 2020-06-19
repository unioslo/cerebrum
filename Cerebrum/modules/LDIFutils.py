# -*- coding: utf-8 -*-

# Copyright 2004-2012 University of Oslo, Norway
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

Modify base64_attrs and needs_base64 to tune the output."""

from __future__ import unicode_literals

import binascii
import re
import string
import os.path
from base64 import b64encode

import six

import cereconf
from Cerebrum import Errors as _Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.atomicfile import SimilarSizeWriter

# Attributes whose values should always be base64-encoded.
# May be modified by the applications.
base64_attrs = {'userPassword': 0, 'authPassword': 0}

needs_base64_readable = re.compile('\\A[\\s:<]|[\0-\37\177]|\\s\\Z').search
needs_base64_safe = re.compile('\\A[ :<]|[\0-\37\177-\377]| \\Z').search

# Return true if the attr.value parameter must be base64-encoded in LDIF.
# May be modified by the applications.  Possible values:
# - needs_base64_readable: only trigger on control characters, leaving
#   values human-readable when possible (expects 8-bit data to be UTF-8).
# - needs_base64_safe: Encode all 8-bit data as well.
needs_base64 = needs_base64_readable


_dummy = object()


def ldapconf(tree, attr, default=_dummy, module=cereconf):
    """Return module.LDAP_<tree>[<attr>] with default.

    Fetch module.LDAP_<tree>[<attr>], or LDAP[<attr>] if <tree> is None.
    If <default> is given, it is used if the setting is absent or None.
    """
    var = tree is None and 'LDAP' or 'LDAP_' + tree
    val = getattr(module, var).get(attr, default)
    if val is _dummy:
        raise _Errors.CerebrumError(
            '{0}.{1}["{2}"] is not set'.format(
                module.__name__,
                var,
                attr))
    if val is None and default is not _dummy:
        val = default
    return val


# Match an escaped character in a DN; group 1 will match the character.
dn_escaped_re = re.compile('\\\\([0-9a-fA-F]{2}|[<>,;+"#\\\\=\\s])')

# Match a character which must be escaped in a DN.
dn_escape_re = re.compile('\\A[\\s#]|["+,;<>\\\\=\0\r\n]|\\s\\Z')


def unescape_match(match):
    """Unescape the hex-escaped character in <match object>.group(1).

    Used e.g. with dn_escaped_re.sub(unescape_match, <attr value in DN>)."""
    escaped = match.group(1)
    if len(escaped) == 1:
        return escaped
    return binascii.a2b_hex(escaped)


def hex_escape_match(match):
    """Return the '\\hex' representation of a match object for a character.

    Used e.g. with dn_escape_re.sub(hex_escape_match, <attr value>)."""
    text = match.group()
    if isinstance(text, six.text_type):
        text = text.encode('utf-8')
    return '\\' + binascii.b2a_hex(text)


def entry_string(dn, attrs, add_rdn=True):
    """Return a string with an LDIF entry with the specified DN and ATTRS.

    DN is the entry name: A string 'rdn (i.e. relative DN),parent DN'.
    ATTRS is a dict {attribute name: value or sequence of values}.

    If ADD_RDN, add the values in the rdn to the attributes if necessary.
    This feature is rudimentary:  Fails with \+ and \, in the DN.  Considers
    attr names case-sensitive, attr values as caseIgnore Directory Strings."""
    if add_rdn:
        attrs = attrs.copy()
        # DN = RDN or "RDN,parentDN".  RDN = "attr=rval+attr=rval+...".
        for ava in dn.split(',', 1)[0].split('+'):
            attr, rval = ava.split('=', 1)
            rval = dn_escaped_re.sub(unescape_match, rval)
            old = attrs.setdefault(attr, rval)
            if old is not rval:
                # The attribute already exists.  Insert rval if needed.
                norm = normalize_string(rval)
                tp = type(old)
                if tp in _attrval_seqtypes:
                    for val in old or ():
                        if normalize_string(val) == norm:
                            break
                    else:
                        attrs[attr] = vals = list(_attrval2iter[tp](old))
                        vals.insert(0, rval)
                elif normalize_string(old) != norm:
                    attrs[attr] = (rval, old)

    need_b64 = needs_base64
    if need_b64(dn):
        result = ["dn:: ", b64encode(dn.encode('utf-8')), "\n"]
    else:
        result = ["dn: ", dn, "\n"]

    extend = result.extend
    attrs = attrs.items()
    attrs.sort()         # not necessary, but minimizes changes in file
    for attr, vals in attrs:
        for val in _attrval2iter[type(vals)](vals):
            if attr in base64_attrs or need_b64(val):
                extend((attr, ":: ", b64encode(val.encode('utf-8')), "\n"))
            else:
                extend((attr, ": ", val, "\n"))

    result.append("\n")
    return "".join(result)


# For entry_string() attrs: map {type: function producing sequence/iterator}
_attrval_seqtypes = (tuple, list, set, frozenset, type(None))
_attrval2iter = {
    tuple: tuple,
    list: iter,
    set: sorted,  # sorting but minimizes changes in the output file
    frozenset: sorted,
    str: (lambda *args: args),
    unicode: (lambda *args: args),
    type(None): (lambda arg: ())}


def container_entry_string(tree_name, attrs={}, module=cereconf):
    """Return a string with an LDIF entry for the specified container entry."""
    entry = dict(ldapconf(None, 'container_attrs', {}, module=module))
    entry.update(attrs)
    entry.update(ldapconf(tree_name, 'attrs', {}, module=module))
    return entry_string(ldapconf(tree_name, 'dn', module=module), entry)


class LDIFWriter(object):
    """Wrapper around ldif_outfile with a minimal but sane API."""

    def __init__(self, tree, filename=None, module=cereconf):
        if filename and os.path.sep not in filename:
            filename = os.path.join(module.LDAP['dump_dir'], filename)
        self.f = ldif_outfile(tree, filename=filename, module=module)
        self.write, self.tree, self.module = self.f.write, tree, module

    def getconf(self, attr, default=_dummy):
        """ldapconf() wrapper for this LDIF file's LDAP tree"""
        return ldapconf(self.tree, attr, default, self.module)

    # def write(): This is (currently) implemented via an attribute.

    def write_container(self, tree=None):
        self.write(
            container_entry_string(
                tree or self.tree,
                module=self.module))

    def write_entry(self, dn, attrs, add_rdn=True):
        self.write(entry_string(dn, attrs, add_rdn))

    def close(self):
        end_ldif_outfile(self.tree, self.f, module=self.module)


def ldif_outfile(tree, filename=None, default=None, explicit_default=False,
                 max_change=None, module=cereconf):
    """(Open and) return LDIF outfile for <tree>.

    Use <filename> if specified,
    otherwise module.LDAP_<tree>['file'] unless <explicit_default>,
    otherwise return <default> (an open filehandle) if that is not None.
    (explicit_default should be set if <default> was opened from a
    <filename> argument and not from module.LDAP*['file'].)

    When opening a file, use SimilarSizeWriter where close() fails if
    the resulting file has changed more than <max_change>, or
    module.LDAP_<tree>['max_change'], or module.LDAP['max_change'].
    If max_change is unset or >= 100, just open the file normally.
    """
    if not (filename or explicit_default):
        filename = getattr(module, 'LDAP_' + tree).get('file')
        if filename:
            filename = os.path.join(module.LDAP['dump_dir'], filename)
    if filename:
        if max_change is None:
            max_change = ldapconf(tree, 'max_change', default=ldapconf(
                None, 'max_change', default=100, module=module),
                module=module)
        if max_change < 100:
            f = SimilarSizeWriter(filename, 'w')
            f.max_pct_change = max_change
        else:
            f = AtomicFileWriter(filename, 'w')
        return f
    if default:
        return default
    raise _Errors.CerebrumError(
        'Outfile not specified and LDAP_{0}["file"] not set'.format(tree))


def end_ldif_outfile(tree, outfile, default_file=None, module=cereconf):
    """Finish the <tree> part of <outfile>.  Close it if != <default_file>."""
    append_file = getattr(module, 'LDAP_' + tree).get('append_file')
    if append_file:
        # Test for isabs() so module.LDAP['dump_dir'] is not required to
        # be set.  (It is a poor variable name for where to fetch an input
        # file.  However, so far we have no need for yet another variable.)
        if not os.path.isabs(append_file):
            append_file = os.path.join(module.LDAP['dump_dir'], append_file)
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
        raise _Errors.CerebrumError(
            'Expected 1 {0}: {1}'.format(constname, arg))
    return values


_const = _Constants = None


def _decode_const(constname, value):
    global _const, _Constants
    try:
        return int(value)
    except ValueError:
        if not _const:
            from Cerebrum import Constants as _Constants
            _const = Factory.get('Constants')(
                Factory.get('Database')())
        try:
            return int(getattr(_const, value))
        except AttributeError:
            try:
                return int(getattr(_Constants, constname)(value))
            except _Errors.NotFoundError:
                raise _Errors.CerebrumError(
                    'Invalid {0}: {1}'.format(constname, value))


postal_escape_re = re.compile(r'[$\\]')

# Uppercase -> lowercase, whitespace -> space
_normalize_trans = {
    ord(s): six.text_type(d) for s, d in zip(
        string.ascii_uppercase + string.whitespace.replace(" ", ""),
        string.ascii_lowercase + " " * (len(string.whitespace) - 1))
}

# Match multiple spaces
_multi_space_re = re.compile('[%s]{2,}' % string.whitespace)

# Match one or more spaces
_space_re = re.compile('[%s]+' % string.whitespace)


def normalize_phone(phone):
    """Normalize phone/fax numbers for comparison of LDAP values."""
    return phone.translate(_normalize_trans).replace(' ', '').replace('-', '')


def normalize_string(s):
    """Normalize strings for comparison of LDAP values."""
    # Note: _normalize_trans lowercases ASCII letters.
    s = _multi_space_re.sub(' ', s.translate(_normalize_trans)).strip()
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

# Return true if the parameter looks like an email address, i.e. contains
# exactly one @ and at least one dot after the @
verify_emailish = re.compile(r"[^@]+@[^@]+\.[^@]+").match


class ldif_parser(object):
    """
    Use the python-ldap's ldif.LDIFParser(). Redirect handle routine
    to local routine. Input is file and following parameter are optionals:
    ignored_attr_types(=None), max_entries(=0), process_url_schemes(=None),
    line_sep(='\n').
    """
    def __init__(self, inputfile,
                 ignored_attr_types=None,
                 max_entries=0,
                 process_url_schemes=None,
                 line_sep='\n'):
        import ldif
        self._ldif = ldif.LDIFParser(
            inputfile, ignored_attr_types, max_entries,
            process_url_schemes, line_sep)
        self._ldif.handle = self.handle
        self.res_dict = {}

    def handle(self, dn, entry):
        """ Load into a dict"""
        self.res_dict[dn] = entry

    def parse(self):
        self._ldif.parse()
        return(self.res_dict)
