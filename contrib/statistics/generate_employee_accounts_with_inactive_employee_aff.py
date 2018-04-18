#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017-2018 University of Oslo, Norway
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

from __future__ import unicode_literals, absolute_import

import argparse
import codecs
import datetime
import logging
import sys

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)
now = datetime.datetime.now


# TODO: Move to actual template, or at least use a base template
template = """
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>Employee accounts with an inactive ANSATT affiliation</title>
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
        width: 100%%;
        text-align: left;
      }
      table thead {
        border-bottom: solid gray 1px;
      }
      table th, table td {
        padding: .5em 1em;
        width: 10%%;
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
      {{ mismatch | length }} account(s) with mismatching affiliations
    </p>

    <h3>Employee accounts with an inactive ANSATT affiliation</h3>
    <p>
      This report find accounts with at least one ANSATT affiliation and checks
      whether it's still valid.
    </p>
    <p>
      Accounts owned by a person with no affiliations of any kind are
      ignored.
    </p>

    <table>
      <thead>
        <tr>
          <th>Person entity id</th>
          <th>Account name</th>
          <th>Account types</th>
          <th>Person affiliations</th>
          <th>Account ANSATT affs missing from person</th>
        </tr>
      </thead>

      {% for item in mismatch %}
      <tr>
        <td>{{ item['person_id'] }}</td>
        <td>{{ item['account_name'] }}</td>
        <td>{{ item['account_types'] }}</td>
        <td>{{ item['person_affiliations'] }}</td>
        <td>{{ item['mismatch'] }}</td>
      </tr>
      {% endfor %}
    </table>

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


def make_aff_lookup(db):
    pe = Factory.get(b'Person')(db)

    @memoize
    def aff_lookup(person_id):
        pe.clear()
        pe.find(person_id)
        return tuple((
            (row['affiliation'], row['ou_id'])
            for row in pe.get_affiliations()))
    return aff_lookup


def make_sko_lookup(db):
    ou = Factory.get(b'OU')(db)

    @memoize
    def sko_lookup(ou_id):
        ou.clear()
        ou.find(ou_id)
        return "{:02d}{:02d}{:02d}".format(ou.fakultet,
                                           ou.institutt,
                                           ou.avdeling)
    return sko_lookup


def get_mismatches(db):
    co = Factory.get(b'Constants')(db)
    ac = Factory.get(b'Account')(db)

    sko_lookup = make_sko_lookup(db)
    aff_lookup = make_aff_lookup(db)
    processed_accounts = set()

    def format_affs(affiliation_list):
        return ', '.join(
            "{}@{}".format(text_type(co.PersonAffiliation(aff)),
                           sko_lookup(ou_id))
            for aff, ou_id in affiliation_list)

    logger.debug('listing account types...')
    accounts = ac.list_accounts_by_type(affiliation=co.affiliation_ansatt)
    logger.debug('... %d account types to consider', len(accounts))

    stats = {
        'duplicate': 0,
        'no-affiliation': 0,
        'no-mismatch': 0,
        'mismatch': 0,
    }

    logger.debug('checking account types ...')
    for i, acc in enumerate(accounts):

        if i and i % 1000 == 0:
            logger.debug('... checked %d account types ...', i)

        if acc['account_id'] in processed_accounts:
            stats['duplicate'] += 1
            continue

        pe_affs = aff_lookup(acc['person_id'])
        if not pe_affs:
            stats['no-affiliation'] += 1
            continue

        ac.clear()
        ac.find(acc['account_id'])
        ac_types = tuple((
            (row['affiliation'], row['ou_id'])
            for row in ac.get_account_types()
            if row['affiliation'] == co.affiliation_ansatt))

        mismatch = [row for row in ac_types if row not in pe_affs]
        if not mismatch:
            stats['no-mismatch'] += 1
            continue

        yield {
            'account_name': ac.account_name.decode(db.encoding),
            'person_id': ac.owner_id,
            'account_types': format_affs(ac_types),
            'person_affiliations': format_affs(pe_affs),
            'mismatch': format_affs(mismatch),
        }
        processed_accounts.add(ac.entity_id)
        stats['mismatch'] += 1
    logger.debug('... done checking accounts')
    logger.debug('stats: %r', stats)


def write_html_report(stream, codec, mismatch):
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    output = codec.streamwriter(stream)
    output.write(report.render({
        'encoding': codec.name,
        'when': now().strftime('%Y-%m-%d %H:%M:%S'),
        'mismatch': mismatch,
    }))
    output.write("\n")


def codec_type(encoding):
    try:
        return codecs.lookup(encoding)
    except LookupError as e:
        raise ValueError(str(e))


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get(b'Database')()

    accounts = sorted(get_mismatches(db),
                      key=lambda x: (x['person_id'],
                                     x['account_name']))
    logger.info('Found %d accounts with mismatches', len(accounts))

    write_html_report(args.output, args.codec, accounts)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
