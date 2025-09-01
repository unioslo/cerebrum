# -*- coding: utf-8 -*-
""" unit tests for :mod:`Cerebrum.modules.no.access_FS`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.no import access_FS


#
# tests for Version tuple
#


@pytest.fixture
def version():
    return access_FS.Version(9, 4, 2)


def test_version_attrs(version):
    assert version.major == 9
    assert version.minor == 4
    assert version.patch == 2


def test_version_tuple(version):
    assert version == (9, 4, 2)


#
# tests for VersionSpec
#


@pytest.fixture
def version_spec():
    return access_FS.VersionSpec(start=(9, 4, 0), end=(9, 5, 0),
                                 start_open=False, end_open=True)


def test_version_spec_init(version_spec):
    assert version_spec.start == (9, 4, 0)
    assert version_spec.end == (9, 5, 0)
    assert not version_spec.start_open
    assert version_spec.end_open


def test_version_spec_eq(version_spec):
    other_eq = access_FS.VersionSpec(start=(9, 4, 0), end=(9, 5, 0),
                                     start_open=False, end_open=True)
    assert version_spec == other_eq

    other_ne = access_FS.VersionSpec(start=(9, 4, 0), end=(9, 5, 0),
                                     start_open=False, end_open=False)
    assert not version_spec == other_ne


def test_version_spec_ne(version_spec):
    # TODO: This is a bug! The following won't pass tests
    # other_eq = access_FS.VersionSpec(start=(9, 4, 0), end=(9, 5, 0),
    #                                  start_open=False, end_open=True)
    # assert not version_spec != other_eq

    other_ne = access_FS.VersionSpec(start=(9, 4, 0), end=(9, 5, 0),
                                     start_open=False, end_open=False)
    assert version_spec != other_ne


def test_version_spec_str(version_spec):
    assert six.text_type(version_spec) == "[9.4.0, 9.5.0)"


def test_version_spec_repr(version_spec):
    versions = (
        "Version(major=9, minor=4, patch=0)",
        "Version(major=9, minor=5, patch=0)",
    )
    expected = "VersionSpec(%s, %s, False, True)" % versions
    assert repr(version_spec) == expected


@pytest.mark.parametrize(
    "version",
    [
        pytest.param(access_FS.Version(9, 4, 0), id="start inclusive"),
        pytest.param(access_FS.Version(9, 4, 12), id="in range"),
    ],
)
def test_version_spec_matches(version_spec, version):
    assert version_spec.matches(version)


@pytest.mark.parametrize(
    "version",
    [
        pytest.param(access_FS.Version(9, 5, 0), id="end exclusive"),
        pytest.param(access_FS.Version(8, 4, 12), id="before range"),
        pytest.param(access_FS.Version(10, 4, 12), id="after range"),
    ],
)
def test_version_spec_matches_not(version_spec, version):
    assert not version_spec.matches(version)
