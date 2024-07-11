# -*- coding: utf-8 -*-
"""
Tests for mod:`Cerebrum.utils.email`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import base64
import os
import tempfile
import textwrap
from email.mime.text import MIMEText

import pytest

from Cerebrum.utils import email


MAIL_TEMPLATE = """
From: noreply@example.com
Subject: hello
X-Custom-Field: foo

FOO=${FOO}
RECIPIENT=${RECIPIENT}
SENDER=${SENDER}
""".lstrip()


@pytest.fixture(autouse=True)
def _patch_email_settings(cereconf):
    """ Patch cereconf with email settings. """
    cereconf.EMAIL_DISABLED = True
    cereconf.TEMPLATE_DIR = tempfile.gettempdir()


#
# email validation tests
#


@pytest.mark.parametrize(
    "addr",
    [
        "foo@example.org",
        "foo+bar@example.org",
        "foo.bar@sub.example.org",
    ],
)
def test_is_email(addr):
    assert email.is_email(addr)


@pytest.mark.parametrize(
    "addr",
    [
        "foo",  # only local-part
        "example.org",  # only domain-part
    ],
)
def test_is_not_email(addr):
    assert not email.is_email(addr)


@pytest.mark.parametrize(
    "local_part",
    [
        "foo",
        "~foo!",
        "foo+bar",
        "foo.bar.baz",
    ],
)
def test_legacy_validate_lp_valid(local_part):
    email.legacy_validate_lp(local_part)
    assert True  # reached without error


@pytest.mark.parametrize(
    "local_part",
    [
        "foo4567890" * 7,  # > 64 chars
        "foo bar",  # space is not permitted (invalid char)
        "foo..bar",  # two or more repeated dots are not permitted
        "foo@bar",  # special chars
        "foo(bar)",  # special chars
    ],
)
def test_legacy_validate_lp_invalid(local_part):
    with pytest.raises(ValueError):
        email.legacy_validate_lp(local_part)


@pytest.mark.parametrize(
    "domain",
    [
        "localhost",
        "example.org"
        "foo0.example.org",
    ],
)
def test_legacy_validate_domain_valid(domain):
    email.legacy_validate_domain(domain)
    assert True  # reached without error


@pytest.mark.parametrize(
    "domain",
    [
        "foo-.example.org",  # label ends with -
        "-foo.example.org",  # label starts with -
        "foo--bar.example.org",  # double -- in label
        "foo_bar.example.org",  # invalid char _
    ],
)
def test_legacy_validate_domain_invalid(domain):
    with pytest.raises(ValueError):
        email.legacy_validate_domain(domain)


#
# email message object utils
#


def test_render_message():
    body = "Hello, World"
    msg = MIMEText(body, _charset="utf-8")
    expect = textwrap.dedent(
        """
        Content-Type: text/plain; charset="utf-8"
        MIME-Version: 1.0
        Content-Transfer-Encoding: base64

        SGVsbG8sIFdvcmxk
        """
    ).lstrip()
    assert email.render_message(msg) == expect


def test_sendmail():
    mail = {
        'toaddr': 'foo@example.com,bar@example.com',
        'fromaddr': 'baz@example.com',
        'cc': 'one@example.com,two@example.com',
        'subject': 'Testing',
        'body': 'hello this is dog',
        # we test with charset=ascii to avoid b64 in subject/body
        'charset': 'ascii',
    }
    # sendmail is a bit ugly - it only returns the rendered message when email
    # sending is disabled
    result = email.sendmail(**mail)
    assert 'To: ' + mail['toaddr'] in result
    assert 'From: ' + mail['fromaddr'] in result
    assert 'Cc: ' + mail['cc'] in result
    assert 'Subject: ' + mail['subject'] in result
    assert mail['body'] in result


def test_mail_template():
    with tempfile.NamedTemporaryFile(prefix='test_mail_template') as f:
        f.write(MAIL_TEMPLATE.encode("ascii"))
        f.flush()
        mail = {
            'recipient': 'foo@example.com',
            'sender': 'bar@example.com',
            'cc': ['baz@example.com', ],
            'template_file': os.path.basename(f.name),
            'substitute': {
                'FOO': 'bar',
            },
            # we test with charset=ascii to avoid b64 in subject/body
            'charset': 'ascii',
        }
        result = email.mail_template(**mail)
    assert 'To: ' + mail['recipient'] in result
    assert 'Cc: ' + mail['cc'][0] in result
    assert 'From: noreply@example.com' in result
    assert 'Subject: hello' in result
    body = result.split("\n\n", 1)[-1]
    assert 'FOO=bar' in body
    assert 'RECIPIENT=' + mail['recipient'] in body
    assert 'SENDER=' + mail['sender'] in body
