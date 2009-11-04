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

from ceresync import config
from ceresync import syncws as sync

log = config.logger

class HomedirSync(object):
    statuses = [
        'archived',
        'create_failed',
        'not_created',
        'on_disk',
        'pending_restore'
    ]

    def __init__(self, hostname, show_db, lint, dryrun, no_report,
                 retry_failed, setup_script, testing_options, root):
        self.cerews = sync.Sync()
        self.hostname = hostname
        self.show_db = show_db
        self.lint = lint
        self.dryrun = dryrun
        self.no_report = no_report
        self.retry_failed = retry_failed
        self.setup_script = setup_script
        self.testing_options = testing_options
        self.root = root

    def execute(self):
        if self.lint:
            self.lint_homedirs()
        elif self.show_db:
            self.show_homedirs()
        else:
            self.make_homedirs()

    def lint_homedirs(self):
        status='on_disk'
        print "Status %s in cerebrum, but does not exist on disk:" % (status,)
        for homedir in self.get_homedirs(status):
            path = self.get_path(homedir)
            if not os.path.isdir(path):
                print path

        status='not_created'
        print "Status %s in cerebrum, but does exist on disk:" % (status,)
        for homedir in self.get_homedirs(status):
            path = self.get_path(homedir)
            if os.path.isdir(path):
                print path

    def show_homedirs(self):
        for status in self.statuses:
            print "Status: %s" % (status,)
            for homedir in self.get_homedirs(status):
                path = self.get_path(homedir)
                print "  %-9s %s" % (homedir.account_name, path)

    def make_homedirs(self):
        status = self.get_create_status()
        for homedir in self.get_homedirs(status):
            self.make_homedir(homedir)

    def get_homedirs(self, status):
        testing_options = self.get_testing_options(status)
        return self.cerews.get_homedirs(status, self.hostname, **testing_options)

    def get_create_status(self):
        if self.retry_failed:
            return 'create_failed'
        return 'not_created'

    def make_homedir(self, homedir):
        path = self.get_path(homedir)
        log.debug("Creating homedir for %s: %s",
            homedir.account_name, path)

        try:
            if not os.path.isdir(path):
                self.create_homedir(path, homedir)
                self.run_setup_script(path, homedir)
                log.info("Created homedir %s for %s" % (
                    path, homedir.account_name))
            else:
                log.debug("Homedir %s for %s is ok" % (
                    path, homedir.account_name))
            result_status = 'on_disk'
        except Exception, e:
            log.exception("Failed creating homedir for %s: %s" % (
                homedir.account_name, e))
            result_status= 'create_failed'

        log.info("Setting status for homedir for %s to %s",
            homedir.account_name, result_status)
        self.set_homedir_status(homedir, result_status)

    def get_testing_options(self, status):
        in_file = '%s_homedir_xml_in' % status
        out_file = '%s_homedir_xml_out' % status
        return {
            'homedir_xml_in': self.testing_options.get(in_file),
            'homedir_xml_out': self.testing_options.get(out_file),
        }

    def create_homedir(self, path, homedir):
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            self.create_parent_directory(parent)

        self.create_directory(
            path, homedir.posix_uid, homedir.posix_gid)

    def run_setup_script(self, path, homedir):
        cmd = "echo %s %d %d %s %s" % (
                    self.setup_script, homedir.posix_uid, homedir.posix_gid,
                    path, homedir.account_name)
        log.info("Running setup script: %s", cmd)
        if not self.dryrun:
            r = os.system(cmd)
            if r != 0:
                raise Exception("\"%s\" failed" % self.setup_script)

    def set_homedir_status(self, homedir, status):
        if not self.no_report and not self.dryrun:
            self.cerews.set_homedir_status(homedir.homedir_id, status)

    def create_parent_directory(self, path):
        log.debug("Creating parent dir: %s", path)
        if not self.dryrun:
            os.mkdir(path, 0755)

    def create_directory(self, path, uid, gid):
        log.debug("Creating dir: %s", path)
        if not self.dryrun:
            os.mkdir(path, 0700)
            os.chown(path, uid, gid)

    def get_path(self, homedir):
        return self.root_path(homedir.homedir)

    def root_path(self, path):
        return os.path.join(self.root, path.lstrip("/"))

def get_option_dict(config):
    return {
        'show_db': config.getboolean('args', 'show_db'),
        'lint': config.getboolean('args', 'lint'),
        'dryrun': config.getboolean('args', 'dryrun'),
        'no_report': config.getboolean('args', 'no_report'),
        'retry_failed': config.getboolean('args', 'retry_failed'),
        'setup_script': config.get('homedir', 'setup_script', default="/local/skel/bdb-setup"),
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

def main():
    config.parse_args([
        config.make_option(
            "-H", "--hostname",
            action="store",
            type="string",
            metavar="HOSTNAME",
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
    sync.execute()

if __name__ == "__main__":
    main()
