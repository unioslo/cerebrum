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
The Cerebrum API.
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

blueprint = Blueprint('api_v1', __name__)

api = Api(
    blueprint,
    version=__version__,
    title='Cerebrum REST API',
    description=(
        'Cerebrum is a user administration and '
        'identity management system.'
    ),
    contact='cerebrum-kontakt@usit.uio.no',
)

from .account import api as account_ns
from .context import api as context_ns
from .emailaddress import api as emailaddress_ns
from .group import api as group_ns
from .ou import api as ou_ns
from .person import api as person_ns
from .search import api as search_ns

api.add_namespace(account_ns)
api.add_namespace(group_ns)
api.add_namespace(emailaddress_ns)
api.add_namespace(context_ns)
api.add_namespace(ou_ns)
api.add_namespace(person_ns)
api.add_namespace(search_ns)
