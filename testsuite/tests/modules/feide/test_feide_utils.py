# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.feide.feide_utils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import uuid

import pytest

from Cerebrum.modules.feide import feide_utils

VALID_UUID = "c05c2d98-b0fc-4fe3-b987-c952252c5a12"
INVALID_UUID = "c05c2d98-b0fc-4fe3-b987-c952252c5a1"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(VALID_UUID, id="uuid-string"),
        pytest.param(uuid.UUID(VALID_UUID), id="uuid-object"),
    ],
)
def test_is_uuid(value):
    assert feide_utils.is_uuid(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param(INVALID_UUID, id="invalid-uuid"),
    ],
)
def test_not_uuid(value):
    assert not feide_utils.is_uuid(value)


@pytest.mark.parametrize(
    "value",
    [
        "all",
        "ALL",
    ],
)
def test_is_keyword_all(value):
    assert feide_utils.is_keyword_all(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "with all values",
        "al",
        "allall",
    ],
)
def test_not_keyword_all(value):
    assert not feide_utils.is_keyword_all(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("all", id="literal-all"),
        pytest.param(VALID_UUID, id="uuid-string"),
        pytest.param(123, id="integer"),
        pytest.param("123", id="digits"),
    ],
)
def test_valid_feide_id(value):
    assert feide_utils.is_valid_feide_id_type(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("some text", id="text"),
        pytest.param(INVALID_UUID, id="invalid-uuid"),
    ],
)
def test_invalid_feide_id(value):
    assert not feide_utils.is_valid_feide_id_type(value)
