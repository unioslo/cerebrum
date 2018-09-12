#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002-2018 University of Oslo, Norway
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
""" This is the install script for the Cerebrum module.

Placement of files when installing Cerebrum
-------------------------------------------

NOTE: At least while developing, I recommend using "--prefix
/cerebrum".  Otherwise all these paths are relative to / unless
otherwise noted.

/
  README.md:       usr/share/cerebrum/doc/
  COPYING:      usr/share/cerebrum/doc/

Cerebrum/
  */*.py:       under site-packages of the running python interpreter
  cereconf.py:  etc/cerebrum/
  */tests/*:    Not installed

  Note that the entire Cerebrum/modules catalog is installed.
  Site-specific components should assert that they do not use names
  that clashes with the files distributed with Cerebrum, otherwise
  they may be overwritten by a later installation.  The naming
  syntax should be that of a reversed dns name with '.' replaced with
  '/'.  E.g., for uio.no, the directory modules/no/uio is used.

design/
  *.sql:        usr/share/cerebrum/design/
  *.html,*.dia: usr/share/cerebrum/doc/

doc/
  *:            Not installed

testsuite/
  *:            Not installed

servers/bofhd/
  bofhd.py:     usr/sbin/
  config.dat:   etc/cerebrum/bofhd.config
  *.py:         usr/share/cerebrum/bofhd (site-packages/modules/bofhd better?)

clients/
  *:            Not installed

contrib/
  generate_nismaps.py:  usr/sbin

contrib/no
  *.py:         usr/sbin
contrib/no/uio
  *.py:         usr/sbin

contrib/no/uio/studit
  *:            usr/share/cerebrum/studit


Other directories/files:

  var/log/cerebrum/:
    All log-files for cerebrum, unless the number of files is above 4, when a
    seperate directory should be created.

  usr/share/cerebrum/data:
    A number of subdirectories for various backends

TODO:
  comment on template config files (logging.ini, config.dat, cereconf.py)

To install python modules in standard locations, and cerebrum files
under /cerebrum, run like:
 python setup.py install install_data --install-dir=/cerebrum

To get the files in /etc under /cerebrum/etc, add:
 --root=/cerebrum

To build dist file:
 python setup.py sdist

"""
import os
import subprocess
import sys
import pwd
from glob import glob

from distutils import sysconfig
from distutils.command import install_data
from distutils.core import setup, Command
from distutils.util import change_root, convert_path
from setuptools.command.develop import develop
import Cerebrum


#
# Which user should own the installed files
#
cerebrum_user = "cerebrum"

#
# Install directory structure, or,
# where things should be located, Relative to --prefix or root
#
prefix = './'  # Is this 'safeguard' really neccessary?
sharedir = prefix + 'share'
sbindir = prefix + 'sbin'
bindir = prefix + 'bin'
sysconfdir = prefix + os.path.join('etc', 'cerebrum')
logdir = prefix + os.path.join('var', 'log', 'cerebrum')
locale_dir = os.path.join(sys.prefix, 'share', 'locale')

#
# Files that never should overwite installed versions.
# Example: Template config files, like cereconf.py, logging.ini
#
do_not_replace = ('design/cereconf.py',
                  'servers/bofhd/config.dat',
                  'design/logging.ini', )


def _execute_wrapper(*args):
    subprocess.call(args)


class LocaleInstaller(Command):
    """ Abstract install class for building locales. """

    description = 'Compile and install locales'
    user_options = [
        ('locale-dir=', None, "Install directory for locale files."),
    ]

    def initialize_options(self):
        self.locale_dir = locale_dir

    def finalize_options(self):
        pass

    def run(self):
        pass

    def _install_locale_namespace(self, namespace):
        # go through all top dirs in 'locales/'
        lang_base = os.path.join(os.path.dirname(__file__), 'locales')
        mo_basename = os.path.extsep.join((namespace, 'mo'))
        po_basename = os.path.extsep.join((namespace, 'po'))
        for lang_dir in os.listdir(lang_base):
            # Source dir
            messages_dir = os.path.join(lang_base, lang_dir, 'LC_MESSAGES')

            # the abs. path for this specific language
            lang_path = os.path.join(self.locale_dir, lang_dir, 'LC_MESSAGES')
            if not os.path.exists(lang_path):
                # create the path if it doesn't exist
                os.makedirs(lang_path)

            mo_file = os.path.join(messages_dir, mo_basename)
            if os.path.isfile(mo_file):
                # .mo file exists for this language. Use it!
                self.copy_file(mo_file, lang_path)
                continue
            # no .mo file found. See is there is a .po file
            po_file = os.path.join(messages_dir, po_basename)
            if os.path.isfile(po_file):
                # ... then compile the .po file into .mo file
                self.execute(_execute_wrapper,
                             ('msgfmt',
                              '-o',
                              os.path.join(lang_path, mo_basename),
                              po_file))
                continue
            self.warn('No locale for {!r} in language {!r}'.format(namespace,
                                                                   lang_dir))


class CerebrumDevelop(develop):
    def run(self):
        self.run_command('install_locales')


class CerebrumLocales(LocaleInstaller):
    def run(self):
        self._install_locale_namespace('cerebrum')


class my_install_data(install_data.install_data, object):
    """ Custom install_data class. """

    def finalize_options(self):
        """ Prepare my_install_data options.

        This function adds wildcard support for filenames.
        It also generates the cerebrum_path.py file (allthough this should
        probably be performed by the run() method...

        """
        super(my_install_data, self).finalize_options()

        # Wildcard lookup.
        #
        # We remove filenames with '*', and expand to (and add) all files that
        # match the pattern.
        #
        # ldata - the location-dict from data_files
        # fdata - the (filename, mode) tuple from data_files
        #
        for ldata, fdata in self.data_files:
            i = 0
            while i < len(fdata):
                if fdata[i][0].find('*') > -1:
                    for e in glob(fdata[i][0]):
                        fdata.append((e, fdata[i][1]))
                    fdata.pop(i)
                    i -= 1
                i += 1

        # Remove files from data_files already exists in the target location,
        # and are in the `do_not_replace' list.
        for ldata, fdata in self.data_files:
            path = os.path.realpath(os.path.join(self.install_dir,
                                                 ldata.get('path')))
            for fn, mode in fdata[:]:
                # We iterate through a copy, so that fdata.remove() won't break
                # the loop
                if fn in do_not_replace and os.path.exists(
                        os.path.join(path, os.path.basename(fn))):
                    print "Ignoring '%s', already exists in '%s'" % (
                        fn, path)
                    fdata.remove((fn, mode))

        # cerebrum_path.py.in -> cerebrum_path.py
        # TODO/FIXME: We should do this smarter. If sysconfig.get_python_lib()
        # is writeable by the user, we should try to install the
        # cerebrum_path.py file. uid != null is not a good test.
        #
        # This is all very hacky and weird
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
            self.run_command('install_locales')

#
# Files to install
#
sbin_files = [
    ('servers/job_runner/job_runner.py', 0755),
    ('makedb.py', 0755),
    ('servers/bofhd/bofhd.py', 0755),
    ('servers/event/exchange_daemon.py', 0755),
    ('servers/event/cim_daemon.py', 0755),
    ('servers/event/event_publisher.py', 0755),
    ('servers/cis/SoapIndividuationServer.py', 0755),
    ('servers/cis/SoapPostmasterServer.py', 0755),
    ('servers/cis/SoapGroupServer.py', 0755),
    ('servers/cis/SoapServer.py', 0755),
    ('consumers/no/uio/tiny_scheduler.py', 0755),
    ('consumers/no/uio/consumer_sap.py', 0755),
    ('consumers/no/uio/consumer_enforce_forward_policy.py', 0755)
]

bin_files = []

share_files = []

data_files = [
    ({'path': "%s/cerebrum/design" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('design/*.sql', 0644), ]),
    ({'path': "%s/cerebrum/doc" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('design/cerebrum-core.dia', 0644),
      ('design/cerebrum-core.html', 0644),
      ('design/adminprotocol.html', 0644),
      ('README.md', 0644),
      ('COPYING', 0644), ]),
    ({'path': sbindir,
      'owner': cerebrum_user,
      'mode': 0755}, sbin_files),
    ({'path': "%s/cerebrum/contrib" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/audit" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/audit/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/exchange" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/exchange/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/dns-info" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/dns-info/*.py', 0755)]),
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
    ({'path': "%s/cerebrum/contrib/no/Indigo" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/Indigo/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/statistics" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/statistics/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/statistics/templates/" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/statistics/templates/*.html', 0644)]),
    ({'path': "%s/cerebrum/contrib/no/uio" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uio/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uio/printer_quota/" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uio/printer_quota/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/hia" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/hia/*.py', 0755)]),
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
    ({'path': "%s/cerebrum/contrib/tsd" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/tsd/*.py', 0755)]),
    ({'path': bindir,
      'owner': cerebrum_user,
      'mode': 0755}, bin_files),
    ({'path': sysconfdir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('design/cereconf.py', 0644),
      ('servers/bofhd/config.dat', 0644),
      ('design/logging.ini', 0644), ]),
    ({'path': logdir,
      'owner': cerebrum_user,
      'mode': 0750},
     []),
    ({'path': "%s/cerebrum/data" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     []),
]


setup(
    name="Cerebrum",
    version=Cerebrum.__version__,
    url="https://bitbucket.usit.uio.no/scm/crb/cerebrum.git",
    maintainer="Cerebrum Developers",
    maintainer_email="do.we@want.this.here",
    description="Cerebrum is a user-administration system",
    license="GPL",
    long_description=("System for semi-automatic user "
                      "administration in a heterogenous "
                      "environment"),
    platforms = "UNIX",
    # NOTE: all scripts ends up in the same dir!
    # scripts = ['contrib/no/uio/import_FS.py',
    # 'contrib/generate_nismaps.py'],
    packages=[
        'Cerebrum',
        'Cerebrum/extlib',
        'Cerebrum/extlib/Plex',
        'Cerebrum/logutils',
        'Cerebrum/modules',
        'Cerebrum/modules/ad',
        'Cerebrum/modules/ad2',
        'Cerebrum/modules/audit',
        'Cerebrum/modules/statsd',
        'Cerebrum/modules/celery_tasks',
        'Cerebrum/modules/celery_tasks/apps',
        'Cerebrum/modules/consent',
        'Cerebrum/modules/cim',
        'Cerebrum/modules/dns',
        'Cerebrum/modules/event',
        'Cerebrum/modules/event/clients',
        'Cerebrum/modules/event_consumer',
        'Cerebrum/modules/event_publisher',
        'Cerebrum/modules/exchange',
        'Cerebrum/modules/feide',
        'Cerebrum/modules/gpg',
        'Cerebrum/modules/hostpolicy',
        'Cerebrum/modules/bofhd',
        'Cerebrum/modules/guest',
        'Cerebrum/modules/job_runner',
        'Cerebrum/modules/no',
        'Cerebrum/modules/no/Indigo',
        'Cerebrum/modules/no/uio',
        'Cerebrum/modules/no/uio/printer_quota',
        'Cerebrum/modules/no/uio/voip',
        'Cerebrum/modules/no/uio/AutoStud',
        'Cerebrum/modules/no/uio/exchange',
        'Cerebrum/modules/no/uio/SoapAPI',
        'Cerebrum/modules/no/hia',
        'Cerebrum/modules/no/hia/exchange',
        'Cerebrum/modules/no/hiof',
        'Cerebrum/modules/no/nmh',
        'Cerebrum/modules/no/nih',
        'Cerebrum/modules/password_notifier',
        'Cerebrum/modules/password_generator',
        'Cerebrum/modules/posix',
        'Cerebrum/modules/pwcheck',
        'Cerebrum/modules/printutils',
        'Cerebrum/modules/synctools',
        'Cerebrum/modules/synctools/ad_ldap',
        'Cerebrum/modules/synctools/clients',
        'Cerebrum/modules/tsd',
        'Cerebrum/modules/templates',
        'Cerebrum/modules/xmlutils',
        'Cerebrum/modules/abcenterprise',
        'Cerebrum/modules/process_entity',
        'Cerebrum/lib',
        'Cerebrum/modules/LMS',
        'Cerebrum/modules/virthome',
        'Cerebrum/modules/cis',
        'Cerebrum/modules/virtualgroup',
        'Cerebrum/config',
        'Cerebrum/database',
        'Cerebrum/utils',
        'Cerebrum/rest',
        'Cerebrum/rest/api',
        'Cerebrum/rest/api/v1',
    ],
    # options override --prefix
    # options = {'install_data': {'root' : '/foo/bar',  # prefix on slash
    # 'install_dir': '/dddddddd' # prefix on no-slash
    #                            }},
    # data_files doesn't seem to handle wildcards
    data_files=data_files,

    # Overridden command classes
    cmdclass={
        'install_data': my_install_data,
        'install_locales': CerebrumLocales,
        'develop': CerebrumDevelop,
    }
)

setup(
    name='ClientAPI',
    packages=['ClientAPI'],
    cmdclass={
        'install_locales': LocaleInstaller,
    }
)
