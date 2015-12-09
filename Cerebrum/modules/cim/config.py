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

from Cerebrum.Utils import Factory

__db = Factory.get('Database')()
__co = Factory.get('Constants')(__db)

# Authoritative system settings
authoritative_system = __co.system_sap
system_perspective = __co.OUPerspective('SAP')

# Cerebrum -> CIM value mappings
# Phone data settings
country_phone_prefix = '+47'
phone_entry_mappings = {'job_mobile': __co.contact_mobile_phone,
                        'job_phone': __co.contact_phone,
                        'private_mobile': __co.contact_private_mobile,
                        'private_phone': __co.contact_phone_private,
                        }

# Company / Department data settings
company_name = 'Universitetet i Oslo'
company_hierarchy = ['company',
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
                     ]
