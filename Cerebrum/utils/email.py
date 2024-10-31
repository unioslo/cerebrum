#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2024 University of Oslo, Norway
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
"""
Utilities for sending e-mail.

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
Separate formatting and sending
    We should split our functions (``sendmail``, ``mail_template``) into
    preparing messages and sending messages.  Rough suggestion:

    1. Define a PreparedMessage class to wrap a MIMEBase message object,
       along with *SMTP.sendmail* arguments.

    2. Change ``mail_template`` and ``sendmail`` to create a PreparedMessage
       rather than actually sending mail

    3. Rewrite ``send_message`` to take a single PreparedMessage and send it
       using the wrapped arguments.

Simplify sendmail
    Do we really need to separate between our headers (To, Cc) and our actual
    recipients?

Global sender
    We should consider using a global, *default* sender email address, e.g. a
    ``cereconf.SMTP_DEFAULT_SENDER = "Cerebrum <noreply@usit.uio.no>"``
    so that we don't have to specify this to everything that sends mail.

Better templates
    The templating system should ideally be replaced with simple jinja2
    templates.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import copy
import io
import logging
import smtplib
import re
import os
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formatdate, getaddresses

import six

from . import text_compat

import cereconf

logger = logging.getLogger(__name__)


def _is_disabled(disable_flag):
    global_disable = getattr(cereconf, 'EMAIL_DISABLED', False)
    if disable_flag or global_disable:
        logger.info("email disabled, will not send (EMAIL_DISABLED=%r)",
                    disable_flag or global_disable)
        return True
    return False


def is_email(address):
    """Return whether an email address follows the legal syntax or not

    An email address is compromised of a local and domain part, seperated by @

    Local name consists of letters, numbers and some special characters
    Can have dot . as well, but not first, last or consecutively

    Domain name consists of labels seperated by the dot character .
    Labels are made of letters, numbers and the hyphen symbol,
    labels can not start or end with a hyphen.

    NOTE: does not allow utf8 symbols even though the official standard does

    Keyword arguments:
    address -- string to be checked

    Returns:
    boolean -- is address a legal email address
    """
    letnums = "a-zA-Z0-9"
    special = "!#$%&'*+-/=?^_`{|}~"
    local = r'[' + letnums + special + r'](\.?[' + letnums + special + ']+)*'
    label = '(?!-)[a-zA-Z0-9-]{1,63}(?<!-)'
    domain = '(' + label + r'\.)+' + label
    pattern = '^' + local + '@' + domain + '$'
    return bool(re.match(pattern, address))


def legacy_validate_lp(localpart):
    """
    Check if string is valid for use as localpart in an email address.

    This is a subset (simplification) of RFC 2821 syntax, so e.g. quotes
    (neither quotation marks nor backslash) or comments (in parentheses) are
    not allowed.

    Legacy function from Cerebrum.modules.Email.
    """
    # 64 characters should be enough for everybody.
    # (RFC 2821 4.5.3.1)
    if len(localpart) > 64:
        raise ValueError("localpart too long: %d (max: 64)"
                         % len(localpart))
    # Only allow US-ASCII, and no SPC or DEL either.
    invalid = re.findall(r'[^!-~]', localpart)
    if invalid:
        raise ValueError("invalid chars in localpart: " + repr(set(invalid)))
    # No empty atoms
    if localpart.count(".."):
        raise ValueError("invalid atom in localpart (..)")
    # No "specials" (RFC 2822 3.2.1)
    specials = re.findall(r'[()<>\[\]:;@\\,]', localpart)
    if specials:
        raise ValueError("invalid chars in localpart: " + repr(set(specials)))


def legacy_validate_domain(domain):
    """
    Check if string is valid for use as domain in an email address.

    Legacy function from Cerebrum.modules.Email.
    """
    uber_hyphen = re.compile(r'--+')
    valid_chars = re.compile(r'^[a-zA-Z\-0-9]+$')

    # TODO/TDB: Doesn't check for:
    # # 1. Blank domain - we should probably:
    # if not domain or not domain.strip():
    #     raise ValueError("Illegal name: %s; Empty value" % repr(domain))
    # # 2. Empty/blank elements/labels - we should probably:
    # if domain.startswith('.') or '..' in domain:
    #     # domain *can* end with a single '.'
    #     raise ValueError("Illegal name: %s; Element cannot be empty"
    #                      % repr(domain))

    for element in domain.split("."):
        if element.startswith("-") or element.endswith("-"):
            raise ValueError("Illegal name: %s;"
                             " Element cannot start or end with '-'"
                             % repr(domain))
        if uber_hyphen.search(element):
            raise ValueError("Illegal name: %s; More than one '-' in a row"
                             % repr(domain))
        if not valid_chars.search(element):
            raise ValueError("Illegal name: %s; Invalid character(s)"
                             % repr(domain))


def render_message(message):
    """ Get a formatted string from an email message object.

    :type message: email.message.Message
    :return six.text_type: returns the raw email message
    """
    raw_msg = message.as_string()
    if isinstance(raw_msg, bytes):
        # PY2
        charset = message.get_charset()
        return raw_msg.decode(str(charset) if charset else "ascii")
    return raw_msg


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
                  substitute=None, charset='utf-8', debug=False):
    """
    Send e-mail template to a recipient.

    :type recipient: str
    :param recipient:
        Email address for the receiver of this email.

        This value is also used as the default 'To' header, and made available
        as 'RECIPIENT' in the `substitute`_ dict.

    :type template_file: str
    :param template_file:
        Filename of the template to send.

        If a relative path is given, it will be relative to
        ``cereconf.TEMPLATE_DIR``.

        The template may contain email headers, and should contain at least a
        Subject header.  It may also contain substitution strings e.g.
        ``${SOME_KEY}``.

    :type sender: str
    :param sender:
        Email address for the sender of this email.

        This value is also used as the default 'From' header, and made
        available as 'SENDER' in the substitute dict.

    :type substitute: dict
    :param substitute:
        A dict with substitution mappings for the template.

        The substitution strings ${RECIPIENT} and ${SENDER} are available by
        default, but this can be extended and replaced by this dict.

    :type charset: str
    :param charset:
        Charset for the email. The template must use this encoding as well.

    :type debug: bool
    :param debug:
        If ``True``, don't send email - just return the email contents.
    """
    if not template_file.startswith('/'):
        template_file = os.path.join(cereconf.TEMPLATE_DIR, template_file)
    with io.open(template_file, encoding=charset, mode='r') as f:
        message = f.read()

    substitute = dict(substitute or ())
    substitute['RECIPIENT'] = recipient
    if sender:
        substitute['SENDER'] = sender

    for key, value in substitute.items():
        try:
            value = text_compat.to_text(value)
            message = message.replace("${%s}" % key, value)
        except Exception:
            logger.error("unable to insert key %r into template %r",
                         key, template_file)
            raise

    headers, body = message.split("\n\n", 1)
    msg = MIMEText(body, _charset=charset)
    # Date is always set, and shouldn't be in the template
    msg['Date'] = formatdate(localtime=True)
    preset_fields = {
        'from': sender,
        'to': recipient,
        'subject': "<none>",
    }
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
    if six.PY2:
        flatmsg = msg_copy.as_string()
    else:
        flatmsg = msg_copy.as_bytes()
    logger.info("sending email to %r", to_addrs)
    result = smtp_obj.sendmail(from_addr, to_addrs, flatmsg, mail_options,
                               rcpt_options)
    for addr, error_tuple in result.items():
        logger.error("unable to send to %r: %r", addr, error_tuple)
    return result
