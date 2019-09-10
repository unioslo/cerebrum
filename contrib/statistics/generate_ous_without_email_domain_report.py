#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
""" Generate an HTML report on OUs without email domains.

Email domains can be configured with domain affiliations. This report will list
OUs that are not in the configuration for any email domains.
"""
import argparse
import datetime
import logging
import sys
from collections import defaultdict

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)
now = datetime.datetime.now

# TODO: Move to actual template, or at least use a base template
template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>{{ title | default('Stedkoder uten e-postdomene') }}</title>
    <style type="text/css">
      /* <![CDATA[ */
      h1 {
        margin: 1em .8em 1em .8em;
        font-size: 1.4em;
      }
      h2 {
        margin: 1.5em 1em 1em 1em;
        font-size: 1em;
      }
      table + h1 {
        margin-top: 3em;
      }
      table {
        border-collapse: collapse;
        width: 100%;
        text-align: left;
      }
      table thead {
        border-bottom: solid gray 1px;
      }
      table th, table td {
        padding: .5em 1em;
        width: 10%;
      }
      .meta {
        color: gray;
        text-align: right;
      }
      /* ]] >*/
    </style>
  </head>
  <body>
    <p class="meta">
      {{ ous | count }} OU(er) uten e-postdomene
    </p>

    <h1>Stedkoder uten e-postdomene</h1>
    <table>
      <thead>
        <tr>
          <th>Stedkode</th>
          <th>OU Entity ID</th>
          <th>Antall brukere</th>
          <th>Navn</th>
        </tr>
      </thead>

      {% for ou in ous | sort(attribute='sko') %}
      <tr>
        <td>{{ ou['sko'] }}</td>
        <td>{{ ou['id'] }}</td>
        <td>{{ ou['num_accounts'] }}</td>
        <td>{{ ou['name'] }}</td>
      </tr>
      {% endfor %}

    </table>

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


def get_report(exclude_empty):
    """Returns a list of OUs with no email domain"""

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)
    ac = Factory.get("Account")(db)
    email = Email.EmailDomain(db)
    eed = Email.EntityEmailDomain(db)

    def _u(db_value):
        if db_value is None:
            return text_type('')
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return text_type(db_value)

    # count the number of accounts in each OU
    logger.debug('caching account types ...')
    ou_to_num_accounts = defaultdict(int)
    for acc in ac.list_accounts_by_type():
        ou_to_num_accounts[acc['ou_id']] += 1

    # Map OU ids to email domain
    ou_to_domain = {}
    logger.debug('caching email domains ...')
    for dom in email.list_email_domains():
        for affs in eed.list_affiliations(domain_id=dom['domain_id']):
            ou_to_domain[affs[0]] = dom['domain_id']

    logger.debug('fetching ous ...')
    for sko in ou.get_stedkoder():
        ou_id = sko['ou_id']

        if exclude_empty and ou_id not in ou_to_num_accounts:
            continue

        if ou_id in ou_to_domain:
            continue

        ou.clear()
        ou.find(ou_id)

        # Skip if OU is in quarantine
        if len(ou.get_entity_quarantine()) > 0:
            continue

        ou_num_accounts = ou_to_num_accounts[ou_id]
        ou_name = ou.get_name_with_language(
            name_variant=co.ou_name,
            name_language=co.language_nb,
            default="")
        yield {
            'id': ou_id,
            'name': _u(ou_name),
            'sko': '%02d%02d%02d' % (sko['fakultet'],
                                     sko['institutt'],
                                     sko['avdeling']),
            'num_accounts': ou_num_accounts,
        }
    logger.debug('done fetching ous')


def write_html_report(stream, codec, ous):
    """ Write an HTML report to an open bytestream. """
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    output.write(
        report.render({
            'ous': ous,
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
            'encoding': codec.name,
        })
    )
    output.write('\n')


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='The file to print the report to, defaults to stdout')
    parser.add_argument(
        '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="Output file encoding, defaults to %(default)s")
    parser.add_argument(
        '-e', '--exclude-empty',
        dest='exclude_empty_ous',
        action='store_true',
        default=False,
        help="Exclude OUs with no affiliated users")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    ous = list(get_report(args.exclude_empty_ous))
    write_html_report(args.output, args.codec, ous)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
