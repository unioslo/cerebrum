#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import getopt
import os
import shutil
import sys
import time

def fix_file(jar_file, cert_file, property_file):
    zip = 'zip'
    unzip = 'unzip'
    new_file = 'jbofh_new.jar'
    tmp_dir = 'tmp_%s' % time.time()
    os.mkdir(tmp_dir)
    os.chdir(tmp_dir)
    cmd = [unzip, jar_file]
    ret = os.spawnvp(os.P_WAIT, unzip, cmd)
    if ret != 0:
        raise IOError, "Error running %s" % unzip
    if property_file is not None:
        shutil.copyfile(property_file, 'jbofh.properties')
    if cert_file is not None:
        shutil.copyfile(cert_file, 'cacert.pem')
    cmd = [zip, '-r', '../%s' % new_file, '.']
    ret = os.spawnvp(os.P_WAIT, zip, cmd)
    if ret != 0:
        raise IOError, "Error running %s" % zip
    print "New file: %s" % new_file
    os.chdir('..')
    shutil.rmtree(tmp_dir)

def usage():
    print """Usage: fx_jbofh_jar.py [-c cert_file | -p property_file] jar_file

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
