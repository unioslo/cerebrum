# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import os
import sys
from ceresync import errors
import ceresync.backend.file as filebackend

class StdoutFile(filebackend.CLFileBack):
    def begin(self, incr=False, unicode=False, *args, **kwargs):
        self.f = sys.stdout
        self.unicode = unicode

    def close(self):
        pass
    abort = close

class Account(StdoutFile):
    def format(self, account):
        if account.posix_uid is None:
            raise errors.NotPosixError, account.name
        res="%s:%s:%s:%s:%s:%s:%s\n" % (
            self.wash(account.name),
            self.wash(account.passwd or 'x'),
            self.wash(account.posix_uid),
            self.wash(account.posix_gid),
            self.wash(account.gecos),
            self.wash(account.homedir),
            self.wash(account.shell))
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

class Group(StdoutFile, filebackend.GroupFile):
    pass

class Alias(StdoutFile, filebackend.AliasFile):
    pass

class Samba(StdoutFile, filebackend.SambaFile):
    pass
