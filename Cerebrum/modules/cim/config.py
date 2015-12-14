#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
""" This module defines all necessary config for the CIM integration. """

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)

from Cerebrum.config.loader import read, read_config

from Cerebrum.config.settings import (Boolean,
                                      Integer,
                                      Setting,
                                      String,
                                      Iterable,
                                      NotSet)

class CIMDataSourceConfig(Configuration):
    """Configuration for the CIM data source."""
    authoritative_system = ConfigDescriptor(
        String,
        default="SAP",
        doc=u'Authoritative system to fetch contact information from.')

    ou_perspective = ConfigDescriptor(
        String,
        default="SAP",
        doc=u'Perspective to use when fetching OU structure.')

    phone_country_default = ConfigDescriptor(
        String,
        default="NO",
        doc=u'Assume this phone region when otherwise unknown.')

    # TODO
    #phone_mappings = ConfigDescriptor(
    #    Iterable,
    #    default=NotSet,
    #    doc=u'Mapping from field name to contact constant code.')

    company_name = ConfigDescriptor(
        String,
        default=NotSet,
        doc=(u'Company name.'))

    company_hierarchy = ConfigDescriptor(
        Iterable(template=String),
        default=['company',
                 'department',
                 'subdep1',
                 'subdep2',
                 'subdep3',
                 'subdep4',
                 'subdep5',
                 'subdep6',
                 'subdep7',
                 'subdep8',
                 'subdep9',
                 'subdep10',
                 ],
        doc=(u'Hierarchy of field names expected by the CIM web service.'))

