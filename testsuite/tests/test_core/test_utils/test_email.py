#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests for e-mail utlities. """
from __future__ import print_function, unicode_literals

import pytest
import base64
import os
import tempfile


MAIL_TEMPLATE = """From: noreply@example.com
Subject: hello
X-Custom-Field: foo

FOO=${FOO}
RECIPIENT=${RECIPIENT}
SENDER=${SENDER}
"""


@pytest.fixture
def cereconf(cereconf):
    cereconf.EMAIL_DISABLED = True
    cereconf.TEMPLATE_DIR = tempfile.gettempdir()
    return cereconf


def test_sendmail(cereconf):
    from Cerebrum.utils.email import sendmail
    mail = {
        'toaddr': 'foo@example.com,bar@example.com',
        'fromaddr': 'baz@example.com',
        'cc': 'one@example.com,two@example.com',
        'subject': 'Testing',
        'body': 'hello this is dog'
    }
    result = sendmail(**mail)
    assert 'To: ' + mail['toaddr'] in result
    assert 'From: ' + mail['fromaddr'] in result
    assert 'Cc: ' + mail['cc'] in result
    assert 'Subject: ' + mail['subject'] in result
    assert base64.b64encode(mail['body']) in result


def test_mail_template(cereconf):
    from Cerebrum.utils.email import mail_template
    with tempfile.NamedTemporaryFile(prefix='test_mail_template') as f:
        f.write(MAIL_TEMPLATE)
        f.flush()
        mail = {
            'recipient': 'foo@example.com',
            'sender': 'bar@example.com',
            'cc': ['baz@example.com', ],
            'template_file': os.path.basename(f.name),
            'substitute': {
                'FOO': 'bar',
            },
        }
        result = mail_template(**mail)
    assert 'To: ' + mail['recipient'] in result
    assert 'Cc: ' + mail['cc'][0] in result
    assert 'From: noreply@example.com' in result
    assert 'Subject: hello' in result
    body = base64.b64decode(result.split('\n')[-2])
    assert 'FOO=bar' in body
    assert 'RECIPIENT=' + mail['recipient'] in body
    assert 'SENDER=' + mail['sender'] in body
