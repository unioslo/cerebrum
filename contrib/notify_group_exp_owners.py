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
"""
Script for notifying the owners of expiring groups

The near future is defined using two time limits such that owners are notified
two times about the expiration. We keep track of this by setting a trait on
the groups whose owners have been notified. The trait has a numval with value
1 for the first notification, and 2 for the second one.

The script also does clean up of the trait, such that any group with the trait
that has an expire date further into the future than the second time limit, has
the trait removed. This ensures that owners can be notified of the same group
multiple times.
"""
from __future__ import unicode_literals, print_function

import argparse
import collections
import datetime
import logging
import os
from smtplib import SMTPException

import six

import Cerebrum.utils.email
import cereconf
from Cerebrum import logutils
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.argutils import codec_type
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.email_report.utils import (
    timestamp_title,
    write_html_report,
    create_html_message,
    get_account_email
)
from Cerebrum.modules.email_report.plain_text_table import get_table

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__),
                                       'statistics',
                                       'templates')
TEMPLATE_NAME = 'group_expiring_table.html'
FROM_ADDRESS = 'noreply@usit.uio.no'
SENDER = 'USIT\nUiO'
DEFAULT_ENCODING = 'utf-8'
DEFAULT_LANGUAGE = 'nb'
BRUKERINFO_GROUP_MANAGE_LINK = 'https://brukerinfo.uio.no/groups/?group='
INFO_LINK = 'https://www.uio.no/tjenester/it/brukernavn-passord/brukeradministrasjon/hjelp/grupper/rapportering/?'

TRANSLATION = {
    'en': {
        'title': 'Review of soon expiring groups you are administrating',
        'greeting': 'Hi,',
        'message': "The following groups will expire in the near future. If "
                   "you want the groups to remain, please extend their expire "
                   "date. If you would like the group to expire, no action is "
                   "needed."

                   "The groups can be managed with the account {}. "
                   "You are considered to be an administrator of these groups "
                   "because you are a direct administrator, or a member of "
                   "administrator group(s) giving you that role. ",
        'info_link': 'For more information go to the page ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Best regards,',
        'manage': 'Manage group',
        'headers': collections.OrderedDict([
            ('group_name', 'Managed group'),
            ('expire_date', 'Expire date'),
            ('manage_link', 'Link to Brukerinfo'),
        ]),
    },
    'nb': {
        'title': 'Oversikt over grupper med kort utløpsdato du administrerer',
        'greeting': 'Hei,',
        'message': "Her følger en oversikt over grupper med utløpsdato i "
                   "nærmeste fremtid. Vennligst forleng utløpsdato om du "
                   "ønsker å beholde dem. Hvis du vil at gruppene skal utløpe "
                   "trenger du ikke foreta deg noe. "
                   "Gruppene kan administrereres med kontoen {}. "
                   "Du blir regnet som administrator for disse gruppene fordi "
                   "du er satt som administrator, eller er medlem av "
                   "administrator-gruppe(r) som gir deg den rollen. "
                   "På UiO blir tilgang til nettsider og en del verktøy "
                   "definert av gruppemedlemskap. Det er derfor viktig at "
                   "grupper vedlikeholdes kontinuerlig.",
        'info_link': 'For mer informasjon gå til ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennlig hilsen,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppe du administrerer'),
            ('expire_date', 'Utløpsdato'),
            ('manage_link', 'Link til Brukerinfo'),
        ]),
    },
    'nn': {
        'title': 'Oversikt over grupper med kort utløpsdato du administrerer',
        'greeting': 'Hei,',
        'message': 'Her følgjer ei oversikt over alle grupper du kan '
                   'administrerere med brukaren {}. Du blir '
                   'rekna som administrator for desse gruppene fordi du er '
                   'medlem av administrator-gruppe(r) som gir deg den rolla. '
                   'På UiO blir tilgang til nettsider og ein '
                   'del verktøy definert av gruppemedlemskap. Det er derfor '
                   'viktig at kun riktige personer er medlemmar i kvar '
                   'gruppe. Sjå over at medlemma er riktige, og '
                   'fjern medlemmar som ikkje lenger skal vere med. ',
        'info_link': 'For meir informasjon gå til sida ',
        'here': 'Automatisk rapportering av grupper.',
        'signature': 'Med vennleg helsing,',
        'manage': 'Administrer gruppe',
        'headers': collections.OrderedDict([
            ('group_name', 'Gruppe du administrerer'),
            ('expire_date', 'Utløpsdato'),
            ('manage_link', 'Link til Brukerinfo'),
        ]),
    }
}


def write_plain_text_report(codec, translation=None, sender=None,
                            expiring_groups=None,
                            account_name=None):
    def get_table_rows():
        keys = translation['headers'].keys()
        rows = [translation['headers'].values()]
        for group in expiring_groups:
            rows.append([group[k] for k in keys])
        return rows

    return (
            '\n' + translation['greeting'] +
            '\n\n' + translation['message'].format(account_name) +
            '\n\n' + translation['info_link'] + translation['here'] + ': ' +
            INFO_LINK +
            '\n\n' + get_table(get_table_rows()) +
            '\n' + translation['signature'] +
            '\n' + sender
    ).encode(codec.name)


def send_mails(args, group_info_dict, translation, title):
    owner2groupids = group_info_dict['owner2groupids']
    owner2mail = group_info_dict['owner2mail']
    groupid2name = group_info_dict['groupid2name']
    groupid2expdate = group_info_dict['groupid2expdate']

    for account_name, groups in owner2groupids.items():
        email_address = owner2mail.get(account_name, None)
        if not email_address:
            logger.warning('No primary email for %s', account_name)
            continue

        expiring_groups = [{
            'group_name': groupid2name[gr_id],
            'expire_date': groupid2expdate[gr_id],
            'manage_link': BRUKERINFO_GROUP_MANAGE_LINK + groupid2name[gr_id]
        } for gr_id in groups]

        html = write_html_report(
            TEMPLATE_NAME,
            args.template_folder,
            args.codec,
            title=title,
            translation=translation,
            sender=SENDER,
            expiring_groups=expiring_groups,
            info_link=INFO_LINK,
            account_name=account_name,
        )
        plain_text = write_plain_text_report(
            args.codec,
            translation=translation,
            sender=SENDER,
            expiring_groups=expiring_groups,
            account_name=account_name,
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
        except SMTPException:
            logger.warning("Failed to notify moderator with username %s",
                           account_name,
                           exc_info=True)


def get_expiring_groups(db, co, today, timelimit1, timelimit2):
    gr = Factory.get('Group')(db)

    # Find the mods of the groups
    manual_group_types = list(
        co.GroupType(i) for i in cereconf.PERISHABLE_MANUAL_GROUP_TYPES)
    all_groups = gr.search(group_type=manual_group_types, filter_expired=True)

    before_t1 = [i['group_id'] for i in all_groups
                 if i['expire_date'] is not None and
                 today < i['expire_date'] <= timelimit1]
    after_t1_before_t2 = [i['group_id'] for i in all_groups
                          if i['expire_date'] is not None and
                          timelimit1 < i['expire_date'] < timelimit2]
    return set(before_t1), set(after_t1_before_t2)


def make_parser():
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
    limits = parser.add_argument_group(
        "Limits",
        "Time limits for first and second warnings"
    )
    limits.add_argument('--limit1',
                        required=True,
                        type=int,
                        help='Time until expire date in days')
    limits.add_argument('--limit2',
                        required=True,
                        type=int,
                        help='Time until expire date in days')
    test_group = parser.add_argument_group('Testing',
                                           'Arguments useful when testing')
    test_group.add_argument(
        '-p', '--print-messages',
        action='store_true',
        help='Print messages to console'
    )
    add_commit_args(parser, commit_desc='Send emails to group owners')
    return parser


@memoize
def get_group_info(gr, group_id):
    gr.clear()
    gr.find(group_id)
    return gr.group_name, six.text_type(gr.expire_date.date)


def get_admins_groups_emails(db, expiring_groups):
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    # Cache owner and group info
    owner2groupids = {}
    owner2mail = {}
    groupid2name = {}
    groupid2expdate = {}

    def cache_owner_groups_and_email(account_id, group_id):
        email = get_account_email(co, ac, account_id)
        account_name = ac.account_name
        if email:
            owner2mail[account_name] = email
        else:
            # No way to contact this person, go to next group
            # member
            return
        grname, exp_date = get_group_info(gr, group_id)
        if account_name in owner2groupids:
            owner2groupids[account_name].add(group_id)
        else:
            owner2groupids[account_name] = {group_id, }
        groupid2name[group_id] = grname
        groupid2expdate[group_id] = exp_date
        return

    roles = GroupRoles(db)
    admins = roles.search_admins(group_id=expiring_groups)
    for admin in admins:
        gr_id = admin['group_id']
        if admin['admin_type'] == co.entity_group:
            for row in gr.search_members(
                    group_id=admin['admin_id'],
                    member_type=(co.entity_account, co.entity_person)
            ):
                if row['member_type'] == co.entity_account:
                    ac_id = row['member_id']
                    cache_owner_groups_and_email(ac_id, gr_id)

                elif row['member_type'] == co.entity_person:
                    pe.clear()
                    pe.find(row['member_id'])
                    ac_id = pe.get_primary_account()
                    if ac_id is not None:
                        cache_owner_groups_and_email(ac_id, gr_id)

        elif admin['admin_type'] == co.entity_account:
            ac_id = admin['admin_id']
            cache_owner_groups_and_email(ac_id, gr_id)

        elif admin['admin_type'] == co.entity_person:
            pe.clear()
            pe.find(admin['admin_id'])
            ac_id = pe.get_primary_account()
            if ac_id is not None:
                cache_owner_groups_and_email(ac_id, gr_id)

        else:
            raise ValueError(
                "Unknown admin type '{}'".format(admin['admin_type']))
    return {'owner2groupids': owner2groupids,
            'owner2mail': owner2mail,
            'groupid2name': groupid2name,
            'groupid2expdate': groupid2expdate}


def main(inargs=None):
    # Parse arguments
    parser = make_parser()

    # Setup logging
    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    # Do the main logic of the script
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    co = Factory.get('Constants')(db)

    # Find owners of groups expiring between today and limit_1, and groups
    # expiring between limit_1 and limit_2
    today = datetime.date.today()
    limit_1 = today + datetime.timedelta(days=args.limit1)
    limit_2 = today + datetime.timedelta(days=args.limit2)
    logger.info("Finding expiring groups")
    soon_expiring, later_expiring = get_expiring_groups(
        db,
        co,
        today,
        limit_1,
        limit_2
    )

    # Filter out groups that have already been notified
    gr = Factory.get('Group')(db)

    def filter_with_trait(groups, numval=NotSet):
        notified_groups = set(
            row['entity_id'] for row in
            gr.list_traits(code=co.trait_group_expire_notify,
                           numval=numval) if
            row['entity_type'] == co.entity_group
        )
        return groups - notified_groups

    logger.info("Filtering out groups that have been notified")
    # Remove those that have gotten the second warning from the groups in the
    # today < x < limit_1 period
    soon_expiring = filter_with_trait(soon_expiring, 2)
    logger.info("Found %d groups expiring before %s",
                len(soon_expiring), str(limit_1))

    # Remove those that have gotten any warning from the groups in the
    # limit_1 < x < limit_2 period
    later_expiring = filter_with_trait(later_expiring)
    logger.info("Found %d groups expiring between %s and %s",
                len(later_expiring), str(limit_1), str(limit_2))

    # Set traits on the groups whose admins have been notified
    logger.info("Setting traits on groups to notify")
    for group_id in soon_expiring:
        gr.clear()
        gr.find(group_id)
        gr.populate_trait(co.trait_group_expire_notify, numval=2)
        gr.write_db()
        logger.debug("Set trait (numval=2) for group id %s", group_id)
    for group_id in later_expiring:
        gr.clear()
        gr.find(group_id)
        gr.populate_trait(co.trait_group_expire_notify, numval=1)
        gr.write_db()
        logger.debug("Set trait (numval=1) for group id %s", group_id)

    # Get the emails of the group admins and notify them
    if soon_expiring:
        logger.info("Finding emails to admins")
        soon = get_admins_groups_emails(db, soon_expiring)
        logger.info("Notifying admins of groups expiring before %s",
                    str(limit_1))
        send_mails(args,
                   soon,
                   TRANSLATION[DEFAULT_LANGUAGE],
                   timestamp_title(TRANSLATION[DEFAULT_LANGUAGE]['title']))

    if later_expiring:
        logger.info("Finding emails to admins")
        later = get_admins_groups_emails(db, later_expiring)
        logger.info("Notifying admins of groups expiring between %s and %s",
                    str(limit_1), str(limit_2))
        send_mails(args,
                   later,
                   TRANSLATION[DEFAULT_LANGUAGE],
                   timestamp_title(TRANSLATION[DEFAULT_LANGUAGE]['title']))

    # Remove traits for notified groups where the expire date has been
    # extended, so that the group can be notified again in the future.
    logger.info("Cleaning up traits for groups where admins have taken action")
    groups_with_expiring_trait = list(i['entity_id'] for i in
                                      gr.list_traits(
                                          code=co.trait_group_expire_notify)
                                      if i['entity_type'] == co.entity_group)
    for group_id in groups_with_expiring_trait:
        gr.clear()
        gr.find(group_id)
        if gr.expire_date > limit_2:
            gr.delete_trait(co.trait_group_expire_notify)
            logger.debug("Removed trait for group id %s", group_id)
    # Commit or rollback
    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        db.rollback()
        logger.info("Changes rolled back (dryrun)")

    logger.info("DONE %s", parser.prog)


if __name__ == '__main__':
    main()
