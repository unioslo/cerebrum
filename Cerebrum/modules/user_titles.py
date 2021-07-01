# -*- coding: utf-8 -*-

# Copyright 2021 University of Oslo, Norway
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
Module for making user title look ups and translations
"""
from __future__ import unicode_literals
import logging

from six import text_type
import cereconf

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

class UserTitles(object):
    """
    This class allows us to translate user titles.
    Available key types are:
      (must have both)
        - norTitle (Norwegian title)
        - engTitle (English title)
      (xor)
        - code (integer)
        - customTitleId (abbreviated Norwegian title)
    """
    def __init__(self, db, title_map):
        self.db = db
        self.title_map = cereconf.USER_TITLE_MAP
        # Make this as config variables or keep it here?
        self.nor_key = text_type('norTitle')
        self.en_key = text_type('engTitle')
        self.code_key = text_type('code')
        self.custom_key = text_type('customTitleId')
        self.index = text_type('index')
        self.valid_keys = [self.nor_key, self.en_key,
                           self.code_key, self.custom_key]

    def valid_search(self, search_type, search_val):
        return (search_type and
                search_val and
                search_type in self.valid_keys)

    def exact_search(self, search_type, search_val):
        '''Checks if search value exactly matches
        any entries.'''
        if not self.valid_search(search_type, search_val):
            return None
        matches = []
        for index, entry in self.title_map.items():
            if search_type in entry:
                value = entry[search_type]
                if search_type != self.code_key:
                    value = value.lower()
                    search_val = search_val.lower()
                if search_val == value:
                    entry[self.index] = index
                    matches.append(entry)
        return matches

    def translate(self, from_val, from_type, to_type):
        '''Translate a title from one description to another'''
        matches = self.exact_search(from_type, from_val)
        translations = []
        for match in matches:
            if to_type in match and from_type in match:
                translations.append(match[to_type])
        return translations

    def extract_from_list(self, results):
        '''Return results from list of results
        iff only one candidate exist.'''
        if (type(results) == list and len(results) == 1):
            return text_type(results[0])
        return None
