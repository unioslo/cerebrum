#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import time
import getopt
import sys
import os
import mx

import cerebrum_path
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.Entity import EntityName
from Cerebrum import QuarantineHandler
from Cerebrum.Constants import _SpreadCode

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")
posix_user = PosixUser.PosixUser(db)
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

class NISMapException(Exception): pass
class UserSkipQuarantine(NISMapException): pass
class NISMapError(NISMapException): pass
class BadUsername(NISMapError): pass
class NoDisk(NISMapError): pass

def generate_passwd(filename, shadow_file, spread=None):
    logger.debug("generate_passwd: "+str((filename, shadow_file, spread)))
    if spread is None:
        raise ValueError, "Must set user_spread"
    shells = {}
    for s in posix_user.list_shells():
        shells[int(s['code'])] = s['shell']
    f = Utils.SimilarSizeWriter(filename, "w")
    f.set_size_change_limit(10)
    if shadow_file:
        s = Utils.SimilarSizeWriter(shadow_file, "w")
        s.set_size_change_limit(10)
    n = 0
    diskid2path = {}
    disk = Factory.get('Disk')(db)
    static_posix_user = PosixUser.PosixUser(db)
    for d in disk.list(spread=spread):
        diskid2path[int(d['disk_id'])] = d['path']
    def process_user(user_rows):
        row = user_rows[0]
        uname = row['entity_name']
        tmp = posix_user.illegal_name(uname)
        if tmp:
            raise BadUsername, "Bad username %s" % tmp            
        if len(uname) > 8:
            raise BadUsername, "Bad username %s" % uname
        passwd = row['auth_data']
        if passwd is None:
            passwd = '*'
        posix_group.posix_gid = row['posix_gid']
        gecos = row['gecos']
        if gecos is None:
            gecos = row['name']
        if gecos is None:
            gecos = "GECOS NOT SET"
        gecos = Utils.latin1_to_iso646_60(gecos)
        home = row['home']
        shell = shells[int(row['shell'])]
        if row['quarantine_type'] is not None:
            now = mx.DateTime.now()
            quarantines = []
            for qrow in user_rows:
                if (qrow['start_date'] <= now
                    and (qrow['end_date'] is None or qrow['end_date'] >= now)
                    and (qrow['disable_until'] is None
                         or qrow['disable_until'] < now)):
                    # The quarantine found in this row is currently
                    # active.
                    quarantines.append(qrow['quarantine_type'])
            qh = QuarantineHandler.QuarantineHandler(db, quarantines)
            if qh.should_skip():
                raise UserSkipQuarantine
            if qh.is_locked():
                passwd = '*locked'
            qshell = qh.get_shell()
            if qshell is not None:
                shell = qshell

        if home is None:
            if row['disk_id'] is None:
                # TBD: Is this good enough?
                home = '/'
                #raise NoDisk, "Bad disk for %s" % uname
            else:
                home = diskid2path[int(row['disk_id'])] + "/" + uname

        if shadow_file:
            s.write("%s:%s:::\n" % (uname, passwd))
            if not passwd[0] == '*':
                passwd = "!!"

        line = join((uname, passwd, str(row['posix_uid']),
                     str(posix_group.posix_gid), gecos,
                     str(home), shell))
        if debug:
            logger.debug(line)
        f.write(line+"\n")
        # convert to 7-bit
    user_iter = posix_user.list_extended_posix_users(
        auth_method=co.auth_type_crypt3_des,
        spread=spread, include_quarantines=True)
    prev_user = None
    user_rows = []
    for row in user_iter:
        if prev_user != row['account_id'] and prev_user is not None:
            try:
                process_user(user_rows)
            except NISMapError, e:
                logger.error("NISMapError", exc_info=1)
            except NISMapException:
                pass
            user_rows = [row]
        else:
            user_rows.append(row)
        prev_user = row['account_id']
    else:
        if user_rows:
            try:
                process_user(user_rows)
            except NISMapError, e:
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
        for row in self._group.list_all(spread=group_spread):
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
        u, i, d = self._group.list_members(spread=self._member_spread,
                                           member_type=self._member_type)
        for row in u:
            name = self._entity2name.get(int(row[1]), None)
            if not name:
                logger.warn("Was %i very recently created?" % int(row[1]))
                continue
            ret_non_groups.append(name)

        # Subgroups
        u, i, d = self._group.list_members(member_type=co.entity_group)
        for row in u:
            gid = int(row[1])
            if self._exported_groups.has_key(gid):
                ret_groups.append( self._exported_groups[gid])
            else:
                t_g, t_ng = self._expand_group(gid)
                ret_groups.extend(t_g)
                ret_non_groups.extend(t_ng)
        # TODO: Also process intersection and difference members.
        return ret_groups, ret_non_groups

    def _make_tmp_name(self, notused):
        while True:
            tmp_gname = "%s%02x" % (self._tmp_group_prefix, self._num)
            self._num += 1
            if not self._exported_groups.has_key(tmp_gname):
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

        f = Utils.SimilarSizeWriter(filename, "w")
        f.set_size_change_limit(5)

        for group_id in self._exported_groups.keys():
            group_name = self._exported_groups[group_id]
            group_members, user_members = self._expand_group(group_id)
            logger.debug("%s -> g=%s, u=%s" % (
                group_id, group_members, user_members))
            f.write(self._wrap_line(group_name,
                                    self._format_members(
                group_members, user_members, group_name), ' ', is_ng=True))
        if e_o_f:
            f.write('E_O_F\n')
        f.close()

    def _filter_illegal_usernames(self, unames):
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

class FileGroup(NISGroupUtil):
    def __init__(self, group_spread, member_spread):
        super(FileGroup, self).__init__(
            co.account_namespace, co.entity_account,
            group_spread, member_spread)
        self._group = PosixGroup.PosixGroup(db)
        self._account2def_group = {}
        for row in posix_user.list_extended_posix_users():
            self._account2def_group[int(row['account_id'])] = int(row['posix_gid'])
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
                if not self._exported_groups.has_key(tname):
                    self._exported_groups[tname] = True
                    return tname
                i += 1
            harder = True

    def _expand_group(self, gid):
        ret = []
        self._group.clear()
        self._group.find(gid)
        for account_id in self._group.get_members(spread=self._member_spread):
            if self._account2def_group.get(account_id, None) == self._group.posix_gid:
                continue  # Don't include the users primary group
            name = self._entity2name.get(account_id, None)
            if not name:
                logger.warn("Was %i very recently created?" % int(account_id))
                continue
            ret.append(name)
        return None, ret

    def generate_filegroup(self, filename):
        logger.debug("generate_group: %s" % filename)
        f = Utils.SimilarSizeWriter(filename, "w")
        f.set_size_change_limit(5)

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
                logger.warn("Group %s, spread %s has no GID"%(
                    row.group_id,group_spread))
                continue
            tmp_users = self._filter_illegal_usernames(user_members)

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
        tmp_users = self._filter_illegal_usernames(user_members)

        return " ".join((" ".join(group_members),
                         " ".join(["(,%s,)" % m for m in tmp_users])))

class MachineNetGroup(NISGroupUtil):
    def __init__(self, group_spread, member_spread, zone):
        super(MachineNetGroup, self).__init__(
            co.dns_owner_namespace, co.entity_dns_owner,
            group_spread, member_spread, tmp_group_prefix='m')
        self.zone = zone
        self.len_zone = len(zone)

    def _format_members(self, group_members, user_members, group_name):
        return " ".join(
            (" ".join(group_members),
             " ".join(["(%s,-,)" % m[:-self.len_zone] for m in user_members
                       if m.endswith(self.zone)]),
             " ".join(["(%s,-,)" % m[:-1] for m in user_members])))

def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping %s" % id  # no need to use logger here
        raise

def main():
    global debug
    global e_o_f
    global max_group_memberships
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dg:p:n:s:m:',
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
        elif opt in ('--zone',):
            zone = val
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
    print """Usage: [options]
  
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
    -z dns zone postfix (example: .uio.no.)

   User options:
    --user_spread value
      Filter by user_spread
    -s | --shadow outfile
      Write shadow file. Password hashes in passwd will then be '!!' or '*'.
    -p | --passwd outfile
      Write password map to outfile

    Generates a NIS map of the requested type for the requested spreads."""
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 5c17b956-2586-4146-84f0-c1c327739506
