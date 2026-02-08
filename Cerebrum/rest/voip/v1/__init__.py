# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
The Cerebrum VOIP API.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from flask import Blueprint
from flask_restx import Api

__version__ = '1.0'

blueprint = Blueprint('voip_api_v1', __name__)

api = Api(
    blueprint,
    version=__version__,
    title='Cerebrum VOIP REST API',
    description=(
        'VOIP microservice API for managing voip services and addresses.'
    ),
    contact='cerebrum-kontakt@usit.uio.no',
)

from .service import api as service_ns
from .address import api as address_ns

api.add_namespace(service_ns)
api.add_namespace(address_ns)
