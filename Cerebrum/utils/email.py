#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Utilities for sending e-mail."""

from __future__ import absolute_import

import cereconf
import smtplib
import six


def sendmail(toaddr, fromaddr, subject, body, cc=None,
             charset='utf-8', debug=False):
    """Sends e-mail, mime-encoding the subject.  If debug is set,
    message won't be send, and the encoded message will be
    returned."""

    from email.MIMEText import MIMEText
    from email.Header import Header
    from email.Utils import formatdate

    msg = MIMEText(body, _charset=charset)
    msg['Subject'] = Header(subject.strip(), charset)
    msg['From'] = fromaddr.strip()
    msg['To'] = toaddr.strip()
    msg['Date'] = formatdate(localtime=True)
    # recipients in smtp.sendmail should be a list of RFC 822
    # to-address strings
    toaddr = [addr.strip() for addr in toaddr.split(',')]
    if cc:
        toaddr.extend([addr.strip() for addr in cc.split(',')])
        msg['Cc'] = cc.strip()
    if debug or getattr(cereconf, 'EMAIL_DISABLED', False):
        return msg.as_string()
    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    smtp.sendmail(fromaddr, toaddr, msg.as_string())
    smtp.quit()


def mail_template(recipient, template_file, sender=None, cc=None,
                  substitute={}, charset='utf-8', debug=False):
    """Read template from file, perform substitutions based on the
    dict, and send e-mail to recipient.  The recipient and sender
    e-mail address will be used as the defaults for the To and From
    headers, and vice versa for sender.  These values are also made
    available in the substitution dict as the keys 'RECIPIENT' and
    'SENDER'.

    When looking for replacements in the template text, it has to be
    enclosed in ${}, ie. '${SENDER}', not just 'SENDER'.  The template
    should contain at least a Subject header.  Make each header in the
    template a single line, it will be folded when sent.  Note that
    due to braindamage in Python's email module, only Subject and the
    body will be automatically MIME encoded.  The lines in the
    template should be terminated by LF, not CRLF.

    """
    from email.MIMEText import MIMEText
    from email.Header import Header
    from email.Utils import formatdate, getaddresses

    if not template_file.startswith('/'):
        template_file = cereconf.TEMPLATE_DIR + "/" + template_file
    f = open(template_file)
    message = "".join(f.readlines())
    f.close()
    substitute['RECIPIENT'] = recipient
    if sender:
        substitute['SENDER'] = sender
    for key in substitute:
        if isinstance(substitute[key], six.text_type):
            message = message.replace("${%s}" % key, substitute[key].encode(
                charset))
        else:
            message = message.replace("${%s}" % key, substitute[key])

    headers, body = message.split('\n\n', 1)
    msg = MIMEText(body, _charset=charset)
    # Date is always set, and shouldn't be in the template
    msg['Date'] = formatdate(localtime=True)
    preset_fields = {'from': sender,
                     'to': recipient,
                     'subject': '<none>'}
    for header in headers.split('\n'):
        field, value = map(six.text_type.strip, header.split(':', 1))
        field = field.lower()
        if field in preset_fields:
            preset_fields[field] = value
        else:
            msg[field] = Header(value)
    msg['From'] = Header(preset_fields['from'])
    msg['To'] = Header(preset_fields['to'])
    msg['Subject'] = Header(preset_fields['subject'], charset)
    # recipients in smtp.sendmail should be a list of RFC 822
    # to-address strings
    to_addrs = [recipient]
    if cc:
        to_addrs.extend(cc)
        msg['Cc'] = ', '.join(cc)

    if debug or getattr(cereconf, 'EMAIL_DISABLED', False):
        return msg.as_string()

    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    smtp.sendmail(sender or getaddresses([preset_fields['from']])[0][1],
                  to_addrs, msg.as_string())
    smtp.quit()
