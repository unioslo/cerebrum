#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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
import os
import shutil
import sys
import time

def fix_file(jar_file, cert_file, property_file):
    zip = 'zip'
    jar = 'jar'
    unzip = 'unzip'
    new_file = 'jbofh_new.jar'
    tmp_dir = 'tmp_%s' % time.time()
    os.mkdir(tmp_dir)
    cmd = [unzip, '-d', tmp_dir, jar_file]
    ret = os.spawnvp(os.P_WAIT, unzip, cmd)
    if ret != 0:
        raise IOError, "Error running %s" % unzip
    if property_file is not None:
        shutil.copyfile(property_file, tmp_dir + '/jbofh.properties')
    if cert_file is not None:
        shutil.copyfile(cert_file, tmp_dir + '/cacert.pem')
    os.chdir(tmp_dir)
    cmd = [jar, '-c', '-f', '../%s' % new_file, '.']
    ret = os.spawnvp(os.P_WAIT, jar, cmd)
    if ret != 0:
        raise IOError, "Error running %s" % jar
    print "New file: %s" % new_file
    os.chdir('..')
    shutil.rmtree(tmp_dir)

def usage():
    print """Usage: fix_jbofh_jar.py [-c cert_file | -p property_file] jar_file

This utility is for people who want to update the JBofh.jar file
without running ant.  It can replace the cacert.pem and
jbofh.properties files.
"""

def main():
    opts, args = getopt.getopt(sys.argv[1:], 'c:p:h',
                               ['cert-file', 'property-file', 'help'])

    cert_file = property_file = None
    for opt, val in opts:
        if opt in ('-c', '--cert-file'):
            cert_file = val
        elif opt in('-p', '--property-file'):
            property_file = val
        elif opt in('-h', '--help'):
            usage()
            sys.exit()
        else:
            usage()
            sys.exit()
    jar_file = sys.argv[-1]
    if not jar_file.endswith(".jar"):
        usage()
        sys.exit()
    fix_file(jar_file, cert_file, property_file)

if __name__ == '__main__':
    main()

# arch-tag: ca29e86c-4b9c-47ae-b7ab-7a972042238b
