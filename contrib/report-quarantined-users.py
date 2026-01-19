#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2025 University of Oslo, Norway""
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
Generate and send an email report of accounts with quarantines.

This script generates a list of *active users* with quarantines, accordig to a
time criteria based on the date when the active quarantine was set first.

History
-------
This script was moved here from the 'cerebrum_config' repository.  The original
'bin/quarantine_users_report.py', can be seen in:

    Commit: fdfd2171f843b97938486287bdd0515f5f9007ea
    Date:   Wed May 23 19:34:39 2018 +0200

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import email
import io
import logging
import textwrap

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.email
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)

EMAIL_CHARSET = 'utf-8'
TEMPLATE_ENCODING = 'utf-8'


def iter_account_quarantines(db, q_types):
    """ Iterate over accounts with quarantines.

    :type q_types: sequence or NoneType
    :param q_types:
        Optionally only include the given quarantine types. ``None`` includes
        all quarantine types.

    :return generator:
        Returns a generator that yields tuples with the entity id and start
        date of account quarantines.
    """
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    for row in ac.list_entity_quarantines(entity_types=co.entity_account,
                                          quarantine_types=q_types,
                                          only_active=False):
        yield (row['entity_id'], date_compat.get_date(row['start_date']))


def make_account_name_lookup(db):
    """
    :return callable:
        Returns a function that maps account entity ids to account names.
    """
    ac = Factory.get('Account')(db)
    logger.debug("caching account names...")
    cache = {row['account_id']: row['name']
             for row in ac.search(expire_start=None)}
    logger.debug("done caching account names")

    def get_account_name(entity_id):
        if entity_id in cache:
            return cache[entity_id]
        return '<id:{:d}>'.format(entity_id)

    return get_account_name


def make_spread_filter(db):
    """
    :return callable:
        Returns a function that returns ``True`` iff the given account entity
        id has spreads.
    """
    es = EntitySpread(db)
    co = Factory.get('Constants')(db)
    logger.debug("caching spreads...")
    cache = set(
        entity_id
        for entity_id, spread_code
        in es.list_all_with_spread(entity_types=co.entity_account))
    logger.debug("done caching spreads")
    return (lambda entity_id: entity_id in cache)


def make_date_filter(start, end):
    """
    :type start: datetime.date or None
    :type end: datetime.date or None

    :return callable:
        Returns a function that returns ``True`` iff the given datetime is
        within the given interval of dates.
    """
    def filter_date(date_obj):
        if start and date_obj < start:
            return False
        if end and date_obj > end:
            return False
        return True
    return filter_date


def get_quarantined(db, start, end, q_types):
    """ get the account name of active, quarantined accounts.

    An account is 'active' if it is not deleted or expired (i.e. has spreads)

    :return generator:
        Returns a generator that yields account names.
    """
    get_account_name = make_account_name_lookup(db)
    is_active = make_date_filter(start, end)
    has_spread = make_spread_filter(db)

    for account_id, quar_date in iter_account_quarantines(db, q_types=q_types):
        if not has_spread(account_id):
            continue
        if not is_active(quar_date):
            continue
        account_name = get_account_name(account_id)
        yield account_name


def get_template(filename, encoding='utf-8'):
    """ Get email message template from file.

    The template must include all the neccessary headers, including Subject,
    From and To.

    :rtype: email.message.Message
    """
    with io.open(filename, mode='r', encoding=encoding) as f:
        return email.message_from_file(f)


def prepare_report(template, account_names, charset=EMAIL_CHARSET):
    """ Insert account name list into email template body.

    This replaces the text '${REPORT}' with a list of account names in the
    email body.

    :param email.message.Message template:
        The template to process. NOTE: The template is modified in-place.

    :param list account_names:
        A list of account names to insert into the email body.

    :return email.message.Message:
        The same message object that is passed into this function.
    """

    body = template.get_payload()
    body = body.replace('${REPORT}', '\n'.join(account_names))
    template.set_payload(body)
    template.set_charset(charset)
    return template


def days_ago_date_type(value):
    days = abs(int(value))
    return datetime.date.today() - datetime.timedelta(days=days)


description = """
Generate a list of active users with quarantines of a given age.
""".strip()

epilog = """
Examples:

  Generate a list of obsolete users, quarantined with "auto_no_aff" or
  "auto_inaktiv" for at least 30 days:

      quarantine_users_report.py -b 30 -q auto_no_aff -q auto_inaktiv -o -

  Generate a list of users recently quarantined with "autopassord":

      quarantine_users_report.py -a 30 -q autopassord -o -

  Generate a list of all quarantines from the last week, and send by mail:

      quarantine_users_report.py -a 7 --mail /path/to/email-template.txt
      quarantine_users_report.py -a 7 --mail <(cat <<"EOF"
      To: example@example.org
      From: noreply@example.org
      Subject: Some quarantines here

      Here are some users with new quarantines:
      ${REPORT}
      EOF
      )
""".lstrip()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description,
        epilog=epilog,
    )
    parser.add_argument(
        '-d', '--dryrun',
        action='store_true',
        default=False,
        help="dryrun, don't send mail even if an email template is supplied",
    )

    select_group = parser.add_argument_group(
        "Selection",
        textwrap.dedent(
            """
            Quarantine selection parameters.

            Select whether to include quarantines started before or after a
            given date with `--before` / `--after` (required).

            Select one or more quarantines with the `--quarantine` argument.
            If no quarantines are given, all quarantines will be considered.
            """
        ).strip(),
    )
    # TODO: Rework so that *both* before and after can be used
    date_arg = select_group.add_mutually_exclusive_group(required=True)
    date_arg.add_argument(
        '-a', '--after',
        type=days_ago_date_type,
        help='report quarantines started after %(metavar)s days ago',
        metavar='DAYS',
    )
    date_arg.add_argument(
        '-b', '--before',
        type=days_ago_date_type,
        help='report quarantines started before %(metavar)s days ago',
        metavar='DAYS',
    )
    q_arg = select_group.add_argument(
        '-q', '--quarantine',
        dest='quarantines',
        action='append',
        default=[],
        help="only report on quarantines of this type",
    )

    report_group = parser.add_argument_group(
        "Report",
        textwrap.dedent(
            """
            Where to write or send the report (required).

            To send by email:
                `--mail` is an actual email text template, including headers
                (To, From, etc...).  The placeholder value `${REPORT}` is
                replaced by a list of quarantined account names.

            To write a file:
                `--output-file` is the name of a text file where the list of
                quarantined account names are written.  Use "-" to write to
                stdout.
            """
        ).strip(),
    )
    report_group.add_argument(
        '-m', '--mail',
        dest='template',
        help="send account list by email according to template %(metavar)s",
        metavar='FILE',
    )
    report_group.add_argument(
        '-o', '--output-file',
        dest="output_file",
        help="write account list to %(metavar)s",
        metavar="FILE",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf("cronjob", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    # extra argument sanity checks:

    if not any((args.template, args.output_file)):
        parser.error("must provide one of: --mail, --output-file")

    quarantines = [
        argutils.get_constant(db, parser, co.Quarantine, q_value, q_arg)
        for q_value in args.quarantines
    ] or None

    # fetch quarantined accounts:

    logger.info("quarantines: %r", quarantines)
    logger.info("mail template: %r", args.template)
    logger.info("after: %s", args.after)
    logger.info("before: %s", args.before)

    message = get_template(args.template) if args.template else None
    logger.debug("fetching quarantined accounts...")
    accounts = sorted(set(get_quarantined(db, args.after, args.before,
                                          q_types=quarantines)))
    logger.info("found %d quarantined accounts to report", len(accounts))

    # generate reports:

    if args.output_file:
        logger.debug("writing report to %s", args.output_file)
        with file_stream.get_output_context(args.output_file,
                                            encoding="utf-8") as f:
            for account_name in accounts:
                print(account_name, file=f)
        logger.info("wrote report to file %s", repr(f))

    if message:
        logger.debug("sending report by mail")
        prepare_report(message, accounts)
        Cerebrum.utils.email.send_message(message, debug=args.dryrun)

    logger.info('Done %s', parser.prog)


if __name__ == "__main__":
    main()
