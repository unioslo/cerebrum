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

from ceresync import config
from ceresync import syncws as sync

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
        for homedir in self._get_homedirs(status):
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

    def _get_path(self, homedir):
        return self._root_path(homedir.homedir)

    def _get_homedirs(self, status):
        testing_options = self._get_testing_options(status)
        return self.cerews.get_homedirs(status, self.hostname, **testing_options)

    def _get_create_status(self):
        if self.retry_failed:
            return 'create_failed'
        return 'not_created'

    def _make_homedir(self, homedir):
        path = self._get_path(homedir)
        log.debug("Creating homedir for %s: %s",
            homedir.account_name, path)

        result_status = 'on_disk'
        if not os.path.isdir(path):
            try:
                self._run_create_script(path, homedir)
                log.info("Created homedir %s for %s" % (
                    path, homedir.account_name))
            except Exception, e:
                result_status = 'create_failed'
                log.info("Failed creating homedir for %s: %s" % (
                    homedir.account_name, e))
        else:
            log.debug("Homedir %s for %s already exists" % (
                path, homedir.account_name))

        log.info("Setting status for homedir for %s to %s",
            homedir.account_name, result_status)
        self._set_homedir_status(homedir, result_status)

    def _root_path(self, path):
        return os.path.join(self.root, path.lstrip("/"))

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

        log.info("Running create script: %s", cmd)

        returncode = subprocess.call(cmd)
        if returncode != 0:
            raise Exception("\"%s\" failed" % self.setup_script)

    def _set_homedir_status(self, homedir, status):
        if self.no_report or self.dryrun:
            return

        self._verify_consistency(homedir, status)
        self.cerews.set_homedir_status(homedir.homedir_id, status)

    def _verify_consistency(self, homedir, status):
        if status == "on_disk" and not self._homedir_exists(homedir):
            raise InconsistencyError(
                "Would report non-existing homedir as %s: %s" % (
                    status, homedir.homedir))

        if status == "create_failed" and self._homedir_exists(homedir):
            raise InconsistencyError(
                "Would report existing homedir as %s: %s" % (
                    status, homedir.homedir))

    def _homedir_exists(self, homedir):
        return os.path.isdir(homedir.homedir)

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
    hostname = config.get('homedir', 'hostname', default=os.uname()[1]),
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
            help="pretend to be file server HOSTNAME"),
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
            "-s", "--show-db",
            action="store_true",
            default=False,
            help="only show database contents"),
        config.make_option(
            "-l", "--lint",
            action="store_true",
            default=False,
            help="only warn about inconsistencies between Cerebrum and the filesystem"),
    ] + get_testing_args())

    options = get_option_dict(config)
    options['testing_options'] = get_testing_option_dict(config)

    sync = HomedirSync(**options)
    if config.getboolean('args', 'lint'):
        sync.lint_homedirs()
    elif config.getboolean('args', 'show_db'):
        sync.show_homedirs()
    else:
        sync.make_homedirs()

if __name__ == "__main__":
    main()
