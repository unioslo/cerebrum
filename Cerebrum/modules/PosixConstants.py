# coding: utf-8
#
# Copyright 2018 University of Oslo, Norway
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
""" Constant types and common constants for the Posix module. """

from Cerebrum import Constants


class _PosixShellCode(Constants._CerebrumCode):
    """Mappings stored in the posix_shell_code table"""
    _lookup_table = '[:table schema=cerebrum name=posix_shell_code]'
    _lookup_desc_column = 'shell'
    pass


class Constants(Constants.Constants):

    PosixShell = _PosixShellCode

    posix_shell_bash = _PosixShellCode('bash', '/bin/bash')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_false = _PosixShellCode('false', '/bin/false')
    posix_shell_nologin = _PosixShellCode('nologin', '/bin/nologin')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/bin/tcsh')
    posix_shell_zsh = _PosixShellCode('zsh', '/bin/zsh')
