#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 - 2020 University of Oslo, Norway
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
""" Generate and send individual HTML reports to group owners

The report should contain an overview of the owners groups and the members in
each group.
"""
from __future__ import unicode_literals
import argparse
import datetime
import logging
import os
import collections

import six

from smtplib import SMTPException

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.email
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type
from Cerebrum.modules.email_report.GroupAdminCacher import GroupAdminCacher
from Cerebrum.modules.email_report.utils import (
    timestamp_title,
    get_account_name,
    get_account_email,
    create_html_message,
    write_html_report,
    check_date,
    count_members
)
from Cerebrum.modules.email_report.plain_text_table import get_table

logger = logging.getLogger(__name__)

# TODO maybe use absolute path
DEFAULT_TEMPLATE_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'statistics',
    'templates'
)
TEMPLATE_NAME = 'report_group_members.html'
FROM_ADDRESS = 'noreply@usit.uio.no'
SENDER = 'USIT\nUiO'
DEFAULT_ENCODING = 'utf-8'
DEFAULT_LANGUAGE = 'nb'
BRUKERINFO_GROUP_MANAGE_LINK = 'https://brukerinfo.uio.no/groups/?group='
INFO_LINK = 'https://www.uio.no/tjenester/it/brukernavn-passord/brukeradministrasjon/hjelp/grupper/rapportering/?'
TRANSLATION = {
    'en': {
        'title': 'Review of the groups you are administrating',
        'greeting': 'Hi,',
        'message': 'The following is an overview of groups that you '
                   'can manage with the account {}. You are considered to be'
                   'an administrator of these groups because you are member '
                   'of administrator group(s) which gives you that role. '
                   'At UiO access to web pages and some '
                   'tools is defined by group memberships. Therefore it is '
                   'important that only the correct persons are members in '
                   'each group. Please make sure that the member list '
                   'is correct and remove members which do not belong in the '
                   'group.',
        'info_link': 'For more information go to the page ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Best regards,',
        'manage': 'Manage group',
        'headers': collections.OrderedDict([
            ('group_name', 'Managed group'),
            ('owner_group_name', 'Administrator group'),
            ('members', 'Member count'),
            ('manage_link', 'Link to brukerinfo'),
        ]),
    },
    'nb': {
        'title': 'Oversikt over gruppene du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følger en oversikt over grupper du kan '
                   'administrerere med kontoen {}. Du blir '
                   'regnet som administrator for disse gruppene fordi du er '
                   'medlem av administrator-gruppe(r) som gir deg den rollen. '
                   'På UiO blir tilgang til nettsider og en '
                   'del verktøy definert av gruppemedlemskap. Det er derfor '
                   'viktig at kun riktige personer er medlemmer i hver gruppe.'
                   ' Se over at medlemmene er riktige, og '
                   'fjern medlemmer som ikke lenger skal være med.',
        'info_link': 'For mer informasjon gå til siden ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennlig hilsen,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppe du administrerer'),
            ('owner_group_name', 'Administrator-gruppe'),
            ('members', 'Antall medlemmer'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    },
    'nn': {
        'title': 'Oversikt over gruppene du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følgjer ei oversikt over grupper du kan'
                   'administrerere med brukaren {}. Du blir '
                   'rekna som administrator for desse gruppene fordi du er '
                   'medlem av administrator-gruppe(r) som gir deg den rolla. '
                   'På UiO blir tilgang til nettsider og ein '
                   'del verktøy definert av gruppemedlemskap. Det er derfor '
                   'viktig at kun riktige personer er medlemmar i kvar gruppe.'
                   'Sjå over at medlemma er riktige, og '
                   'fjern medlemmar som ikkje lenger skal vere med.',
        'info_link': 'For meir informasjon gå til sida ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennleg helsing,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppe du administrerer'),
            ('owner_group_name', 'Administrator-gruppe'),
            ('members', 'Antal medlemmar'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    }
}


def write_plain_text_report(codec, translation=None, sender=None,
                            owned_groups=None,
                            account_name=None, info_link=None):
    def get_table_rows():
        def get_cell_value(key):
            return group[key]

        keys = translation['headers'].keys()
        rows = [translation['headers'].values()]
        for group in owned_groups:
            rows.append([get_cell_value(k) for k in keys])
        return rows

    return (
            '\n' + translation['greeting'] +
            '\n\n' + translation['message'].format(account_name) +
            '\n\n' + translation['info_link'] + translation['here'] + ': ' +
            info_link +
            '\n\n' + get_table(get_table_rows()) +
            '\n' + translation['signature'] +
            '\n' + sender
    ).encode(codec.name)


def cache_one_accounts_groups(db, ac, account_name):
    account_id2groups = collections.defaultdict(list)
    ac.clear()
    ac.find_by_name(account_name)
    gr = Factory.get('Group')(db)
    for owner_group in gr.search(member_id=ac.entity_id):
        for group in gr.search(admin_id=owner_group['group_id']):
            account_id2groups[ac.entity_id].append(
                {
                    'group_name': group['name'],
                    'owner_group_name': owner_group['name'],
                    'members': six.text_type(
                        count_members(gr, group['group_id'])),
                    'manage_link': (BRUKERINFO_GROUP_MANAGE_LINK +
                                    group['name'])
                }
            )
    return account_id2groups


def cache_info(db, fields, nr_of_admins=None):
    cacher = GroupAdminCacher(db, BRUKERINFO_GROUP_MANAGE_LINK)
    return cacher.cache_admins_by_membership(
        fields,
        nr_of_admins=nr_of_admins
    )


def send_mails(db, args):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    if args.only_owner:
        account_id2managed_groups = cache_one_accounts_groups(db,
                                                              ac,
                                                              args.only_owner)
    else:
        account_id2managed_groups = cache_info(
            db,
            TRANSLATION[DEFAULT_LANGUAGE]['headers'].keys(),
            nr_of_admins=10 if args.ten else None
        )

    for account_id, groups in six.iteritems(account_id2managed_groups):
        email_address = get_account_email(co, ac, account_id)
        if not email_address:
            logger.warning('No primary email for %s', account_id)
            continue

        account_name = get_account_name(ac, account_id)
        title = timestamp_title(TRANSLATION[DEFAULT_LANGUAGE]['title'])

        html = write_html_report(
            TEMPLATE_NAME,
            args.template_folder,
            args.codec,
            title=title,
            translation=TRANSLATION[DEFAULT_LANGUAGE],
            sender=SENDER,
            owned_groups=groups,
            info_link=INFO_LINK, account_name=account_name,
        )
        plain_text = write_plain_text_report(
            args.codec,
            translation=TRANSLATION[DEFAULT_LANGUAGE],
            sender=SENDER,
            owned_groups=groups,
            account_name=account_name,
            info_link=INFO_LINK,
        )

        if args.print_messages:
            print(html)
            print(plain_text)

        message = create_html_message(html,
                                      plain_text,
                                      args.codec,
                                      subject=title,
                                      from_addr=FROM_ADDRESS,
                                      to_addrs=email_address)
        try:
            Cerebrum.utils.email.send_message(message, debug=not args.commit)
        except SMTPException as e:
            logger.warning(e)


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="html encoding, defaults to %(default)s")
    parser.add_argument(
        '-t', '--template-folder',
        default=DEFAULT_TEMPLATE_FOLDER,
        help='Path to the template folder'
    )
    parser.add_argument(
        '-d', '--dates',
        type=lambda date: datetime.datetime.strptime(date, '%d-%m'),
        default=None,
        action='append',
        help='Check date before running the script. Yearly dates to run the '
             'script on the format: <day>-<month>. The script runs normally if'
             ' no date is given.'
    )
    test_group = parser.add_argument_group('Testing',
                                           'Arguments useful when testing')
    test_group.add_argument(
        '-p', '--print-messages',
        action='store_true',
        help='Print messages to console'
    )
    test_mutex = test_group.add_mutually_exclusive_group()
    test_mutex.add_argument(
        '-o', '--only-owner',
        default=None,
        help='Only search for groups owned by the given account'
    )
    test_mutex.add_argument(
        '--ten',
        action='store_true',
        help='Only process 10 group owners'
    )
    add_commit_args(parser, commit_desc='Send emails to group owners')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    if check_date(args.dates):
        db = Factory.get('Database')()
        send_mails(db, args)
    else:
        logger.info('Today is not in the given list of dates')

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
