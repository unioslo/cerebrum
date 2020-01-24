#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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

from smtplib import SMTPException

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.email
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type
from Cerebrum.modules.email_report.GroupOwnerCacher import GroupOwnerCacher
from Cerebrum.modules.email_report.utils import (
    timestamp_title,
    get_account_name,
    get_account_email,
    create_html_message,
    write_html_report,
    check_date
)
from Cerebrum.modules.email_report.plain_text_table import get_table

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'statistics',
    'templates'
)
TEMPLATE_NAME = 'group_members_table.html'
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
        'message': 'The following is an overview of all the groups that you '
                   'can manage with the account {}. You are considered to be'
                   'an administrator of these groups because your account '
                   'is set as admin for them. '
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
            ('members', 'Member count'),
            ('manage_link', 'Link to brukerinfo'),
        ]),
    },
    'nb': {
        'title': 'Oversikt over gruppene du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følger en oversikt over alle grupper du kan '
                   'administrerere med brukerkontoen {}. Du blir '
                   'regnet som administrator for disse gruppene fordi du '
                   'kontoen din er satt til å være administrator for dem. '
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
            ('members', 'Antall medlemmer'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    },
    'nn': {
        'title': 'Oversikt over gruppene du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følgjer ei oversikt over alle grupper du kan'
                   'administrerere med brukarkontoen {}. Du blir '
                   'rekna som administrator for desse gruppene fordi kontoen '
                   'din er sett til å vere administrator for dei. '
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
            ('members', 'Antal medlemmar'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    }
}


def write_plain_text_report(codec, translation=None, sender=None,
                            owned_groups=None, group_id2members=None,
                            account_name=None, info_link=None):
    def get_table_rows():
        def get_cell_value(key):
            if key == 'members':
                return str(group_id2members[group['group_id']])
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


def get_one_admins_groups(group, account, admin_name):
    account.clear()
    account.find_by_name(admin_name)
    return {
        account.entity_id: {
            'group_id': row['group_id'],
            'group_name': row['group_name'],
            'manage_link': (BRUKERINFO_GROUP_MANAGE_LINK +
                            row['group_name'])
        } for row in group.search(admin_id=account.entity_id)
    }


def send_mails(db, args):
    group_owner_cacher = GroupOwnerCacher(db, BRUKERINFO_GROUP_MANAGE_LINK)
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    if args.only_owner:
        gr = Factory.get('Group')(db)
        admin_id2groups = get_one_admins_groups(gr, ac, args.only_owner)
    else:
        admin_id2groups = group_owner_cacher.cache_owner_id2groups(
            co.entity_account,
            ('group_id', 'group_name', 'manage_link'),
            nr_of_admins=10 if args.ten else None
        )

    all_owned_groups = []
    map(all_owned_groups.extend, admin_id2groups.values())
    group_id2members = group_owner_cacher.cache_group_id2members(
        all_owned_groups)

    for account_id, groups in admin_id2groups.items():
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
            group_id2members=group_id2members,
            info_link=INFO_LINK, account_name=account_name,
        )
        plain_text = write_plain_text_report(
            args.codec,
            translation=TRANSLATION[DEFAULT_LANGUAGE],
            sender=SENDER,
            owned_groups=groups,
            group_id2members=group_id2members,
            account_name=account_name,
            info_link=INFO_LINK
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
        '-ten',
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
