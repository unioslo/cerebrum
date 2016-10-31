#!/usr/bin/env python
# coding: utf-8
""" Generate reports on discrepancies in authoritative data. """
from __future__ import print_function, unicode_literals

import argparse

from collections import namedtuple
from functools import partial
from xml.etree import ElementTree

from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.Utils import Factory

TEMPLATE = """
<html>
    <head>
        <meta charset="utf-8" />
        <title></title>
    </head>
    <body>
    </body>
</html>
""".strip()


Name = namedtuple('Name', ('pid', 'system', 'variant', 'value'))


def get_names(db, system, variant, pid=None):
    """ Fetch names. """
    co = Factory.get(b'Constants')(db)
    pe = Factory.get(b'Person')(db)

    for row in pe.search_person_names(
            source_system=system,
            name_variant=variant,
            person_id=pid):
        yield Name(
            row['person_id'],
            co.AuthoritativeSystem(row['source_system']),
            co.PersonName(row['name_variant']),
            row['name'].decode(db.encoding, 'replace'))


def compare_names(db, logger, args):
    """ Generates an XML report for missing names. """
    co = Factory.get(b'Constants')(db)
    pe = Factory.get(b'Person')(db)
    variants = [co.PersonName(t[0]) for t in pe.list_person_name_codes()]

    logger.debug("Fetching names from {!s}".format(args.check_system))
    to_check = dict()
    for name in get_names(db, args.check_system, variants):
        to_check.setdefault(name.pid, dict())[name.variant] = name

    logger.debug("Fetching names for {:d} persons from {!s}".format(
        len(to_check), args.source_system))
    diff = dict()
    for name in get_names(
            db, args.source_system, variants, pid=to_check.keys()):
        if name.variant not in to_check[name.pid]:
            continue
        if to_check[name.pid][name.variant].value != name.value:
            diff.setdefault(name.pid, []).append(
                (name, to_check[name.pid][name.variant]))

    logger.debug("Generating report ({:d} names)".format(len(diff)))
    report = generate_report('Names', diff)
    logger.debug("Done generating report")
    return report


def generate_report(title, data):
    """ Generate a HTML document from a dict.

    :param str title:
        The report title.
    :param dict data:
        A dict that maps entity_id to a list of tuples. Each tuple contains two
        mismatched names: {int: [ (Name, Name), ..., ], ... }

    :return xml.etree.ElementTree.Element:
        Returns a 'html' element with the report.
    """
    document = ElementTree.fromstring(TEMPLATE)
    document.find('head/title').text = title
    table = ElementTree.SubElement(document.find('body'), 'table')

    def make_row(col, cols):
        tr = ElementTree.Element('tr')
        for c in cols:
            if not isinstance(c, basestring):
                c = str(c)
            if not isinstance(c, unicode):
                c = unicode(c)
            cc = ElementTree.Element(col)
            cc.text = c
            tr.append(cc)
        return tr

    table.append(
        make_row('th', ('entity', 'name type', 'sys', 'name', 'sys', 'name')))

    for pid, diffs in data.iteritems():
        for source, diff in diffs:
            table.append(
                make_row('td', (
                    source.pid,
                    source.variant,
                    source.system,
                    source.value,
                    diff.system,
                    diff.value)))

    return document


def get_const(db, const_type, const_val):
    u""" Gets a constant by value. """
    if isinstance(const_val, const_type):
        return const_val
    const = Factory.get('Constants')(db)
    value = const.human2constant(const_val, const_type)
    if value is None:
        raise ValueError(
            'Invalid {!s} {!r}'.format(const_type.__name__, const_val))
    return value


def argparse_const(db, const_type, const_val):
    u""" Get a constant from argument. """
    try:
        return get_const(db, const_type, const_val)
    except ValueError as e:
        raise argparse.ArgumentTypeError(e)


def main(args=None):
    ENCODING = 'utf-8'
    logger = Factory.get_logger('cronjob')
    db = Factory.get(b'Database')()
    co = Factory.get(b'Constants')(db)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--output', default='/tmp/report.html')
    commands = parser.add_subparsers(help="available commands")

    # name
    name_command = commands.add_parser(
        'name',
        help="Generate report on differences in names.")
    name_command.set_defaults(func=compare_names)
    name_command.set_defaults(check_system=co.system_sap)
    name_command.add_argument(
        'source_system',
        type=partial(argparse_const, db, co.AuthoritativeSystem))

    args = parser.parse_args(args)
    command = args.func
    del args.func

    # Other commands?
    logger.info('Generating report ({!s})'.format(args.output))
    af = AtomicFileWriter(args.output)

    report = command(db, logger, args)
    report.find('head/meta[@charset]').set('charset', ENCODING)
    af.write("<!DOCTYPE html>\n")
    af.write(ElementTree.tostring(report, encoding=ENCODING))

    af.close()
    logger.info('Done')


if __name__ == '__main__':
    main()
