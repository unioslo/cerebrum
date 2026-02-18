# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
Wrapper module for running reguser commands

Reguser is a collection of scripts for managing user home directories on a home
directriy management host.

More info:

- `Scripts <https://github.uio.no/IT-OPS/reguser>`_
- `Docs <https://www.uio.no/tjenester/it/maskin/linux/hjelp/server/home.html>`_


Configuration
=============
The following settings from :mod:`cereconf` applies to this modoule:

``ARCHIVE_USER_SERVER``
    An ssh connection string to use for commands.

    If set to ``[<user>@]<hostname>[:<port>]``, reguser commands will run on
    that host, using ``ssh``.  If unset, commands will run locally.

``CREATE_USER_SCRIPT``
    Location of the reguser ``create_user`` script.

``MVUSER_SCRIPT``
    Location of the reguser ``move_user`` script.

``RMUSER_SCRIPT``
    Location of the reguser ``delete_user`` script.

Script locations must be the full path to the script.  If
``ARCHIVE_USER_SERVER`` is set, this must be the full path on that host.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

import cereconf

from Cerebrum.utils import reprutils
from Cerebrum.utils import subproc

logger = logging.getLogger(__name__)

SSH_CMD = "/usr/bin/ssh"
SUDO_CMD = "sudo"


def _str_arg(value, allow_empty=False):
    """ normalize string command argument. """
    if not isinstance(value, six.string_types):
        raise ValueError("invalid argument: " + repr(value))
    value = value.strip()
    if not allow_empty and not value:
        raise ValueError("invalid argument: " + repr(value))
    return value


def _int_arg(value):
    """ normalize integer command argument. """
    if not isinstance(value, int):
        value = int(value)
    return _str_arg(format(value, 'd'))


class ReguserCommands(reprutils.ReprEvalMixin):
    """
    Handler/wrapper for running reguser commands.

    This class can archive, create, or restore user homedirs using commands
    from the reguser script package.  These commands are normally executed
    on a remote management host using ssh.

    It has a dryrun mode that prevents running any actual commands.
    """
    repr_module = False
    repr_kwargs = ("dryrun", "remote_dryrun")

    ssh_command = "/usr/bin/ssh"
    sudo_command = "sudo"

    def __init__(self, dryrun=True, remote_dryrun=True, remote_debug=True):
        """
        :param str dryrun: don't actually run any commands
        :param str remote_dryrun: add "--dryrun" argument to commands
        :param str debug: add "--debug" argument to commands
        """
        self.dryrun = dryrun
        self.remote_dryrun = remote_dryrun
        self.remote_debug = remote_debug

    @property
    def remote_host(self):
        return getattr(cereconf, "ARCHIVE_USER_SERVER", None)

    def _run_command(self, cmd):
        if self.dryrun:
            logger.info("dryrun: %s", subproc.format_command(cmd))
            return True
        result_t = subproc.run(cmd, retval=(subproc.RETURN_RC,))
        return not result_t[0]

    def _add_common_args(self, cmd):
        if self.remote_debug:
            cmd.append("--debug")
        if self.remote_dryrun:
            cmd.append("--dryrun")
        if self.remote_host:
            cmd = [self.ssh_command, self.remote_host] + cmd
        return cmd

    @property
    def reguser_create_user(self):
        return cereconf.CREATE_USER_SCRIPT

    def _create_user_cmd(self, username, homedir, uid, gid, gecos):
        return self._add_common_args([
            self.sudo_command, self.reguser_create_user,
            '--username', _str_arg(username),
            '--homedir', _str_arg(homedir),
            '--uid', _int_arg(uid),
            '--gid', _int_arg(gid),
            '--gecos', _str_arg(gecos, allow_empty=True),
        ])

    def create_user(self, username, homedir, uid, gid, gecos):
        """
        Create a user homedir.

        :param str username: username of the homedir owner
        :param str homedir: the homedir to create
        :param str uid: posix uid of the homedir owner
        :param str gid: posix gid of default filegroup of the homedir owner
        :param str gecos: gecos of the homedir owner
        """
        logger.debug("%s.create_user(%s, %s, %s, %s, %s)",
                     repr(self), repr(username), repr(homedir), repr(uid),
                     repr(gid), repr(gecos))
        return self._run_command(
            self._create_user_cmd(username, homedir, uid, gid, gecos)
        )

    @property
    def reguser_delete_user(self):
        return cereconf.RMUSER_SCRIPT

    def _delete_user_cmd(self, username, deleted_by, homedir, generation):
        return self._add_common_args([
            self.sudo_command, self.reguser_delete_user,
            "--username", _str_arg(username),
            "--deleted-by", _str_arg(deleted_by),
            "--homedir", _str_arg(homedir),
            "--generation", _int_arg(generation),
        ])

    def delete_user(self, username, deleted_by, homedir, generation):
        """
        Delete a user homedir.

        :param str username: username of the homedir owner
        :param str deleted_by: username of the operator that runs this command
        :param str homedir: the homedir to delete
        :param int generation: a delete counter for this user/homedir
        """
        logger.debug("%s.delete_user(%s, %s, %s, %s)",
                     repr(self), repr(username), repr(deleted_by),
                     repr(homedir), repr(generation))
        return self._run_command(
            self._delete_user_cmd(username, deleted_by, homedir, generation)
        )

    @property
    def reguser_move_user(self):
        return cereconf.MVUSER_SCRIPT

    def _move_user_cmd(self, user, uid, gid, old_disk, new_disk, operator):
        return self._add_common_args([
            self.sudo_command, self.reguser_move_user,
            "--user", _str_arg(user),
            "--uid", _int_arg(uid),
            "--gid", _int_arg(gid),
            "--old-disk", _str_arg(old_disk),
            "--new-disk", _str_arg(new_disk),
            "--operator", _str_arg(operator),
        ])

    def move_user(self, user, uid, gid, old_disk, new_disk, operator):
        """
        Move a user homedir.

        :param str user: username of the homedir owner
        :param str uid: posix uid of the homedir owner
        :param str gid: posix gid of default filegroup of the homedir owner
        :param str old_disk: current disk of the homedir
        :param str new_disk: new disk for the homedir
        :param str operator: username of the operator that runs this command
        """
        logger.debug("%s.move_user(%s, %s, %s, %s, %s, %s)",
                     repr(self), repr(user), repr(uid), repr(gid),
                     repr(old_disk), repr(new_disk), repr(operator))
        return self._run_command(
            self._move_user_cmd(user, uid, gid, old_disk, new_disk, operator)
        )
