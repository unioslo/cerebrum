# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
#

import unittest
from time import time
from turbogears import testutil
from htdocs.ajax import *
import cjson

class FakeSession(object):
    def ping(self):
        return True
    def new_transaction(self):
        return None

class SearchTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(SearchTest, self).__init__(*args, **kwargs)

        cherrypy.root = search
        cherrypy.session = {
            'client_encoding': 'iso8859-1',
            'spine_encoding': 'iso8859-1',
            'session': FakeSession(),
        }

    def test_that_account_search_for_alf_contains_alfborge(self):
        expected = [{
            'type': 'account',
            'name': 'alfborge',
            'id': 173809
        }]

        self._do_search("/?query=a:alf", expected)

    def test_that_person_search_for_alf_contains_alf_lervag(self):
        expected = [{
            'name': 'Alf Børge Bjørdal Lervåg'.decode('utf8'),
            'type': 'person',
            'id': 13830,
        }]

        self._do_search("/?query=p:Alf", expected)

    def test_that_group_search_for_cer_contains_cereweb_orakler(self):
        expected = [{
            'name': 'cereweb_orakel',
            'type': 'group',
            'id': 354447,
        }]

        self._do_search('/?query=g:cer', expected)

    def test_that_account_search_with_output_account_returns_owner(self):
        expected = [{
            'type': 'account',
            'name': 'alfborge',
            'id': 173809,
            'owner': {
                'name': 'Alf Børge Bjørdal Lervåg'.decode('utf8'),
                'type': 'person',
                'id': 13830,
            },
        }]

        self._do_search("/?query=a:alf&output=account", expected)

    def test_that_person_search_with_output_account_returns_accounts_with_owner(self):
        expected = [{
            'type': 'account',
            'name': 'alfborge',
            'id': 173809,
            'owner': {
                'name': 'Alf Børge Bjørdal Lervåg'.decode('utf8'),
                'type': 'person',
                'id': 13830,
            },
        }]

        self._do_search("/?query=p:Alf&output=account", expected)

    def _do_search(self, query, expected):
        start_time = time.time()

        testutil.createRequest(query)
        self.assertEqual('200 OK', cherrypy.response.status)
        response = cjson.decode(cherrypy.response.body[0])

        end_time = time.time()

        results = response['ResultSet']

        match = [x for x in results if x['name'] == expected[0]['name']]
        self.assertEqual(expected, match)

        self._assert_that_search_is_fast_enough(start_time, end_time)

    def _assert_that_search_is_fast_enough(self, start_time, end_time):
        delta = end_time - start_time
        self.assert_(delta < 0.3, "Test should run in less than 0.3 seconds.  Used %s" % delta)

if __name__ == '__main__':
    unittest.main()
