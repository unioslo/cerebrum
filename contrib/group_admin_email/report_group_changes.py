#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
    check_date
)
from Cerebrum.modules.email_report.plain_text_table import get_table

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'statistics',
    'templates'
)
FIELDS = ('group_id',
          'group_name',
          'changes',
          'manage_link')
TEMPLATE_NAME = 'report_group_changes.html'
FROM_ADDRESS = 'noreply@usit.uio.no'
SENDER = 'USIT\nUiO'
DEFAULT_ENCODING = 'utf-8'
DEFAULT_LANGUAGE = 'nb'
BRUKERINFO_GROUP_MANAGE_LINK = 'https://brukerinfo.uio.no/groups/?group='
INFO_LINK = 'https://www.uio.no/tjenester/it/brukernavn-passord/brukeradministrasjon/hjelp/grupper/rapportering/?'

# TODO change report templates html, and this one:
# TODO change other scripts use of GroupAdminCacher
TRANSLATION = {
    'en': {
        'title': 'Changes to the groups you are managing',
        'greeting': 'Hi,',
        'message': 'The following is a report of changes to the groups you'
                   'are managing. Please make sure that the changes are in '
                   'line with what you expect. To see more information about '
                   'a group, or to delete it once it is no longer needed, you '
                   'can click on "Manage group". If you want to investigate '
                   'the changes more closely, you can also use bofh with the '
                   'command "entity history group:<name>".',
        'changes': {
            'group:modify': 'group attributes modified {} times',
            'group_member:add': '{} members added',
            'group_member:remove': '{} members removed',
            'spread:add': '{} spreads added',
            'spread:delete': '{} spreads removed'
        },
        'info_link': 'For more information go to the page ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Best regards,',
        'manage': 'Manage group',
        'headers': collections.OrderedDict([
            ('group_name', 'Managed group'),
            ('changes', 'Changes last 30 days'),
            ('manage_link', 'Link to brukerinfo'),
        ]),
    },
    'nb': {
        'title': 'Endringer på gruppene du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følger en oversikt over endringer som har skjedd med '
                   'gruppene du er administrator for. Vi ber om at du går '
                   'gjennom disse endringene for å se at de er riktige. For å '
                   'se mer informasjon om en gruppe, eller slette den om den '
                   'ikke er i bruk, kan du klikke på "Administrer gruppe". Om '
                   'du vil undersøke endringene grundigere kan du bruke '
                   'kommandoen "entity history group:<navn>" som er '
                   'tilgjengelig kommandolinje-verktøyet bofh.',
        'changes': {
            'group:modify': '{} endringer på gruppen',
            'group_member:add': '{} medlemmer lagt til',
            'group_member:remove': '{} medlemmer fjernet',
            'spread:add': '{} spreads lagt til',
            'spread:delete': '{} spreads fjernet'
        },
        'info_link': 'For mer informasjon gå til siden ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennlig hilsen,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppe du administrerer'),
            ('changes', 'Hendelser siste 30 dager'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    },
    'nn': {
        'title': 'Endringar på gruppene du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følgjer ei oversikt over endringar som har skjedd med '
                   'gruppene du er administrator for. Vi ber om at du går '
                   'gjennom desse endringane for å sjå til at dei er riktige. '
                   'For å sjå meir informasjon om ei gruppe, eller slette '
                   'henne om den ikkje lenger er i bruk, kan du klikke på '
                   '"Administrer gruppe". Om du vil undersøke endringane '
                   'grundigare kan du bruke kommandoen '
                   '"entity history group:<navn>" som er tilgjengeleg i '
                   'kommandolinje-verktøyet bofh.',
        'changes': {
            'group:modify': '{} endringer på gruppen',
            'group_member:add': '{} medlemer lagt til',
            'group_member:remove': '{} medlemer fjernet',
            'spread:add': '{} spreads lagt til',
            'spread:delete': '{} spreads fjernet'
        },
        'info_link': 'For meir informasjon gå til sida ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennleg helsing,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppe du administrerer'),
            ('changes', 'Hendingar siste 30 dager'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    }
}


def write_plain_text_report(codec, translation=None, sender=None,
                            owned_groups=None,
                            account_name=None, info_link=None):
    def get_table_rows():
        def get_cell_value(key):
            if key == 'changes':
                return [
                    translation['changes'][k].format(v) for k, v in
                    six.iteritems(group[key])
                ]
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


def merge_admin_types(admins1, admins2):
    for admin_id, group_info in six.iteritems(admins2):
        admins1[admin_id].extend(group_info)
    return admins1


def cache_info(db, nr_of_admins=None):
    cacher = GroupAdminCacher(db, BRUKERINFO_GROUP_MANAGE_LINK)
    cl_const = Factory.get('CLConstants')(db)
    change_types = (cl_const.group_add,
                    cl_const.group_rem,
                    cl_const.group_mod,
                    cl_const.spread_add,
                    cl_const.spread_del)
    fields = TRANSLATION['headers'].keys(),
    direct_admins = cacher.cache_direct_admins(
        fields,
        change_types=change_types,
        nr_of_admins=nr_of_admins
    )
    admins_by_membership = cacher.cache_admins_by_membership(
        fields,
        change_types=change_types,
        nr_of_admins=nr_of_admins
    )
    return merge_admin_types(
        direct_admins,
        admins_by_membership
    )


def send_mails(db, args):
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    account_id2managed_groups = cache_info(
        db,
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
            account_name=account_name,
            info_link=INFO_LINK,
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
    test_group.add_argument(
        '--ten',
        action='store_true',
        help='Only process 10 group admins of each type'
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
