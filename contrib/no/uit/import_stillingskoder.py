#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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

import csv
import getopt
import os
import sys

import cereconf

from Cerebrum.Utils import Factory

progname = __file__.split("/")[-1]
__doc__ = """

    This program reads a csv file containing 3 fields:
    Stillingskode,Stillingsbetegnelse;stillingskategori
    Content of this file is synced with table person_stillingskoder in Cerebrum

    Usage:
    %s [options]
    options:
    -h|--help                : Show this message
    -k|--kodefile filename   : Use this file as input file instead of default
    -d|--dryrun              : dryrun
    --logger-name name       : Use specified logger name
    --logger-level name      : Use specified log level

    """ % (progname,)

logger = Factory.get_logger('console')
db = Factory.get('Database')()
CHARSEP = ';'
default_file = os.path.join(cereconf.CB_SOURCEDATA_PATH, 'stillingskoder.csv')


def parse_source_file(filename):
    result = dict()
    for detail in csv.DictReader(open(filename, 'r'), delimiter=CHARSEP):
        stbnv = detail['Stillingsbetegnelse']
        stkat = detail['UiT Stillingskategori']
        result[int(detail['Stillingskode'])] = (stbnv, stkat)
    logger.info("Loaded sourcefile %s, found %d kodes", filename, len(result))
    return result


class Stillingskoder(object):

    def __init__(self, db):
        self.db = db

    def insert(self, skode, sbeneving, skategori):
        qry = """
        INSERT INTO
            [:table schema = cerebrum name = person_stillingskoder]
            (stillingskode, stillingstittel, stillingstype)
        VALUES
            (:skode, :sbeneving, :skategori)
        """
        params = {
            'skode': skode,
            'skategori': skategori,
            'sbeneving': sbeneving,
        }
        self.db.execute(qry, params)

    def delete(self, skode):
        qry = """
        DELETE
        FROM
            [:table schema = cerebrum name = person_stillingskoder]
        WHERE
            stillingskode = :skode
        """
        self.db.execute(qry, {'skode': skode})

    def update(self, skode, sbeneving, skategori):
        qry = """
        UPDATE
            [:table schema = cerebrum name = person_stillingskoder]
        SET
            stillingstype = :skategori, stillingstittel = :sbeneving
        WHERE
            stillingskode = :skode
        """
        params = {
            'skode': skode,
            'skategori': skategori,
            'sbeneving': sbeneving,
        }
        self.db.execute(qry, params)

    def list_stillingskoder(self, skode=None, skat=None):
        filter = []
        params = dict()

        if skode:
            filter.append('skode = :skode')
            params['skode'] = skode

        if skat:
            filter.append('stillingstype = :skat')
            params['skat'] = skat

        where = ""
        if filter:
            where = "WHERE %s" % (" AND ".join(filter))

        qry = """
        SELECT
            stillingskode, stillingstittel, stillingstype
        FROM
            [:table schema = cerebrum name = person_stillingskoder]
        %s
        """ % where
        return self.db.query(qry, {'skode': skode})


def sync_skoder(current, new):

    current_set = set(current.keys())
    new_set = set(new.keys())

    to_add = new_set.difference(current_set)
    to_delete = current_set.difference(new_set)
    to_update = new_set.intersection(current_set)

    # add new
    for skode in to_add:
        sben, skat = new.get(skode)
        logger.info("Insert new stillingskode=%04d, tittel=%r, type=%r",
                    skode, sben, skat)
        skode_obj.insert(skode, sben, skat)

    # remove old
    for skode in to_delete:
        logger.info("Delete stillingskode=%04d", skode)
        skode_obj.delete(skode)

    # update remaining
    updated = False
    for skode in to_update:
        new_sben, new_skat = new.get(skode)
        old_sben, old_skat = current.get(skode)
        if new_sben != old_sben or new_skat != old_skat:
            updated += 1
            logger.info("Update stillingskode = %04d, new=%r, old=%r",
                        skode, (new_sben, new_skat), (old_sben, old_skat))
            new_sben = unicode(new_sben, 'utf-8').encode('iso-8859-1')
            new_skat = unicode(new_skat, 'utf-8').encode('iso-8859-1')
            skode_obj.update(skode, new_sben, new_skat)
    if to_add or to_delete or updated:
        logger.info("Added %d kodes, removed %d kodes and updated %d kodes",
                    len(to_add), len(to_delete), updated)


def usage(exit_code=0, msg=None):
    if msg:
        print msg
    print __doc__
    sys.exit(exit_code)


def main():
    global skode_obj

    # lets set default file
    kode_file = default_file
    dryrun = False
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'k:hd',
            ['kodefile = ', 'help', 'dryrun'])
    except getopt.GetoptError as m:
        usage(1, m)

    for opt, val in opts:
        if opt in ('-k', '--kodefile'):
            kode_file = val
        elif opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            dryrun = True

    skode_obj = Stillingskoder(db)
    new_skode = parse_source_file(kode_file)
    current_skode = dict()
    for skode, sbeneving, skat in skode_obj.list_stillingskoder():
        def _utf_name(name, encoding='iso-8859-1'):
            return unicode(name, encoding).encode('utf-8')
        current_skode[int(skode)] = (_utf_name(sbeneving),
                                     _utf_name(skat))

    sync_skoder(current_skode, new_skode)

    if dryrun:
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


if __name__ == '__main__':
    main()
