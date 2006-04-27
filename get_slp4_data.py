#! /usr/bin/env python
#-*- coding: iso-8859-1 -*-
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


#
# This file reads ou data from a text file. Compares the stedkode
# code with what already exists in a ou data file form FS and inserts
# right ou information from that file. For stedkoder who doesnt
# exist in the FS file, default data is inserted
#

import os
import re
import ftplib
import time
import string
import getopt
import sys
import DCOracle2
import locale

import cerebrum_path
import cereconf
import Cerebrum.Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory

class process:
    def __init__(self,out):
        #locale.setlocale(locale.NLS_LANG, ('american_america', 'we8iso8859p1'))
        #locale.setlocale(locale.LC_ALL,"en_US.ISO-8859-1")
        list = []
        db = DCOracle2.connect("slp4/grimfandango@slp4")
        c = db.cursor()
        c.execute("select PERSONNAVN,FODT_DATO,FODSELSNR,KJONN,ANSVARSSTED,FAKULTET,INSTITUTT,STILLINGSKODE,STILLINGSBETEGNELSE,BEGYNT from web_fak_inst_ftt_pers ORDER BY fakultet,institutt,personnavn")
        list = c.fetchall()
        #for foo in list:
            #print "navn = %s" % foo[0]
        #    if(foo[2]==31564):
        #        print "navn = %s" % foo[0]
            #print "list = %s" % list[0]
        foo = self.nice_print(list,out)




    def nice_print(self,list,out):
        #print "out = %s" % out
        file_handle = open(out,"w")
        max = 10
        for elem in list:
            i = 0
            begynt = "%s" % elem[9]
            #print "%s" % begynt
            #try:
            if ((elem[2] is not None) and (len(elem[2]) != 5)):
                # For some reason leading zeroes in elem[2] is not registered in the
                # slp4 shadow database. Reason unknown. This leads to people with
                # leading zeroes in elem[2] not being registred in cerebrum
                # and neither exported to FRIDA (and quite possible other external systems)
                # There are two solutions
                # 1. Add a leading zero for internal cerebrum use
                # 2. Fix the data in the slp4 shadow database.
                # option 2 is by far the one prefered, but is also the one that will take
                # the most time....what to do ?
                #print "fodselsdato = '%s' AND personnr = '%s'" % (elem[1],elem[2])
                elem[2] = "0%s" % elem[2]
                #print "new elem[2] = '%s'" % elem[2]
                
            if(begynt != 'None'):
                dag,mnd,aar = begynt.split(".")
            elem[9]="%s/%s/%s" % (mnd,dag,aar)
            for item in elem:
                # need to reformat the "begynt" field
                day,month,year=elem[1].split(".")
                if((day[0]!='8') and(day[0] !='9')):
                    # Do not insert persons that has 8 or 9 as the first digit in the birth day.
                    # These persons only has an internal slp code. not meant for external use.
                    file_handle.writelines("\"%s\"" % item)
                    #item = item.rstrip()
                    #print "\"%s\"" % item
                    if(i < ((max)-1)):
                        file_handle.writelines(",")
                    else:
                        file_handle.writelines("\n")
                    i = i+1
        file_handle.close()
        
def main():

    # lets set default out_file
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    file_path = cereconf.CB_PREFIX + '/var/dumps/slp4'
    file_name = '%s/slp4_personer_%02d%02d%02d.txt' % (file_path,year,month,day)
    out_file = file_name 

    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:',['out='])

    except getopt.GetoptError:
    
        usage()
        sys.exit()

    for opt ,val in opts:
        if opt in('-o','--out'):
            out_file = val

    
    if(out_file != 0):
        process(out_file)

    else:
        usage()
        sys.exit()

def usage():
    print """Usage: python get_slp4_data.py

    This file gets person data from slp4 and stores
    them in the indicated file

    options:
    -o | --out: file to store the data in"""

if __name__=='__main__':
    main()

# arch-tag: b2885aae-b426-11da-9b7f-25da2113c75c
