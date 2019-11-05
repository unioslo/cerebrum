# -*- coding: utf-8-*-
# Copyright 2002, 2003, 2019 University of Oslo, Norway
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
Uit specific extension for Cerebrum. Read data from SystemX
"""
from __future__ import unicode_literals, print_function

import argparse
import datetime
import logging
import sys

import cereconf
import mx.DateTime
from Cerebrum.Utils import read_password
from Cerebrum.utils import csvutils

logger = logging.getLogger(__name__)


def parse_sysx_birth_date(value):
    try:
        day, mon, year = value.split('.')
        return datetime.date(int(year), int(mon), int(day))
    except ValueError:
        return None


def parse_sysx_expire_date(value):
    try:
        year, mon, day = value.split('-')
        return datetime.date(int(year), int(mon), int(day))
    except ValueError:
        return None


class SYSX(object):

    SPLIT_CHAR = ':'

    def __init__(self, data_file):
        self.sysx_data = data_file
        self.today = datetime.date.today()
        self.sysxids = {}
        self.sysxfnrs = {}

    def _prepare_data(self, data_list):
        """
        Take in a list of lists, where the inner lists contain strings in order
        sysx_id, fodsels_dato, fnr, gender, fornavn, etternavn, ou,
        affiliation, affiliation_status, expire_date, spreads, hjemmel,
        kontaktinfo, ansvarlig_epost, bruker_epost, national_id, approved

        :param data_list: iterable with data fields for one sysx person.

        :rtype: dict
        :return: dict with the same information pre-processed
        """
        try:
            (
                sysx_id,
                birth_date,
                fnr,
                gender,
                fornavn,
                etternavn,
                ou,
                affiliation,
                affiliation_status,
                expire_date,
                spreads,
                hjemmel,
                kontaktinfo,
                ansvarlig_epost,
                bruker_epost,
                national_id,
                approved,
            ) = data_list
        except ValueError as m:
            logger.error("data_list:%s##%s", data_list, m)
            raise

        # Fix for people placed on top OU
        if ou == '0':
            ou = '000000'

        birth_date = parse_sysx_birth_date(birth_date)

        expire_date = parse_sysx_expire_date(expire_date)
        if not expire_date:
            logger.warning('sysx_id=%r has no expire_date', sysx_id)

        spreads = [s.strip() for s in (spreads or '').split(',')]

        approved = (approved == 'Yes')
        if not approved:
            logger.warning('sysx_id=%r is not approved', sysx_id)

        return {
            'id': sysx_id,
            'birth_date': birth_date,
            'fnr': fnr,
            'gender': gender,
            'fornavn': fornavn.strip(),
            'etternavn': etternavn.strip(),
            'ou': ou,
            'affiliation': affiliation,
            'affiliation_status': affiliation_status.lower(),
            'expire_date': expire_date,
            'spreads': spreads,
            'ansvarlig_epost': ansvarlig_epost,
            'bruker_epost': bruker_epost,
            'national_id': national_id,
            'approved': approved,
            'kontaktinfo': kontaktinfo,
            'hjemmel': hjemmel,
        }

    def list(self, filter_expired=True):
        stats = {
            'expired': 0,
        }
        for item in csvutils.read_csv_tuples(
                self.sysx_data, 'utf-8', self.SPLIT_CHAR):
            sysx_data = self._prepare_data(item)
            sysx_id = sysx_data['id']

            expire_date = sysx_data['expire_date']

            if (not expire_date) or expire_date < self.today:
                stats['expired'] += 1
                if filter_expired:
                    logger.debug('Skipping sysx_id=%r, expire=%r',
                                 sysx_id, expire_date)
                    continue

            self.sysxids[sysx_id] = sysx_data
            if sysx_data['fnr']:
                self.sysxfnrs[sysx_data['fnr']] = sysx_data

        return self.sysxids


def main(inargs=None):
    """
    Function used for testing the module
    """
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        '-f', '--filter_expired',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        'datafile',
        help='Path to to guest file',
    )
    args = parser.parse_args(inargs)

    sysx = SYSX(data_file=args.datafile)
    sysx.list(filter_expired=args.filter_expired)
    print("SYS_IDs: {}".format(len(sysx.sysxids)))
    print("SYS_Fnrs: {}".format(len(sysx.sysxfnrs)))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
