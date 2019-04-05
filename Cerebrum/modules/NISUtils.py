#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2018 University of Oslo, Norway
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

from __future__ import with_statement, unicode_literals

import mx
import sys
import logging
from contextlib import closing
from six import text_type

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import transliterate
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules import PosixGroup
from Cerebrum.Entity import EntityName
from Cerebrum import QuarantineHandler
from Cerebrum.modules.posix.UserExporter import HomedirResolver
from Cerebrum.modules.posix.UserExporter import OwnerResolver
from Cerebrum.modules.posix.UserExporter import UserExporter


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clconst = Factory.get('CLConstants')(db)
logger = logging.getLogger(__name__)
posix_user = Factory.get('PosixUser')(db)
posix_group = PosixGroup.PosixGroup(db)

# The "official" NIS max line length (consisting of key + NUL + value
# + NUL) is 1024; however, some implementations appear to have lower
# limits.
#
# Specifically, on Solaris 9 makedbm(1M) chokes on lines longer than
# 1018 characters.  Other systems might be even more limited.
MAX_LINE_LENGTH = 1000


class NISMapException(Exception):
    pass


class UserSkipQuarantine(NISMapException):
    pass


class NISMapError(NISMapException):
    pass


class BadUsername(NISMapError):
    pass


class NoDisk(NISMapError):
    pass


def join(fields, sep=':'):
    for f in fields:
        if not isinstance(f, text_type):
            raise ValueError("Type of '%r' is not text." % f)
        if f.find(sep) != -1:
            raise ValueError("Separator '%s' present in string '%s'" %
                             (sep, f))
    return sep.join(fields)


class Passwd(object):

    """Simple class for making a passwd map. generate_passwd() will make
    a list of list that translates to the info found in a passwd file."""

    def __init__(self, auth_method=None, spread=None):
        if spread is None:
            raise ValueError('spread is required')
        self.spread = spread
        self.auth_method = auth_method
        self.user_exporter = UserExporter(db)

        self.shells = self.user_exporter.shell_codes()
        self.gid2posix_gid = self.user_exporter.make_posix_gid_cache()
        self.quarantine_cache = self.user_exporter.make_quarantine_cache(
            spread
        )
        self.account2auth_data = self.user_exporter.make_auth_cache(
            spread,
            auth_method
        )

        self.homedirs = HomedirResolver(db, spread)
        self.homedirs.make_home_cache()
        self.owners = OwnerResolver(db)
        self.owners.make_owner_cache()
        self.owners.make_name_cache()

    def process_user(self, row):
        account_id = row['account_id']
        logger.debug('Processing %s', account_id)

        uname, passwd = self.account2auth_data[account_id]
        if posix_user.illegal_name(uname):
            raise BadUsername("Bad username %s" % uname)
        if passwd is None:
            passwd = '*'

        gecos = row['gecos']
        if gecos is None:
            gecos = self.owners.get_name(account_id)
        if gecos is None:
            gecos = uname
        gecos = transliterate.to_iso646_60(gecos)

        shell = self.shells[row['shell']]
        quarantine_types = self.quarantine_cache.get(account_id, None)
        if quarantine_types is not None:
            qh = QuarantineHandler.QuarantineHandler(db, quarantine_types)
            if qh.should_skip():
                raise UserSkipQuarantine
            if qh.is_locked():
                passwd = '*locked'
            qshell = qh.get_shell()
            if qshell is not None:
                shell = qshell

        home = self.homedirs.get_homedir(account_id, allow_no_disk=True)
        if home is None:
            # TBD: Is this good enough?
            home = '/'

        posix_gid = self.gid2posix_gid[row['gid']]
        return [uname, passwd, text_type(row['posix_uid']),
                text_type(posix_gid), gecos,
                text_type(home), shell]

    def generate_passwd(self):
        """Data generating method. returns a list of lists which looks like
        (uname, passwd, uid, gid, gecos, home, shell)."""
        user_iter = posix_user.list_posix_users(
            spread=self.spread,
            filter_expired=True
        )

        user_rows = []
        for row in user_iter:
            # We only want to append users with the selected auth_method.
            # When self.auth_method is None, accounts with MD5-crypt are
            # appended.
            if self.account2auth_data.get(row['account_id'], None):
                try:
                    user_rows.append(self.process_user(row))
                except NISMapError:
                    logger.error("NISMapError", exc_info=1)
                except NISMapException:
                    pass
        return user_rows

    def write_passwd(self, filename, shadow_file, e_o_f=False):
        logger.debug("write_passwd: filename=%r, shadow_file=%r, spread=%r",
                     filename, shadow_file, self.spread)
        f = SimilarSizeWriter(filename, "w", encoding='latin-1')
        f.max_pct_change = 10
        if shadow_file:
            s = SimilarSizeWriter(shadow_file, "w")
            s.max_pct_change = 10

        user_rows = self.generate_passwd()
        for row in user_rows:
            uname = row[0]
            if self.auth_method is None and row[1] != '*locked':
                # substitute pwdcrypt with an 'x' if auth_method is None
                passwd = 'x'
            else:
                passwd = row[1]
            rest = row[2:]
            if shadow_file:
                s.write("%s:%s:::\n" % (uname, passwd))
                if not passwd[0] == '*':
                    passwd = "!!"
            line = join([uname, passwd] + rest)
            f.write(line + "\n")
        if e_o_f:
            f.write('E_O_F\n')
        f.close()
        if shadow_file:
            s.close()


class NISGroupUtil(object):

    """Utility class for the two group classes."""

    def __init__(self, namespace, member_type, group_spread, member_spread,
                 tmp_group_prefix='x'):
        self._entity2name = self._build_entity2name_mapping(namespace)
        self._namecachedtime = mx.DateTime.now()
        self._member_spread = member_spread
        self._member_type = member_type
        self._exported_groups = {}
        self._tmp_group_prefix = tmp_group_prefix
        self._group = Factory.get('Group')(db)
        for row in self._group.search(spread=group_spread):
            self._exported_groups[int(row['group_id'])] = row['name']
        self._num = 0

    def _build_entity2name_mapping(self, namespace):
        ret = {}
        en = EntityName(db)
        logger.debug("list names in %s" % namespace)
        for row in en.list_names(namespace):
            ret[int(row['entity_id'])] = row['entity_name']
        return ret

    def _is_new(self, entity_id):
        """
        Returns true if there is a change log create event for
        entity_id (group or account) since we cached entity names.
        """
        try:
            events = list(db.get_log_events(
                types=(clconst.group_create, clconst.account_create),
                subject_entity=entity_id,
                sdate=self._namecachedtime))
            return bool(events)
        except Exception:
            logger.debug("Checking change log failed: %s", sys.exc_value)
        return False

    def _expand_group(self, gid):
        """Expand a group and all of its members.  Subgroups are
        included regardles of spread, but if they are of a different
        spread, the groups members are expanded.
        """
        ret_groups = set()
        ret_non_groups = set()
        self._group.clear()
        self._group.find(gid)

        # direct members
        for row in self._group.search_members(group_id=gid,
                                              member_spread=self._member_spread,
                                              member_type=self._member_type):
            member_id = int(row["member_id"])
            name = self._entity2name.get(member_id)
            if not name:
                if not self._is_new(member_id):
                    logger.warn("Was %i very recently created?", member_id)
                continue
            ret_non_groups.add(name)

        # subgroups
        for row in self._group.search_members(group_id=gid,
                                              member_type=co.entity_group):
            gid = int(row["member_id"])
            if gid in self._exported_groups:
                ret_groups.add(self._exported_groups[gid])
            else:
                t_g, t_ng = self._expand_group(gid)
                ret_groups.update(t_g)
                ret_non_groups.update(t_ng)

        return ret_groups, ret_non_groups
    # end _expand_groups

    def _make_tmp_name(self, notused):
        while True:
            tmp_gname = "%s%02x" % (self._tmp_group_prefix, self._num)
            self._num += 1
            if tmp_gname not in self._exported_groups:
                return tmp_gname

    def _wrap_line(self, group_name, line, g_separator, is_ng=False):
        """ If the line length (total length of member entity names +
        separators) exceeds MAX_LINE_LENGTH, this method will add the offending
        members to new groups with the same gid. """
        if is_ng:
            delim = ' '
        else:
            delim = ','
        ret = ''
        maxlen = MAX_LINE_LENGTH - (len(group_name) + len(g_separator))
        while len(line) > maxlen:
            tmp_gname = self._make_tmp_name(group_name)
            maxlen = MAX_LINE_LENGTH - (len(tmp_gname) + len(g_separator))
            if len(line) <= maxlen:
                pos = 0
            else:
                pos = line.index(delim, len(line) - maxlen)
            ret += "%s%s%s\n" % (tmp_gname, g_separator,
                                 line[pos:].strip(delim))
            line = line[:pos]
            if is_ng:
                line = "%s %s" % (tmp_gname, line)
        return ret + "%s%s%s\n" % (group_name, g_separator, line)

    def generate_netgroup(self):
        # TODO: What does the "subject to change to a python structure shortly"
        # part mean? Should this be fixed?
        """Returns a list of lists. Data looks like (gname, string of
        groupmembers). This is subject to change to a python structure
        shortly."""
        netgroups = []
        for group_id in self._exported_groups.keys():
            group_name = self._exported_groups[group_id]
            group_members, user_members = map(list,
                                              self._expand_group(group_id))
            # logger.debug("%s -> g=%s, u=%s" % (
            #    group_id, group_members, user_members))
            netgroups.append((group_name,
                              (self._format_members(
                                  group_members, user_members, group_name))))
        return netgroups

    def write_netgroup(self, filename, e_o_f=False):
        logger.debug("generate_netgroup: %s" % filename)

        f = SimilarSizeWriter(filename, "w")
        f.max_pct_change = 5

        netgroups = self.generate_netgroup()
        for group_name, members in netgroups:
            f.write(self._wrap_line(group_name, members, ' ', is_ng=True))
        if e_o_f:
            f.write('E_O_F\n')
        f.close()

    def _filter_illegal_usernames(self, unames, group_name="?"):
        tmp_users = []
        for uname in unames:
            tmp = posix_user.illegal_name(uname)
            if tmp:
                logger.warn("Bad username %s in %s" % (uname, group_name))
            else:
                tmp_users.append(uname)
        return tmp_users


class FileGroup(NISGroupUtil):

    """Class for generating filegroups."""

    def __init__(self, group_spread, member_spread):
        super(FileGroup, self).__init__(
            co.account_namespace, co.entity_account,
            group_spread, member_spread)
        self._group = PosixGroup.PosixGroup(db)
        user_exporter = UserExporter(db)
        gid2posix_gid = user_exporter.make_posix_gid_cache()
        self._account2posix_gid = {}
        for row in posix_user.list_posix_users(filter_expired=True):
            self._account2posix_gid[row['account_id']] = gid2posix_gid[
                row['gid']]
        logger.debug("__init__ done")

    def _make_tmp_name(self, base):
        """ Helper, generates available filegroup entity names for the
        _wrap_line method, based on the original group entity name.
        """
        name = base
        harder = False
        while len(name) > 0:
            i = 0
            if harder:
                name = name[:-1]
            format = "%s%x"
            if len(name) < 7:
                format = "%s%02x"
            while True:
                tname = format % (name, i)
                if len(tname) > 8:
                    break
                if tname not in self._exported_groups:
                    self._exported_groups[tname] = True
                    return tname
                i += 1
            harder = True

    def _expand_group(self, gid):
        ret = set()
        self._group.clear()
        self._group.find(gid)
        members = self._group.search_members(
                group_id=self._group.entity_id,
                indirect_members=True,
                member_type=co.entity_account,
                member_spread=self._member_spread
        )
        for row in members:
            account_id = int(row["member_id"])
            if (self._account2posix_gid.get(account_id, None) ==
                    self._group.posix_gid):
                continue  # Don't include the users primary group
            name = self._entity2name.get(account_id, None)
            if not name:
                if not self._is_new(account_id):
                    logger.warn("Was %i very recently created?" %
                                int(account_id))
                continue
            ret.add(name)
        return set(), ret

    def generate_filegroup(self):
        """Generates a list of lists. An entry looks like (gname, gid,
        [members])."""
        filegroups = []
        groups = self._exported_groups.keys()
        groups.sort()
        for group_id in groups:
            group_name = self._exported_groups[group_id]
            if posix_group.illegal_name(group_name):
                logger.warn("Bad groupname %s" % group_name)
                continue
            try:
                group_members, user_members = map(list,
                                                  self._expand_group(group_id))
            except Errors.NotFoundError:
                logger.warn("Group %s has no GID", group_id)
                continue
            tmp_users = self._filter_illegal_usernames(user_members,
                                                       group_name)

            # logger.debug("%s -> g=%s, u=%s" % (
            #    group_id, group_members, tmp_users))
            filegroups.append((group_name, self._group.posix_gid, tmp_users))
        return filegroups

    def write_filegroup(self, filename, e_o_f=False):
        """Write the filegroups to the given filename.
        If e_o_f is True, "E_O_F" is written after every written file group.
        """
        logger.debug("write_filegroup: %s" % filename)

        with closing(SimilarSizeWriter(filename, "w")) as f:
            f.max_pct_change = 5
            for group_name, gid, users in self.generate_filegroup():
                f.write(self._wrap_line(group_name, ",".join(users), ':*:%i:'
                                        % gid))
            if e_o_f:
                f.write('E_O_F\n')


class UserNetGroup(NISGroupUtil):

    """Class for making standard user netgroups. Most of the code
    resides in NISGroupUtil."""

    def __init__(self, group_spread, member_spread):
        super(UserNetGroup, self).__init__(
            co.account_namespace, co.entity_account,
            group_spread, member_spread)

    def _format_members(self, group_members, user_members, group_name):
        tmp_users = self._filter_illegal_usernames(user_members, group_name)

        return " ".join((" ".join(group_members),
                         " ".join(["(,%s,)" % m for m in tmp_users])))


class MachineNetGroup(NISGroupUtil):

    """Class for making more complex machine netgroups. Most of
    the code resides in NISGroupUtil."""

    def __init__(self, group_spread, member_spread, zone):
        super(MachineNetGroup, self).__init__(
            co.dns_owner_namespace, co.entity_dns_owner,
            group_spread, member_spread, tmp_group_prefix='m')
        self.zone = zone.postfix
        self.len_zone = len(zone.postfix)
        self._num_map = {}

    def _format_members(self, group_members, user_members, group_name):
        return " ".join(
            (" ".join(group_members),
             " ".join(["(%s,-,)" % m[:-self.len_zone] for m in user_members
                       if m.endswith(self.zone)]),
             " ".join(["(%s,-,)" % m[:-1] for m in user_members])))

    def _make_tmp_name(self, group_name):
        n = self._num_map.get(group_name, 0)
        while True:
            n += 1
            tmp_gname = "%s-%02x" % (group_name, n)
            if tmp_gname not in self._exported_groups:
                self._num_map[group_name] = n
                return tmp_gname


class HackUserNetGroupUIO(UserNetGroup):

    """Class for hacking members of {meta_ansatt,ansatt}@<sko> groups.

    These groups contain *people* (rather than accounts), which is not what
    NISUtils framework opens for (i.e. we'll need to combine people and users)
    Unfortunately, for a period of about 6-8 weeks we need to push employees'
    primary accounts to UIO-nismaps from certain groups.

    So, this class should help us do just that. For certain group (i.e. groups
    with certain traits) we'll collect direct account members of groups AND
    primary accounts of person members of groups. In all cases user_spread is
    used as a filter, and it's always an account that must have this spread if
    it is to be collected into a NIS map.
    """

    def __init__(self, group_spread, member_spread):
        super(HackUserNetGroupUIO, self).__init__(group_spread, member_spread)
        # collect person_id -> primary account_id. Notice that we collect
        # accounts with member_spread only. The rest is irrelevant.
        self._person2primary_account = dict()
        for i in Factory.get("Account")(db).list_accounts_by_type(
            account_spread=member_spread,
                primary_only=True):
            self._person2primary_account[i["person_id"]] = i["account_id"]

        # auto-generated groups are special. We want to find them quickly.
        self._auto_groups = set([x["entity_id"] for x in
                                 Factory.get("Group")(db).list_traits(
                                     code=(co.trait_auto_group,
                                           co.trait_auto_meta_group))])
    # end __init__

    def _expand_group(self, gid):
        ret_groups, ret_non_groups = super(HackUserNetGroupUIO,
                                           self)._expand_group(gid)
        # For automatically generated groups we need to sweep person members
        # as well :( This is the hackish part.
        if gid not in self._auto_groups:
            return ret_groups, ret_non_groups

        # Ah, let's fish all the person members (direct or indirect) and remap
        # them to primary accounts.
        # NB! Notice that group members are not processed here -- they've been
        # covered by the super()._expand_group() call above.
        for row in self._group.search_members(group_id=gid,
                                              indirect_members=True,
                                              member_type=co.entity_person):
            person_id = int(row["member_id"])
            # Fuck this crap, we don't want to generate any noise about the
            # hacks. Continue as nothing had happened with no error.
            if person_id not in self._person2primary_account:
                continue

            account_id = self._person2primary_account[person_id]
            name = self._entity2name.get(account_id)
            # See above.
            if not name:
                continue
            # FIXME: Should this be an adjoin?
            ret_non_groups.add(name)

        return ret_groups, ret_non_groups
