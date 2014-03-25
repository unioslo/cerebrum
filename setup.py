#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002-2011 University of Oslo, Norway
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
#   *.sql:        usr/share/cerebrum/design/
#   *.html,*.dia: usr/share/doc/cerebrum/
#
# doc/
#   *:            Not installed
#
# testsuite/
#   *:            Not installed
#
# servers/bofhd/
#   bofhd.py:     usr/sbin/
#   config.dat:   etc/cerebrum/bofhd.config
#   *.py:         usr/share/cerebrum/bofhd (site-packages/modules/bofhd better?)
#
# clients/examples/
#   bofh.py:      usr/bin
#   passweb.py:   usr/share/cerebrum/client ?
#
#   As the client will be installed stand-alone on numerous machines,
#   the files for it resides in a separate directory to make
#   distribution easier.  All clients should share at least one config
#   file
#
# clients/jbofh/
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
#  python setup.py install install_data --install-dir=/cerebrum
#
# To get the files in /etc under /cerebrum/etc, add:
#  --root=/cerebrum
#
# To build dist file:
#  python setup.py sdist

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

# Ugly hack to decide whether bofh was disabled
# through ./configure
bofh = True
try:
    for line in open('Makefile'):
        if line.startswith('bofh ='):
            _, b = line.split('=')
            b = b.strip()
            break
    bofh = b != 'no'
except Exception, e:
    pass

#
# Which user should own the installed files
#
cerebrum_user = "cerebrum"


class my_install_data (install_data.install_data, object):

    def finalize_options(self):
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
        cere_path = os.path.join(
            sysconfig.get_python_lib(),
            "cerebrum_path.py")
        if self.root:
            cere_path = os.path.normpath(cere_path)
            if os.path.isabs(cere_path):
                cere_path = cere_path[1:]
            cere_path = os.path.join(self.root, cere_path)
        f_out = open(cere_path, "w")
        python_dir = sysconfig.get_python_lib(prefix=self.install_dir)
        for line in f_in.readlines():
            line = line.replace("@CONFDIR@", sysconfdir)
            line = line.replace("@PYTHONDIR@", python_dir)
            f_out.write(line)
        f_in.close()
        f_out.close()

    def run(self):
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

    def initialize_options(self):
        self.check = None
        self.dbcheck = None

    def finalize_options(self):
        if self.check is None and self.dbcheck is None:
            raise RuntimeError, "Must specify test option"

    def run(self):
        if self.dbcheck is not None:
            os.system(
                '%s testsuite/Run.py -v Cerebrum.tests.SQLDriverTestCase.suite' %
                sys.executable)
        if self.check is not None:
            os.system('%s testsuite/Run.py -v' % sys.executable)


class my_sdist(sdist, object):

    def finalize_options(self):
        super(my_sdist, self).finalize_options()
        if bofh and os.system('cd clients/jbofh && ant dist') != 0:
            raise RuntimeError, "Error running ant"


def wsdl2py(name):
    try:
        from ZSI.generate.wsdl2python import WriteServiceModule
        from ZSI.wstools import WSDLTools
    except ImportError:
        pass
    else:
        reader = WSDLTools.WSDLReader()
        wsdl = reader.loadFromFile(name)
        dir = os.path.dirname(name)

        wsm = WriteServiceModule(wsdl, addressing=True)
        fd = open(os.path.join(dir, '%s.py' % wsm.getClientModuleName()), 'w+')
        print os.path.join(dir, '%s.py' % wsm.getClientModuleName())
        wsm.writeClient(fd)
        fd.close()

        fd = open(os.path.join(dir, '%s.py' % wsm.getTypesModuleName()), 'w+')
        wsm.writeTypes(fd)
        fd.close()


def wsdl2dispatch(name):
    try:
        from ZSI.wstools import WSDLTools
        from ZSI.generate.wsdl2dispatch import ServiceModuleWriter as ServiceDescription
        from ZSI.generate.wsdl2dispatch import DelAuthServiceModuleWriter as DelAuthServiceDescription
        from ZSI.generate.wsdl2dispatch import WSAServiceModuleWriter as ServiceDescriptionWSA
        from ZSI.generate.wsdl2dispatch import DelAuthWSAServiceModuleWriter as DelAuthServiceDescriptionWSA

    except ImportError:
        pass
    else:
        reader = WSDLTools.WSDLReader()
        wsdl = reader.loadFromFile(name)

        dir = os.path.dirname(name)

        ss = ServiceDescription(do_extended=False)
        ss.fromWSDL(wsdl)

        fd = open(os.path.join(dir, ss.getServiceModuleName() + '.py'), 'w+')
        print os.path.join(dir, ss.getServiceModuleName() + '.py')
        ss.write(fd)
        fd.close()

# Ugly hack to get path names from configure
# Please fix this if you see a better solution.
vars = locals()
try:
    for line in open('Makefile'):
        if line.find(':') != -1:
            break  # Only scan until the first target.
        if line.find('$') != -1:
            continue  # Don't read in variable names.
        try:
            name, value = line.split('=')
            name = name.strip()
            value = value.strip()
            # We only overwrite variables that are not already set.
            if not vars.has_key(name):
                vars[name] = value
        except ValueError, e:
            continue
except IOError, e:
    pass

# Then we set the default value of these variables.  If they are already
# set, we keep the original value.
vars.setdefault('prefix', ".")
                # Should preferably be initialized from the command-line
                # argument
vars.setdefault('sharedir', "%s/share" % prefix)
vars.setdefault('sbindir', "%s/sbin" % prefix)
vars.setdefault('bindir', "%s/bin" % prefix)
vars.setdefault(
    'sysconfdir', "%s/etc/cerebrum" %
    prefix)  # Should be /etc/cerebrum/
vars.setdefault(
    'logdir', "%s/var/log/cerebrum" %
    prefix)  # Should be /var/log/cerebrum/
# End ugly hack

sbin_files = [
    ('servers/job_runner/job_runner.py', 0755),
    ('makedb.py', 0755)
]
if (bofh):
    sbin_files.append(('servers/bofhd/bofhd.py', 0755))
    sbin_files.append(('servers/event/event_daemon.py', 0755))
    sbin_files.append(('servers/cis/SoapIndividuationServer.py', 0755))
    sbin_files.append(('servers/cis/SoapPostmasterServer.py', 0755))
    sbin_files.append(('servers/cis/SoapGroupServer.py', 0755))
    sbin_files.append(('servers/cis/SoapGroupPublish.py', 0755))
    sbin_files.append(('servers/cis/SoapVirthomeServer.py', 0755))

if (bofh):
    bin_files = [
        ('clients/examples/bofh.py', 0755),
        ('clients/jbofh/fix_jbofh_jar.py', 0755)
    ]
else:
    bin_files = []

share_files = [
    ('clients/examples/passweb.py', 0755),
    ('clients/examples/passweb_form.html', 0644),
    ('clients/examples/passweb_receipt.html', 0644),
]
if (bofh):
    jar_file = 'clients/jbofh/dist/lib/JBofh.jar'
    try:
        open(jar_file)
        share_files.append((jar_file, 0644))
    except IOError, e:
        print "'%s': not found. Skipping." % jar_file

data_files = [
    ({'path': "%s/cerebrum/design" % sharedir,
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
    # ("%s/samples" % sharedir,
    # ['doc/*.cron']),
    ({'path': sbindir,
      'owner': cerebrum_user,
      'mode': 0755}, sbin_files),
    ({'path': "%s/cerebrum/contrib" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/exchange" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/exchange/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/dns" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/dns/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/hostpolicy" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/hostpolicy/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/migrate" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/migrate/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/*.py', 0755)]),

    ({'path': "%s/cerebrum/contrib/virthome" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/virthome/*.py', 0755)]),

    ({'path': "%s/cerebrum/contrib/ad" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/ad/*.py', 0755)]),

    # Indigo.  A recurse-like option would be great...
    ({'path': "%s/cerebrum/contrib/no/Indigo" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/*.html', 0644),
      ('contrib/no/Indigo/web/templates/*.png', 0644),
      ('contrib/no/Indigo/web/templates/*.css', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates/ofk" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/ofk/*.zpl', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates/giske" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/giske/*.zpl', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates/ofk/macro" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/ofk/macro/*.zpl', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates/giske/macro" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/giske/macro/*.zpl', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates/default" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/default/*.zpl', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/Indigo/web/templates/default/macro" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/web/templates/default/macro/*.zpl', 0644)]),

    ({'path': "%s/cerebrum/contrib/statistics" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/statistics/*.py', 0755)]),

    ({'path': "%s/cerebrum/contrib/no/uio" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uio/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uio/printer_quota/" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uio/printer_quota/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/giske" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/giske/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/hia" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/hia/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/hih" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/hih/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/hiof" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/hiof/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/nmh" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/nmh/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/nih" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/nih/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/hine" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/hine/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/nvh" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/nvh/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/tsd" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/tsd/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uit" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uit/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uit" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uit/*.pl', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uit/misc" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uit/misc/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uit/misc" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uit/misc/*.sh', 0755)]),
    ({'path': bindir,
      'owner': cerebrum_user,
      'mode': 0755}, bin_files),
    ({'path': "%s/cerebrum/client" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755}, share_files),
    ({'path': sysconfdir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('design/cereconf.py', 0644),
      ('servers/bofhd/config.dat', 0644),
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
]

wsdl2py('servers/cerews/lib/cerews.wsdl')
wsdl2dispatch('servers/cerews/lib/cerews.wsdl')


setup(name="Cerebrum", version=Cerebrum.__version__,
      url="http://cerebrum.sourceforge.net",
      maintainer="Cerebrum Developers",
      maintainer_email="do.we@want.this.here",
      description="Cerebrum is a user-administration system",
      license="GPL",
      long_description=("System for user semi-automatic user " +
                        "administration in a heterogenous " +
                        "environment"),
      platforms = "UNIX",
      # NOTE: all scripts ends up in the same dir!
      # scripts = ['contrib/no/uio/import_FS.py',
      # 'contrib/generate_nismaps.py'],
      packages = ['Cerebrum',
                  'Cerebrum/extlib',
                  'Cerebrum/extlib/Plex',
                  'Cerebrum/extlib/json',
                  'Cerebrum/modules',
                  'Cerebrum/modules/ad',
                  'Cerebrum/modules/ad2',
                  'Cerebrum/modules/dns',
                  'Cerebrum/modules/event',
                  'Cerebrum/modules/exchange',
                  'Cerebrum/modules/exchange/v2013',
                  'Cerebrum/modules/hostpolicy',
                  'Cerebrum/modules/bofhd',
                  'Cerebrum/modules/job_runner',
                  'Cerebrum/modules/no',
                  'Cerebrum/modules/no/Indigo',
                  'Cerebrum/modules/no/uio',
                  'Cerebrum/modules/no/uio/printer_quota',
                  'Cerebrum/modules/no/uio/voip',
                  'Cerebrum/modules/no/uio/AutoStud',
                  'Cerebrum/modules/no/hia',
                  'Cerebrum/modules/no/hih',
                  'Cerebrum/modules/no/hiof',
                  'Cerebrum/modules/no/nmh',
                  'Cerebrum/modules/no/nih',
                  'Cerebrum/modules/no/hine',
                  'Cerebrum/modules/no/notur',
                  'Cerebrum/modules/no/nvh',
                  'Cerebrum/modules/tsd',
                  'Cerebrum/modules/templates',
                  'Cerebrum/modules/xmlutils',
                  'Cerebrum/modules/abcenterprise',
                  'Cerebrum/modules/process_entity',
                  'Cerebrum/modules/no/uit',
                  'Cerebrum/modules/no/uit/AutoStud',
                  'Cerebrum/lib',
                  'Cerebrum/client',
                  'Cerebrum/modules/LMS',
                  'Cerebrum/modules/virthome',
                  'Cerebrum/modules/cis',
                  'Cerebrum/config',
                  ],

      # options override --prefix
      # options = {'install_data': {'root' : '/foo/bar',  # prefix on slash
      # 'install_dir': '/dddddddd' # prefix on no-slash
      #                            }},
      # data_files doesn't seem to handle wildcards
      data_files = data_files,
      # Overridden command classes
      cmdclass = {'install_data': my_install_data,
                  'sdist': my_sdist,
                  'test': test}
      )
