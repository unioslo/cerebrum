# -*- coding: utf-8-*-
#
# Copyright 2004-2019 University of Tromso, Norway
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
from __future__ import unicode_literals

import logging
import xml.sax

import six

logger = logging.getLogger(__name__)


class PagaDataParserClass(xml.sax.ContentHandler):
    """
    Class that iterates over elements in a paga xml file.
    """
    def __init__(self, filename, callback):
        self.callback = callback
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):  # noqa: N802
        if name == 'data':
            pass
        elif name in ("tils", "gjest", "permisjon"):
            tmp = {}
            for k in attrs.keys():
                tmp[k] = six.text_type(attrs[k])

            self.p_data[name] = self.p_data.get(name, []) + [tmp]
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = six.text_type(attrs[k])
        else:
            logger.warning('Unknown element %r (attrs: %r)',
                           name, attrs.keys())

    def endElement(self, name):  # noqa: N802
        if name == "person":
            self.callback(self.p_data)
