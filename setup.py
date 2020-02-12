#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
"""
Install script for the Cerebrum scipts and modules.
"""

import os
import pwd
import subprocess
import sys
from distutils.command import install_data
from distutils.core import setup, Command
from distutils.util import change_root, convert_path
from glob import glob

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
bindir = prefix + 'bin'
sbindir = prefix + 'sbin'
default_locale_dir = os.path.join(sys.prefix, 'share', 'locale')


def _execute_wrapper(*args):
    subprocess.call(args)


class LocaleInstaller(Command):
    """Abstract command class for installing gettext locales."""

    description = 'Compile and install locales'
    user_options = [
        ('locale-dir=', None, "Install directory for locale files."),
    ]

    namespaces = tuple()

    def initialize_options(self):
        self.locale_dir = default_locale_dir

    def finalize_options(self):
        pass

    def run(self):
        for namespace in self.namespaces:
            self.announce('Installing locale namespace ' + repr(namespace))
            self._install_locale_namespace(namespace)

    def _install_locale_namespace(self, namespace):
        """
        Builds and installs gettext translations from locales/

        For each language directory in ``locales/*``:

        - If a LC_MESSAGES/<namespace>.mo machine object file exists, it is
          copied directly to the appopriate directory in *locale_dir*.
        - Otherwise, if a LC_MESSAGES/<namespace>.po portable object source
          file exists, it is compiled with *msgfmt* and written to
          *locale_dir*
        """
        # go through all top dirs in 'locales/'
        source_dir = os.path.join(os.path.dirname(__file__), 'locales')
        mo_basename = os.path.extsep.join((namespace, 'mo'))
        po_basename = os.path.extsep.join((namespace, 'po'))
        for lang in os.listdir(source_dir):
            # Source dir
            messages_dir = os.path.join(source_dir, lang, 'LC_MESSAGES')

            # the absolute target path for this specific language
            install_dir = os.path.join(self.locale_dir, lang, 'LC_MESSAGES')
            if not os.path.exists(install_dir):
                # create the path if it doesn't exist
                self.announce('Making locale dir ' + repr(install_dir))
                os.makedirs(install_dir)

            mo_file = os.path.join(messages_dir, mo_basename)
            if os.path.isfile(mo_file):
                # .mo file exists for this language. Use it!
                self.copy_file(mo_file, install_dir)
                continue
            # no .mo file found. See is there is a .po file
            po_file = os.path.join(messages_dir, po_basename)
            if os.path.isfile(po_file):
                # ... then compile the .po file into .mo file
                self.execute(_execute_wrapper,
                             ('msgfmt',
                              '-o',
                              os.path.join(install_dir, mo_basename),
                              po_file))
                continue
            self.warn('Missing locale files for {namespace!r} in '
                      'language {lang!r}'.format(namespace=namespace,
                                                 lang=lang))


class CerebrumLocales(LocaleInstaller):
    """
    Build and install gettext locales.
    """
    namespaces = ('cerebrum', )


class CerebrumData(install_data.install_data, object):
    """
    Custom class to install files from the data_files argument to setup().

    The class adds support for:
    - wildcards (* glob pattern) in filenames
    - setting ownership and permissions for both files and directories
    """

    def finalize_options(self):
        super(CerebrumData, self).finalize_options()

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
bin_files = [
    ('clients/job-runner-cli.py', 0755),
]

sbin_files = [
    ('servers/gunicorn-server.py', 0755),
    ('servers/job_runner/job_runner.py', 0755),
    ('makedb.py', 0755),
    ('servers/bofhd/bofhd.py', 0755),
    ('servers/event/exchange_daemon.py', 0755),
    ('servers/event/cim_daemon.py', 0755),
    ('servers/event/event_publisher.py', 0755),
    ('servers/cis/SoapIndividuationServer.py', 0755),
    ('servers/cis/SoapPostmasterServer.py', 0755),
    ('servers/cis/SoapGroupServer.py', 0755),
    ('consumers/no/consumer_affiliations.py', 0755),
    ('consumers/no/uio/tiny_scheduler.py', 0755),
    ('consumers/no/uio/consumer_sap.py', 0755),
    ('consumers/no/uio/consumer_enforce_forward_policy.py', 0755)
]

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
    ({'path': bindir,
      'owner': cerebrum_user,
      'mode': 0755}, bin_files),
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
    ({'path': "%s/cerebrum/contrib/group_admin_email" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/group_admin_email/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/disk-quota" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/disk-quota/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/hostpolicy" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/hostpolicy/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/migrate" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/migrate/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/nis" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/nis/*.py', 0755)]),
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
    ({'path': "%s/cerebrum/contrib/no/uit" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uit/*.py', 0755)]),
    ({'path': "%s/cerebrum/contrib/no/uit/misc/" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/no/uit/misc/*.py', 0755)]),
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
    ({'path': "%s/cerebrum/contrib/utils" % sharedir,
      'owner': cerebrum_user,
      'mode': 0755},
     [('contrib/utils/*.py', 0755)]),
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
    platforms="UNIX",
    # NOTE: all scripts ends up in the same dir!
    # scripts = ['contrib/no/uio/import_FS.py',
    # 'contrib/generate_nismaps.py'],
    packages=[
        'Cerebrum',
        'Cerebrum/auth',
        'Cerebrum/export',
        'Cerebrum/extlib',
        'Cerebrum/extlib/Plex',
        'Cerebrum/group',
        'Cerebrum/logutils',
        'Cerebrum/logutils/mp',
        'Cerebrum/modules',
        'Cerebrum/modules/ad',
        'Cerebrum/modules/ad2',
        'Cerebrum/modules/apikeys',
        'Cerebrum/modules/audit',
        'Cerebrum/modules/statsd',
        'Cerebrum/modules/celery_tasks',
        'Cerebrum/modules/celery_tasks/apps',
        'Cerebrum/modules/consent',
        'Cerebrum/modules/cim',
        'Cerebrum/modules/disk_quota',
        'Cerebrum/modules/dns',
        'Cerebrum/modules/email_report',
        'Cerebrum/modules/entity_expire',
        'Cerebrum/modules/event',
        'Cerebrum/modules/event/clients',
        'Cerebrum/modules/event_consumer',
        'Cerebrum/modules/event_publisher',
        'Cerebrum/modules/exchange',
        'Cerebrum/modules/feide',
        'Cerebrum/modules/fs',
        'Cerebrum/modules/gpg',
        'Cerebrum/modules/hostpolicy',
        'Cerebrum/modules/bofhd',
        'Cerebrum/modules/bofhd_requests',
        'Cerebrum/modules/guest',
        'Cerebrum/modules/job_runner',
        'Cerebrum/modules/no',
        'Cerebrum/modules/no/Indigo',
        'Cerebrum/modules/no/uio',
        'Cerebrum/modules/no/uio/pq_exemption',
        'Cerebrum/modules/no/uio/voip',
        'Cerebrum/modules/no/uio/AutoStud',
        'Cerebrum/modules/no/uio/exchange',
        'Cerebrum/modules/no/hia',
        'Cerebrum/modules/no/hia/exchange',
        'Cerebrum/modules/no/hiof',
        'Cerebrum/modules/no/nmh',
        'Cerebrum/modules/no/nih',
        'Cerebrum/modules/no/uit',
        'Cerebrum/modules/ou_disk_mapping',
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
        'install_data': CerebrumData,
        'install_locales': CerebrumLocales,
    }
)
