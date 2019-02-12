#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sys
import mx
import getopt
import argparse

from six import text_type

import cerebrum_path

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import transliterate
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules import PosixGroup
from Cerebrum.Entity import EntityName
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode

del cerebrum_path

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
posix_user = Factory.get('PosixUser')(db)
posix_group = PosixGroup.PosixGroup(db)

# The "official" NIS max line length (consisting of key + NUL + value
# + NUL) is 1024; however, some implementations appear to have lower
# limits.
#
# Specifically, on Solaris 9 makedbm(1M) chokes on lines longer than
# 1018 characters.  Other systems might be even more limited.
MAX_LINE_LENGTH = 1000
_SpreadCode.sql = db

debug = 0
e_o_f = False


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


def make_shells_cache(posix_user):
    logger.debug('Making shells cache')
    shells = {}
    for s in posix_user.list_shells():
        shells[int(s['code'])] = s['shell']
    return shells


def generate_passwd(filename, shadow_file, spread):
    def process_user(row):
        account_id = row['account_id']
        logger.debug('Processing account: %s', account_id)
        row_auth = posix_user.list_account_authentication(
            account_id=account_id
        )[0]
        uname = row_auth['entity_name']
        is_illegal_name = posix_user.illegal_name(uname)
        if is_illegal_name:
            raise BadUsername("Bad username %s" % is_illegal_name)
        if len(uname) > 8:
            raise BadUsername("Bad username %s" % uname)
        passwd = row_auth['auth_data']
        if passwd is None:
            passwd = '*'
        posix_gid = get_posix_gid(row, posix_group)
        gecos = row['gecos']
        if gecos is None:
            gecos = "GECOS NOT SET"
        gecos = transliterate.to_iso646_60(gecos)
        shell = shells[int(row['shell'])]

        posix_user.clear()
        posix_user.find(account_id)
        quarantines = posix_user.get_entity_quarantine(only_active=True)
        quarantine_types = []
        if quarantines is not None:
            for q in quarantines:
                quarantine_types.append(q['quarantine_type'])
            qh = QuarantineHandler.QuarantineHandler(db, quarantine_types)
            if qh.should_skip():
                raise UserSkipQuarantine
            if qh.is_locked():
                passwd = '*locked'
            qshell = qh.get_shell()
            if qshell is not None:
                shell = qshell

        home = posix_user.get_posix_home(spread)
        if home is None:
            # TBD: Is this good enough?
            home = '/'

        if shadow_file:
            s.write("%s:%s:::\n" % (uname, passwd))
            if not passwd[0] == '*':
                passwd = "!!"

        line = ':'.join((uname, passwd, text_type(row['posix_uid']),
                         text_type(posix_gid), gecos,
                         text_type(home), shell))
        if debug:
            logger.debug(line)
        f.write(line+"\n")
        # convert to 7-bit

    logger.debug("generate_passwd: %s", (filename, shadow_file, spread))
    shells = make_shells_cache(posix_user)

    f = SimilarSizeWriter(filename, "w", encoding='ISO-8859-1')
    f.max_pct_change = 10
    if shadow_file:
        s = SimilarSizeWriter(shadow_file, "w", encoding='UTF-8')
        s.max_pct_change = 10

    user_iter = posix_user.list_posix_users(spread=spread,
                                            filter_expired=True)

    for row in user_iter:
        try:
            process_user(row)
        except NISMapError:
            logger.error("NISMapError", exc_info=1)
        except NISMapException:
            pass

    if e_o_f:
        f.write('E_O_F\n')
    f.close()
    if shadow_file:
        s.close()


class NISGroupUtil(object):
    def __init__(self, namespace, member_type, group_spread, member_spread,
                 tmp_group_prefix='x'):
        self._entity2name = self._build_entity2name_mapping(namespace)
        self._member_spread = member_spread
        self._member_type = member_type
        self._exported_groups = {}
        self._tmp_group_prefix = tmp_group_prefix
        self._group = Factory.get('Group')(db)
        for row in self._group.search(spread=int(group_spread)):
            self._exported_groups[int(row['group_id'])] = row['name']
        self._num = 0

    def _build_entity2name_mapping(self, namespace):
        ret = {}
        en = EntityName(db)
        logger.debug("list names in %s" % namespace)
        for row in en.list_names(namespace):
            ret[int(row['entity_id'])] = row['entity_name']
        return ret

    def _expand_group(self, gid):
        """Expand a group and all of its members.  Subgroups are
        included regardles of spread, but if they are of a different
        spread, the groups members are expanded.
        """
        ret_groups = []
        ret_non_groups = []
        self._group.clear()
        self._group.find(gid)

        # Direct members
        for row in self._group.search_members(
                group_id=self._group.entity_id,
                member_spread=self._member_spread,
                member_type=self._member_type):
            member_id = int(row["member_id"])
            name = self._entity2name.get(member_id)
            if not name:
                logger.warn("Was %i very recently created?", member_id)
                continue
            ret_non_groups.append(name)

        # Subgroups
        for row in self._group.search_members(group_id=self._group.entity_id,
                                              member_type=co.entity_group):
            gid = int(row["member_id"])
            if gid in self._exported_groups:
                ret_groups.append(self._exported_groups[gid])
            else:
                t_g, t_ng = self._expand_group(gid)
                ret_groups.extend(t_g)
                ret_non_groups.extend(t_ng)
        return ret_groups, ret_non_groups

    def _make_tmp_name(self, notused):
        while True:
            tmp_gname = "%s%02x" % (self._tmp_group_prefix, self._num)
            self._num += 1
            if tmp_gname not in self._exported_groups:
                return tmp_gname

    def _wrap_line(self, group_name, line, g_separator, is_ng=False):
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
            ret += "%s%s%s\n" % (tmp_gname, g_separator, line[pos+1:])
            line = line[:pos]
            if is_ng:
                line = "%s %s" % (tmp_gname, line)
        return ret + "%s%s%s\n" % (group_name, g_separator, line)

    def generate_netgroup(self, filename):
        logger.debug("generate_netgroup: %s" % filename)

        f = SimilarSizeWriter(filename, "w", encoding='UTF-8')
        f.max_pct_change = 5

        for group_id in self._exported_groups.keys():
            group_name = self._exported_groups[group_id]
            group_members, user_members = self._expand_group(group_id)
            logger.debug("%s -> g=%s, u=%s" % (
                group_id, group_members, user_members))
            f.write(self._wrap_line(group_name,
                                    self._format_members(
                                        group_members, user_members,
                                        group_name), ' ', is_ng=True))
        if e_o_f:
            f.write('E_O_F\n')
        f.close()

    def _filter_illegal_usernames(self, unames, group_name):
        tmp_users = []
        for uname in unames:
            tmp = posix_user.illegal_name(uname)
            if tmp:
                logger.warn("Bad username %s in %s" % (tmp, group_name))
            elif len(uname) > 8:
                logger.warn("Bad username %s in %s" % (uname, group_name))
            else:
                tmp_users.append(uname)
        return tmp_users


def get_posix_gid(row, group):
    group.clear()
    group.find(int(row['gid']))
    return int(group.posix_gid)


def make_account_cache(posix_user, group):
    logger.debug('Making account cache')
    account2posix_gid = {}
    for row in posix_user.list_posix_users(filter_expired=True):
        account2posix_gid[int(row['account_id'])] = get_posix_gid(row, group)
    return account2posix_gid


class FileGroup(NISGroupUtil):
    def __init__(self, group_spread, member_spread):
        super(FileGroup, self).__init__(
            co.account_namespace, co.entity_account,
            group_spread, member_spread)
        self._group = PosixGroup.PosixGroup(db)
        self._account2posix_gid = make_account_cache(posix_user, self._group)
        logger.debug("__init__ done")

    def _make_tmp_name(self, base):
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
        ret = []
        self._group.clear()
        self._group.find(gid)
        for row in self._group.search_members(
                group_id=self._group.entity_id,
                member_spread=self._member_spread,
                indirect_members=True,
                member_type=co.entity_account):
            account_id = int(row["member_id"])
            if (self._account2posix_gid.get(account_id, None) ==
                    self._group.posix_gid):
                continue  # Don't include the users primary group
            name = self._entity2name.get(account_id, None)
            if not name:
                logger.warn("Was %i very recently created?" % int(account_id))
                continue
            ret.append(name)
        return None, list(set(ret))

    def generate_filegroup(self, filename):
        logger.debug("generate_group: %s" % filename)
        f = SimilarSizeWriter(filename, "w", encoding='UTF-8')
        f.max_pct_change = 5

        groups = self._exported_groups.keys()
        groups.sort()
        for group_id in groups:
            group_name = self._exported_groups[group_id]
            tmp = posix_group.illegal_name(group_name)
            if tmp or len(group_name) > 8:
                logger.warn("Bad groupname %s %s" % (group_name, tmp))
                continue
            try:
                group_members, user_members = self._expand_group(group_id)
            except Errors.NotFoundError:
                logger.warn("Group %s has no GID", group_id)
                continue
            tmp_users = self._filter_illegal_usernames(user_members,
                                                       group_name)

            logger.debug("%s -> g=%s, u=%s" % (
                group_id, group_members, tmp_users))
            f.write(self._wrap_line(group_name, ",".join(tmp_users),
                                    ':*:%i:' % self._group.posix_gid))
        if e_o_f:
            f.write('E_O_F\n')
        f.close()


class UserNetGroup(NISGroupUtil):
    def __init__(self, group_spread, member_spread):
        super(UserNetGroup, self).__init__(
            co.account_namespace, co.entity_account,
            group_spread, member_spread)

    def _format_members(self, group_members, user_members, group_name):
        tmp_users = self._filter_illegal_usernames(user_members, group_name)

        return " ".join((" ".join(group_members),
                         " ".join(["(,%s,)" % m for m in tmp_users])))


class MachineNetGroup(NISGroupUtil):
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


def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print("Error mapping %s" % id)  # no need to use logger here
        raise


def main():
    # parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     'd', '--debug',
    #     dest='debug',
    #
    # )
    # TODO: finish this and make sure job_runner doesn't crash

    global debug
    global e_o_f
    global max_group_memberships
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dg:p:n:s:m:Z:',
                                   ['debug', 'help', 'eof', 'group=',
                                    'passwd=', 'group_spread=',
                                    'user_spread=', 'netgroup=',
                                    'max_memberships=', 'shadow=',
                                    'mnetgroup=', 'zone='])
    except getopt.GetoptError:
        usage(1)

    user_spread = group_spread = None
    max_group_memberships = 16
    shadow_file = None
    zone = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('--eof',):
            e_o_f = True
        elif opt in ('-g', '--group'):
            if not (user_spread and group_spread):
                sys.stderr.write("Must set user and group spread!\n")
                sys.exit(1)
            fg = FileGroup(group_spread, user_spread)
            fg.generate_filegroup(val)
        elif opt in ('-p', '--passwd'):
            if not user_spread:
                sys.stderr.write("Must set user spread!\n")
                sys.exit(1)
            generate_passwd(val, shadow_file, user_spread)
            shadow_file = None
        elif opt in ('-n', '--netgroup'):
            if not (user_spread and user_spread):
                sys.stderr.write("Must set user and group spread!\n")
                sys.exit(1)
            ung = UserNetGroup(group_spread, user_spread)
            ung.generate_netgroup(val)
        elif opt in ('-m', '--mnetgroup'):
            ngu = MachineNetGroup(group_spread, None, zone)
            ngu.generate_netgroup(val)
        elif opt in ('--group_spread',):
            group_spread = map_spread(val)
        elif opt in ('-Z', '--zone',):
            zone = co.DnsZone(val)
        elif opt in ('--max_memberships',):
            max_group_memberships = val
        elif opt in ('--user_spread',):
            user_spread = map_spread(val)
        elif opt in ('-s', '--shadow'):
            shadow_file = val
        else:
            usage()
    if len(opts) == 0:
        usage(1)


def usage(exitcode=0):
    print("""Usage: [options]

   [--user_spread spread [--shadow outfile]* [--passwd outfile]* \
    [--group_spread spread [--group outfile]* [--netgroup outfile]*]*]+

   Any of the two types may be repeated as many times as needed, and will
   result in generate_nismaps making several maps based on spread. If eg.
   user_spread is set, generate_nismaps will use this if a new one is not
   set before later passwd files. This is not the case for shadow.

   Misc options:
    -d | --debug
      Enable deubgging
    --eof
      End dump file with E_O_F to mark successful completion

   Group options:
    --group_spread value
      Filter by group_spread
    -g | --group outfile
      Write posix group map to outfile
    -n | --netgroup outfile
      Write netgroup map to outfile
    -m | --mnetgroup outfile
      Write netgroup.host map to outfile
    -Z | --zone dns zone postfix (example: .uio.no.)

   User options:
    --user_spread value
      Filter by user_spread
    -s | --shadow outfile
      Write shadow file. Password hashes in passwd will then be '!!' or '*'.
    -p | --passwd outfile
      Write password map to outfile

    Generates a NIS map of the requested type for the requested spreads.""")
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
