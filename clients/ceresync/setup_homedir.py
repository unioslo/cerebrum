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

import os, sys, shutil
import getpass, pwd
import logging
import subprocess
import errno

from optparse import OptionParser

from ceresync import config
logger = config.logger

class Homedir(object):
    skeldir = "/local/skel"
    webdir = "/web/folk"
    weblink = "public_html"
    webmode = 0755
    homemode = 0700

    files = [
        '.bash_logout',
        '.bash_profile',
        '.bashrc',
    ]

    def __init__(self, uid, gid, path, username):
        self.undolist = []

        self.uid = int(uid)
        self.gid = int(gid)
        self.path = path
        self.username = username

    def __str__(self):
        return self.path

    def setup(self):
        self._setup_homedir()
        self._setup_webdir()

    def rollback(self):
        logger.debug("Rolling back directory: %s", self.path)

        for fn in self.undolist:
            fn()

    def _setup_homedir(self, path=None):
        """
        If the directory does not exist, create it.  If it already exists
        assert the permission and ownership.  Finally copy the skel files
        to the directory, moving away the old ones if they already exist.
        """
        path = path or self.path

        self._setup_parent_directory(path)

        if not os.path.exists(path):
            self._create_dir(path, self.homemode)
        else:
            self._fix_permissions(path, self.homemode)

        self._fix_owner(path)

        self._copy_skel_files(self.path)

    def _setup_webdir(self):
        webdir = self._get_webdir()
        if not os.path.exists(webdir):
            self._create_dir(webdir, self.webmode)
        else:
            self._fix_permissions(webdir, self.webmode)

        self._fix_owner(webdir)

        self._setup_weblink(self.path)

    def _setup_parent_directory(self, path):
        parent = os.path.dirname(path)
        if not os.path.exists(parent):
            self._create_dir(parent, 0755)
        else:
            self._fix_permissions(parent, 0755)

    def _create_dir(self, path, mode):
        logger.debug("Creating directory: %s", path)
        os.mkdir(path, mode)

        def undo():
            logger.debug("Removing directory: %s", path)
            if os.path.isdir(self.path):
                os.rmdir(self.path)
        self.undolist.insert(0, undo)

    def _fix_owner(self, path):
        if not self._is_superuser():
            logger.warning("Not changing ownership since user is not root.")
            return

        logger.debug("Changing owner and group of path: %s", path)
        os.chown(path, self.uid, self.gid)

    def _fix_permissions(self, path, mode):
        if os.path.isdir(path):
            logger.debug("Changing permissions of directory: %s", path)
        elif os.path.isfile(path):
            logger.debug("Changing permissions of file: %s", path)
        os.chmod(path, mode)

    def _copy_skel_files(self, path):
        for file in self.files:
            source = self._get_skel_file(file)
            target = os.path.join(path, file)

            self._copy(source, target)
            self._fix_owner(target)
            self._fix_permissions(target, 0600)

    def _get_webdir(self):
        return os.path.join(self.webdir, self.username)

    def _remove_symlink(self, name):
        target = os.readlink(name)
        os.unlink(name)

        def undo():
            logger.debug("Restoring symlink from %s to %s", name, target)
            os.symlink(target, name)
        self.undolist.insert(0, undo)


    def _setup_weblink(self, path):
        name = os.path.join(self.path, self.weblink)
        target = self._get_webdir()

        self._set_symlink(target, name)

    def _set_symlink(self, target, name):
        try:
            os.lstat(name)
            self._remove_symlink(name)
        except OSError, e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

        os.symlink(target, name)

        def undo():
            logger.debug("Removing symlink: %s", name)
            os.unlink(name)
        self.undolist.insert(0, undo)

    def _is_superuser(self):
        return os.geteuid() == 0

    def _get_skel_file(self, file):
        return os.path.join(self.skeldir, "usr%s" % file)

    def _copy(self, source, target):
        if os.path.exists(target):
            self._move_to_old(target)

        def undo():
            logger.debug("Removing skel file %s", target)
            os.unlink(target)

        logger.debug("Copying %s to %s", source, target)
        shutil.copy(source, target)
        self.undolist.insert(0, undo)

    def _move_to_old(self, path):
        target = path + ".old"

        i = 0
        while os.path.exists(target):
            target = path + ".old." + str(i)
            i += 1

        def undo():
            logger.debug("Moving %s to %s", target, path)
            os.rename(target, path)
        self.undolist.insert(0, undo)

        logger.debug("Moving %s to %s", path, target)
        os.rename(path, target)

class StudentHomedir(Homedir):
    def setup(self):
        super(StudentHomedir, self).setup()

        self._setup_stud_link()

    def _setup_stud_link(self):
        """
        Create a symbolic link from /home/stud/username to the
        correct homedir.
        """
        link = "/home/stud/%s" % self.username

        self._set_symlink(self.path, link)

class AnsattHomedir(Homedir):
    homemode = 0701
    mhomeroot = "/home/mhome"

    def setup(self):
        super(AnsattHomedir, self).setup()

        m_home = self._get_mailhomedir(self.path)
        self._setup_homedir(m_home)
        self._setup_weblink(m_home)
        self._setup_maildir(m_home)
        self._setup_ubit_profile(m_home)

    def _get_mailhomedir(self, path):
        mpath = path.replace("/home/ahome", "")
        return self.mhomeroot + mpath[1:]

    def _setup_maildir(self, path):
        target = os.path.join(path, "mail")
        if not os.path.exists(target):
            self._create_dir(target, 0700)
        else:
            self._fix_permissions(target, 0700)
        self._fix_owner(target)

    def _setup_ubit_profile(self, path):
        profil = os.path.join(path, ".profil")
        if not os.path.exists(profil):
            self._create_dir(profil, 0700)
        else:
            self._fix_permissions(profil, 0700)
        self._fix_owner(profil)

        target = os.path.join(profil, "ubit")
        if not os.path.exists(target):
            self._create_dir(target, 0700)
        else:
            self._fix_permissions(target, 0700)
        self._fix_owner(target)

def update_args(args):
    if len(args) == 0:
        username = getpass.getuser()
    elif len(args) == 1:
        username = args[0]
    else:
        return args

    _, _, uid, gid, _, path, _ = pwd.getpwnam(username)

    return uid, gid, path, username
    
def verify_args(options, args):
    if len(args) != 4:
        return "incorrect number of arguments"

    if options.student and options.ansatt:
        return "Need either -s or -a.  Not both."

    if not (options.student or options.ansatt):
        return "Need either -s or -a."

    uid, gid, path, username = args

    if int(uid) == 0:
        return "Will not setup a super user."

def setup_logger(options):
    if options.debug:
        logger.setLevel(logging.DEBUG)
    elif options.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARN)

def main():
    usage = "usage: %prog [options] [[uid gid path] username]"
    parser = OptionParser(usage)
    parser.add_option("-s", "--student",
                      action="store_true", dest="student")
    parser.add_option("-a", "--ansatt",
                      action="store_true", dest="ansatt")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug")
    (options, args) = parser.parse_args()

    setup_logger(options)

    args = update_args(args)

    if not (options.student or options.ansatt):
        mode = config.get('homedir', 'mode', None)
        if mode == "student":
            options.student = True
        elif mode == "ansatt":
            options.ansatt = True

    error_message = verify_args(options, args)
    if error_message:
        parser.error(error_message)

    if options.student:
        homedir = StudentHomedir(*args)
    elif options.ansatt:
        homedir = AnsattHomedir(*args)

    try:
        homedir.setup()
    except Exception, e:
        logger.exception("Could not setup home directory: %s", homedir)
        homedir.rollback()
        sys.exit(1)

if __name__ == "__main__":
   main()
