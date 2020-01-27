#!/usr/bin/env python
# encoding: utf-8
"""
Additional test config for gpg tests.

These fixtures sets up a GPG homedir and gpgme context for testing
Cerebrum.utils.gpg and Cerebrum.modules.gpg
"""
import shutil
import tempfile

import gpgme
import pytest


# parameters for gpgme.genkey(), see
# <https://pygpgme.readthedocs.io/en/latest/api.html> and
# <https://www.gnupg.org/documentation/manuals/gnupg/Unattended-GPG-key-generation.html>
KEY_PARAMS = """
<GnupgKeyParms format="internal">
    %no-protection
    %transient-key
    Key-Type: RSA
    Key-Length: 2048
    Name-Real: Cerebrum Testsuite
    Expire-Date: 0
</GnupgKeyParms>
"""


def _make_key(ctx):
    """ Make a new key and return its fingerprint. """
    keyres = ctx.genkey(KEY_PARAMS)
    return keyres.fpr


@pytest.fixture(scope='session')
def gpg_home():
    """ a temporary gpg homedir """
    tempdir = tempfile.mkdtemp(suffix='crb-test-gpg')
    # Fortunately, mkdtemp() already creates using the perms we need (0700)
    yield tempdir
    shutil.rmtree(tempdir)


@pytest.fixture
def cereconf(cereconf, gpg_home):
    old_home = cereconf.GNUPGHOME
    cereconf.GNUPGHOME = gpg_home
    yield cereconf
    cereconf.GNUPGHOME = old_home


@pytest.fixture(scope='session')
def gpg_context(gpg_home):
    """ a gpg context for this test session. """
    ctx = gpgme.Context()
    ctx.set_engine_info(gpgme.PROTOCOL_OpenPGP, None, gpg_home)
    ctx.armor = True
    return ctx


@pytest.fixture(scope='session')
def gpg_key(gpg_context):
    """ a gpg key for this test session. """
    return _make_key(gpg_context)
