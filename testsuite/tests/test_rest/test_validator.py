#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for api.validator """

import pytest

from Cerebrum.rest.api import validator


def test_string():
    chain = validator.Chain()
    chain.add(validator.String(min_len=3))
    chain.add(validator.String(max_len=6, trim=True))
    assert chain('xxx') == 'xxx'
    assert chain('xxxx    ') == 'xxxx'
    with pytest.raises(ValueError):
        chain('x')
    with pytest.raises(ValueError):
        chain('xxxxxxxxxx')


def test_integer():
    chain = validator.Chain()
    chain.add(validator.Integer(min_val=10))
    chain.add(validator.Integer(max_val=20))
    assert chain(15) == 15
    with pytest.raises(ValueError):
        chain(5)
    with pytest.raises(ValueError):
        chain(25)
    with pytest.raises(TypeError):
        chain('x')
