# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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
A simple xml helper util.

Moved from Factory.Utils for compatibility reasons
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import datetime
import re
import six

from Cerebrum.utils.date_compat import to_mx_format, is_mx_datetime

class XMLHelper(object):

    def __init__(self, encoding='utf-8'):
        self.xml_hdr = '<?xml version="1.0" encoding="{}"?>\n'.format(encoding)

    def conv_colnames(self, cols):
        """Strip tablename prefix from column name."""
        prefix = re.compile(r"[^.]*\.")
        for i in range(len(cols)):
            cols[i] = re.sub(prefix, "", cols[i]).lower()
        return cols

    def xmlify_dbrow(self, row, cols, tag, close_tag=1, extra_attr=None):
        if close_tag:
            close_tag = "/"
        else:
            close_tag = ""
        assert(len(row) == len(cols))
        if extra_attr is not None:
            extra_attr = " " + " ".join(
                ["%s=%s" % (k, self.escape_xml_attr(extra_attr[k]))
                 for k in extra_attr.keys()])
        else:
            extra_attr = ''
        return "<%s " % tag + (
            " ".join(["%s=%s" % (x, self.escape_xml_attr(row[x]))
                      for x in cols if row[x] is not None]) +
            "%s%s>" % (extra_attr, close_tag))

    def escape_xml_attr(self, a):
        """Escapes XML attributes."""
        if isinstance(a, int):
            a = six.text_type(a)
        elif is_mx_datetime(a):
            a = six.text_type(to_mx_format(a))
        elif isinstance(a, datetime.datetime):
            a = six.text_type(to_mx_format(a))
        a = a.replace('&', "&amp;")
        a = a.replace('"', "&quot;")
        a = a.replace('<', "&lt;")
        a = a.replace('>', "&gt;")
        return '"{}"'.format(a)
