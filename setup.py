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

# Placement of files when installing Cerebrum
# -------------------------------------------
#
# NOTE: At least while developing, I recommend using "--prefix
# /cerebrum".  Otherwise all these paths are relative to / unless
# otherwise noted.
#
# /
#   README:       usr/share/cerebrum/doc/
#   COPYING:      usr/share/cerebrum/doc/
#
# Cerebrum/
#   */*.py:       under site-packages of the running python interpreter
#   cereconf.py:  etc/cerebrum/
#   */tests/*:    Not installed
#
#   Note that the entire Cerebrum/modules catalog is installed.
#   Site-specific components should assert that they do not use names
#   that clashes with the files distributed with Cerebrum, otherwise
#   they may be overwritten by a later installation.  The naming
#   syntax should be that of a reversed dns name with '.' replaced with
#   '/'.  E.g., for uio.no, the directory modules/no/uio is used.
#
# design/
#   *.sql:        usr/share/cerebrum/doc/design/
#   *.html,*.dia: usr/share/cerebrum/doc/
#
# doc/
#   *:            usr/share/cerebrum/doc/
#   *cron*:       usr/share/cerebrum/doc/samples
#
# testsuite/
#   *:            Not installed
#
# server/
#   bofhd.py:     usr/sbin/
#   config.dat:   etc/cerebrum/bofhd.config
#   *.py:         usr/share/cerebrum/bofhd (site-packages/modules/bofhd better?)
#
# client/
#   bofh.py:      usr/bin
#   config-files: etc/cerebrum/client
#   template.ps:  usr/share/cerebrum/client
#   passweb.py:   usr/share/cerebrum/client ?
#
#   As the client will be installed stand-alone on numerous machines,
#   the files for it resides in a separate directory to make
#   distribution easier.  All clients should share at least one config
#   file
#
# java/jbofh/
#   jbofh.jar:    usr/share/cerebrum/client
#   libJavaReadline.so:
#                 usr/share/cerebrum/client/linux
#   jbofh.sh:     usr/bin
#
# contrib/
#   generate_nismaps.py:  usr/sbin
#
# contrib/no
#   *.py:         usr/sbin
# contrib/no/uio
#   *.py:         usr/sbin
#
# contrib/no/uio/studit
#   *:            usr/share/cerebrum/studit
#
#
# Other directories/files:
#
#   var/log/cerebrum/:
#        All log-files for cerebrum, unless the number of files is
#        above 4, when a seperate directory should be created.
#
#   usr/share/cerebrum/data:
#        A number of subdirectories for various backends

# To install python modules in standard locations, and cerebrum files
# under /cerebrum, run like:
#  python2.2 setup.py install install_data --install-dir=/cerebrum
#
# To get the files in /etc under /cerebrum/etc, add:
#  --root=/cerebrum
#
# To build dist file:
#  python2.2 setup.py sdist

import os
import sys
import pwd
from glob import glob
from types import StringType

from distutils import sysconfig
from distutils.command import install_data, install_lib
from distutils.command.build import build
from distutils.command.sdist import sdist
from distutils.core import setup, Command
from distutils.util import change_root, convert_path
import Cerebrum

#
# Which user should own the installed files
#
cerebrum_user = "cerebrum"

class my_install_data (install_data.install_data, object):
    def finalize_options (self):
        """Add wildcard support for filenames.  Generate cerebrum_path.py"""
        super(my_install_data, self).finalize_options()
        for f in self.data_files:
            if type(f) != StringType:
                files = f[1]
                i = 0
                while i < len(files):
                    if files[i][0].find('*') > -1:
                        for e in glob(files[i][0]):
                            files.append((e, files[i][1]))
                        files.pop(i)
                        i -= 1
                    i += 1
        if(os.geteuid() != 0):
            print "Warning, uid!=0, not writing cerebrum_path.py"
            return
        f_in = open("cerebrum_path.py.in", "r")
        cere_path = os.path.join(sysconfig.get_python_lib(), "cerebrum_path.py")
        if self.root:
            cere_path = os.path.normpath(cere_path)
            if os.path.isabs(cere_path):
                cere_path = cere_path[1:]
            cere_path = os.path.join(self.root, cere_path)
        f_out = open(cere_path, "w")
        etc_dir = "%s/etc/cerebrum" % self.install_dir
        python_dir = sysconfig.get_python_lib(prefix=self.install_dir)
        for line in f_in.readlines():
            line = line.replace("@CONFDIR@", etc_dir)
            line = line.replace("@PYTHONDIR@", python_dir)
            f_out.write(line)
        f_in.close()
        f_out.close()

    def run (self):
        self.mkpath(self.install_dir)
        for f in self.data_files:
            # it's a tuple with dict to install to and a list of files
            tdict = f[0]
            dir = convert_path(tdict['path'])
            if not os.path.isabs(dir):
                dir = os.path.join(self.install_dir, dir)
            elif self.root:
                dir = change_root(self.root, dir)
            self.mkpath(dir)
            os.chmod(dir, tdict['mode'])
            if(os.geteuid() == 0):
                try:
                    uinfo = pwd.getpwnam(tdict['owner'])
                except KeyError:
                    print "Error: Unkown user %s" % tdict['owner']
                    sys.exit(1)
                uid, gid = uinfo[2], uinfo[3]
                os.chown(dir, uid, gid)
            if f[1] == []:
                # If there are no files listed, the user must be
                # trying to create an empty directory, so add the
                # directory to the list of output files.
                self.outfiles.append(dir)
            else:
                # Copy files, adding them to the list of output files.
                for data, mode in f[1]:
                    data = convert_path(data)
                    (out, _) = self.copy_file(data, dir)
                    self.outfiles.append(out)
                    os.chmod(out, mode)
                    if(os.geteuid() == 0):
                        os.chown(out, uid, gid)

class test(Command):
    user_options = [('check', None, 'Run check'),
                    ('dbcheck', None, 'Run db-check')]
    def initialize_options (self):
        self.check = None
        self.dbcheck = None

    def finalize_options (self):
        if self.check is None and self.dbcheck is None:
            raise RuntimeError, "Must specify test option"
    
    def run (self):
        if self.dbcheck is not None:
            os.system('%s testsuite/Run.py -v Cerebrum.tests.SQLDriverTestCase.suite' % sys.executable)
        if self.check is not None:
            os.system('%s testsuite/Run.py -v' % sys.executable)

class my_sdist(sdist, object):
    def finalize_options (self):
        super(my_sdist, self).finalize_options()
        if os.system('cd java/jbofh && ant dist') != 0:
            raise RuntimeError, "Error running ant"

prefix="."  # Should preferably be initialized from the command-line argument
sharedir="%s/share" % prefix
sbindir="%s/sbin" % prefix
bindir="%s/bin" % prefix
sysconfdir = "%s/etc/cerebrum" % prefix # Should be /etc/cerebrum/
logdir = "%s/var/log/cerebrum" % prefix # Should be /var/log/cerebrum/

setup (name = "Cerebrum", version = Cerebrum.__version__,
       url = "http://cerebrum.sourceforge.net",
       maintainer = "Cerebrum Developers",
       maintainer_email = "do.we@want.this.here",
       description = "Cerebrum is a user-administration system",
       license = "GPL",
       long_description = ("System for user semi-automatic user "+
                           "administration in a heterogenous "+
                           "environment"),
       platforms = "UNIX",
       # NOTE: all scripts ends up in the same dir!
       # scripts = ['contrib/no/uio/import_FS.py', 'contrib/generate_nismaps.py'],
       packages = ['Cerebrum',
                   'Cerebrum/extlib',
                   'Cerebrum/extlib/Plex',
                   'Cerebrum/modules',
                   'Cerebrum/modules/bofhd',
                   'Cerebrum/modules/job_runner',
                   'Cerebrum/modules/no',
                   'Cerebrum/modules/no/uio',
                   'Cerebrum/modules/no/uio/printer_quota',
                   'Cerebrum/modules/no/uio/AutoStud',
                   'Cerebrum/modules/no/feidegvs',
                   'Cerebrum/modules/no/hia',
                   'Cerebrum/modules/templates',
                   'Cerebrum/client',
                   ],

       # options override --prefix
       #options = {'install_data': {'root' : '/foo/bar',  # prefix on slash
       #                            'install_dir': '/dddddddd' # prefix on no-slash
       #                            }},
       # data_files doesn't seem to handle wildcards
       data_files = [({'path': "%s/doc/cerebrum/design" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('design/*.sql', 0644),
                       ]),
                     ({'path': "%s/doc/cerebrum" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('design/cerebrum-core.dia', 0644),
                       ('design/cerebrum-core.html', 0644),
                       ('design/adminprotocol.html', 0644),
                       ('README', 0644),
                       ('COPYING', 0644)
                       # 'doc/*'
                       ]),
                     ## ("%s/samples" % sharedir,
                     ##  ['doc/*.cron']),
                     ({'path': sbindir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('server/bofhd.py', 0755),
                       ('server/job_runner.py', 0755),
                       ('makedb.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/*.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib/no" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/no/*.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib/no/uio" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/no/uio/*.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib/no/uio/printer_quota/" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/no/uio/printer_quota/*.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib/no/feidegvs" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/no/feidegvs/*.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib/no/hia" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/no/hia/*.py', 0755)]),
                     ({'path': "%s/cerebrum/contrib/no/hist" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('contrib/no/hist/*.py', 0755)]),
                     ({'path': bindir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('client/bofh.py', 0755),
                       ('java/jbofh/fix_jbofh_jar.py', 0755)]),
                     ({'path': "%s/cerebrum/client" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                       [('client/passweb.py', 0755),
                        ('client/passweb_form.html', 0644),
                        ('client/passweb_receipt.html', 0644),
                        ('java/jbofh/dist/lib/JBofh.jar', 0644)]),
                     ({'path': sysconfdir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      [('design/cereconf.py', 0644),
                       ('server/config.dat', 0644),
                       ('design/logging.ini', 0644)
                       ]),
                     ({'path': logdir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      []),
                     ({'path': "%s/cerebrum/data" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0755},
                      []),
                     ],
       # Overridden command classes
       cmdclass = {'install_data': my_install_data,
                   'sdist': my_sdist,
                   'test': test}
      )

# arch-tag: 9be53bbd-d5f4-4bcd-bcca-34d123099623
