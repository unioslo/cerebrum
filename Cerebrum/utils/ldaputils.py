# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" Ldap utilities.

Utilities for wrapping communication with LDAP servers.

TODO: Consolidate Cerebrum.modules.Ldap and
Cerebrum.modules.bofhd.bofhd_email:LdapUpdater into this module.

Also, the scripts in contrib/exchange/ use Ldap extensively -- there should
probably be a generic implementation of those objects here.
"""


def decode_attrs(result_data):
    """ Decodes text data in an ldap result list.

    :param list result_data:
        A list of result-data tuples from ldap.search() + ldap.result()

    :return list:
        Returns a new list with decoded values.
    """
    def decode(value):
        # value is either bytes or a list of bytes
        rvalue = value
        if isinstance(value, bytes):
            try:
                # text values should be ascii or utf-8
                rvalue = value.decode('utf-8')
            except UnicodeDecodeError:
                # if not valid utf-8, probably binary
                rvalue = bytearray(value)
        elif isinstance(value, list):
            rvalue = [decode(v) for v in value]
        return rvalue

    new_list = []
    for dn, attrs in result_data:
        new_dn = decode(dn)
        new_attrs = dict()
        for attr in attrs:
            new_attrs[decode(attr)] = decode(attrs[attr])
        new_list.append(tuple((new_dn, new_attrs)))
    return new_list
