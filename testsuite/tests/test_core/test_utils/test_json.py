# encoding: utf-8
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


from __future__ import unicode_literals
import six
from Cerebrum.utils import json
from mx.DateTime import DateTime


def test_mxdatetime():
    assert json.dumps(
        DateTime(2018, 1, 1, 12, 0, 0)) == '"2018-01-01T12:00:00+01:00"'
    assert json.dumps(DateTime(2018, 1, 1, 0, 0, 0)) == '"2018-01-01"'


def test_constants(factory):
    co = factory.get('Constants')(None)
    assert json.dumps(co.entity_account) == (
        '{{"__cerebrum_object__": "code", '
        '"code": {d}, '
        '"str": "{c}", '
        '"table": "{t}"}}').format(
            c=co.entity_account,
            d=int(co.entity_account),
            t=co.EntityType._lookup_table)


def test_entity(initial_account, factory):
    co = factory.get('Constants')(None)
    assert json.dumps(initial_account) == (
        '{{"__cerebrum_object__": "account", '
        '"entity_id": {}, '
        '"entity_type": {}, '
        '"str": {}}}'
        .format(
            initial_account.entity_id,
            json.dumps(co.entity_account),
            six.text_type(initial_account)))
