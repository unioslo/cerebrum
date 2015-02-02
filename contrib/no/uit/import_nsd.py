#!/usr/bin/env python
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



import getopt
import sys

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory     
from Cerebrum.modules.no.uit.nsd import nsd      


def parse_nsd(nsd_file):

    db = Factory.get('Database')()                                                                                              
    my_nsd = nsd()                                                                                                              
    file_handle = open(nsd_file,"r")
    lines = file_handle.readlines()
    file_handle.close()
    
    for line in lines:                                                                                                    
        fakultet,institutt,avdeling,nsd_code = line.split(",")                                                                  
        nsd_code = nsd_code.rstrip() # remove trailing newline                                                                  
        
        #only insert the codes into the nsd table if they are numeric                                                           
        if(fakultet.isdigit() and institutt.isdigit() and avdeling.isdigit()):                                                  
            my_nsd.insert_data(fakultet,institutt,avdeling,nsd_code,db)                                                         
    
    db.commit()                                                                                                                 
            
            
            
                                        
def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'n:','')
    except getopt.GetoptError:
        usage()
        sys.exit()
        
    log_path = "%s/%s" % (cereconf.CB_PREFIX,'var/log/')
    log_file= "%s/%s" % (log_path,"nsd.log")
    log_handle = open (log_file,"w")
    nsd_file = 0
    message = ""
    for opt,val in opts:
        if opt in('-n'):
            nsd_file = val
            
    if(nsd_file != 0):
        message = parse_nsd(nsd_file)
    else:
        usage()
                    
def usage():
    print """Usage: python import_nsd.py -n <file>
    
    -n :        inserts nsd kodes from the file given
    """
                        
                        
                        
if __name__=='__main__':
    main()
