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
from __future__ import unicode_literals

import io
import logging
import os
import sys
import getopt
import mx.DateTime

import cereconf

from Cerebrum.Utils import read_password

logger = logging.getLogger(__name__)


class SYSX(object):
    _default_datafile = os.path.join(cereconf.DUMPDIR, 'system-x',
                                     'guest_data')
    _guest_host = cereconf.GUEST_HOST
    _guest_host_dir = cereconf.GUEST_HOST_DIR
    _guest_host_file = cereconf.GUEST_HOST
    # Dummy username as password is a api key
    _guest_host_auth = "?auth={}".format(
        read_password('systemx', cereconf.GUEST_HOST))
    _guest_file = cereconf.GUEST_FILE
    today = str(mx.DateTime.today())

    sysxids = {}
    sysxfnrs = {}
    SPLIT_CHAR = ':'

    def __init__(self, data_file=None, update=False):
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

    def load_sysx_data(self):
        data = []
        file_handle = io.open(self.sysx_data, "r", encoding="utf-8")
        lines = file_handle.readlines()
        file_handle.close()
        for line in lines:
            line = line.rstrip()
            # line = line.decode("UTF-8")
            if not line or line.startswith('#'):
                continue
            # line = line.decode("UTF-8")
            data.append(line)
        return data

    def _prepare_data(self, data_list):
        data_list = data_list.rstrip()
        try:
            (id, fodsels_dato, personnr, gender, fornavn, etternavn, ou,
             affiliation, affiliation_status, expire_date, spreads,
             hjemmel, kontaktinfo, ansvarlig_epost, bruker_epost,
             national_id, approved) = data_list.split(self.SPLIT_CHAR)
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
            return {'id': id,
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
        for item in self.load_sysx_data():
            sysx_data = self._prepare_data(item)
            if filter_expired:
                if sysx_data['expire_date'] < self.today:
                    continue
            self.sysxids[sysx_data['id']] = sysx_data
            if sysx_data['personnr']:
                self.sysxfnrs[sysx_data['personnr']] = sysx_data


def usage():
    print(__doc__)


def main():
    do_update = False
    filter_expired = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'uhf',
                                   ['update', 'help', 'filter_expired'])
    except getopt.GetoptError as m:
        print("Unknown option: {}".format(m))
        usage()

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-u', '--update'):
            do_update = True
        elif opt in ('-f', '--filter_expired'):
            filter_expired = True

    sysx = SYSX(update=do_update)
    sysx.list(filter_expired=filter_expired)
    print("SYS_IDs: {}".format(len(sysx.sysxids)))
    print("SYS_Fnrs: {}".format(len(sysx.sysxfnrs)))


if __name__ == '__main__':
    main()
