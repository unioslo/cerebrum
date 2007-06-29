#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2004 University of Oslo, Norway
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

# This file 

import sys

import getopt
import smtplib
import urllib

import os
import re
import ftplib
import time
import string

import cerebrum_path
import cereconf
import Cerebrum.Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import Email


# Define default file locations
dumpdir = os.path.join(cereconf.DUMPDIR,"FS")
default_temp_emner_file = os.path.join(dumpdir,'temp_emner')
default_temp_studieprog_file = os.path.join(dumpdir,'temp_studieprog')
default_studieprogram_file = os.path.join(dumpdir,'studieprog.xml')
default_emne_file = os.path.join(dumpdir,'emner.xml')


class execute:
    
    def __init__(self,out_file=None):
        #print "__init__"
        #global_ret is used to check the return value from all system commands
        # if it any time is != 0 an email will be sent to the developer showing the return value from
        # all system commands.
        self.global_ret = 0
        
    # We need a temp undervenhet at 186:000000
    def insert_temp_undervenhet(self,undervenhet,log_handle,message):
        #print "insert temp undervenhet."
        message +="***insert temp undervenhet***\n"
        file_handle = open(undervenhet,"r+")
        file_handle.seek(-15,2)

        # lets insert the following 2 lines at the end of the file
        file_handle.writelines("<undenhet institusjonsnr=\"186\" emnekode=\"FLS-007\" versjonskode=\"1\" emnenavnfork=\"Felles-007\" emnenavn_bokmal=\"Dette er en falsk undervisnings enhet\" faknr_kontroll=\"0\" instituttnr_kontroll=\"0\" gruppenr_kontroll=\"0\" terminnr=\"1\" terminkode=\"HØST\" arstall=\"2005\"/>\n")
        file_handle.writelines("</undervenhet>")
        file_handle.close()
        log_handle.writelines("insert_temp_undervenhet...done\n")
        return message
        

    def update_emner(self,message,emner):
        #we need to parse the emner.xml file and remove all references to the stedkode 4902.
        # it must be replaced with 186
        tmp_file = default_temp_emner_file
        
        message +="***updating stedkode for KUN***\n"
        file_handle = open(emner,"r+")
        file_handle_write = open(tmp_file,"w")
        #print "emner fil = %s" % emner

        for line in file_handle:
            foo = line.replace("institusjonsnr_reglement=\"4902\" faknr_reglement=\"1\" instituttnr_reglement=\"0\" gruppenr_reglement=\"0\"","institusjonsnr_reglement=\"186\" faknr_reglement=\"99\" instituttnr_reglement=\"30\" gruppenr_reglement=\"0\"")
            #print "foo = %s" % foo
            file_handle_write.writelines(foo)
        
        file_handle.close()
        file_handle_write.close()

        mv_cmd = "mv %s %s" % (tmp_file,emner)
        ret = os.system(mv_cmd)
        #print "line = %s" % foo
        message +="%s: %s" % (mv_cmd,ret)

        #ret = os.system("mv /cerebrum/dumps/FS/temp_emner /cerebrum/dumps/FS/emner.xml")
        #print "line = %s" % foo
        #message +="mv /cerebrum/dumps/FS/temp_emner /cerebrum/dumps/FS/emner.xml: %s" % ret
        return message
            
    def update_studieprog(self,message,studieprogfile):
        #we need to parse the studieprog.xml file and remove all references to the stedkode 4902-*-*-*.
        # it must be replaced with 186-99-30-0
        
        tmp_file = default_temp_studieprog_file
        
        message +="***updating stedkode for KUN***\n"
        file_handle = open(studieprogfile,"r+")
        file_handle_write = open(tmp_file,"w")
        #print "studieprog fil = %s" % studieprogfile

        for line in file_handle:
            foo = line.replace("institusjonsnr_studieansv=\"4902\" faknr_studieansv=\"1\" instituttnr_studieansv=\"0\" gruppenr_studieansv=\"0\"",
                               "institusjonsnr_studieansv=\"186\" faknr_studieansv=\"99\" instituttnr_studieansv=\"30\" gruppenr_studieansv=\"0\"")
            #print "foo = %s" % foo
            file_handle_write.writelines(foo)
        
        file_handle.close()
        file_handle_write.close()
        mv_cmd = "mv %s %s" % (tmp_file,studieprogfile)
        ret = os.system(mv_cmd)
        #print "line = %s" % foo
        message +="%s: %s" % (mv_cmd,ret)
        return message

    
def main():
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'hes',['help','efile=','sfile='])
    except getopt.GetoptError:
        usage()
        sys.exit()

    update_emner = 0
    update_studieprog = 0
    emnefile = default_emne_file
    studieprogfile = default_studieprogram_file
    foo = execute()
    message = ""
    
    for opt,val in opts:
        if opt in('-e'):
            update_emner = 1
        elif opt in('-s'):
            update_studieprog = 1
        elif opt in('--efile'):
            emnefile = val
        elif opt in('--sfile'):
            studieprogfile = val

    if ((update_emner == 0) and (update_studieprog == 0)):
        usage()
        sys.exit(0)

        
    if(update_emner != 0):
        message = foo.update_emner(message,emnefile)

    if(update_studieprog != 0):
        message = foo.update_studieprog(message,studieprogfile)
    return 0        

   


def usage():
    print """Usage: python instiution_update.py -e -s --efile --sfile
    
    This script substitutes all references to the institution number 4902 with 186 in the affected files
    
    -e   Update emner.xml default file, or also use
        --efile to specify other location
    -s   Update studieprog.xml file, or also use
        --sfile to specify other location
    -h | --help Shows this help text
    """
if __name__=='__main__':
    main()

