#! /local/bin/python
#
# Copyright 2013 University of Oslo, Norway
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
"""This script can be used for sending an export to a Fronter instance"""

import sys
import getopt
import httplib
import time

def export(filename, key):
    """Runs the export"""
    t = lambda: time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())

    print t() + ': Reading file'
    f = open(filename)
    data = f.read()
    f.close()
    print t() + ': Done reading file'

    print t() + ': Connecting'
    
    conn = httplib.HTTPSConnection('ws.fronter.com')
    print t() + ': Starting request'
    headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': '*/*'}
    conn.request('POST',
                 '/es/?authkey=%s' % key,
                 'POSTFILE\n%s\n%s' % (filename, data), headers)

    print t() + ': Fetching response'
    r = conn.getresponse()
    print r.read()
    print r.status
    conn.close()

def status(key):
    """Polls the WS for a status"""
    conn = httplib.HTTPSConnection('ws.fronter.com')
    headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': '*/*'}
    conn.request('POST',
                 '/es/?authkey=%s' % key,
                 'STATUS\n', headers)
    r = conn.getresponse()
    print r.read()
    print r.status
    conn.close()

def usage(i=0):
    """Usage information"""
    print """Usage: %s -k <key> -f <file>
      -k <key> defines which Fronter-integration will receive the file.
      -f <file> is the filename to the file.
    
      If you run the export with only -k, it will tell you if the service is
      OK and running.

      The file supplied should be zip'ed if it is too big (whatever that is).
      I.E: A 500MB file might not get imported. Compress it to 10-20MB and it
      gets imported.
      
      Visit https://ws.fronter.com/es/?authkey=<key> in order to view the
      integration status. The "Data Exported" row tells you when the file was
      correctly received by the WS. "Data Imported" tells you when the last
      import was run.

      It seems like the import maintains an internal state in regards to the
      files you upload. If "there hasn't been large enough changes", the
      import might not actually import everything. It might be wise to change
      the file name of the file each time you upload, in order for the
      integration to understand that there are changes. All this is based on a
      bit of speculation. Will try to inquire Fronter about this.
      """
    sys.exit(i)

def main():
    """Arg parsing and execution"""
    file = None
    key = ''

    opts, j = getopt.getopt(sys.argv[1:], 'f:k:h')
    
    for opt, val in opts:
        if opt in ('-f',):
            file = val
        elif opt in ('-k',):
            key = val
        elif opt in ('-h',):
            usage()
        else:
            print "Error: Invalid arg"
            usage(2)
    
    if file and key:
        export(file, key)
    elif key:
        status(key)
    else:
        usage(1)

if __name__ == '__main__':
    main()
