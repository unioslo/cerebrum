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
    dryrun = True

    def add(self, account, *args, **kwargs):
        super(Account, self).add(account)

    def close(self, *args, **kwargs):
        super(Account, self).close()

    def format(self, account):
        if not account.posix_uid:
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

class Person(StdoutFile):
    def format(self, person):
        res = "%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s\n" % (
            self.wash(person.id),
            self.wash(person.first_name),
            self.wash(person.last_name),
            self.wash(person.display_name),
            self.wash(person.full_name),
            self.wash(person.primary_account_name),
            self.wash(person.address_text),
            self.wash(person.traits),
            self.wash(person.city),
            self.wash(person.primary_account),
            self.wash(person.affiliations),
            self.wash(person.type),
            self.wash(person.email),
            self.wash(person.nin),
            self.wash(person.primary_account_password),
            self.wash(person.phone),
            self.wash(person.quarantines),
            self.wash(person.export_id),
            self.wash(person.url),
            self.wash(person.birth_date),
            self.wash(person.work_title),
            self.wash(person.postal_number))
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

class OU(StdoutFile):
    def format(self, ou):
        res = "%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s:%s\n" % (
            self.wash(ou.id),
            self.wash(ou.stedkode),
            self.wash(ou.name),
            self.wash(ou.acronym),
            self.wash(ou.short_name),
            self.wash(ou.sort_name),
            self.wash(ou.display_name),
            self.wash(ou.phone),
            self.wash(ou.email),
            self.wash(ou.url),
            self.wash(ou.post_address),
            self.wash(ou.parent_id),
            self.wash(ou.parent_stedkode),
            self.wash(ou.quarantines))
        if self.unicode:
            return res.encode(self.encoding)
        else:
            return res

class Group(StdoutFile, filebackend.GroupFile):
    pass

class Alias(StdoutFile, filebackend.AliasFile):
    pass

class PasswdWithHash(StdoutFile, filebackend.PasswdFileCryptHash):
    pass

class Samba(StdoutFile, filebackend.SambaFile):
    pass
