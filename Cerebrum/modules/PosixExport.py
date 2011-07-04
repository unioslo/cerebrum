#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2010-2011 University of Oslo, Norway
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

import optparse
import os
import sys
import mx

import posixconf
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Entity import EntityName
from Cerebrum.Utils import Factory, SimilarSizeWriter, latin1_to_iso646_60
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.LDIFutils import ldapconf, \
     ldif_outfile, end_ldif_outfile, map_constants, map_spreads, \
     entry_string, container_entry_string, iso2utf

from Cerebrum.QuarantineHandler import QuarantineHandler

MAX_LINE_LENGTH = 1000

class PosixUserData(object):
    pass

class PosixExport(object):
    usage_string = "Usage: %s [options]%s" % (os.path.basename(sys.argv[0]),"""

Dump NIS and/or LDIF data: passwd, shadow, groups.

Options with FILE arguments enable the particular export type, and
export to the given file.  They require a corresponding SPREAD option.

Enabling host netgroups will also require a zone. To enable host
netgroups in the LDIF export, supply a host netgroup spread. This also
requires a zone.

Examples:

  generate_posix_data.py -U NIS_user@uio -G NIS_fg@uio -N NIS_ng@uio \\
    -H NIS_mng@uio -l foo.ldif -p passwd -g groups -n netgroup.user \\
    -h netgroup.host -z .uio.no -a MD5-crypt

 Creates both a full LDIF file and all four NIS files.

  generate_posix_data.py -U NIS_user@uio -G NIS_fg@uio -N NIS_ng@uio -l foo.ldif

 Creates an LDIF with all entities apart from host groups (missing
 host netgroup spread and zone option).

  generate_posix_data.py -U NIS_user@uio -p passwd -s passwd.shadow -a MD5-crypt

 Creates a passwd and shadow file.""")

    OptionParser = optparse.OptionParser

    def build_option_parser(self):
        parser = self.OptionParser(self.usage_string)
        o = parser.add_option
        o("-U", "--user-spread", metavar="SPREAD", dest="user_spread",
          help="Filter users by spreads.")
        o("-G", "--group-spread", metavar="SPREAD", dest="group_spread",
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
        o("-g", "--group", metavar="FILE", dest="group",
          help="Export filegroups to FILE.")
        o("-n", "--netgroup", metavar="FILE", dest="netgroup",
          help="Export netgroups to FILE.")
        o("-j", "--host-netgroup", metavar="FILE", dest="host_netgroup",
          help="Export host netgroups to FILE.  Requires '-H' and '-z'.")
        o("-s", "--shadow", metavar="FILE", dest="shadow",
          help="Export shadow file to FILE.")
        o("-z", "--zone", metavar="DNS-ZONE-POSTFIX", dest="zone",
          help="Zone to use for host netgroups.")
        o("-e", "--eof", dest="eof",
          help="Append 'E_O_F' at the end of the passwd file.",
          default=False, action="store_true")
        o("-a", "--auth-method", metavar="METHOD", dest="auth_method",
          help="Specify passwd auth method. Does not affect LDIF output.")
        return parser

    def usage(self, msg):
        sys.exit("Bad options, try --help.  %s\n%s" % (msg, self.usage_string))

    def __init__(self, logger):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.disk = Factory.get('Disk')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.group = Factory.get('Group')(self.db)
        self.posix_user = PosixUser.PosixUser(self.db)
        self.posix_group = PosixGroup.PosixGroup(self.db)
        self.logger = logger
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
        self.spread_d = {}
        self._names = set()

    def parse_options(self):
        """Parse command line options.  These override config variables."""

        self.opts, args = self.build_option_parser().parse_args()
        if args:
            sys.exit("Spurious arguments %s.  Try --help." % ", ".join(args))
        if self.opts.ldif          and not (self.opts.user_spread and
                                            self.opts.group_spread and
                                            self.opts.netgroup_spread):
            self.usage("--ldif requires -U, -G and -N")
        if self.opts.passwd        and not (self.opts.user_spread and
                                            self.opts.auth_method):
            self.usage("--passwd requirse -U and -a")
        if self.opts.group         and not self.opts.group_spread:
            self.usage("--group requires -G")
        if self.opts.netgroup      and not self.opts.netgroup_spread:
            self.usage("--netgroup requires -N")
        if self.opts.host_netgroup and not (self.opts.host_netgroup_spread and
                                            self.opts.zone):
            self.usage("--host-netgroup requires -H and -z")

        if self.opts.zone:
            self.opts.zone = self.co.DnsZone(self.opts.zone)

        # Validate spread from arg
        for x in ('user-spread', 'group-spread', 'netgroup-spread',
                  'host-netgroup-spread'):
            spread = map_spreads(getattr(self.opts, x.replace('-', '_')))
            if spread:
                self.spread_d[x] = spread

    def generate_files(self):
        # Load caches for the specified jobs and open files
        f_ldif =             self.setup_ldif()
        f_passwd, f_shadow = self.setup_passwd() or (None, None)
        f_group =            self.setup_group()
        f_netgroup =         self.setup_netgroup()
        f_host_netgroup =    self.setup_host_netgroup()
        # Generate the output
        self.generate_passwd_output(f_ldif, f_passwd, f_shadow)
        self.generate_filegroup_output(f_ldif, f_group)
        self.generate_netgroup_output(f_ldif, f_netgroup)
        self.generate_host_netgroup_output(f_ldif, f_netgroup)
        # Finish
        if self.opts.ldif:          self.close_ldif(f_ldif)
        if self.opts.passwd:        self.close_passwd(f_passwd, f_shadow)
        if self.opts.group:         self.close_group(f_group)
        if self.opts.netgroup:      self.close_netgroup(f_netgroup)
        if self.opts.host_netgroup: self.close_host_netgroup(f_host_netgroup)

    def setup_ldif(self):
        if self.opts.ldif:
            self.user_dn = ldapconf('USER', 'dn', default=None,
                                    module=posixconf)
            self.fgrp_dn = ldapconf('FILEGROUP', 'dn', default=None,
                                    module=posixconf)
            self.ngrp_dn = ldapconf('NETGROUP', 'dn', default=None,
                                    module=posixconf)
            self.hgrp_dn = ldapconf('HOSTNETGROUP', 'dn', default=None,
                                    module=posixconf)
            self.load_auth_tab()
            self.load_posix_users()
            self._build_entity2name_mapping(self.co.account_namespace)
            self._build_entity2name_mapping(self.co.group_namespace)
            self.load_groups('group', self.filegroups)
            self.load_groups('netgroup', self.netgroups)
            self.load_group_gids()
            self.load_auth_tab()
            self.load_disk_tab()
            self.load_shell_tab()
            self.load_quaratines()
            self.load_person_names()
            self.load_account_info()
            return self.open_ldif()

    def setup_passwd(self):
        if self.opts.passwd:
            self.load_posix_users()
            self._build_entity2name_mapping(self.co.account_namespace)
            self.load_group_gids()
            self.load_auth_tab()
            self.load_disk_tab()
            self.load_shell_tab()
            self.load_quaratines()
            self.load_person_names()
            self.load_account_info()
            return self.open_passwd()
            
    def setup_group(self):
        if self.opts.group or self.opts.ldif:
            self.load_posix_users()
            self._build_entity2name_mapping(self.co.account_namespace)
            self._build_entity2name_mapping(self.co.group_namespace)
            self.load_groups('group', self.filegroups)
            self.load_group_gids()
            if self.opts.group:
                return self.open_group()

    def setup_netgroup(self):
        if self.opts.netgroup or self.opts.ldif:
            self.load_posix_users()
            self._build_entity2name_mapping(self.co.account_namespace)
            self._build_entity2name_mapping(self.co.group_namespace)
            self.load_groups('netgroup', self.netgroups)
            if self.opts.netgroup:
                return self.open_netgroup()

    def setup_host_netgroup(self):
        if self.opts.host_netgroup or \
                (self.opts.host_netgroup_spread and self.opts.ldif):
            self._build_entity2name_mapping(self.co.group_namespace)
            self._build_entity2name_mapping(self.co.dns_owner_namespace)
            self.load_groups('host-netgroup', self.host_netgroups)
            if self.opts.host_netgroup:
                return self.open_host_netgroup()

    def generate_passwd_output(self, f_ldif, f_passwd, f_shadow):
        if self.opts.ldif:
            f_ldif.write(container_entry_string('USER', module=posixconf))
        elif not self.opts.passwd:
            return
        for row in self.posix_users:
                data = self.gather_user_data(row)
                if data is None:
                    continue
                if self.opts.ldif:
                    dn,entry = self.ldif_user(data)
                    f_ldif.write(entry_string(dn, entry, False))
                if self.opts.passwd:
                    # TODO: shadow
                    passwd = data.passwd
                    try:
                        if self.opts.auth_method == 'NOCRYPT':
                            a = row['account_id']
                            m = self.co.auth_type_crypt3_des
                            if passwd == '*invalid' and self.auth_data[a][m]:
                                passwd = 'x'
                    except KeyError:
                        pass
                    f_passwd.write("%s\n" % self.join((
                        data.uname, passwd, data.uid, data.gid,
                        data.gecos, data.home, data.shell)))

    def generate_filegroup_output(self, f_ldif, f_group):
        if self.opts.ldif:
            f_ldif.write(container_entry_string('FILEGROUP', module=posixconf))
        elif not self.opts.group:
            return
        self.exported_groups = {}
        for row in self.group.search(spread=self.spread_d['group-spread']):
            self.exported_groups[int(row['group_id'])] = row['name']
        # Loop over gids to sort properly
        #for gid in self.filegroups:
        from operator import itemgetter

        #sorted(self.g_id2gid.iteritems(), key=itemgetter(1))
        for g_id, gid in sorted(self.g_id2gid.iteritems(), key=itemgetter(1)):
            if g_id not in self.filegroups:
                continue
            users = self._expand_filegroup(g_id)
            if self.opts.ldif:
                # TODO: description
                dn = ','.join((('cn='+self.filegroups[g_id]), self.fgrp_dn))
                entry = self.ldif_filegroup(self.filegroups[g_id],
                                            gid, None, users)
                f_ldif.write(entry_string(dn, entry, False))
            if self.opts.group:
                f_group.write(self._wrap_line(
                    self.filegroups[g_id], ",".join(users), ':*:%i:' % gid,
                    self._make_tmp_filegroup_name))

    def generate_netgroup_output(self, f_ldif, f_netgroup):
        if self.opts.ldif:
            f_ldif.write(container_entry_string('NETGROUP', module=posixconf))
        elif not self.opts.netgroup:
            return
        self.exported_groups = {}
        for row in self.group.search(spread=self.spread_d['netgroup-spread']):
            self.exported_groups[int(row['group_id'])] = row['name']
        for g_id in self.netgroups:
            name = self.netgroups[g_id]
            group_members, user_members = self.expand_netgroup(
                g_id, self.co.entity_account, self.spread_d["user-spread"])
            if self.opts.ldif:
                #TODO: description
                dn = ','.join((('cn='+self.netgroups[g_id]), self.ngrp_dn))
                entry = self.ldif_netgroup(self.netgroups[g_id], None, 
                                           group_members,
                                           ["(,%s,)" % m for m in user_members])
                f_ldif.write(entry_string(dn, entry, False))
            if self.opts.netgroup:
                f_netgroup.write(self._wrap_line(
                    self.netgroups[g_id], 
                    " ".join((" ".join(group_members),
                              " ".join(["(,%s,)" % m for m in user_members]))), 
                    ' ', self._make_tmp_netgroup_name, is_ng=True))
 
    def generate_host_netgroup_output(self, f_ldif, f_netgroup):
        do_ldif = self.opts.host_netgroup_spread and self.opts.ldif
        if do_ldif:
            f_ldif.write(container_entry_string('HOSTNETGROUP',module=posixconf))
        elif not self.opts.host_netgroup:
            return
        self._num_map = {}
        self.exported_groups = {}
        zone = self.opts.zone.postfix
        for row in self.group.search(spread=self.spread_d['host-netgroup-spread']):
            self.exported_groups[int(row['group_id'])] = row['name']
        for g_id in self.host_netgroups:
            name = self.host_netgroups[g_id]
            group_members, host_members = \
                self.expand_netgroup(g_id,self.co.entity_dns_owner, None)
            formated_host_members = [
                " ".join(sorted(group_members)),
                " ".join(sorted(["(%s,-,)" % m[:-len(zone)] 
                                 for m in host_members
                                 if m.endswith(zone)])),
                " ".join(sorted(["(%s,-,)" % m[:-1] 
                                 for m in host_members]))]
            if do_ldif:
                #TODO: description
                dn = ','.join((('cn='+self.host_netgroups[g_id]), self.hgrp_dn))
                entry = self.ldif_netgroup(self.host_netgroups[g_id], None,
                                           group_members,
                                           formated_host_members)
                f_ldif.write(entry_string(dn, entry, False))
            if self.opts.host_netgroup:
                f_host_netgroup.write(self._wrap_line(
                        self.host_netgroups[g_id], 
                        " ".join(formated_host_members),
                        ' ', self._make_tmp_host_netgroup_name, is_ng=True))

    def open_passwd(self):
        f = SimilarSizeWriter(self.opts.passwd, "w")
        f.set_size_change_limit(10)
        s = None
        if self.opts.shadow:
            s = SimilarSizeWriter(self.opts.shadow, "w")
            s.set_size_change_limit(10)
        return f,s

    def close_passwd(self, f, s):
        if self.opts.eof:
            f.write('E_O_F\n')
        f.close()
        if s:
            s.close()

    def open_ldif(self):
        f_ldif = ldif_outfile('POSIX',filename=self.opts.ldif,module=posixconf)
        f_ldif.write(container_entry_string('POSIX', module=posixconf))
        return f_ldif

    def close_ldif(self, f):
        end_ldif_outfile('POSIX', f, module=posixconf)

    def open_group(self):
        f = SimilarSizeWriter(self.opts.group, "w")
        f.set_size_change_limit(10)
        return f

    def close_group(self, f):
        f.close()

    def open_netgroup(self):
        f = SimilarSizeWriter(self.opts.netgroup, "w")
        f.set_size_change_limit(10)
        return f

    def close_netgroup(self, f):
        f.close()

    def open_host_netgroup(self):
        f = SimilarSizeWriter(self.opts.host_netgroup, "w")
        f.set_size_change_limit(10)
        return f

    def close_host_netgroup(self, f):
        f.close()

    def _build_entity2name_mapping(self, namespace):
        if namespace in self._names:
            return
        en = EntityName(self.db)
        self.logger.debug("list names in %s" % namespace)
        for row in en.list_names(namespace):
            self.e_id2name[int(row['entity_id'])] = row['entity_name']
        self._names.add(namespace)

    def join(self, fields, sep=':'):
        for f in fields:
            if not isinstance(f, str):
                raise ValueError, "Type of '%r' is not str." % f
            if f.find(sep) <> -1:
                raise ValueError, \
                      "Separator '%s' present in string '%s'" % (sep, f)
        return sep.join(fields)

    def load_posix_users(self):
        if self.posix_users: return
        for row in self.posix_user.list_posix_users(
                spread=self.spread_d['user-spread']):
            self.account2def_group[int(row['account_id'])] = int(row['gid'])
            self.posix_users.append(row.copy())

    def load_disk_tab(self):
        if self.disk_tab: return
        for hd in self.disk.list():
            self.disk_tab[int(hd['disk_id'])] = hd['path']

    def load_shell_tab(self):
        if self.shell_tab: return
        for sh in self.posix_user.list_shells():
            self.shell_tab[int(sh['code'])] = sh['shell']

    def load_groups(self, group_type, struct):
        # TBD: This will only act as a filter in reality as e_id2name contains
        # the group name. Make something more clever.
        if struct: return
        spread = self.spread_d[group_type + '-spread']
        for row in self.posix_group.search(spread=int(spread)):
            struct[int(row['group_id'])] = row['name']

    def load_group_gids(self):
        if self.g_id2gid: return
        for row in self.posix_group.list_posix_groups():
            self.g_id2gid[int(row['group_id'])] = int(row['posix_gid'])

    def load_quaratines(self):
        if self.quarantines: return
        now = mx.DateTime.now()
        for row in self.posix_user.list_entity_quarantines(
                            entity_types = self.co.entity_account):
            if (row['start_date'] <= now and (row['end_date'] is None
                                              or row['end_date'] >= now)
                                         and (row['disable_until'] is None
                                              or row['disable_until'] < now)):
                # The quarantine in this row is currently active.
                self.quarantines.setdefault(int(row['entity_id']), []).append(
                    int(row['quarantine_type']))

    def load_person_names(self):
        if self.p_id2name: return
        for n in self.person.list_persons_name(
                source_system=self.co.system_cached,
                name_type=self.co.name_full):
            self.p_id2name[n['person_id']] = n['name']

    def load_account_info(self):
        if self.a_id2owner: return
        for row in self.posix_user.list_account_home(
                home_spread=self.spread_d['user-spread'],
                account_spread=self.spread_d['user-spread'],
                include_nohome=True):
            self.a_id2owner[row['account_id']] = row['owner_id']
            self.a_id2home[row['account_id']] = (
                row['path'], row['disk_id'], row['host_id'], row['home'])

    def _expand_filegroup(self, gid):
        ret = set()
        self.posix_group.clear()
        self.posix_group.find(gid)
        for row in self.posix_group.search_members(
                group_id=self.posix_group.entity_id, 
                indirect_members=True,
                member_type=self.co.entity_account,
                member_spread=self.spread_d["user-spread"]):
            account_id = int(row["member_id"])
            if self.account2def_group.get(account_id) == self.posix_group.entity_id:
                continue  # Don't include the users primary group
            name = self.e_id2name.get(account_id)
            if not name:
                self.logger.warn("Was %i very recently created?" % int(account_id))
                continue
            ret.add(name)
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
        ret_groups = set()
        ret_non_groups = set()
        self.group.clear()
        self.group.find(gid)

        # direct members
        for row in self.group.search_members(
                group_id=self.group.entity_id,
                member_spread=member_spread,
                member_type=member_type):
            member_id = int(row["member_id"])
            name = self.e_id2name.get(member_id)
            if not name:
                if not self._is_new(member_id):
                    self.logger.warn("Was %i very recently created?", member_id)
                continue
            ret_non_groups.add(name)
        
        # subgroups
        for row in self.group.search_members(group_id=gid,
                                             member_type=self.co.entity_group):
            t_gid = int(row["member_id"])
            if t_gid in self.exported_groups:
                ret_groups.add(self.exported_groups[t_gid])
            else:
                t_g, t_ng = self.expand_netgroup(t_gid, member_type, member_spread)
                ret_groups.update(t_g)
                ret_non_groups.update(t_ng)

        return ret_groups, ret_non_groups

    def _wrap_line(self, group_name, line, g_separator, proc, is_ng=False):
        if is_ng:
            delim = ' '
        else:
            delim = ','
        ret = ''
        maxlen = MAX_LINE_LENGTH - (len(group_name) + len(g_separator))
        while len(line) > maxlen:
            tmp_gname = proc(group_name)
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


    def gather_user_data(self, row):
        data = PosixUserData()
        data.account_id = int(row['account_id'])
        data.uname = self.e_id2name[data.account_id]
        data.uid = str(row['posix_uid'])
        data.gid = str(self.g_id2gid[row['gid']])

        if not row['shell']:
            self.logger.warn("User %s has no posix-shell!" % data.uname)
            return None
        data.shell = self.shell_tab[int(row['shell'])]

        data.quarantined, data.passwd = False, '*invalid'
        if data.account_id in self.quarantines:
            qh = QuarantineHandler(self.db, self.quarantines[data.account_id])
            if qh.should_skip():
                return None
            if qh.is_locked():
                data.quarantined, data.passwd = True, '*locked'
            qshell = qh.get_shell()
            if qshell is not None:
                data.shell = qshell
        try:
            if self.a_id2home[data.account_id][1]:
                disk_path = self.disk_tab[int(self.a_id2home[data.account_id][1])]
            else:
                disk_path = None
            data.home = self.posix_user.resolve_homedir(
                account_name=data.uname,
                home=self.a_id2home[data.account_id][3], disk_path=disk_path)
        except:
            self.logger.warn("User %s has no home-directory!" % data.uname)
            return None

        cn = None
        if data.account_id in self.a_id2owner:
            cn = self.p_id2name.get(self.a_id2owner[data.account_id])
        data.gecos = latin1_to_iso646_60(row['gecos'] or cn or data.uname)
        data.cn    = cn or data.gecos
        return data

    def ldif_user(self, data):
        passwd = '{crypt}%s' % data.passwd
        for uauth in filter(self.auth_format.has_key, self.a_meth):
            #method = int(self.co.auth_type_crypt3_des)
            try:
                #if uauth in self.auth_format.keys():
                fmt = self.auth_format[uauth]['format']
                if fmt:
                    passwd = fmt % self.auth_data[data.account_id][uauth]
                    passwd_attr = self.auth_format[uauth]['attr']
                else:
                    passwd = self.auth_data[data.account_id][uauth]
            except KeyError:
                pass
        entry = {'objectClass':   ['top','account','posixAccount'],
                 'cn':            (iso2utf(data.cn),),
                 'uid':           (data.uname,),
                 'uidNumber':     (data.uid,),
                 'gidNumber':     (data.gid,),
                 'homeDirectory': (data.home,),
                 'userPassword':  (passwd,),
                 'loginShell':    (data.shell,),
                 'gecos':         (data.gecos,)}
        dn = ','.join((('uid=' + data.uname), self.user_dn))
        return dn,entry


    def ldif_filegroup(self, name, gid, desc, members):
        """Create the group-entry attributes"""
        entry = {'objectClass': ('top', 'posixGroup'),
                 'cn':          (name,),
                 'gidNumber':   (str(gid),)}
        if desc:
            # latin1_to_iso646_60 later
            entry['description'] = (iso2utf(desc),)
        # There may be duplicates in the resulting sequence
        entry['memberUid'] = members
        return entry

    def ldif_netgroup(self, name, desc, direct_members, group_members):
        """Create the group-entry attributes"""
        entry = {'objectClass': ('top', 'nisNetGroup'),
                 'cn':          (name,),}
        if desc:
            # latin1_to_iso646_60 later
            entry['description'] = (iso2utf(desc),)
        # There may be duplicates in the resulting sequence
        entry['nisNetgroupTriple'] = direct_members
        entry['memberNisNetgroup'] = group_members
        return entry


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
        if self.opts.passwd:
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
            for x in self.posix_user.list_account_authentication(
                    auth_type=self.a_meth):
                if not (x['account_id'] and x['method']):
                    continue
                acc_id, meth = int(x['account_id']), int(x['method'])
                if acc_id not in self.auth_data:
                    self.auth_data[acc_id] = {meth : x['auth_data']}
                else:
                    self.auth_data[acc_id][meth] = x['auth_data']

    def _is_new(self, entity_id):
        """
        Returns true if there is a change log create event for 
        entity_id (group or account) since we cached entity names.
        """
        try:
            events = list(self.db.get_log_events(
                    types=(self.co.group_create, self.co.account_create),
                    subject_entity=entity_id,
                    sdate=self._namecachedtime))
            return bool(events)
        except:
            self.logger.debug("Checking change log failed: %s", sys.exc_value)
        return False


class PosixExportRadius(PosixExport):
    """General mixin for Radius type attributes."""
    # Based on Cerebrum.modules.PosixLDIF.PosixLDIFRadius

    def ldif_auth_methods(self):
	# Also fetch NT password, for attribute sambaNTPassword.
        meth = super(PosixExportRadius, self).ldif_auth_methods()
        if self.opts.ldif:
            self.auth_type_radius = int(self.co.auth_type_md4_nt)
            meth.append(self.auth_type_radius)
	return meth

    def ldif_user(self, data):
        # Add sambaNTPassword (used by FreeRadius)
        dn, entry = ret = super(PosixExportRadius, self).ldif_user(data)
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
