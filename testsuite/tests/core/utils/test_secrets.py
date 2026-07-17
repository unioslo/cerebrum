# -*- coding: utf-8 -*-
"""
Unit tests for mod:`Cerebrum.utils.secrets`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import os

import pytest

from Cerebrum.utils import secrets

# these tests uses the conftest fixtures:
#
# - 'write_dir' - as cereconf.DB_AUTH_DIR
# - 'new_file' - as password file in some tests


class _LegacyFile(object):
    """ legacy password data helper. """

    def __init__(self, user, passwd, system, host=None):
        self.user = user
        self.passwd = passwd
        self.system = system
        self.host = host

    @property
    def content(self):
        """ password file content. """
        return "\t".join((self.user, self.passwd))

    @property
    def args(self):
        """ arguments for legacy_read_password. """
        if self.host:
            return (self.user, self.system, self.host)
        else:
            return (self.user, self.system)

    @property
    def key(self):
        """ key for the legacy-file source handler. """
        return "@".join(self.args)

    @property
    def filename(self):
        """ basename of the password file in DB_AUTH_DIR. """
        return "passwd-" + self.key.lower()


# legacy files: (user, passwd, system, host)
legacy_sys = _LegacyFile(user="Foo", passwd="BarBaz", system="System")
legacy_host = _LegacyFile(user="AzureDiamond", passwd="hunter2",
                          system="IRC", host="example.org")


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf, write_dir):
    """ cereconf with a temporary DB_AUTH_DIR. """

    for data in (legacy_sys, legacy_host):
        # place a legacy file in DB_AUTH_DIR
        with io.open(os.path.join(write_dir, data.filename), mode="w",
                     encoding="utf-8") as f:
            f.write(data.content)
            # add some trailing newlines
            f.write("\n\n")

    cereconf.DB_AUTH_DIR = write_dir


@pytest.mark.parametrize('data',
                         (legacy_sys, legacy_host),
                         ids=("system", "host"))
def test_legacy_read_password(data):
    passwd = secrets.legacy_read_password(*data.args)
    assert passwd == data.passwd


#
# secret source handler tests.
#

file_handlers = (
    ('file', secrets._read_secret_file),
    ('auth-file', secrets._read_secret_auth_file),
    ('legacy-file', secrets._read_legacy_password_file),
)


@pytest.mark.parametrize('source, expect_handler',
                         file_handlers,
                         ids=[t[0] for t in file_handlers])
def test_get_file_handlers(source, expect_handler):
    """ check that we get the *file* handler by lookup """
    handler = secrets.get_handler(source)
    assert handler is expect_handler


def test_get_invalid_handler():
    """ Check that a ValueError is raised when fetching an unknown handler. """
    with pytest.raises(ValueError):
        secrets.get_handler("foo")


def test_plaintext_handler():
    """ check that the plaintext handler is an identity function. """
    value = secrets.get_secret('plaintext', "foo")
    assert value == "foo"


example_content = "hello, world!"


@pytest.fixture
def example_file(new_file):
    """ filename of a file with *example_content* outside DB_AUTH_DIR """
    with io.open(new_file, mode="w", encoding="utf-8") as f:
        f.write(example_content)
        # add trailing newlines
        f.write("\n\n")
    return new_file


def test_file_handler(example_file):
    """ check that we get the full content of *file* by lookup. """
    content = secrets.get_secret('file', example_file)
    assert content == example_content


def test_auth_file_handler():
    """ verify content from an *auth-file* in DB_AUTH_DIR. """
    # test_legacy_file is the basename of a file in DB_AUTH_DIR, and should
    # contain test_legacy_content.  This is set up by the cereconf fixture at
    # the start of this test module.
    content = secrets.get_secret('auth-file', legacy_sys.filename)
    assert content == legacy_sys.content


@pytest.mark.parametrize('data',
                         (legacy_sys, legacy_host),
                         ids=("system", "host"))
def test_legacy_file_handler(data):
    """ verify password from a *legacy-file* user@system[@host]. """
    # key is the "legacy name" (user@system[@host]) of the password file
    # in DB_AUTH_DIR
    passwd = secrets.get_secret('legacy-file', data.key)
    assert passwd == data.passwd


#
# secret string ("source:arg") serialization tests.
#

def test_split_string():
    """ verify secret strings splits correctly into source, source-arg. """
    assert secrets.split_secret_string("foo:bar:baz") == ("foo", "bar:baz")


def test_get_secret_from_string():
    passwd = secrets.get_secret_from_string("plaintext:hunter2")
    assert passwd == "hunter2"


def test_get_blank_secret_from_string():
    passwd = secrets.get_secret_from_string("plaintext:")
    assert passwd == ""


def test_get_secret_from_invalid_format():
    with pytest.raises(ValueError):
        secrets.get_secret_from_string("plaintext")


def test_get_secret_from_unknown_source():
    with pytest.raises(ValueError):
        secrets.get_secret_from_string("foo:bar")
