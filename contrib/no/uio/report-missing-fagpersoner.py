#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2019 University of Oslo, Norway
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
Generate list of fagpersons not registered in SAP.

We want an overview of all persons with the affiliation TILKNYTTET/fagperson
from FS, but no with any affiliation registered from SAP. This is originally
requested by UiO, as fagpersons should in most cases also be registered in SAP.

Missing features:

- Might want to present if accounts are active or not
- Make use of a decent HTML writer instead of hardcoding it

History
-------
This script was previously a part of the old cerebrum_hacks repository. It was
moved into the main Cerebrum repository as it was currently in use by UiO.

The original can be found in cerebrum_hacks.git, as
'uio/generate_report_fagpersons_not_in_sap.py' at:

  commit 684a204f90bd508d34d97c562621be56cdace7dd
  Merge: 1f396ba f248bf8
  Date:   Tue Jun 11 11:08:24 2019 +0200
"""
import argparse
import codecs
import collections
import csv
import datetime
import logging
import os
import sys

import jinja2

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.csvutils import UnicodeWriter as CsvUnicodeWriter

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
    <title>{{ title | default('Users on disk without affiliations') }}</title>
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
        Antal fagpersonar totalt: {{ num_total | default('?') }} -
        Antal utan SAP-tilknytting og med konto:
        {{ num_account | default('?') }}
    </p>

    <h1>Oversikt over fagpersonar som ikkje har tilknytting frå SAP</h1>

    {% for group in data | groupby('sko') | sort(attribute='grouper') %}

    <h2>
      {{ group.grouper }} - {{ group.list[0]['ou_name'] }}
      ({{ group.list | length }} personar)
    </h2>
    <table>
      <thead>
        <tr>
          <th>entity_id</th>
          <th>Fornamn</th>
          <th>Etternamn</th>
          <th>SAP-id (ansattnr.)</th>
          <th>Kontoar</th>
        </tr>
      </thead>

      {% for p in group.list %}
      <tr>
        <td>{{ p['person_id'] }}</td>
        <td>{{ p['firstname'] }}</td>
        <td>{{ p['lastname']['type'] }}</td>
        <td>{{ p['sapid'] }}</td>
        <td>{{ p['accounts'] | join(', ') }}</td>
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


class CsvDialect(csv.excel):
    """Specifying the CSV output dialect the script uses.

    See the module `csv` for a description of the settings.

    """
    delimiter = ';'
    lineterminator = '\n'


def fetch_targets(db, stats=None):
    """Fetch all relevant fagpersons"""
    logger.debug('fetch_targets')

    if stats is None:
        stats = dict()
    stats.update({'total': 0, 'accounts': 0})

    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)

    fagpersons = set(
        row['person_id']
        for row in pe.list_affiliations(
                source_system=co.system_fs,
                affiliation=co.affiliation_tilknyttet,
                status=co.affiliation_tilknyttet_fagperson))
    logger.debug("Found %d fagpersons", len(fagpersons))

    persons_in_sap = set(
        row['person_id']
        for row in pe.list_affiliations(source_system=co.system_sap))
    targets = fagpersons - persons_in_sap
    logger.debug("Found %d fagpersons without SAP-aff", len(targets))

    pe_with_account = set(
        row['owner_id']
        for row in ac.search(owner_type=co.entity_person))
    targets.intersection_update(pe_with_account)
    logger.debug("Found %d fagpersons without SAP-aff but with account",
                 len(targets))

    stats['total'] = len(fagpersons)
    stats['accounts'] = len(targets)

    return targets


def fetch_target_info(db, targets):
    logger.debug('fetch_target_info')

    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    ou = Factory.get('OU')(db)

    # Cache data
    logger.debug('caching data...')
    ou2sko = dict(
        (row['ou_id'], "{:02}{:02}{:02}".format(row['fakultet'],
                                                row['institutt'],
                                                row['avdeling']))
        for row in ou.get_stedkoder())

    sko2name = dict(
        (ou2sko[row['entity_id']], row['name'])
        for row in ou.search_name_with_language(
                name_variant=co.ou_name_display,
                name_language=co.language_nb))

    def get_ou_data(ou_id):
        return {
            'ou_id': ou_id,
            'sko': ou2sko[ou_id],
            'ou_name': sko2name.get(ou2sko[ou_id]),
        }

    default_ou = {
        'ou_id': -1,
        'sko': '000000',
        'ou_name': None,
    }

    pe2firstname = dict(
        (row['person_id'], row['name'])
        for row in pe.search_person_names(name_variant=co.name_first))
    pe2lastname = dict(
        (row['person_id'], row['name'])
        for row in pe.search_person_names(name_variant=co.name_last))
    pe2sapid = dict(
        (row['entity_id'], row['external_id'])
        for row in pe.search_external_ids(
            source_system=co.system_sap,
            id_type=co.externalid_sap_ansattnr,
            fetchall=False))

    pe2accounts = dict()
    for row in ac.search(owner_type=co.entity_person):
        pe2accounts.setdefault(row['owner_id'], set()).add(row['name'])

    pe2fagpaff = collections.defaultdict(set)
    for row in pe.list_affiliations(
            source_system=co.system_fs,
            affiliation=co.affiliation_tilknyttet,
            status=co.affiliation_tilknyttet_fagperson):
        pe2fagpaff[row['person_id']].add(row['ou_id'])

    def get_person_data(person_id):
        """Get the person's data, if defined"""
        return {
            'person_id': person_id,
            'firstname': pe2firstname.get(person_id, '<Not set>'),
            'lastname': pe2lastname.get(person_id, '<Not set>'),
            'sapid': pe2sapid.get(person_id, '<Not set>'),
            'accounts': pe2accounts.get(person_id, ['<Ingen>']),
        }

    logger.debug('formatting data...')

    for p_id in targets:
        person_data = get_person_data(p_id)
        if p_id not in pe2fagpaff:
            yield person_data, default_ou
        for ou_id in pe2fagpaff[p_id]:
            yield person_data, get_ou_data(ou_id)


def aggregate(iterable):
    """ Organize data by ou/sko. """
    def _merge_dicts(*dicts):
        d = dict()
        for dd in dicts:
            d.update(dd)
        return d

    for person_data, ou_data in iterable:
        yield _merge_dicts(person_data, ou_data)


def write_csv_report(stream, codec, data, stats):
    """ Write a CSV report to an open bytestream. """
    logger.debug('write_csv_report')

    output = codec.streamwriter(stream)
    writer = CsvUnicodeWriter(output, dialect=CsvDialect)

    # TODO: should probably use a proper dict writer
    writer.writerow(
        ['sko', 'person_id', 'fornavn', 'etternavn', 'sap-id/ansattnr',
         'brukerkontoer'])

    for p in sorted(data, key=lambda d: d['sko']):
        p['accounts'] = ', '.join(p['accounts'])
        writer.writerow((
            p[k]
            for k in ('sko', 'person_id', 'firstname', 'lastname', 'sapid',
                      'accounts')))


def write_html_report(stream, codec, data, stats):
    """ Write an HTML report to an open bytestream. """
    logger.debug('write_html_report')
    output = codec.streamwriter(stream)
    template_env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)

    report = template_env.from_string(template)
    output.write(
        report.render({
            'data': data,
            'num_total': stats['total'],
            'num_account': stats['accounts'],
            'when': now().strftime('%Y-%m-%d %H:%M:%S'),
            'encoding': codec.name,
        })
    )
    output.write('\n')


FORMATS = {
    'csv': write_csv_report,
    'html': write_html_report,
}


def codec_type(encoding):
    try:
        return codecs.lookup(encoding)
    except LookupError as e:
        raise ValueError(str(e))


DEFAULT_ENCODING = 'latin1'
DEFAULT_FORMAT = 'csv'


description = """
Generate list of fagpersons not registered in SAP.

We want an overview of all persons with the affiliation TILKNYTTET/fagperson
from FS, but no with any affiliation registered from SAP. This is originally
requested by UiO, as fagpersons should in most cases also be registered in SAP.
""".lstrip()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '-e', '--output-encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding (default: %(default)s)",
        metavar='<encoding>',
    )
    format_arg = parser.add_argument(
        '-f', '--output-format',
        dest='format',
        choices=FORMATS.keys(),
        default=None,
        help=("output file format, will try to guess if filename is given"
              " (default:  %s" % (DEFAULT_FORMAT,)),
        metavar='<format>',
    )
    parser.add_argument(
        'output',
        type=argparse.FileType('w'),
        default='-',
        nargs='?',
        metavar='<file>',
        help='output file for the report (default: stdout)',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    if not args.format:
        if args.output in (sys.stdout, sys.stderr):
            args.format = 'csv'
        else:
            filename, filetype = os.path.splitext(args.output.name)
            args.format = filetype[1:]

    try:
        write_report = FORMATS[args.format]
    except KeyError as e:
        parser.error(str(argparse.ArgumentError(format_arg, e)))

    db = Factory.get('Database')()

    logger.info("Start generating report")
    stats = {}
    persons = fetch_targets(db, stats)
    logger.debug("stats: %r", stats)
    data = aggregate(fetch_target_info(db, persons))

    write_report(args.output, args.codec, data, stats)

    args.output.flush()

    # If the output is being written to file, close the filehandle
    if args.output is not sys.stdout:
        args.output.close()

    logger.info("Done generating report")


if __name__ == '__main__':
    main()
