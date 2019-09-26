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
""" Generate individual HTML reports for all group owners

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
DEFAULT_AUTH_OPERATION_SET = ['Group-owner']
DEFAULT_ENCODING = 'utf-8'
DEFAULT_LANGUAGE = 'nb'
TEMPLATE_NAME = 'group_members_table.html'
# TODO is this too vulnerable to changes in brukerinfo?
BRUKERINFO_GROUP_MANAGE_LINK = 'https://brukerinfo.uio.no/groups/?group='
TRANSLATION = {
    'en': {
        'greeting': 'Hi,',
        'message': 'The following is an overview of all the groups where you '
                   'have an administrating role.',
        'signature': 'Best regards,',
        'group_name': 'Group name',
        'role': 'Role',
        'members': 'Members',
        'manage_link': 'Manage group',
        'alternative_text': (
            'Your email reader seems to be unable to show the html contents '
            'of this message. Please ensure that you allow rendering of html.')
    },
    'nb': {
        'greeting': 'Hei,',
        'message': 'Her følger en oversikt over alle grupper hvor du har'
                   ' en administrerende rolle.',
        'signature': 'Med vennlig hilsen,',
        'group_name': 'Gruppenavn',
        'role': 'Rolle',
        'members': 'Medlemmer',
        'manage_link': 'Administrer gruppe',
    },
    'nn': {
        'greeting': 'Hei,',
        'message': 'Her følgjer ei oversikt over alle grupper kor du har'
                   ' ei administrerende rolle.',
        'signature': 'Med vennleg helsing,',
        'group_name': 'Gruppenamn',
        'role': 'Rolle',
        'members': 'Medlem',
        'manage_link': 'Administrer gruppe',
    }
}


def get_title(language='english'):
    iso_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if language == 'english':
        return (
            'Review of the groups you are administrating ({timestamp})'.format(
                timestamp=iso_timestamp)
        )


def write_html_report(template_path, codec, **kwargs):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    template = env.get_template(TEMPLATE_NAME)

    return template.render(encoding=codec.name, **kwargs).encode(codec.name)


def create_html_message(html,
                        alternative_text,
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

    message.attach(MIMEText(alternative_text, 'plain'))
    message.attach(MIMEText(html, 'html'))
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
        self.gr = Factory.get('Group')(db)
        self.co = Factory.get('Constants')(db)
        self.ac = Factory.get('Account')(db)
        self.pe = Factory.get('Person')(db)
        self.dns_owner = DnsOwner(db)
        self.email_target = EmailTarget(db)
        self.email_address = EmailAddress(db)

    @memoize
    def get_entity_primary_email(self, member_id, member_type):
        if member_type == self.co.entity_person:
            self.pe.clear()
            self.pe.find(member_id)
            account = self.pe.get_primary_account()

            return get_address(
                self.email_target.list_email_target_primary_addresses(
                    target_entity_id=account['account_id'])[0])

        primary_addresses = (
            self.email_target.list_email_target_primary_addresses(
                target_entity_id=member_id)
        )
        if primary_addresses:
            return get_address(primary_addresses[0])
        return None

    @memoize
    def get_entity_name(self, entity_id, entity_type):
        # TODO: make this more general and smart
        # TODO: if member is not an account append (member_type)
        try:
            if entity_type == self.co.entity_account:
                self.ac.clear()
                self.ac.find(entity_id)
                return self.ac.get_name(domain=self.co.account_namespace)
            elif entity_type == self.co.entity_group:
                self.gr.clear()
                self.gr.find(entity_id)
                return self.gr.get_name(domain=self.co.group_namespace)
            elif entity_type == self.co.entity_dns_owner:
                self.dns_owner.clear()
                self.dns_owner.find(entity_id)
                return self.dns_owner.get_name(
                    domain=self.co.dns_owner_namespace)
            elif entity_type == self.co.entity_person:
                self.pe.clear()
                self.pe.find(entity_id)
                return self.pe.get_name(self.co.system_cached,
                                        self.co.name_full)
        except NotFoundError:
            pass
        return None

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
            for member in self.gr.search_members(group_id=group_id):
                cache[member['member_id']].append(group_id)
        return cache

    def cache_owner_id2groups(self, auth_op_set_names, ten):
        """Caches entities which have an auth_role for a group

        :argument auth_op_set_names: which auth_op_set to filter roles on
        :type auth_op_set_names: list
        :returns: a mapping from owner_id to a list of dicts on the form:
            {
                group_id: unicode,
                auth_op_set_name: unicode,
                group_name: unicode,
                manage_link: unicode
            }
        """
        bofhd_auth_op_set = BofhdAuthOpSet(self.db)
        bofhd_auth_role = BofhdAuthRole(self.db)
        bofhd_auth_op_target = BofhdAuthOpTarget(self.db)

        owner_id2groups = collections.defaultdict(list)
        for auth_op_set_name in auth_op_set_names:
            count = 0
            if not find_bofhd_auth_op_set(self.db, bofhd_auth_op_set,
                                          auth_op_set_name):
                continue
            for role in bofhd_auth_role.list(
                    op_set_id=bofhd_auth_op_set.op_set_id):

                # We only want to find owners who are groups
                if not find_group(self.db, self.gr, role['entity_id']):
                    continue

                bofhd_auth_op_target.clear()
                bofhd_auth_op_target.find(role['op_target_id'])

                if not bofhd_auth_op_target.target_type == 'group':
                    continue

                count += 1
                group_name = self.get_entity_name(role['entity_id'],
                                                  self.co.entity_group)
                owner_id2groups[role['entity_id']].append(
                    {
                        'group_id': bofhd_auth_op_target.entity_id,
                        'auth_op_set_name': auth_op_set_name,
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
        group_id2members = collections.defaultdict(list)
        for group in groups:
            group_id = group['group_id']

            for member in self.gr.search_members(group_id=group_id):
                group_id2members[group_id].append(self.get_entity_name(
                    member['member_id'], member['member_type'])
                )
        return group_id2members


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

    db = Factory.get('Database')()
    group_owner_cacher = GroupOwnerCacher(db)

    owner_id2groups = group_owner_cacher.cache_owner_id2groups(
        args.auth_operation_set,
        args.ten
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

        owned_groups = []
        for owner_id in owner_ids:
            owned_groups.extend(owner_id2groups[owner_id])

        title = get_title()
        html = write_html_report(
            args.template_folder,
            args.codec,
            title=title,
            # TODO How to decide which language?
            translation=TRANSLATION[DEFAULT_LANGUAGE],
            sender='TODO who?',
            owned_groups=owned_groups,
            group_id2members=group_id2members
        )

        logger.debug(html)
        message = create_html_message(html,
                                      TRANSLATION['en']['alternative_text'],
                                      subject=title,
                                      # TODO who is the sender?
                                      from_addr='h@uio.no',
                                      to_addrs=entity_email_address)
        Cerebrum.utils.email.send_message(message,
                                          debug=not args.commit)

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
