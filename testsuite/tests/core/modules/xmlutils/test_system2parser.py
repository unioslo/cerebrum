# coding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.xmlutils.system2parser`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest
import six

from Cerebrum.modules.xmlutils import system2parser
from Cerebrum.modules.xmlutils import sapxml2object
from Cerebrum.modules.xmlutils import ltxml2object
from Cerebrum.modules.xmlutils import fsxml2object


TESTS = {
    "FS": fsxml2object.FSXMLDataGetter,
    "LT": ltxml2object.LTXMLDataGetter,
    "ORGREG": sapxml2object.SAPXMLDataGetter,
    "system_fs": fsxml2object.FSXMLDataGetter,
    "system_lt": ltxml2object.LTXMLDataGetter,
    "system_orgreg": sapxml2object.SAPXMLDataGetter,
}


@pytest.mark.parametrize(
    "name",
    sorted(TESTS),
)
def test_get_parser(name):
    expeceted = TESTS[name]
    parser = system2parser.system2parser(name)
    assert parser is expeceted


@pytest.mark.parametrize(
    "name",
    sorted(TESTS),
)
@pytest.mark.skipif(six.PY3, reason="not supported on Python 3")
def test_get_parser_py2_bytestring(name):
    expeceted = TESTS[name]

    bytename = name.encode("ascii")
    parser = system2parser.system2parser(bytename)
    assert parser is expeceted
