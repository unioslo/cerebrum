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
import urllib

def export(filename, key):
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
    conn = httplib.HTTPSConnection('ws.fronter.com')
    headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': '*/*'}
    conn.request('POST',
                 '/es/?authkey=%s' % key,
                 'STATUS\n', headers)
    r = conn.getresponse()
    print r.read()
    print r.status
    conn.close()

def main():
    file = None
    key = ''

    opts, j = getopt.getopt(sys.argv[1:], 'f:k:')
    
    for opt, val in opts:
        if opt in ('-f',):
            file = val
        elif opt in ('-k',):
            key = val
        else:
            print "Error: Invalid arg"
            sys.exit(2)
    
    if file and key:
        export(file, key)
    elif key:
        status(key)
    else:
        print "Error: Need at least a key"
        sys.exit(1)

if __name__ == '__main__':
    main()
