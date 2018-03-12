#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests that string/unicode input to the REST API gets normalized. """

from __future__ import unicode_literals

import pytest

from Cerebrum.rest.api import validator


def test_string_normalizes_unicode():
    ohm_sign = '\N{OHM SIGN}'
    letter_omega = '\N{GREEK CAPITAL LETTER OMEGA}'
    assert validator.String()(ohm_sign) == letter_omega
