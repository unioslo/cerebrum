#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010-2018 University of Oslo, Norway
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

from __future__ import unicode_literals

import optparse
import os
import sys
import mx
from itertools import ifilter
from operator import itemgetter
from six import text_type

import posixconf

from Cerebrum.Entity import EntityName
from Cerebrum.Utils import Factory, auto_super
from Cerebrum.utils import transliterate
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.utils.atomicfile import FileSizeChangeError
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.LDIFutils import (
    ldapconf, LDIFWriter, map_constants, map_spreads, entry_string)

MAX_LINE_LENGTH = 1000


class PosixData(object):
    """Just a class in which we can set attributes."""
    pass


class PosixExport(object):
    EMULATE_POSIX_LDIF = False

    __metaclass__ = auto_super
    usage_string = "Usage: %s [options]%s" % (os.path.basename(sys.argv[0]),"""

Dump NIS and/or LDIF data: passwd, shadow, groups.

Options with FILE arguments enable the particular export type, and
export to the given file.  They require a corresponding SPREAD option.

SPREAD options take a comma-separated list of spreads.

To enable host netgroups in the netgroup and LDIF exports, supply a host
netgroup spread and a zone.

Examples:

  generate_posix_data.py -U NIS_user@uio -G NIS_fg@uio -N NIS_ng@uio \\
    -H NIS_mng@uio -l foo.ldif -p passwd -g groups -n netgroups \\
    -z uio -a MD5-crypt

 Creates both a full LDIF file and all four NIS files.

  generate_posix_data.py -U NIS_user@uio -G NIS_fg@uio -N NIS_ng@uio -l foo.ldif

 Creates an LDIF with all entities apart from host groups (missing
 host netgroup spread and zone option).

  generate_posix_data.py -U NIS_user@uio -p passwd -s passwd.shadow -a MD5-crypt

 Creates a passwd and shadow file.""")

    OptionParser = optparse.OptionParser

    def __init__(self, logger):
        self.logger = logger
        self.build_option_parser()

    def build_option_parser(self):
        self.parser = self.OptionParser(self.usage_string)
        o = self.parser.add_option
        o("-U", "--user-spread", metavar="SPREAD", dest="user_spread",
          help="Filter users by spreads.")
        o("-G", "--group-spread", metavar="SPREAD", dest="filegroup_spread",
          help="Filter filegroups by spreads.")
        o("-N", "--netgroup-spread", metavar="SPREAD", dest="netgroup_spread",
          help="Filter netgroups by spreads.")
        o("-H", "--host-netgroup-spread", metavar="SPREAD",
          dest="host_netgroup_spread",
          help="Filter host netgroups by spreads.")
        o("-l", "--ldif", metavar="FILE", dest="ldif",
          help="Export LDIF to FILE.  Requires '-U', '-G' and '-N'.")
        o("-p", "--passwd", metavar="FILE", dest="passwd",
          help="Export passwd file to FILE.  Requires '-U' and '-a'.")
        o("-g", "--group", metavar="FILE", dest="filegroup",
          help="Export filegroups to FILE.")
        o("-n", "--netgroup", metavar="FILE", dest="netgroup",
          help="Export netgroups to FILE.")
        o("-s", "--shadow", metavar="FILE", dest="shadow",
          help="Export shadow file to FILE.  Requires '-p', '-U' and '-a'.")
        o("-z", "--zone", metavar="DNS-ZONE-POSTFIX", dest="zone",
          help="Zone to use for host netgroups.")
        o("-e", "--eof", dest="eof",
          help="Append 'E_O_F' at the end of the passwd file.",
          default=False, action="store_true")
        o("-a", "--auth-method", metavar="METHOD", dest="auth_method",
          help="Specify passwd auth method. Does not affect LDIF output.")

    def usage(self, msg):
        sys.exit("Bad options, try --help.  %s\n%s" % (msg, self.usage_string))

    def main(self):
        self.parse_options()

        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.group = Factory.get('Group')(self.db)
        self.posix_user = Factory.get('PosixUser')(self.db)
        self.posix_group = PosixGroup.PosixGroup(self.db)
        self._namecachedtime = mx.DateTime.now()

        self._num = 0
        self.posix_users = []
        self.e_id2name = {}
        self.p_id2name = {}
        self.auth_data = {}
        self.disk_tab = {}
        self.shell_tab = {}
        self.quarantines = {}
        self.filegroups = {}
        self.netgroups = {}
        self.host_netgroups = {}
        self.account2def_group = {}
        self.g_id2gid = {}
        self.a_id2owner = {}
        self.a_id2home = {}
        self._names = set()

        self.setup()
        self.generate_files()

    def parse_options(self):
        """Parse command line options.  These override config variables."""

        self.opts, args = self.parser.parse_args()
        if args:
            sys.exit("Spurious arguments %s.  Try --help." % ", ".join(args))
        opts = self.opts
        if opts.ldif and not (opts.zone or (opts.user_spread      and
                                            opts.filegroup_spread and
                                            opts.netgroup_spread)):
            self.usage("--ldif requires -U, -G, -N, and/or -H, -z")
        if opts.passwd        and not (opts.user_spread and opts.auth_method):
            self.usage("--passwd requires -U and -a")
        if opts.shadow        and not opts.passwd:
            self.usage("--shadow requires -p (and thus -U and -a)")
        if opts.filegroup     and not opts.filegroup_spread:
            self.usage("--group requires -G")
        if opts.netgroup      and not (opts.netgroup_spread or opts.zone):
            self.usage("--netgroup requires -N or -H, -z")
        if opts.host_netgroup_spread or opts.zone:
            if (not opts.host_netgroup_spread) != (not opts.zone):
                self.usage("-H and -z require each other")

    def setup(self):
        self.zone = self.opts.zone and self.co.DnsZone(self.opts.zone)
        self.spreads = PosixData()
        for name in ('user', 'filegroup', 'netgroup', 'host_netgroup'):
            spread = getattr(self.opts, name + '_spread')
            spread = spread and spread.split(',')
            setattr(self.spreads, name, map_spreads(spread) or None)

        if self.opts.ldif:          self.setup_ldif()
        if self.opts.passwd:        self.setup_passwd()
        if self.opts.filegroup:     self.setup_filegroup()
        if self.opts.netgroup_spread: self.setup_netgroup()
        if self.opts.zone:            self.setup_host_netgroup()

    def generate_files(self):
        parts = ('ldif', 'passwd', 'shadow', 'filegroup', 'netgroup')
        files = map(self.open, parts)
        f = PosixData(); f.__dict__ = dict(zip(parts, files))

        self.generate_user_output(f.ldif, f.passwd, f.shadow)
        self.generate_filegroup_output(f.ldif, f.filegroup)
        self.generate_netgroup_output(f.ldif, f.netgroup)

        self.close_files(files)

    def setup_ldif(self):
        DNs = [ldapconf(which, 'dn', default=None, module=posixconf)
               for which in ('USER', 'FILEGROUP', 'NETGROUP')]
        self.user_dn, self.fgrp_dn, self.ngrp_dn = DNs
        self.type2groups = (self.netgroups, self.host_netgroups)
        if self.opts.user_spread:
            self.setup_passwd()
            self.setup_filegroup()
            self.setup_netgroup()

    def setup_passwd(self):
        self._build_entity2name_mapping(self.co.account_namespace)
        self.load_person_names()
        self.load_account_info()
        self.load_disk_tab()
        self.load_shell_tab()
        self.load_filegroup_gids()
        self.load_auth_tab()
        self.load_quaratines()
        self.load_posix_users()

    def setup_filegroup(self):
        self._build_entity2name_mapping(self.co.account_namespace)
        self._build_entity2name_mapping(self.co.group_namespace)
        self.load_groups('filegroup', self.filegroups)
        self.load_filegroup_gids()
        self.load_posix_users()

    def setup_netgroup(self):
        self._build_entity2name_mapping(self.co.account_namespace)
        self._build_entity2name_mapping(self.co.group_namespace)
        self.load_groups('netgroup', self.netgroups)
        self.load_posix_users()
        if self.opts.host_netgroup_spread:
            self.setup_host_netgroup()

    def setup_host_netgroup(self):
        self._build_entity2name_mapping(self.co.group_namespace)
        self._build_entity2name_mapping(self.co.dns_owner_namespace)
        self.load_groups('host_netgroup', self.host_netgroups)

    def open(self, which):
        fname = getattr(self.opts, which)
        if fname:
            if which == 'ldif':
                f = LDIFWriter('POSIX', fname, module=posixconf)
                if self.opts.user_spread:
                    f.write_container()
            else:
                f = SimilarSizeWriter(fname, "w")
                f.max_pct_change = 10
            return f

    @staticmethod
    def close_files(files):
        err = False
        for f in filter(None, files):
            try:
                f.close()
            except FileSizeChangeError, err:
                print >>sys.stderr, "%s: %s" % (err.__class__.__name__, err)
        if err:
            sys.exit(1)


    def generate_user_output(self, f_ldif, f_passwd, f_shadow):
        if not self.opts.user_spread:
            return
        if f_ldif:
            f_ldif.write_container('USER')
        elif not self.opts.passwd:
            return
        for data in ifilter(None, self.posix_users):
            if f_ldif:
                dn,entry = self.ldif_user(data)
                f_ldif.write(entry_string(dn, entry, False))
            if f_passwd:
                # TODO: shadow
                passwd = data.passwd or '*invalid'
                try:
                    if self.opts.auth_method == 'NOCRYPT':
                        a = data.account_id
                        m = self.co.auth_type_crypt3_des
                        if passwd == '*invalid' and self.auth_data[a][m]:
                            passwd = 'x'
                except KeyError:
                    pass
                f_passwd.write(self.join((
                    data.uname, passwd, data.uid, data.gid,
                    data.gecos, data.home, data.shell)) + "\n")
        if f_passwd and self.opts.eof:
            f_passwd.write('E_O_F\n')

    def find_groups(self, group_type):
        """Must be called before expand_*group()."""
        groups, descs = {}, {}
        for row in self.group.search(spread=getattr(self.spreads, group_type),
                 filter_expired=not self.EMULATE_POSIX_LDIF):
            group_id = int(row['group_id'])
            groups[group_id] = row['name']
            descs [group_id] = (row['description'] or "").rstrip()
        self.exported_groups = groups
        self.group2desc      = self.opts.ldif and descs.get

    def clear_groups(self):
        """Cleanup after find_groups()"""
        del self.exported_groups, self.group2desc

    def generate_filegroup_output(self, f_ldif, f_filegroup):
        if not self.opts.filegroup_spread:
            return
        if f_ldif:
            f_ldif.write_container('FILEGROUP')
        elif not self.opts.filegroup:
            return
        self.find_groups('filegroup')
        # Loop over gids to sort properly for gid in self.filegroups:
        for g_id, gid in sorted(self.g_id2gid.iteritems(), key=itemgetter(1)):
            if g_id not in self.filegroups:
                continue
            users = sorted(self.expand_filegroup(g_id))
            if f_ldif:
                dn, entry = self.ldif_filegroup(g_id, gid, users)
                f_ldif.write(entry_string(dn, entry, False))
            if f_filegroup:
                f_filegroup.write(self._wrap_line(
                    self.filegroups[g_id], ",".join(users), ':*:%i:' % gid,
                    self._make_tmp_filegroup_name))
        self.clear_groups()

    def generate_netgroup_output(self, f_ldif, f_netgroup):
        if f_ldif and (self.opts.netgroup_spread or self.opts.zone):
            f_ldif.write_container('NETGROUP')
        self.generate_user_netgroup_output(f_ldif, f_netgroup)
        self.generate_host_netgroup_output(f_ldif, f_netgroup)

    def generate_user_netgroup_output(self, f_ldif, f_netgroup):
        if not self.opts.netgroup_spread:
            return
        self.find_groups('netgroup')
        self.netgroup_names = set(self.netgroups.values())
        for g_id in self.netgroups:
            group_members, user_members = map(sorted, self.expand_netgroup(
                    g_id, self.co.entity_account, self.spreads.user))
            user_members = ["(,%s,)" % m for m in user_members]
            if f_ldif:
                dn, entry = self.ldif_netgroup(False, g_id,
                                               group_members, user_members)
                f_ldif.write(entry_string(dn, entry, False))
            if f_netgroup:
                f_netgroup.write(self._wrap_line(
                    self.netgroups[g_id],
                    # TODO: Drop the 'or's, whihch are equivalent to orig code?
                    " ".join((group_members or [""]) + (user_members or [""])),
                    ' ', self._make_tmp_netgroup_name, is_ng=True))
        self.clear_groups()

    def generate_host_netgroup_output(self, f_ldif, f_netgroup):
        if not self.opts.zone:
            return
        self._num_map = {}
        zone = self.zone.postfix
        zone_offset = -len(zone or "")
        self.find_groups('host_netgroup')
        for g_id in self.host_netgroups:
            group_members, host_members = map(sorted, self.expand_netgroup(
                    g_id, self.co.entity_dns_owner, None))
            members = set("(%s,-,)" % m[:-1] for m in host_members)
            if zone is not None:
                members.update("(%s,-,)" % m[:zone_offset]
                               for m in host_members if m.endswith(zone))
            if self.opts.ldif:
                dn, entry = self.ldif_netgroup(True, g_id,
                                               group_members, members)
                f_ldif.write(entry_string(dn, entry, False))
            if f_netgroup:
                f_netgroup.write(self._wrap_line(
                        self.host_netgroups[g_id],
                        " ".join(group_members) + " " + " ".join(members),
                        ' ', self._make_tmp_host_netgroup_name, is_ng=True))
        self.clear_groups()


    def _build_entity2name_mapping(self, namespace):
        if namespace in self._names:
            return
        self.logger.debug("list names in %s" % namespace)
        for row in EntityName(self.db).list_names(namespace):
            self.e_id2name[int(row['entity_id'])] = row['entity_name']
        self._names.add(namespace)

    @staticmethod
    def join(fields, sep=':'):
        for f in fields:
            if not isinstance(f, str):
                raise ValueError, "Type of '%r' is not str." % f
            if f.find(sep) != -1:
                raise ValueError, \
                      "Separator '%s' present in string '%s'" % (sep, f)
        return sep.join(fields)

    def load_posix_users(self):
        if self.account2def_group: return
        save = (self.opts.ldif or self.opts.passwd) and self.posix_users.append
        for row in self.posix_user.list_posix_users(spread=self.spreads.user):
            self.account2def_group[int(row['account_id'])] = int(row['gid'])
            if save:
                save(self.gather_user_data(row))

    def load_disk_tab(self):
        if self.disk_tab: return
        self.disk_tab[None] = None
        for row in Factory.get('Disk')(self.db).list():
            self.disk_tab[int(row['disk_id'])] = row['path']

    def load_shell_tab(self):
        if self.shell_tab: return
        for row in self.posix_user.list_shells():
            self.shell_tab[int(row['code'])] = row['shell']

    def load_groups(self, group_type, struct):
        # TBD: This will only act as a filter in reality as e_id2name contains
        # the group name. Make something more clever.
        if struct: return
        spread = getattr(self.spreads, group_type)
        for row in self.posix_group.search(spread=spread,
                filter_expired=not self.EMULATE_POSIX_LDIF):
            struct[int(row['group_id'])] = row['name']

    def load_filegroup_gids(self):
        if self.g_id2gid: return
        for row in self.posix_group.list_posix_groups():
            self.g_id2gid[int(row['group_id'])] = int(row['posix_gid'])

    def load_quaratines(self):
        if self.quarantines:
            return
        for row in self.posix_user.list_entity_quarantines(
                entity_types=self.co.entity_account,
                only_active=True):
            self.quarantines.setdefault(int(row['entity_id']), []).append(
                int(row['quarantine_type']))

    def load_person_names(self):
        if self.p_id2name: return
        for row in Factory.get('Person')(self.db).search_person_names(
                source_system=self.co.system_cached,
                name_variant=self.co.name_full):
            self.p_id2name[int(row['person_id'])] = row['name']

    def load_account_info(self):
        if self.a_id2owner: return
        for row in self.posix_user.list_account_home(
                home_spread=self.spreads.user,
                account_spread=self.spreads.user,
                include_nohome=True):
            account_id = int(row['account_id'])
            self.a_id2owner[account_id] = int(row['owner_id'])
            self.a_id2home[account_id] = (
                row['path'], row['disk_id'], row['host_id'], row['home'])

    def expand_filegroup(self, gid):
        ret = set()             # A member may be added several times
        self.posix_group.clear()
        self.posix_group.find(gid)
        group_id = self.posix_group.entity_id
        for row in self.posix_group.search_members(
                group_id=group_id,
                indirect_members=True,
                member_type=self.co.entity_account,
                member_spread=self.spreads.user):
            account_id = int(row["member_id"])
            if self.account2def_group.get(account_id) == group_id:
              if not self.EMULATE_POSIX_LDIF:
                continue  # Don't include the user's primary group
            try:
                ret.add(self.e_id2name[account_id])
            except KeyError:
                self.logger.warn("Was %i very recently created?" % int(account_id))
        return ret

    def _make_tmp_filegroup_name(self, name):
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
                if tname not in self.exported_groups:
                    # Hack to reserve the name
                    self.exported_groups[tname] = True
                    return tname
                i += 1
            harder = True
        assert False

    def _make_tmp_netgroup_name(self, name):
        while True:
            tmp_gname = "x%02x" %  self._num
            self._num += 1
            if tmp_gname not in self.netgroups.values():
                return tmp_gname

    def _make_tmp_host_netgroup_name(self, name):
        n = self._num_map.get(name, 0)
        while True:
            n += 1
            tmp_gname = "%s-%02x" % (name, n)
            if tmp_gname not in self.exported_groups:
                self._num_map[name] = n
                return tmp_gname

    def expand_netgroup(self, gid, member_type, member_spread):
        """Expand a group and all of its members.  Subgroups are
        included regardles of spread, but if they are of a different
        spread, the groups members are expanded.
        """

        groups, non_groups = set(), set() # A member may be added several times
        self.group.clear()
        self.group.find(gid)

        # direct members
        for row in self.group.search_members(
                group_id=self.group.entity_id,
                member_spread=member_spread,
                member_type=member_type):
            member_id = int(row["member_id"])
            name = self.e_id2name.get(member_id)
            if name:
                if "_" not in name:
                    non_groups.add(name)
            elif not self._is_new(member_id):
                self.logger.warn("Was %i very recently created?", member_id)

        # subgroups
        for row in self.group.search_members(group_id=gid,
                                             member_type=self.co.entity_group):
            t_gid = int(row["member_id"])
            if t_gid in self.exported_groups:
                groups.add(self.exported_groups[t_gid])
            else:
                t_g, t_ng = self.expand_netgroup(
                    t_gid, member_type, member_spread)
                groups.update(t_g)
                non_groups.update(t_ng)

        return groups, non_groups

    @staticmethod
    def _wrap_line(group_name, line, g_separator, proc, is_ng=False):
        ret = []
        if is_ng:
            delim = ' '
        else:
            delim = ','
        max_namelen = MAX_LINE_LENGTH - len(g_separator)
        maxlen = max_namelen - len(group_name)
        while len(line) > maxlen:
            tmp_gname = proc(group_name)
            maxlen = max_namelen - len(tmp_gname)
            pos = len(line) > maxlen and line.index(delim, len(line) - maxlen)
            ret.extend((tmp_gname, g_separator, line[pos+1:], "\n"))
            line = line[:pos]
            if is_ng:
                line = "%s %s" % (tmp_gname, line)
        ret.extend((group_name, g_separator, line, "\n"))
        return "".join(ret)

    def gather_user_data(self, row):
        data = PosixData()
        data.account_id = int(row['account_id'])
        data.uname = self.e_id2name[data.account_id]
        data.uid = text_type(row['posix_uid'])
        data.gid = text_type(self.g_id2gid[row['gid']])

        if not row['shell']:
            self.logger.warn("User %s has no posix-shell!" % data.uname)
            return None
        data.shell = self.shell_tab[int(row['shell'])]

        data.quarantined, data.passwd = False, None
        if data.account_id in self.quarantines:
            qh = QuarantineHandler(self.db, self.quarantines[data.account_id])
            if qh.should_skip():
                return None
            if qh.is_locked():
                data.quarantined, data.passwd = True, '*Locked'
            qshell = qh.get_shell()
            if qshell is not None:
                data.shell = qshell
        try:
            home = self.a_id2home[data.account_id]
            data.home = self.posix_user.resolve_homedir(
                account_name=data.uname,
                home=home[3], disk_path=self.disk_tab[home[1]])
        except:
            self.logger.warn("User %s has no home-directory!" % data.uname)
            return None

        cn = gecos = row['gecos']
        if data.account_id in self.a_id2owner:
            cn = self.p_id2name.get(self.a_id2owner[data.account_id], gecos)
        data.cn = cn or data.uname
        data.gecos = transliterate.to_iso646_60(gecos or data.cn)
        return data

    def ldif_user(self, data):
        passwd = data.passwd
        if passwd is not None:          # Quarantined
            passwd = '{crypt}' + passwd
        else:
            passwd = '{crypt}*Invalid'
            for uauth in filter(self.auth_format.has_key, self.a_meth):
                #method = int(self.co.auth_type_crypt3_des)
                try:
                    #if uauth in self.auth_format.keys():
                    fmt = self.auth_format[uauth]['format']
                    if fmt:
                        passwd = fmt % self.auth_data[data.account_id][uauth]
                        #passwd_attr = self.auth_format[uauth]['attr']
                    else:
                        passwd = self.auth_data[data.account_id][uauth]
                except KeyError:
                    pass
#                else:
#                    break
        entry = {'objectClass':   ['top','account','posixAccount'],
                 'cn':            (data.cn,),
                 'uid':           (data.uname,),
                 'uidNumber':     (data.uid,),
                 'gidNumber':     (data.gid,),
                 'homeDirectory': (data.home,),
                 'userPassword':  (passwd,),
                 'loginShell':    (data.shell,),
                 'gecos':         (data.gecos,)}
        return ','.join((('uid=' + data.uname), self.user_dn)), entry


    def ldif_filegroup(self, group_id, posix_gid, members):
        """Create the group-entry attributes"""
        name = self.filegroups[group_id]
        entry = {'objectClass': ('top', 'posixGroup'),
                 'cn':          (name,),
                 'gidNumber':   (text_type(posix_gid),),
                 'memberUid':   members}
        desc = self.group2desc(group_id)
        if desc:
            # becomes iso646_60 later
            entry['description'] = (desc,)
        return ','.join(('cn=' + name, self.fgrp_dn)), entry

    def ldif_netgroup(self, is_hostg, group_id, group_members, direct_members):
        """Create the group-entry attributes"""
        groups = self.type2groups[is_hostg] # TODO: Can we combine these?
        name = groups[group_id]
        entry = {'objectClass':       ('top', 'nisNetGroup'),
                 'cn':                (name,),
                 'nisNetgroupTriple': direct_members,
                 'memberNisNetgroup': group_members}
        desc = self.group2desc(group_id)
        if desc:
            entry['description'] = (transliterate.to_iso646_60(desc),)
        return ','.join(('cn=' + name, self.ngrp_dn)), entry


    def ldif_auth_methods(self):
        """Which authentication methods to fetch. Mixin-support.
        If all only one entry, it will prefect any in auth_table.
        If None, it will use default API authentication (crypt3des).
        """
        self.auth_format = {}
        auth_meth_l = []
        self.user_auth = None
        code = '_AuthenticationCode'
        # Priority is arg, else cereconf default value
        # auth_meth_l is a list sent to load_auth_tab and contains
        # all methods minus primary which is called by
        auth = posixconf.LDAP['auth_attr']
        if isinstance(auth,dict):
            if not 'userPassword' in auth:
                self.logger.warn("Only support 'userPassword'-attribute")
                return None
            default_auth = auth['userPassword'][:1][0]
            self.user_auth = map_constants(code, default_auth[0])
            if len(default_auth) == 2:
                format = default_auth[1]
            else:
                format = None
            self.auth_format[int(self.user_auth)] = {'attr':'userPassword',
                                                     'format':format}
            for entry in auth['userPassword'][1:]:
                auth_t = map_constants(code, entry[0])
                if len(entry) == 2:
                    format = entry[1]
                else:
                    format = None
                auth_meth_l.append(auth_t)
                self.auth_format[int(auth_t)] = {'attr':'userPassword',
                                                 'format':format}
        if isinstance(auth,(list,tuple)):
             self.user_auth = int(getattr(self.co, auth[:1][0]))
             for entry in auth[1:]:
                auth_meth_l.append(int(getattr(self.co, entry)))
        elif isinstance(auth,str):
            self.user_auth = int(getattr(self.co, auth))
        return auth_meth_l


    def load_auth_tab(self):
        # Only populate the cache if cache is empty
        if self.auth_data: return
        self.a_meth = []
        if self.opts.ldif:
            self.a_meth = self.ldif_auth_methods()
        if self.opts.passwd or True:    # DEBUG
            # Need to fetch a crypt to check if password should be squashed
            # or 'x'ed.
            if self.opts.auth_method == 'NOCRYPT':
                meth = self.co.auth_type_crypt3_des
            else:
                meth = map_constants('_AuthenticationCode',
                                     self.opts.auth_method)
            if meth not in self.a_meth:
                self.a_meth.append(meth)
        if self.a_meth:
            for row in self.posix_user.list_account_authentication(
                    auth_type=self.a_meth):
                if not (row['account_id'] and row['method']):
                    continue
                acc_id, meth = int(row['account_id']), int(row['method'])
                if acc_id not in self.auth_data:
                    self.auth_data[acc_id] = {meth: row['auth_data']}
                else:
                    self.auth_data[acc_id][meth] = row['auth_data']
# TODO  self.a_trymeth = filter(self.auth_format.has_key,reversed(self.a_meth))

    def _is_new(self, entity_id):
        """
        Returns true if there is a change log create event for
        entity_id (group or account) since we cached entity names.
        """
        try:
            # TODO: Try 'for event in self.db.get_log_events(): return True'.
            events = list(self.db.get_log_events(
                    types=(self.co.group_create, self.co.account_create),
                    subject_entity=entity_id,
                    sdate=self._namecachedtime))
            return bool(events)
        except:
            self.logger.debug("Checking change log failed: %s", sys.exc_value)
        return False


class PosixExportRadius(PosixExport):
    """Mixin adding LDAP attributes for FreeRadius."""
    # Based on the obsolete Cerebrum.modules.PosixLDIF.PosixLDIFRadius.

    def ldif_auth_methods(self):
        # Also fetch NT password, for attribute sambaNTPassword.
        meth = self.__super.ldif_auth_methods()
        if meth is not None and self.opts.ldif:
            self.auth_type_radius = int(self.co.auth_type_md4_nt)
            meth.append(self.auth_type_radius)
        return meth

    def ldif_user(self, data):
        # Add sambaNTPassword (used by FreeRadius)
        dn, entry = ret = self.__super.ldif_user(data)
        if not data.quarantined:
            try:
                pw = self.auth_data[data.account_id][self.auth_type_radius]
            except KeyError:
                pass
            else:
                if pw:
                    entry['sambaNTPassword'] = (pw,)
                    # TODO: Remove these after Radius-testing
                    entry['objectClass'].append('sambaSamAccount')
                    entry['sambaSID'] = entry['uidNumber']
        return ret
