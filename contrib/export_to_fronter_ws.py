#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2014 University of Oslo, Norway
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
"""This script can be used for sending an export to a Fronter instances
webservice"""

import sys
import socket
import getopt
import httplib
import io

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')


def export(filename, key, host):
    """Runs the export"""
    logger.debug('Reading file %s' % filename)

    f = io.open(filename, 'rb')
    data = f.read()
    f.close()

    logger.debug('Done reading file')
    logger.info('Connecting to %s, key is %s' % (host, key))

    conn = httplib.HTTPSConnection(host)

    logger.info('Starting request')

    headers = {'Content-type': 'application/x-www-form-urlencoded',
               'Accept': '*/*'}
    try:
        conn.request('POST',
                     '/es/?authkey=%s' % key,
                     'POSTFILE\n%s\n%s' % (filename, data), headers)
    except socket.error, err:
        logger.error('Error during request: %s' % err[1])
        return -8

    logger.debug('Fetching response')

    r = conn.getresponse()

    # Log the return message from the webservice
    logger.info("Response: %s" % r.read())

    conn.close()
    return 0 if r.status == 200 else r.status


def status(key, host):
    """Polls the WS for a status"""
    conn = httplib.HTTPSConnection(host)
    headers = {'Content-type': 'application/x-www-form-urlencoded',
               'Accept': '*/*'}
    try:
        conn.request('POST',
                     '/es/?authkey=%s' % key,
                     'STATUS\n', headers)
    except socket.error, err:
        logger.error('Error during request: %s' % err[1])
        return -8

    r = conn.getresponse()

    logger.info("Response: %s" % r.read())
    conn.close()
    return 0 if r.status == 200 else r.status


def usage(i=0):
    """Usage information"""
    print """Usage: %s -k <key> -f <file> --logger-name <logger>
      -k <key> defines which Fronter-integration will receive the file.
      -i <instance> the instance to export to, i.e. 'prod'.
      -f <file> defines the filename to the file.
      --logger-name <logger> defines the logger to use (default: cronjob)

      If you run the export with only -k, it will tell you if the service is
      OK and running.

      The file supplied should be zip'ed if it is too big (whatever that is).
      I.E: A 500MB file might not get imported. Compress it to 10-20MB and it
      gets imported.

      Visit https://ws.fronter.com/es/?authkey=<key> in order to view the
      integration status. The "Data Exported" row tells you when the file was
      correctly received by the WS. "Data Imported" tells you when the last
      import was run. These timestamps do not update instantly, you'll probably
      need to wait quite a while before they update :)

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
    instance = ''
    host = 'ws.fronter.com'

    try:
        opts, j = getopt.getopt(sys.argv[1:], 'f:k:hH:i:')
    except getopt.GetoptError, err:
        print 'Error: %s' % err
        usage(-2)

    for opt, val in opts:
        if opt in ('-f',):
            file = val
        elif opt in ('-k',):
            key = val
        elif opt in ('-i',):
            instance = val
        elif opt in ('-h',):
            usage()
        elif opt in ('-H',):
            host = val
        else:
            print "Error: Invalid arg"
            usage(-2)

    if not key:
        from Cerebrum.Utils import read_password
        try:
            key = read_password(instance, host)
        except Exception, e:
            logger.error("Error: %s" % e)
            sys.exit(-3)

    if file and key:
        return export(file, key, host)
    elif key:
        return status(key, host)
    else:
        usage(-1)

if __name__ == '__main__':
    main()
