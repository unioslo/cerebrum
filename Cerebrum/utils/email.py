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
""" Utilities for sending e-mail.


cereconf
--------
``EMAIL_DISABLED`` (bool)
    Flag to disable all email sending -- should be set to ``False`` in
    production.

``SMTP_HOST`` (basestring)
    The SMTP host to use for sending email.

``TEMPLATE_DIR`` (basestring)
    Path to a directory with email templates, for use with ``mail_template``.


TODO
----
- Clean up the sendmail and mail_template functions.
- Consider removing possibility for using different sender/receivers than
  what's in the email headers.
- Consider using a global, default sender email address (no-reply)
- Replace all use of mail_template with proper (jinja2) template rendering and
  just sendmail/send_message?

"""

from __future__ import absolute_import

import copy
import logging
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formatdate, getaddresses

import six

import cereconf

logger = logging.getLogger(__name__)


def _is_disabled(disable_flag):
    global_disable = getattr(cereconf, 'EMAIL_DISABLED', False)
    if disable_flag or global_disable:
        logger.info("email disabled, will not send (EMAIL_DISABLED=%r)",
                    global_disable)
        return True
    return False


def get_charset(message, default='ascii'):
    """
    :type message: email.message.Message
    :return str: returns the charset name
    """
    charset = message.get_charset()
    return str(charset) if charset else default


def render_message(message):
    """ Get a formatted string from an email message object.

    :type message: email.message.Message
    :return six.text_type: returns the raw email message
    """
    email_bytes = message.as_string()
    return email_bytes.decode(get_charset(message))


def sendmail(toaddr, fromaddr, subject, body, cc=None,
             charset='utf-8', debug=False):
    """ Build and send an email message.

    If debug is set, message won't be sent, and the encoded message will be
    returned.
    """
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

    # TODO: This makes no sense -- return the result of _send_message!
    if _is_disabled(debug):
        return render_message(msg)

    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    _send_message(smtp, msg, from_addr=fromaddr, to_addrs=toaddr)
    smtp.quit()


def mail_template(recipient, template_file, sender=None, cc=None,
                  substitute={}, charset='utf-8', debug=False):
    """ Send e-mail template.

    Reads template from file, performs substitutions based on the
    dict, and sends e-mail to recipient.  The recipient and sender
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

    # TODO: This makes no sense -- return the result of _send_message!
    if _is_disabled(debug):
        return render_message(msg)

    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    _send_message(smtp, msg, from_addr=sender, to_addrs=to_addrs)
    smtp.quit()


def send_message(message,
                 from_addr=None, to_addrs=None,
                 mail_options=None, rcpt_options=None,
                 debug=False):
    """ Send an email message.

    Note that all fields must be Header objects or bytestrings -- unicode
    strings *will* fail.

    :type message: email.message.Message
    :param bool debug:
        Iff True, message will *only* get rendered and returned.
    """
    if _is_disabled(debug):
        return {}

    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    result = _send_message(smtp,
                           message,
                           from_addr=from_addr,
                           to_addrs=to_addrs,
                           mail_options=mail_options,
                           rcpt_options=rcpt_options)
    smtp.quit()
    return result


def _send_message(smtp_obj, msg,
                  from_addr=None, to_addrs=None,
                  mail_options=None, rcpt_options=None):
    """ Convert message to a bytestring and passes it to sendmail.

    :type smtp_obj: smtplib.SMTP
    :type msg: email.message.Message
    :type from_addr: basestring or email.header.Header
    :type to_addrs: list of basestring or list of email.header.Header
    :type mail_options: list
    :type rcpt_options: dict

    This function is adapted from the python3 implementation of
    ``smtplib.SMTP.send_message``.

    """
    mail_options = mail_options or []
    rcpt_options = rcpt_options or {}
    # if the global cereconf disable is set -- abort here!
    if _is_disabled(False):
        raise RuntimeError("email disabled!")
    # 'Resent-Date' is a mandatory field if the Message is resent (RFC 2822
    # Section 3.6.6). In such a case, we use the 'Resent-*' fields.  However,
    # if there is more than one 'Resent-' block there's no way to
    # unambiguously determine which one is the most recent in all cases,
    # so rather than guess we raise a ValueError in that case.
    #
    # TODO implement heuristics to guess the correct Resent-* block with an
    # option allowing the user to enable the heuristics.  (It should be
    # possible to guess correctly almost all of the time.)
    resent = msg.get_all('Resent-Date')
    if resent is None:
        header_prefix = ''
    elif len(resent) == 1:
        header_prefix = 'Resent-'
    else:
        raise ValueError("message has more than one 'Resent-' header block")
    if from_addr is None:
        # Prefer the sender field per RFC 2822:3.6.2.
        from_addr = (msg[header_prefix + 'Sender']
                     if (header_prefix + 'Sender') in msg
                     else msg[header_prefix + 'From'])
        from_addr = getaddresses([from_addr])[0][1]
    if to_addrs is None:
        addr_fields = [f for f in (msg[header_prefix + 'To'],
                                   msg[header_prefix + 'Bcc'],
                                   msg[header_prefix + 'Cc'])
                       if f is not None]
        to_addrs = [a[1] for a in getaddresses(addr_fields)]
    # Make a local copy so we can delete the bcc headers.
    msg_copy = copy.copy(msg)
    del msg_copy['Bcc']
    del msg_copy['Resent-Bcc']
    flatmsg = msg_copy.as_string()
    logger.info("sending email to %r", to_addrs)
    result = smtp_obj.sendmail(from_addr, to_addrs, flatmsg, mail_options,
                               rcpt_options)
    for addr, error_tuple in result.items():
        logger.error("unable to send to %r: %r", addr, error_tuple)
    return result
