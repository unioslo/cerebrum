# -*- coding: utf-8 -*-
"""tests for Cerebrum.modules.LDIFutils"""
from __future__ import unicode_literals

import re

from Cerebrum.modules import LDIFutils


def test_hex_escape_match_bytes():
    match = re.match('...', b'123')
    assert LDIFutils.hex_escape_match(match) == r'\313233'


def test_hex_escape_match_unicode():
    match = re.match('...', u'123')
    assert LDIFutils.hex_escape_match(match) == r'\313233'
