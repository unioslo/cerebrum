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
import logging
import sys

import cereconf
import mx.DateTime
from Cerebrum.Utils import read_password
from Cerebrum.utils import csvutils

logger = logging.getLogger(__name__)


class SYSX(object):
    def __init__(self, data_file=None, update=False):
        self._default_datafile = cereconf.GUEST_FILE
        if update:
            # Dummy username as password is a api key
            self._guest_host = cereconf.GUEST_HOST
            self._guest_host_dir = cereconf.GUEST_HOST_DIR
            self._guest_host_file = cereconf.GUEST_HOST_FILE
            self._guest_host_auth = "?auth={}".format(
                read_password('systemx', cereconf.GUEST_HOST))
        self.today = str(mx.DateTime.today())

        self.sysxids = {}
        self.sysxfnrs = {}
        self.SPLIT_CHAR = ':'

        if data_file:
            self.sysx_data = data_file
        else:
            self.sysx_data = self._default_datafile

        if update:
            self._update()

    def read_from_sysx(self):
        url = "http://{}{}{}{}".format(
            self._guest_host,
            self._guest_host_dir,
            self._guest_host_file,
            self._guest_host_auth)
        target_file = self.sysx_data
        try:
            import urllib
            fname, headers = urllib.urlretrieve(url, target_file)
        except Exception as m:
            print("Failed to get data from {0}: reason: {1}".format(url, m))
            return 0
        else:
            return 1

    def _prepare_data(self, data_list):
        """
        Take in a list of lists, where the inner lists contain strings in order
        sysx_id, fodsels_dato, personnr, gender, fornavn, etternavn, ou,
        affiliation, affiliation_status, expire_date, spreads, hjemmel,
        kontaktinfo, ansvarlig_epost, bruker_epost, national_id, approved

        :param list data_list: list of strings in order sysx_id, fodsels_dato,
            personnr, gender, fornavn, etternavn, ou, affiliation,
            affiliation_status, expire_date, spreads, hjemmel, kontaktinfo,
            ansvarlig_epost, bruker_epost, national_id, approved
        :return: dict with the same information pre-processed
        """
        try:
            (sysx_id, fodsels_dato, personnr, gender, fornavn, etternavn, ou,
             affiliation, affiliation_status, expire_date, spreads,
             hjemmel, kontaktinfo, ansvarlig_epost, bruker_epost,
             national_id, approved) = data_list
        except ValueError as m:
            logger.error("data_list:%s##%s", data_list, m)
            sys.exit(1)
        else:

            def fixname(name):
                # Cerebrum populate expects iso-8859-1.
                return name.strip()

            # Fix for people placed on top OU
            if ou == '0':
                ou = '000000'

            if spreads:
                spreads = spreads.split(',')
            else:
                spreads = []
            return {'id': sysx_id,
                    'fodsels_dato': fodsels_dato,
                    'personnr': personnr,
                    'gender': gender,
                    'fornavn': fixname(fornavn.strip()),
                    'etternavn': fixname(etternavn.strip()),
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
                    'hjemmel': hjemmel}

    def _update(self):
        return self.read_from_sysx()

    def list(self, filter_expired=True, filter_approved=False):
        self._load_data(filter_expired=filter_expired)

    def _load_data(self, update=False, filter_expired=True):
        if update:
            self._update()
        for item in csvutils.read_csv_tuples(
                self.sysx_data, 'utf-8', self.SPLIT_CHAR):
            sysx_data = self._prepare_data(item)
            if filter_expired:
                if sysx_data['expire_date'] < self.today:
                    continue
            self.sysxids[sysx_data['id']] = sysx_data
            if sysx_data['personnr']:
                self.sysxfnrs[sysx_data['personnr']] = sysx_data


def main(inargs=None):
    """Function used for testing the module

    """
    # Parse arguments
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('-u', '--update',
                        action='store_true',
                        help='',
                        default=False)
    parser.add_argument('-f', '--filter_expired',
                        action='store_true',
                        help='',
                        default=False)
    parser.add_argument('-d', '--datafile',
                        default=cereconf.GUEST_FILE,
                        help='Path to to guest file.')
    args = parser.parse_args(inargs)

    sysx = SYSX(data_file=args.datafile, update=args.update)
    sysx.list(filter_expired=args.filter_expired)
    print("SYS_IDs: {}".format(len(sysx.sysxids)))
    print("SYS_Fnrs: {}".format(len(sysx.sysxfnrs)))


if __name__ == '__main__':
    main()
