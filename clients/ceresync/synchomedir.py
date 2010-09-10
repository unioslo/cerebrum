#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
#
# This filebackend is part of Cerebrum.
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

import os, sys
import subprocess
import unittest

from ceresync import config
from ceresync import syncws as sync
from ceresync.syncws import Homedir

log = config.logger

class InconsistencyError(Exception):
    pass

class HomedirSync(object):
    statuses = [
        'archived',
        'create_failed',
        'not_created',
        'on_disk',
        'pending_restore'
    ]

    def __init__(self, hostname, dryrun, no_report, retry_failed,
                 setup_script, testing_options, root):
        self.cerews = sync.Sync()
        self.hostname = hostname
        self.dryrun = dryrun
        self.no_report = no_report
        self.retry_failed = retry_failed
        self.setup_script = setup_script
        self.testing_options = testing_options
        self.root = root

    def lint_homedirs(self):
        status='on_disk'
        print "Status %s in cerebrum, but does not exist on disk:" % (status,)
        homedirs = self._get_homedirs(status)
        for homedir in homedirs:
            path = self._get_path(homedir)
            if not os.path.isdir(path):
                print path

        status='not_created'
        print "Status %s in cerebrum, but does exist on disk:" % (status,)
        for homedir in self._get_homedirs(status):
            path = self._get_path(homedir)
            if os.path.isdir(path):
                print path

    def show_homedirs(self):
        for status in self.statuses:
            print "Status: %s" % (status,)
            for homedir in self._get_homedirs(status):
                path = self._get_path(homedir)
                print "  %-9s %s" % (homedir.account_name, path)

    def make_homedirs(self):
        status = self._get_create_status()
        for homedir in self._get_homedirs(status):
            self._make_homedir(homedir)

    def delete_homedirs(self):
        for homedir in self._get_homedirs("on_disk", 550):
            path = self._get_path(homedir)
            print "  %-9s %s" % (homedir.account_name, path)
            #XXX

    def _get_path(self, homedir):
        return self._chroot_path(self.root, homedir.homedir)

    def _get_homedirs(self, status, expired_by=None):
        testing_options = self._get_testing_options(status)
        return self.cerews.get_homedirs(status, self.hostname,
                                        expired_by=expired_by,
                                        **testing_options)

    def _get_create_status(self):
        if self.retry_failed:
            return 'create_failed'
        return 'not_created'

    def _make_homedir(self, homedir):
        path = self._get_path(homedir)
        log.info("Making homedir for %s: %s",
            homedir.account_name, path)

        result_status = 'on_disk'
        try:
            self._run_create_script(path, homedir)
            log.debug("Created homedir %s for %s" % (
                path, homedir.account_name))
        except Exception, e:
            result_status = 'create_failed'
            log.debug("Failed creating homedir for %s: %s" % (
                homedir.account_name, e))

        log.debug("Setting status for homedir for %s to %s",
            homedir.account_name, result_status)
        self._set_homedir_status(homedir, result_status)

    def _chroot_path(self, root, path):
        return os.path.join(root, path.lstrip("/"))

    def _get_testing_options(self, status):
        in_file = '%s_homedir_xml_in' % status
        out_file = '%s_homedir_xml_out' % status
        return {
            'homedir_xml_in': self.testing_options.get(in_file),
            'homedir_xml_out': self.testing_options.get(out_file),
        }

    def _run_create_script(self, path, homedir):
        if self.dryrun:
            return

        cmd = (
            str(self.setup_script),
            str(homedir.posix_uid),
            str(homedir.posix_gid),
            str(path),
            str(homedir.account_name),
        )

        log.debug("Running create script: %s", cmd)

        returncode = self._do_run_create_script(cmd)
        if returncode != 0:
            raise Exception("\"%s\" failed" % self.setup_script)

    def _do_run_create_script(self, cmd):
        return subprocess.call(cmd)

    def _set_homedir_status(self, homedir, status):
        if self.no_report or self.dryrun:
            return

        self._do_set_homedir_status(homedir, status)

    def _do_set_homedir_status(self, homedir, status):
        self.cerews.set_homedir_status(homedir.homedir_id, status)

    def _homedir_exists(self, homedir):
        return os.path.isdir(homedir.homedir)

class TestableHomedirSync(HomedirSync):
    can_create = True

    def __init__(self, *args, **kwargs):
        self.retry_failed = False
        self.root = ""
        self.no_report = False
        self.dryrun = False
        self.setup_script = "mock_setup.py"

    def _get_homedirs(self, status):
        return self._get_or_create_mock_homedirs()

    def _do_run_create_script(self, cmd):
        if self.can_create: return 0
        return 1

    def _do_set_homedir_status(self, homedir, status):
        homedir.status = status

    def _get_or_create_mock_homedirs(self):
        homedirs = getattr(self, 'homedirs', None)
        if not homedirs:
            homedirs = self.homedirs = self._create_mock_homedirs()
        return homedirs

    def _create_mock_homedirs(self):
        homedirs = []
        for i in range(10):
            homedir = self._create_mock_homedir(i)
            homedirs.append(homedir)
        return homedirs

    def _create_mock_homedir(self, i):
        obj = lambda: 0
        obj._attrs = {}
        homedir = Homedir(obj)
        homedir.homedir_id = i
        homedir.account_name = "user_%s" % i
        homedir.home = homedir.account_name
        homedir.disk_path = "/home"
        homedir.homedir = os.path.join(homedir.disk_path, homedir.home)
        homedir.posix_uid = i
        homedir.posix_gid = i
        return homedir

class HomedirSyncTest(unittest.TestCase):
    def test_that_sync_tries_to_change_status_to_on_disk_if_setup_succeeds(self):
        sync = TestableHomedirSync()
        sync.can_create = True

        sync.make_homedirs()

        homedirs = sync.homedirs
        self.assertEqual(10, len(homedirs))
        for homedir in homedirs:
            self.assertEqual('on_disk', homedir.status)

    def test_that_sync_tries_to_change_status_to_create_failed_if_setup_fails(self):
        sync = TestableHomedirSync()
        sync.can_create = False

        sync.make_homedirs()

        homedirs = sync.homedirs
        self.assertEqual(10, len(homedirs))
        for homedir in homedirs:
            self.assertEqual('create_failed', homedir.status)

def get_option_dict(config):
    return {
        'dryrun': config.getboolean('args', 'dryrun'),
        'no_report': config.getboolean('args', 'no_report'),
        'retry_failed': config.getboolean('args', 'retry_failed'),
        'setup_script': get_setup_script(config),
        'hostname': get_hostname(config),
        'root': config.get('args', 'root', default="/"),
    }

def get_testing_option_dict(config):
    data = {}
    for status in HomedirSync.statuses:
        data.update({
            '%s_homedir_xml_in' % status: config.get(
                'args', '%s_homedir_xml_in' % status, allow_none=True),
            '%s_homedir_xml_out' % status: config.get(
                'args', '%s_homedir_xml_out' % status, allow_none=True),
        })
    return data

def get_testing_args():
    args = []
    for status in HomedirSync.statuses:
        args.extend([
            config.make_option(
                "--load-%s-homedir-xml" % status,
                action="store",
                dest="%s_homedir_xml_in" % status,
                help="Load homedir data from specified file"),
            config.make_option(
                "--save-%s-homedir-xml" % status,
                action="store",
                dest="%s_homedir_xml_out" % status,
                help="Save homedir data to specified file"),
        ])
    return args

def get_hostname(config):
    hostname = config.get('homedir', 'hostname', default=os.uname()[1])
    return config.get('args', 'hostname', default=hostname) # Allow command-line override

def get_setup_script(config):
    setup_script = config.get('homedir', 'setup_script', default="/local/skel/bdb-setup")
    return config.get('args', 'setup_script', default=setup_script) # Allow command-line override

def main():
    config.parse_args([
        config.make_option(
            "-H", "--hostname",
            action="store",
            type="string",
            help="pretend to be file server HOSTNAME"),
        config.make_option(
            "-S", "--setup_script",
            action="store",
            type="string",
            help="use the specified setup_script.  Overrides the config file"),
        config.make_option(
            "-n", "--no-report",
            action="store_true",
            default=False,
            help="don't report back to cerebrum"),
        config.make_option(
            "-d", "--dryrun",
            action="store_true",
            default=False,
            help="don't create directories, and don't report back to cerebrum (implies --no-report)"),
        config.make_option(
            "--root",
            action="store",
            type="string",
            help="Create homedirs under the specified root.  Default is /"),
        config.make_option("-r", "--retry-failed",
            action="store_true",
            default=False,
            help="retry homedirs with creation failed status"),
        config.make_option(
            "--delete",
            action="store_true",
            default=False,
            help="delete expired homedirs"),
        config.make_option(
            "-s", "--show-db",
            action="store_true",
            default=False,
            help="only show database contents"),
        config.make_option(
            "-l", "--lint",
            action="store_true",
            default=False,
            help="only warn about inconsistencies between Cerebrum and the filesystem"),
        config.make_option(
            "--run-tests",
            action="store_true",
            default=False,
            help="run unit tests"),
    ] + get_testing_args())

    if config.getboolean('args', 'run_tests'):
        sys.argv.remove("--run-tests")
        return unittest.main()

    options = get_option_dict(config)
    options['testing_options'] = get_testing_option_dict(config)

    sync = HomedirSync(**options)
    if config.getboolean('args', 'lint'):
        sync.lint_homedirs()
    elif config.getboolean('args', 'show_db'):
        sync.show_homedirs()
    elif config.getboolean('args', 'delete'):
        sync.delete_homedirs()
    else:
        sync.make_homedirs()

if __name__ == "__main__":
    main()
