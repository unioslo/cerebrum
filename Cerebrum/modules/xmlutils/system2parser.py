# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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
This module implements a convenience layer for selecting appropriate XML
parsers.
"""

from Cerebrum.modules.xmlutils import sapxml2object, ltxml2object, fsxml2object


def system2parser(system_name):
    """Return the appropriate parser.

    The keys are the constant names for the corresponding systems. 
    """

    obj = {"system_lt": ltxml2object.LTXMLDataGetter,
           "LT": ltxml2object.LTXMLDataGetter,
           "system_sap": sapxml2object.SAPXMLDataGetter,
           "SAP": sapxml2object.SAPXMLDataGetter,
           "system_fs": fsxml2object.FSXMLDataGetter,
           "FS": fsxml2object.FSXMLDataGetter,}.get(system_name)
    return obj
# end system2parser
