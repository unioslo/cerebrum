#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2018 University of Oslo, Norway
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
""" Generate a dump of email addresses. """
import argparse
import logging
import os
import sys

from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type
from Cerebrum.modules import Email

logger = logging.getLogger(__name__)

# TODO: This script should probably use the csv module


def text_decoder(encoding, allow_none=True):
    def to_text(value):
        if allow_none and value is None:
            return None
        if isinstance(value, bytes):
            return value.decode(encoding)
        return text_type(value)
    return to_text


def format_entry(entry):
    return u':'.join((
        entry['account_name'],
        u'default',
        entry['default_address'],
        u'valid',
        u':'.join(entry['valid_addresses']),
        entry['email_server_name'] or text_type(entry['email_server_id'])))


def write_email_file(stream, codec, iterable):
    output = codec.streamwriter(stream)
    for entry in iterable:
        output.write(format_entry(entry))
        output.write(u'\n')
    output.write(u'\n')


def generate_email_data(db):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    u = text_decoder(db.encoding)

    email_spread = co.spread_email_account

    def get_valid_email_addrs(et):
        for row in et.get_addresses():
            yield u'{0}@{1}'.format(u(row['local_part']), u(row['domain']))

    def get_server_name(server_id):
        if not server_id:
            return None
        es = Email.EmailServer(db)
        es.find(server_id)
        return u(es.name)

    logger.debug("Fetching email data for users with email spread %s",
                 text_type(email_spread))
    for cnt, row in enumerate(ac.search(spread=email_spread), 1):
        if cnt % 1000 == 0:
            logger.debug('... account #%d ...', cnt)
        ac.clear()
        ac.find(row['account_id'])

        account_name = u(ac.account_name)

        # fetch primary address
        try:
            primary = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.warn("No primary address for %s", account_name)
            continue

        # find email target for this account
        et = Email.EmailTarget(db)
        et.clear()
        try:
            et.find_by_target_entity(ac.entity_id)
        except Errors.NotFoundError:
            logger.warn("No email target for %s", account_name)
            continue

        valid_addrs = list(get_valid_email_addrs(et))
        email_server_name = get_server_name(et.email_server_id)

        yield {
            'account_name': account_name,
            'default_address': primary,
            'valid_addresses': valid_addrs,
            'email_server_id': et.email_server_id,
            'email_server_name': email_server_name,
        }

    logger.debug('Done fetching email data')


DEFAULT_ENCODING = 'utf-8'
DEFAULT_OUTFILE = os.path.join(sys.prefix, 'var', 'cache', 'MAIL',
                               'mail_data.dat')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a report on persons and accounts")

    parser.add_argument(
        '-f', '--file',
        dest='output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default=DEFAULT_OUTFILE,
        help="Output file, defaults to %(default)s (use '-' for stdout)")
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="Output file encoding, defaults to %(default)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get('Database')()

    write_email_file(
        args.output,
        args.codec,
        generate_email_data(db))

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
