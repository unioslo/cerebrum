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
"""Generate an HTML or CSV report with employees on student disks.

This program reports users with employee affiliations, with a homedir on disks
tagged as student disks.

The following functions are defined:

  main():
    Initializes database connections, parses command line parameters
    and starts other functions to collect data and generate a report.

  get_empl_on_student_disks():

  gen_employees_on_student_disk_report():
    Generate HTML report with the accounts found. This function can sort
    the result by SKO-code or by disk. Disk is the default.

Overall flow of execution looks like:

  main():
    - Initializes database connections
    - Parses command line options
    - Starts 'get_empl_on_student_disks()'
    - Starts 'gen_employees_on_student_disk_report()'
    - Closes filehandle, then exits

  get_empl_on_student_disks():

  gen_affles_users_report():
    - Prints out the HTML preamble via the preamble() function
    - For each disk (or SKO) in our data structure:

      - Generate a table header
      - Loop over the accounts associated with the SKO or disk, and print
        rows of information.
"""
import argparse
import datetime
import logging
import sys

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.utils.argutils import codec_type, get_constant
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)
now = datetime.datetime.now


template = u"""
{# HTML template for 'generate_accounts_without_affiliations.py'
 # Note: this template requires a custom filter, sort_by_quarantine
-#}
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>Pure employees on student disks</title>
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
      {{ num_accounts }} account(s) with ANSATT affiliation on student disks
    </p>
    {% set fields = order
        | default([
            'username', 'full_name', 'affiliation', 'disk', 'sko',
            'q_type', 'q_desc', 'q_date'])
        | reject('equalto', key)
        | list %}
    {% set headers = {
        'username': 'Username',
        'full_name': 'Full name',
        'affiliation': 'Affiliation',
        'disk': 'Disk path',
        'sko': 'OU',
        'q_type': 'Quarantine type',
        'q_desc': 'Quarantine description',
        'q_date': 'Quarantine start date'} %}

    {% for group in groups | sort %}
    <h2>{{ group }}</h2>
    <table>
      <thead>
        <tr>
          {% for f in fields %}
          <th>{{ headers[f] }}</th>
          {% endfor %}
        </tr>
      </thead>
      {% for user in groups[group] | sort_by_quarantine %}
      <tr>
        {% for f in fields %}
        <td>{{ user[f] }}</td>
        {% endfor %}
      </tr>
      {% endfor %}
    </table>

    {% endfor %}

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
        return tuple(pe.get_affiliations())
    return aff_lookup


def get_student_disks(db):
    et = EntityTrait(db)
    co = Factory.get('Constants')(db)
    return set((
        t['entity_id']
        for t in et.list_traits(code=co.trait_student_disk)))


class OuCache(object):
    def __init__(self, db):
        co = Factory.get('Constants')(db)
        ou = Factory.get('OU')(db)

        self._ou2sko = dict(
            (row['ou_id'], ("%02d%02d%02d" % (row['fakultet'],
                                              row['institutt'],
                                              row['avdeling'])))
            for row in ou.get_stedkoder())

        self._ou2name = dict(
            (row['entity_id'], row['name'])
            for row in ou.search_name_with_language(
                name_variant=co.ou_name_display,
                name_language=co.language_nb))

    def get_sko(self, ou_id):
        return self._ou2sko[ou_id]

    def get_name(self, ou_id):
        return self._ou2name[ou_id]


# This function searches each student-disk for accounts that
# are owned by persons that are not students, only employees.
def get_empl_on_student_disks(db, spread, key='sko'):
    """ Find employee users on student disks.

    This function searches the database for accounts residing on disks
    that have the 'student_disk' trait set, while the accounts are owned
    by a person with an ansatt-affiliation, but without a student-
    affiliation.
    """

    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    di = Factory.get('Disk')(db)
    co = Factory.get('Constants')(db)

    def _u(db_value):
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return db_value

    def _row_to_quar(row):
        """ list_entity_quarantines row to dict """
        return {
            'q_type': text_type(co.Quarantine(row['quarantine_type'])),
            'q_desc': _u(row['description']),
            'q_date': text_type(row['start_date'].strftime('%Y-%m-%d')),
        }

    aff_lookup = make_aff_lookup(db)

    # Variables to store results from "search"
    # 'empl_on_stud_disk' are employees (only employee affilation) that are
    # located on a student disk.
    #
    # The variable uses the SKO-code as a key, and the corresponding value
    # is a list of dict's containing info about each user.
    report = {}

    stats = {'disk': 0, 'user': 0}

    logger.debug('listing student disks ...')
    student_disks = get_student_disks(db)
    logger.debug('... got %d disk ids', len(student_disks))

    logger.debug('caching ou data ...')
    ou_cache = OuCache(db)
    logger.debug('... done caching ous')

    # Getting a list of all disks, and iterating over it
    for d in di.list():
        # We collect the entity of the disk, need this to check the
        # disk traits (if it is a student disk). We also check the
        # spread of the disk, we'll only want NIS_user@uio.
        if d['spread'] != spread:
            continue

        if d['disk_id'] not in student_disks:
            continue

        stats['disk'] += 1

        # For each of the users on the disk (filtered on spread,
        # we don't want duplicates (i.e., if a user has NIS_user@uio
        # and NIS_user@ifi, it would show up two times (or four,
        # if we don't filter the stuff from di.list))).
        users = ac.list_account_home(disk_id=d['disk_id'],
                                     home_spread=spread)
        stats['user'] += len(users)

        # Look up each of the accounts on the disk, and determine if it
        # is owned by a person or a group (we only process accounts
        # owned by persons). Add them to report if appropriate.
        for u in users:
            ac.clear()

            # Lookup user and person
            try:
                ac.find(u['account_id'])
            except Errors.NotFoundError:
                logger.error("Can't find account_id = %d",
                             u['account_id'])
                continue

            # Some accounts are not personal (i.e, owned by group),
            # we'll exclude these. We'll lookup the entity of the
            # accounts owner, and check to see if this entity is a
            # person.
            if ac.owner_type != co.entity_person:
                continue

            # Checking if this person is ansatt, and not student
            affs = aff_lookup(ac.owner_id)
            if not affs or any(a['affiliation'] != co.affiliation_ansatt
                               for a in affs):
                # is not employee-only (no affs, or student/tilknyttet)
                continue

            tmp = {
                'username': _u(ac.account_name),
                'full_name': _u(ac.get_fullname()),
                'affiliation': text_type(
                    co.PersonAffStatus(affs[0]['status'])),
                'disk': _u(d['path']),
                'sko': ' - '.join((_u(ou_cache.get_sko(affs[0]['ou_id'])),
                                   _u(ou_cache.get_name(affs[0]['ou_id'])))),
                'q_type': '',
                'q_desc': '',
                'q_date': '',
            }

            quar = ac.get_entity_quarantine(only_active=True)
            if quar:
                tmp.update(_row_to_quar(quar[0]))

            report.setdefault(tmp[key], []).append(tmp)

    logger.debug('%(disk)d disks and %(user)d accounts checked', stats)
    logger.info('%d employees on student disks',
                sum(len(v) for v in report.values()))
    return report


def do_sort_by_quarantine(l):
    """ Sort by 'has quarantine'. """
    return sorted(l, cmp=lambda a, b: cmp(bool(a['q_type']),
                                          bool(b['q_type'])))


def write_report_file(stream, codec, data, key):
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    template_env.filters['sort_by_quarantine'] = do_sort_by_quarantine
    report = template_env.from_string(template)

    number_of_users = sum(len(v) for v in data.values())
    output.write(
        report.render({
            'encoding': codec.name,
            'groups': data,
            'key': key,
            'num_accounts': number_of_users,
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    )
    output.write('\n')


DEFAULT_SPREAD = 'NIS_user@uio'
DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='the file to print the report to, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        type=codec_type,
        default=DEFAULT_ENCODING,
        help="output file encoding, defaults to %(default)s")
    parser.add_argument(
        '-a', '--arrange-by',
        dest='sort_by',
        choices=['disk', 'sko'],
        default='sko',
        help='arrange report by diskname or sko, defaults to %(default)s')
    spread_arg = parser.add_argument(
        '-s', '--spread',
        default=DEFAULT_SPREAD,
        metavar='SPREAD',
        help='Spread to filter users by. Defaults to %(default)s')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    # Initialization of database connection
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    spread = get_constant(db, parser, co.Spread, args.spread, spread_arg)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.info("spread: %s", text_type(spread))

    # Collect the data
    empl_on_stud_disk = get_empl_on_student_disks(db, spread, args.sort_by)

    # Print the HTML-report
    write_report_file(args.output, args.codec, empl_on_stud_disk, args.sort_by)

    args.output.flush()

    # If the output is being written to file, close the filehandle
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
