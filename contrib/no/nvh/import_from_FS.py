#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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
The script that imports the data from NVH's FS. The data is put into XML-files
to be further processed by other jobs.
"""

import re
import sys
import getopt
from os.path import join as pj, isabs

import cerebrum_path
import cereconf
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import XMLHelper, MinimumSizeWriter, AtomicFileWriter
from Cerebrum.modules.no.nvh.access_FS import FS
from Cerebrum.Utils import Factory

xml = XMLHelper()
fs = None

def _ext_cols(db_rows):
    # TBD: One might consider letting xmlify_dbrow handle this
    cols = None
    if db_rows:
        cols = list(db_rows[0].keys())
    return cols, db_rows


def write_ou_info(outfile):
    """Lager fil med informasjon om alle OU-er"""
    f = MinimumSizeWriter(outfile)
    f.set_minimum_size_limit(0)
    f.write(xml.xml_hdr + "<data>\n")
    cols, ouer = _ext_cols(fs.info.list_ou(cereconf.DEFAULT_INSTITUSJONSNR)) 
    for o in ouer:
        sted = {}
        for fs_col, xml_attr in (
            ('faknr', 'fakultetnr'),
            ('instituttnr', 'instituttnr'),
            ('gruppenr', 'gruppenr'),
            ('stedakronym', 'akronym'),
            ('stedakronym', 'forkstednavn'),
            ('stednavn_bokmal', 'stednavn'),
            ('stedkode_konv', 'stedkode_konv'),
            ('faknr_org_under', 'fakultetnr_for_org_sted'),
            ('instituttnr_org_under', 'instituttnr_for_org_sted'),
            ('gruppenr_org_under', 'gruppenr_for_org_sted'),
            ('adrlin1', 'adresselinje1_intern_adr'),
            ('adrlin2', 'adresselinje2_intern_adr'),
            ('postnr', 'poststednr_intern_adr'),
            ('adrlin1_besok', 'adresselinje1_besok_adr'),
            ('adrlin2_besok', 'adresselinje2_besok_adr'),
            ('postnr_besok', 'poststednr_besok_adr')):
            if o[fs_col] is not None:
                sted[xml_attr] = xml.escape_xml_attr(o[fs_col])
        komm = []
        for fs_col, typekode in (
            ('telefonnr', 'EKSTRA TLF'),
            ('faxnr', 'FAX'),
            ('emailadresse','EMAIL'),
            ('url', 'URL')):
            if o[fs_col]:               # Skip NULLs and empty strings
                komm.append({'kommtypekode': xml.escape_xml_attr(typekode),
                             'kommnrverdi': xml.escape_xml_attr(o[fs_col])})
        # TODO: Kolonnene 'url' og 'bibsysbeststedkode' hentes ut fra
        # FS, men tas ikke med i outputen herfra.
        f.write('<sted ' +
                ' '.join(["%s=%s" % item for item in sted.items()]) +
                '>\n')
        for k in komm:
            f.write('<komm ' +
                    ' '.join(["%s=%s" % item for item in k.items()]) +
                    ' />\n')
        f.write('</sted>\n')
    f.write("</data>\n")
    f.close()

def usage(exitcode=0):
    print """Usage: [options]

    --datadir       Override the directory where all files should be put.
                    Default: see cereconf.FS_DATADIR

                    Note that the datadir can be overriden by the file path
                    options, if these are absolute paths.

    --ou-file       Override ou xml filename. If the path is relative, it will
                    be put in the datadir. Default: ou.xml.  

    --ou            Generate the OU xml file.

    -h, --help      Show this and quit.
    """
    sys.exit(exitcode)


def assert_connected():
    global fs
    if fs is None:
        fs = Factory.get('FS')()

def set_filepath(datadir, file):
    """Return the string of path to a file. If the given file path is
    relative, the datadir is used as a prefix, otherwise only the file path is
    returned."""
    if isabs(file):
        return file
    return pj(datadir, file)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                   ["ou-file=",
                    "datadir=",
                    "ou",
                    "help"])
    except getopt.GetoptError, ge:
        print ge
        usage(2)

    datadir = cereconf.FS_DATADIR
    ou_file = 'ou.xml'

    # settings
    for o, val in opts:
        if o in ('--ou-file',):
            ou_file = val
        elif o in ('--datadir',):
            datadir = val
        elif o in ('-h', '--help'):
            usage()

    assert_connected()

    # action
    for o, val in opts:
        if o in ('-o',):
            write_ou_info(set_filepath(datadir, ou_file))

if __name__ == '__main__':
    main()
