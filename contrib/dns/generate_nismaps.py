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

class NISGroupUtil(object):
    def __init__(self, namespace, member_type, group_spread, member_spread):
        self._entity2name = self._build_entity2name_mapping(namespace)
        self._member_spread = member_spread
        self._member_type = member_type
        self._exported_groups = {}
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

    def _expand_group(self, gid, flatten=False):
        """Expand a group and all of its members.  Subgroups are
        included regardles of spread, but if they are of a different
        spread, the groups members are expanded.

        If flatten=True, subgroups will always be expanded.
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
            if (not flatten) and self._exported_groups.has_key(gid):
                ret_groups.append( self._exported_groups[gid])
            else:
                t_g, t_ng = self._expand_group(gid, flatten=flatten)
                ret_groups.extend(t_g)
                ret_non_groups.extend(t_ng)
        # TODO: Also process intersection and difference members.
        return ret_groups, ret_non_groups

    def _wrap_line(self, gname, line):
        ret = ''
        maxlen = MAX_LINE_LENGTH - (len(gname) + 1)
        while len(line) > maxlen:
            while True:
                tmp_gname = "x%02x" % self._num
                self._num += 1
                if not self._exported_groups.has_key(tmp_gname):
                    break
            maxlen = MAX_LINE_LENGTH - (len(tmp_gname) + 1)
            if len(line) <= maxlen:
                pos = 0
            else:
                pos = line.index(" ", len(line) - maxlen)
            ret += "%s %s\n" % (tmp_gname, line[pos+1:])
            line = "%s %s" % (tmp_gname, line[:pos])
        return ret + "%s %s\n" % (gname, line)

    def generate_netgroup(self, filename):
        logger.debug("generate_netgroup: %s" % filename)

        f = Utils.SimilarSizeWriter(filename, "w")
        f.set_size_change_limit(5)

        n = 0
        for group_id in self._exported_groups.keys():
            group_name = self._exported_groups[group_id]
            group_members, user_members = self._expand_group(group_id)
            logger.debug("%s -> g=%s, u=%s" % (group_id, group_members, user_members))
            f.write(self._wrap_line(group_name,
                                    self._format_members(
                group_members, user_members, group_name)))
        f.close()
        

class MachineNetGroup(NISGroupUtil):
    def __init__(self, group_spread, member_spread, zone):
        super(MachineNetGroup, self).__init__(
            co.dns_owner_namespace, co.entity_dns_owner, group_spread, member_spread)
        self.zone = zone
        self.len_zone = len(zone)

    def _format_members(self, group_members, user_members, group_name):
        return " ".join((" ".join(group_members),
                         " ".join(["(%s,-,)" % m[:-self.len_zone] for m in user_members
                                   if m.endswith(self.zone)]),
                         " ".join(["(%s,-,)" % m[:-1] for m in user_members])))

class UserNetGroup(NISGroupUtil):
    def __init__(self, group_spread, member_spread):
        super(UserNetGroup, self).__init__(
            co.account_namespace, co.entity_account, group_spread, member_spread)

    def _format_members(self, group_members, user_members, group_name):
        tmp_users = []
        for uname in user_members:
            tmp = posix_user.illegal_name(uname)
            if tmp:
                logger.warn("Bad username %s in %s" % (tmp, group_name))
            elif len(uname) > 8:
                logger.warn("Bad username %s in %s" % (uname, group_name))
            else:
                tmp_users.append(uname)

        return " ".join((" ".join(group_members),
                         " ".join(["(,%s,)" % m for m in tmp_users])))

def main():
    ngu = MachineNetGroup(_SpreadCode('NIS_mng@uio'), None, '.uio.no.')
    ngu.generate_netgroup('mng.dump')

    ung = UserNetGroup(_SpreadCode('NIS_ng@uio'), _SpreadCode('NIS_user@uio'))
    ung.generate_netgroup('ung.dump')

if __name__ == '__main__':
    main()

# arch-tag: 5c17b956-2586-4146-84f0-c1c327739506
