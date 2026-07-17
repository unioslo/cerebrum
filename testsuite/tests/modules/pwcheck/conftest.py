# -*- coding: utf-8 -*-
"""
Test fixtures for :mod:`Cerebrum.modules.pwcheck` tests

These fixtures are super hacky, and involves potentially calling `msgfmt` to
compile `cerebrum.mo` locale files.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import shutil
import subprocess
import sys
import tempfile

import gettext
import pytest
import six


gettext_domain = "cerebrum"
gettext_languages = ("en", "nb")

# potential locale directories, depending on where we run the tests
locale_src = os.path.join(os.path.dirname(__file__), "../../../../locales")
locale_dst = os.path.join(sys.prefix, "share/locale")


def _find_locales():
    """ Find the locale files here, or installed in virtualenv. """
    for path in [locale_src, locale_dst]:
        if os.path.exists(path):
            return path
    pytest.skip(
        "Missing locale for domain=%s (in %s or %s)"
        % (repr(gettext_domain), repr(locale_src), repr(locale_dst)))


@pytest.fixture(scope='session')
def gettext_localedir():
    """ Creates a temp dir for installing locales. """
    dirname = tempfile.mkdtemp(prefix="test-mod-pwcheck-locale-")
    yield dirname
    # `rm -r` the directory after after all tests have completed
    shutil.rmtree(dirname)


def _install_gettext_file(source_dir, dest_dir, domain, lang):
    mo_basename = os.path.extsep.join((domain, 'mo'))
    po_basename = os.path.extsep.join((domain, 'po'))
    # Source dir
    messages_dir = os.path.join(source_dir, lang, 'LC_MESSAGES')

    # the absolute target path for this specific language
    install_dir = os.path.join(dest_dir, lang, 'LC_MESSAGES')
    if not os.path.exists(install_dir):
        # create the path if it doesn't exist
        os.makedirs(install_dir)

    mo_file = os.path.join(messages_dir, mo_basename)
    if os.path.isfile(mo_file):
        # .mo file exists for this language. Use it!
        shutil.copyfile(mo_file, os.path.join(install_dir,
                                              mo_basename))
        return
    # no .mo file found. See is there is a .po file
    po_file = os.path.join(messages_dir, po_basename)
    if os.path.isfile(po_file):
        # ... then compile the .po file into .mo file
        subprocess.call([
            'msgfmt',
            '-o', os.path.join(install_dir, mo_basename),
            po_file,
        ])
        return


@pytest.fixture(autouse=True)
def _install_locales(gettext_localedir):
    """ Installs locales into our temporary gettext_localedir. """
    from Cerebrum.modules.pwcheck import checker
    source_dir = _find_locales()

    try:
        for lang in gettext_languages:
            _install_gettext_file(source_dir, gettext_localedir,
                                  gettext_domain, lang)

        # patch checker directories and values
        checker.locale_dir = gettext_localedir
        checker.gettext_domain = gettext_domain

        # (re-)install current domain/localedir
        if six.PY2:
            gettext.install(gettext_domain, gettext_localedir, unicode=True)
        else:
            gettext.install(gettext_domain, gettext_localedir)
    except Exception as e:
        pytest.skip(
            "Unable to set up locale for domain=%s (%s)"
            % (repr(gettext_domain), e))


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf, gettext_localedir):
    cereconf.GETTEXT_DOMAIN = gettext_domain
    cereconf.GETTEXT_LOCALEDIR = gettext_localedir
    cereconf.GETTEXT_LANGUAGE_IDS = gettext_languages
