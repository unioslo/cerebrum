#!/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

"""


import sys
import getopt
import time
import os

import cerebrum_path
import cereconf


from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit.access_SLP4 import SLP4, Stillingskode

logger=None

def update_stillingskoder(kode_list):

    skode = Stillingskode(logger)
    kodes = kode_list.keys()
    for sko in kodes:
        tittel = kode_list[sko]
        type = skode.sko2type(sko)
        skode.add_sko(sko,tittel,type)        
    skode.commit()


def usage(exit_code=0):

    extra = ""
    prog_inf = "\nThis program reads a slp4 dump file and inserts/updates Cerebrums stillingskoder found in that file\n"
    if (exit_code):
        extra = "Invalid paramater usage!\n"
        prog_inf =""

    print """%s%s    
    Usage:
    import_stillingskoder [-h | [-s file | [-l logger]]]
    options:
    -h               | --help                     : Show this message
    -s filename      | --slp4_file=filename        : Use this file as input file
    -l logger_target | --logger_name logger_target : Use this logger_target

    Without -s, todays SLP4 file from %s is used
    """ % (extra,prog_inf,cereconf.DUMPDIR)
    
    if (exit_code):
        sys.exit()


def main():
    global logger

    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]

    # lets set default file
    logger_name = cereconf.DEFAULT_LOGGER_TARGET
    slp4_file = os.path.join(cereconf.DUMPDIR,'slp4','slp4_personer_%02d%02d%02d.txt' % (year,month,day))
    help = False
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:l:h',['slp4_file=','logger_name=','help'])
    except getopt.GetoptError:
        usage(1)

    for opt,val in opts:
        if opt in ('-l','--logger_name'):
            logger_name = val            
        if opt in ('-s','--slp4_file'):
            slp4_file = val
        if opt in ('-h','--help'):
            help = True

    if (help):
        usage()
        sys.exit(0)

    logger = Factory.get_logger(logger_name)
    slp = SLP4(slp4_file)

    update_stillingskoder(slp.get_stillingskoder())


if __name__ == '__main__':
    main()

