#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Usage: generate_posix_ldif.py [options]

Write user and group information to an LDIF file (if enabled in
cereconf), which can then be loaded into LDAP.

  --user=<outfile>      | -u <outfile>  Write users to a LDIF-file
  --filegroup=<outfile> | -f <outfile>  Write posix filegroups to a LDIF-file
  --netgroup=<outfile>  | -n <outfile>  Write netgroup map to a LDIF-file
  --posix  Write all of the above, plus optional top object and extra file,
           to a file given in cereconf (unless the above options override).
           Also disable ldapsync first.

With none of the above options, do the same as --posix.

  --user_spread=<value>      | -U <value>  (used by all components)
  --filegroup_spread=<value> | -F <value>  (used by --filegroup component)
  --netgroup_spread=<value>  | -N <value>  (used by --netgroup component)

The spread options accept multiple spread-values (<value1>,<value2>,...)."""

import sys
import getopt
import os.path
import time

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import *

disablesync_cn = 'disablesync'

def init_ldap_dump(fd):
    fd.write("\n")
    if cereconf.LDAP_POSIX.get('dn'):
        fd.write(container_entry_string('POSIX'))


def disable_ldapsync_mode():
    try:
        logger = Factory.get_logger("cronjob")
    except IOError, e:
        print >>sys.stderr, "get_logger: %s" % e
        logger = None
    ldap_servers = cereconf.LDAP.get('server')
    if ldap_servers is None:
        if logger:
            logger.info("No active LDAP-sync servers configured")
        return
    try:
        from Cerebrum.modules import LdapCall
    except ImportError:
        if logger:
            logger.info("LDAP modules missing. Probably python-LDAP")
    else:
        s_list = LdapCall.ldap_connect()
        LdapCall.add_disable_sync(s_list,disablesync_cn)
        LdapCall.end_session(s_list)
        log_dir = os.path.join(cereconf.LDAP['dump_dir'], "log")
        if os.path.isdir(log_dir):
            rotate_file = os.path.join(log_dir, "rotate_ldif.tmp")
            if not os.path.isfile(rotate_file):
                f = file(rotate_file,'w')
                f.write(time.strftime("%d %b %Y %H:%M:%S", time.localtime()))
                f.close()


def main():
    short2long_opts = (("u:", "U:", "f:", "F:", "n:", "N:"),
                       ("user=",      "user_spread=",
                        "filegroup=", "filegroup_spread=",
                        "netgroup=",  "netgroup_spread="))
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "".join(short2long_opts[0]),
                                   ("help", "posix") + short2long_opts[1])
        opts = dict(opts)
    except getopt.GetoptError, e:
        usage(str(e))

    if args:
        usage("Invalid arguments: " + " ".join(args))
    if "--help" in opts:
        usage()
    # Copy long options into short options
    for short, longs in zip(*short2long_opts):
        val = opts.get("--" + longs.replace("=", ""))
        if val is not None:
            opts["-" + short.replace(":", "")] = val

    got_file = filter(opts.has_key, ("-u", "-f", "-n"))
    for opt in ("-U", "-F", "-N"):
	if opts.has_key(opt):
	    opts[opt] = opts[opt].split(",")
	else:
	    opts[opt] = None

    do_all = "--posix" in opts or not got_file
    fd = None
    if do_all:
        fd = ldif_outfile('POSIX')
        disable_ldapsync_mode()
        init_ldap_dump(fd)
    db = Factory.get('Database')()
    posldif = Factory.get('PosixLDIF')(db,opts['-U'],opts['-F'],opts['-N'],fd)
    for var, func, arg in \
            (('LDAP_USER',      posldif.user_ldif,            "-u"),
             ('LDAP_FILEGROUP', posldif.filegroup_ldif,       "-f"),
             ('LDAP_NETGROUP',  posldif.netgroup_ldif,        "-n")):
        if (do_all or arg in opts) and getattr(cereconf, var).get('dn'):
	    func(opts.get(arg))
        elif arg in opts:
            sys.exit("Option %s requires cereconf.%s['dn']." % (args[-1], var))
    if fd:
        end_ldif_outfile('POSIX', fd)


def usage(err=0):
    if err:
        print >>sys.stderr, err
    print >>sys.stderr, __doc__
    sys.exit(bool(err))


if __name__ == '__main__':
        main()

# arch-tag: 19f6df39-39ae-4206-b741-cf7b3429e589
