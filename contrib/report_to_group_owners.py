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

import jinja2

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from smtplib import SMTPException

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.email
from Cerebrum.modules.dns.DnsOwner import DnsOwner
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError, TooManyRowsError
from Cerebrum.modules.bofhd.auth import (BofhdAuthOpSet,
                                         BofhdAuthRole,
                                         BofhdAuthOpTarget)
from Cerebrum.modules.Email import EmailTarget, EmailAddress
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)

# TODO maybe use absolute path
DEFAULT_TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__),
                                       'statistics',
                                       'templates')
TEMPLATE_NAME = 'group_members_table.html'
FROM_ADDRESS = 'noreply@usit.uio.no'
SENDER = 'USIT\nUiO'
DEFAULT_AUTH_OPERATION_SET = ['Group-owner']
DEFAULT_ENCODING = 'utf-8'
DEFAULT_LANGUAGE = 'nb'
BRUKERINFO_GROUP_MANAGE_LINK = 'https://brukerinfo.uio.no/groups/?group='
INFO_LINK = 'https://www.uio.no/tjenester/it/brukernavn-passord/brukeradministrasjon/hjelp/grupper/rapportering/?'
TRANSLATION = {
    'en': {
        'greeting': 'Hi,',
        'message': 'The following is an overview of all the groups that you '
                   'are administrating. At UiO access to web pages and some '
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
            ('group_name', 'Group name'),
            ('members', 'Member count'),
            ('manage_link', 'Link to brukerinfo'),
        ]),
    },
    'nb': {
        'greeting': 'Hei,',
        'message': 'Her følger en oversikt over alle grupper du kan '
                   'administrerere. På UiO blir tilgang til nettsider og en '
                   'del verktøy definert av gruppemedlemskap. Det er derfor '
                   'viktig at kun riktige personer er medlemmer i hver gruppe.'
                   ' Se over at medlemmene er riktige, og '
                   'fjern medlemmer som ikke lenger skal være med.',
        'info_link': 'For mer informasjon gå til siden ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennlig hilsen,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppenavn'),
            ('members', 'Antall medlemmer'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    },
    'nn': {
        'greeting': 'Hei,',
        'message': 'Her følgjer ei oversikt over alle grupper du kan'
                   'administrerere. På UiO blir tilgang til nettsider og ein '
                   'del verktøy definert av gruppemedlemskap. Det er derfor '
                   'viktig at kun riktige personer er medlemmar i kvar gruppe.'
                   'Sjå over at medlemma er riktige, og '
                   'fjern medlemmar som ikkje lenger skal vere med.',
        'info_link': 'For meir informasjon gå til sida ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennleg helsing,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppenamn'),
            ('members', 'Antal medlemmar'),
            ('manage_link', 'Link til brukerinfo'),
        ]),
    }
}


def get_title(language):
    iso_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if language == 'en':
        return (
            'Review of the groups you are administrating ({timestamp})'.format(
                timestamp=iso_timestamp)
        )
    elif language == 'nb':
        return (
            'Oversikt over gruppene du administrerer ({timestamp})'.format(
                timestamp=iso_timestamp
            )
        )
    elif language == 'nn':
        return (
            'Oversikt over gruppene du administrerer ({timestamp})'.format(
                timestamp=iso_timestamp
            )
        )


def write_html_report(template_path, codec, **kwargs):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    template = env.get_template(TEMPLATE_NAME)

    return template.render(encoding=codec.name, **kwargs).encode(codec.name)


def write_plain_text_report(codec, translation=None, sender=None,
                            owned_groups=None, group_id2members=None):
    def get_cell_content(text, cell_width):
        return text + (cell_width - len(text)) * ' '

    def get_cell_contents(texts, cell_widths):
        return [get_cell_content(t, l) for t, l in zip(texts, cell_widths)]

    def assemble_line(divider, cell_contents):
        return divider + divider.join(cell_contents) + divider + '\n'

    def get_longest_item_length(lst):
        return max(*map(len, lst))

    def get_cell_widths(headers, owned_groups):
        columns = map(
            lambda key: [headers[key]],
            translation['headers'].keys()
        )

        for group in owned_groups:
            columns[0].append(group['group_name'])
            columns[1].append(str(group_id2members[group['group_id']]))
            columns[2].append(group['manage_link'])

        return map(get_longest_item_length, columns)

    def get_table_rows(cell_widths, divider_line):
        rows = ''
        for group in owned_groups:
            group_name = group['group_name']
            members_count = str(group_id2members[group['group_id']])
            manage_link = group['manage_link']

            row_content_line = assemble_line(
                '|',
                get_cell_contents([group_name, members_count, manage_link],
                                  cell_widths)
            )

            rows += (row_content_line + divider_line)
        return rows

    def get_table():
        headers = collections.OrderedDict(translation['headers'])
        cell_widths = get_cell_widths(headers, owned_groups)

        separators = map(lambda length: length * '-', cell_widths)

        divider_line = assemble_line('+', separators)
        header_line = assemble_line(
            '|',
            get_cell_contents(headers.values(), cell_widths)
        )
        return divider_line + header_line + divider_line + get_table_rows(
            cell_widths, divider_line
        )

    return (
            '\n' + translation['greeting'] + 
            '\n\n' + translation['message'] + 
            '\n\n' + translation['info_link'] + translation['here'] + ': ' +
            INFO_LINK + 
            '\n\n' + get_table() + 
            '\n' + translation['signature'] + 
            '\n' + sender
    ).encode(codec.name)


def create_html_message(html,
                        plain_text,
                        codec,
                        subject=None,
                        from_addr=None,
                        to_addrs=None):
    message = MIMEMultipart('alternative')
    if subject:
        message['Subject'] = subject
    if from_addr:
        message['From'] = from_addr
    if to_addrs:
        message['To'] = to_addrs

    message.attach(MIMEText(plain_text, 'plain', codec.name))
    message.attach(MIMEText(html, 'html', codec.name))
    return message


def find_group(db, gr, entity_id):
    gr.clear()
    try:
        gr.find(entity_id)
    except NotFoundError:
        db.rollback()
        return False
    return True


def find_bofhd_auth_op_set(db, bofhd_auth_op_set, auth_op_set_name):
    bofhd_auth_op_set.clear()
    try:
        bofhd_auth_op_set.find_by_name(auth_op_set_name)
    except NotFoundError:
        db.rollback()
        logger.info('Bofhd auth operation set %s not found, skipping',
                    auth_op_set_name)
        return False
    except TooManyRowsError:
        db.rollback()
        logger.info('Multiple bofhd auth operation sets %s not found, '
                    'skipping', auth_op_set_name)
        return False
    return True


def get_address(row):
    return row['local_part'] + '@' + row['domain']


class GroupOwnerCacher(object):
    def __init__(self, db):
        self.db = db
        self.en = Factory.get('Entity')(db)
        self.co = Factory.get('Constants')(db)
        self.person = Factory.get('Person')(db)
        self.group = Factory.get('Group')(db)
        self.account = Factory.get('Account')(db)
        self.dns_owner = DnsOwner(db)
        self.email_target = EmailTarget(db)
        self.email_address = EmailAddress(db)
        self.bofhd_auth_op_set = BofhdAuthOpSet(self.db)
        self.bofhd_auth_role = BofhdAuthRole(self.db)
        self.bofhd_auth_op_target = BofhdAuthOpTarget(self.db)

    @memoize
    def get_entity_primary_email(self, member_id, member_type):
        if member_type == self.co.entity_person:
            self.person.clear()
            self.person.find(member_id)
            member_id = self.person.get_primary_account()

        primary_addresses = (
            self.email_target.list_email_target_primary_addresses(
                target_entity_id=member_id)
        )
        if primary_addresses:
            return get_address(primary_addresses[0])
        return None

    @memoize
    def get_entity_name(self, entity_id, entity_type):
        cls = getattr(self, str(self.co.EntityType(entity_type)), None)
        if cls:
            cls.clear()
            cls.find(entity_id)
            try:
                if entity_type == self.co.entity_person:
                    return cls.get_name(self.co.system_cached,
                                        self.co.name_full)
                elif entity_type == self.co.entity_account:
                    self.person.clear()
                    try:
                        self.person.find(cls.owner_id)
                        owner_name = self.person.get_name(
                            self.co.system_cached,
                            self.co.name_full
                        )
                    except NotFoundError:
                        return cls.account_name
                    else:
                        return cls.account_name + ' ({})'.format(owner_name)
                return cls.get_domain_name()
            except NotFoundError:
                pass
        return str(entity_id)

    @memoize
    def get_entity_type(self, entity_id):
        self.en.clear()
        self.en.find(entity_id)
        return self.en.entity_type

    def cache_member_id2group_ids(self, group_ids):
        """Maps an entity_id to the group_ids where it is a member

        :type group_ids: list
        :arg group_ids: the group_ids to search for membership
        :returns: a mapping of entity_id to a list of group_ids
        """
        cache = collections.defaultdict(list)
        for group_id in group_ids:
            for member in self.group.search_members(group_id=group_id):
                cache[member['member_id']].append(group_id)
        return cache

    def cache_one_accounts_groups(self, auth_op_set_names, account_name):
        owner_id2groups = collections.defaultdict(list)
        self.account.clear()
        self.account.find_by_name(account_name)
        for auth_op_set_name in auth_op_set_names:
            if not find_bofhd_auth_op_set(self.db,
                                          self.bofhd_auth_op_set,
                                          auth_op_set_name):
                continue

            for group in self.group.search(member_id=self.account.entity_id):
                for role in self.bofhd_auth_role.list(
                        entity_ids=group['group_id'],
                        op_set_id=self.bofhd_auth_op_set.op_set_id
                ):
                    self.bofhd_auth_op_target.clear()
                    self.bofhd_auth_op_target.find(role['op_target_id'])

                    if not self.bofhd_auth_op_target.target_type == 'group':
                        continue

                    group_id = self.bofhd_auth_op_target.entity_id

                    group_name = self.get_entity_name(group_id,
                                                      self.co.entity_group)
                    owner_id2groups[role['entity_id']].append(
                        {
                            'group_id': group_id,
                            'role': auth_op_set_name,
                            'group_name': group_name,
                            'manage_link': (BRUKERINFO_GROUP_MANAGE_LINK +
                                            group_name)
                        }
                    )
        return owner_id2groups

    def cache_owner_id2groups(self, auth_op_set_names, ten):
        """Caches groups which have an auth_role for a group

        :argument auth_op_set_names: which auth_op_set to filter roles on
        :type auth_op_set_names: list
        :returns: a mapping from owner_id to a list of dicts on the form:
            {
                group_id: unicode,
                role: unicode,
                group_name: unicode,
                manage_link: unicode
            }
        """
        owner_id2groups = collections.defaultdict(list)
        for auth_op_set_name in auth_op_set_names:
            count = 0
            if not find_bofhd_auth_op_set(self.db,
                                          self.bofhd_auth_op_set,
                                          auth_op_set_name):
                continue
            for role in self.bofhd_auth_role.list(
                    op_set_id=self.bofhd_auth_op_set.op_set_id):

                # We only want to find owners who are groups
                if not find_group(self.db, self.group, role['entity_id']):
                    continue

                self.bofhd_auth_op_target.clear()
                self.bofhd_auth_op_target.find(role['op_target_id'])

                if not self.bofhd_auth_op_target.target_type == 'group':
                    continue
                group_id = self.bofhd_auth_op_target.entity_id
                count += 1

                group_name = self.get_entity_name(group_id,
                                                  self.co.entity_group)
                owner_id2groups[role['entity_id']].append(
                    {
                        'group_id': group_id,
                        'role': auth_op_set_name,
                        'group_name': group_name,
                        'manage_link': (BRUKERINFO_GROUP_MANAGE_LINK +
                                        group_name)
                    }
                )
                if ten and count >= 10:
                    break
            logger.info('%s %s(s) found. All the owners are groups themselves',
                        count,
                        auth_op_set_name)
        return owner_id2groups

    def cache_group_id2members(self, groups):
        group_id2members = {}
        for group in groups:
            group_id = group['group_id']
            members_count = len(
                [m for m in self.group.search_members(group_id=group_id)]
            )
            group_id2members[group_id] = members_count
        return group_id2members


def send_mails(db, args):
    group_owner_cacher = GroupOwnerCacher(db)

    if args.only_owner:
        owner_id2groups = group_owner_cacher.cache_one_accounts_groups(
            args.auth_operation_set,
            args.only_owner,
        )
        entity_id2owner_ids = {
            group_owner_cacher.account.entity_id:  owner_id2groups.keys()
        }
    else:
        owner_id2groups = group_owner_cacher.cache_owner_id2groups(
            args.auth_operation_set,
            args.ten,
        )
        entity_id2owner_ids = group_owner_cacher.cache_member_id2group_ids(
            owner_id2groups.keys()
        )
    all_owned_groups = []
    map(all_owned_groups.extend, owner_id2groups.values())
    group_id2members = group_owner_cacher.cache_group_id2members(
        all_owned_groups)

    for entity_id, owner_ids in entity_id2owner_ids.items():
        entity_type = group_owner_cacher.get_entity_type(entity_id)
        entity_email_address = group_owner_cacher.get_entity_primary_email(
            entity_id,
            entity_type
        )
        if not entity_email_address:
            logger.warning('No primary email for %s', entity_id)
            continue

        owned_groups = []
        for owner_id in owner_ids:
            owned_groups.extend(owner_id2groups[owner_id])

        title = get_title(DEFAULT_LANGUAGE)

        html = write_html_report(
            args.template_folder,
            args.codec,
            title=title,
            translation=TRANSLATION[DEFAULT_LANGUAGE],
            sender=SENDER,
            owned_groups=owned_groups,
            group_id2members=group_id2members,
            info_link=INFO_LINK,
        )
        plain_text = write_plain_text_report(
            args.codec,
            translation=TRANSLATION[DEFAULT_LANGUAGE],
            sender=SENDER,
            owned_groups=owned_groups,
            group_id2members=group_id2members,
        )
        message = create_html_message(html,
                                      plain_text,
                                      args.codec,
                                      subject=title,
                                      from_addr=FROM_ADDRESS,
                                      to_addrs=entity_email_address)
        try:
            Cerebrum.utils.email.send_message(message, debug=not args.commit)
        except SMTPException as e:
            logger.warning(e)


def check_date(dates, today=None):
    """Check if today is one of the given dates"""
    if not dates:
        return True
    today = today or datetime.date.today()
    return (today.month, today.day) in [(d.month, d.day) for d in dates]


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="html encoding, defaults to %(default)s")
    parser.add_argument(
        '-a', '--auth-operation-set',
        action='append',
        default=DEFAULT_AUTH_OPERATION_SET,
        help='Auth operation set names to filter bofhd_auth_roles by, '
             'defaults to %(default)s'
    )
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
