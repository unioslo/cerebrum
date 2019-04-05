# -*- coding: utf-8 -*-
# Copyright 2004-2018 University of Oslo, Norway
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
""" Common POSIX LDIF generator. """
from __future__ import unicode_literals

import logging
from collections import defaultdict
from six import text_type

import cereconf
from Cerebrum.modules import LDIFutils
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory, auto_super, make_timer
from Cerebrum.utils import transliterate
from Cerebrum import Errors
from Cerebrum.modules.posix.UserExporter import HomedirResolver
from Cerebrum.modules.posix.UserExporter import OwnerResolver
from Cerebrum.modules.posix.UserExporter import UserExporter
from Cerebrum.modules.posix.UserExporter import make_clock_time


logger = logging.getLogger(__name__)
clock_time = make_clock_time(logger)


class PosixLDIF(object):
    """ Generates posix-user, -filegroups and -netgroups.
    Does not support hosts in netgroups.
    """
    __metaclass__ = auto_super

    def __init__(self, db, logger, u_sprd=None, g_sprd=None, n_sprd=None,
                 fd=None):
        """ Initiate database and import modules.

        Spreads are given in initiation and general constants which is
        used in more than one method.

        """
        timer = make_timer(logger, 'Initing PosixLDIF...')
        from Cerebrum.modules import PosixGroup
        self.db = db
        self.logger = logger
        self.const = Factory.get('Constants')(self.db)
        self.grp = Factory.get('Group')(self.db)
        self.posuser = Factory.get('PosixUser')(self.db)
        self.posgrp = PosixGroup.PosixGroup(self.db)
        self.user_dn = LDIFutils.ldapconf('USER', 'dn', None)
        self.get_name = True
        self.fd = fd
        self.spread_d = {}
        # Validate spread from arg or from cereconf
        for x, y in zip(['USER', 'FILEGROUP', 'NETGROUP'],
                        [u_sprd, g_sprd, n_sprd]):
            spread = LDIFutils.map_spreads(
                y or getattr(cereconf, 'LDAP_' + x).get('spread'), list)
            if spread:
                self.spread_d[x.lower()] = spread
        if 'user' not in self.spread_d:
            raise Errors.ProgrammingError(
                "Must specify spread-value as 'arg' or in cereconf")
        self.account2name = dict()
        self.group2gid = dict()
        self.groupcache = defaultdict(dict)
        self.group2groups = defaultdict(set)
        self.group2users = defaultdict(set)
        self.group2persons = defaultdict(list)
        self.shell_tab = dict()
        self.quarantines = dict()

        self.user_exporter = UserExporter(self.db)
        if len(self.spread_d['user']) > 1:
            logger.warning('Exporting users with multiple spreads, '
                           'ignoring homedirs from %r',
                           self.spread_d['user'][1:])
        self.homedirs = HomedirResolver(db, self.spread_d['user'][0])
        self.owners = OwnerResolver(db)
        timer('... done initing PosixLDIF.')

    @clock_time
    def user_ldif(self, filename=None, auth_meth=None):
        """Generate posix-user."""
        self.init_user(auth_meth)
        f = LDIFutils.ldif_outfile('USER', filename, self.fd)
        f.write(LDIFutils.container_entry_string('USER'))
        for row in self.posuser.list_posix_users(
            spread=self.spread_d['user'],
            filter_expired=True
        ):
            if (row['account_id'] not in
                    self.account2auth):
                continue
            dn, entry = self.user_object(row)
            if dn:
                f.write(LDIFutils.entry_string(dn, entry, False))
        LDIFutils.end_ldif_outfile('USER', f, self.fd)

    @clock_time
    def init_user(self, auth_meth=None):
        self.get_name = False
        self.qh = QuarantineHandler(self.db, None)
        self.posuser = Factory.get('PosixUser')(self.db)

        self.shell_tab = self.user_exporter.shell_codes()
        self.quarantines = self.user_exporter.make_quarantine_cache(
            self.spread_d['user']
        )
        self.owners.make_owner_cache()
        self.owners.make_name_cache()
        self.homedirs.make_home_cache()
        self.group2gid = self.user_exporter.make_posix_gid_cache()
        self.account2auth = self.user_exporter.make_auth_cache(
            spread=self.spread_d['user'],
            auth_method=auth_meth,
        )
        self.load_auth_tab(auth_meth)
        self.cache_account2name()
        self.id2uname = {}

    @clock_time
    def cache_account2name(self):
        """Cache account_id to username.
           This one is a bit more lenient that what the self.id2uname
           dictionary contains, as it blindly adds users with correct
           spread."""
        if not self.get_name:
            return
        if len(self.account2name) > 0:
            return
        self.account2name = dict(
            (r['account_id'], r['name']) for r in
            self.posuser.search(spread=self.spread_d['user'],
                                expire_start=None,
                                expire_stop=None))

    @clock_time
    def cache_groups_and_users(self):
        if len(self.group2groups) or len(self.group2users):
            return

        def get_children_not_in_group2groups():
            children = set()
            map(children.update, self.group2groups.itervalues())
            return children.difference(self.group2groups.keys())

        spread = []
        for s in ('filegroup', 'netgroup'):
            if s in self.spread_d:
                spread += self.spread_d[s]

        assert spread

        for row in self.grp.search_members(
                member_type=self.const.entity_group,
                spread=spread):
            self.group2groups[row['group_id']].add(row['member_id'])

        for row in self.grp.search_members(
                member_type=self.const.entity_account,
                member_spread=self.spread_d['user'][0],
                spread=spread):
            self.group2users[row['group_id']].add(row['member_id'])

        children_groups = get_children_not_in_group2groups()
        extra_groups = children_groups.copy()
        while children_groups:
            for group_id in children_groups:
                self.group2groups[group_id] = set()
            for row in self.grp.search_members(
                    member_type=self.const.entity_group,
                    group_id=children_groups):
                member_id = row['member_id']
                self.group2groups[row['group_id']].add(member_id)
                extra_groups.add(member_id)
            children_groups = get_children_not_in_group2groups()

        if extra_groups:
            for row in self.grp.search_members(
                    member_type=self.const.entity_account,
                    member_spread=self.spread_d['user'][0],
                    group_id=extra_groups):
                self.group2users[row['group_id']].add(row['member_id'])

    def cache_group2persons(self):
        """Cache person members in groups. Not used in main module."""
        pass

    def auth_methods(self, auth_meth=None):
        """Which authentication methods to fetch. Mixin-support.
        If all only one entry, it will prefect any in auth_table.
        If None, it will use default API authentication (md5_crypt).
        """
        self.auth_format = {}
        auth_meth_l = []
        self.user_auth = None
        code = '_AuthenticationCode'
        # Priority is arg, else cereconf default value
        # auth_meth_l is a list sent to load_auth_tab and contains
        # all methods minus primary which is called by
        auth = auth_meth or cereconf.LDAP['auth_attr']
        if isinstance(auth, dict):
            if 'userPassword' not in auth:
                self.logger.warn("Only support 'userPassword'-attribute")
                return None
            default_auth = auth['userPassword'][:1][0]
            self.user_auth = LDIFutils.map_constants(code, default_auth[0])
            if len(default_auth) == 2:
                format = default_auth[1]
            else:
                format = None
            self.auth_format[int(self.user_auth)] = {'attr': 'userPassword',
                                                     'format': format}
            for entry in auth['userPassword'][1:]:
                auth_t = LDIFutils.map_constants(code, entry[0])
                if len(entry) == 2:
                    format = entry[1]
                else:
                    format = None
                auth_meth_l.append(auth_t)
                self.auth_format[int(auth_t)] = {'attr': 'userPassword',
                                                 'format': format}
        if isinstance(auth, (list, tuple)):
            self.user_auth = int(getattr(self.const, auth[:1][0]))
            for entry in auth[1:]:
                auth_meth_l.append(int(getattr(self.const, entry)))
        elif isinstance(auth, str):
            self.user_auth = int(getattr(self.const, auth))
        return auth_meth_l

    @clock_time
    def load_auth_tab(self, auth_meth=None):
        self.a_meth = self.auth_methods(auth_meth)
        if not self.a_meth:
            return
        self.auth_data = defaultdict(dict)
        for x in self.posuser.list_account_authentication(
                auth_type=self.a_meth,
                spread=self.spread_d['user']
        ):
            if not x['account_id'] or not x['method']:
                continue
            acc_id, meth = int(x['account_id']), int(x['method'])
            self.auth_data[acc_id][meth] = x['auth_data']

    def user_object(self, row):
        account_id = int(row['account_id'])
        uname, auth_data = self.account2auth[account_id]
        passwd = '{crypt}*Invalid'

        if auth_data:
            if self.auth_format[self.user_auth]['format']:
                passwd = self.auth_format[self.user_auth]['format'] % \
                        auth_data
            else:
                passwd = auth_data
        else:
            for uauth in [x for x in self.a_meth if x in self.auth_format]:
                try:
                    if self.auth_format[uauth]['format']:
                        passwd = self.auth_format[uauth]['format'] % \
                                self.auth_data[account_id][uauth]
                    else:
                        passwd = self.auth_data[account_id][uauth]

                except KeyError:
                    pass
        if not row['shell']:
            self.logger.warn("User %s has no POSIX shell", uname)
            return None, None
        else:
            shell = self.shell_tab[int(row['shell'])]
        if account_id in self.quarantines:
            self.qh.quarantines = self.quarantines[account_id]
            if self.qh.should_skip():
                return None, None
            if self.qh.is_locked():
                passwd = '{crypt}' + '*Locked'
            qshell = self.qh.get_shell()
            if qshell is not None:
                shell = qshell

        home = self.homedirs.get_homedir(row['account_id'], allow_no_disk=True)
        if not home:
            self.logger.warn("User %s has no home directory", uname)
            return None, None

        owner_id = self.owners.get_owner_id(row['account_id'])
        fullname = self.owners.get_name(row['account_id'])
        cn = fullname or row['gecos'] or uname
        gecos = transliterate.to_iso646_60(row['gecos'] or cn)
        posix_gid = self.group2gid[row['gid']]
        entry = {
            'objectClass': ['top', 'account', 'posixAccount'],
            'cn': (cn,),
            'uid': (uname,),
            'uidNumber': (text_type(row['posix_uid']),),
            'gidNumber': (text_type(posix_gid),),
            'homeDirectory': (home,),
            'userPassword': (passwd,),
            'loginShell': (shell,),
            'gecos': (gecos,)
        }
        self.update_user_entry(account_id, entry, owner_id)
        if account_id not in self.id2uname:
            self.id2uname[account_id] = uname
        else:
            self.logger.warn('Duplicate user entry: (%s, %s)',
                             account_id, uname)
            return None, None
        dn = ','.join((('uid=' + uname), self.user_dn))
        return dn, entry

    def update_user_entry(self, account_id, entry, row):
        """ Called by user_object(). Inject additional data here. """
        pass

    @clock_time
    def filegroup_ldif(self, filename=None):
        """ Generate filegroup.

        Groups without group and expanded members from both external and
        internal groups.

        """
        if 'filegroup' not in self.spread_d:
            self.logger.warn("No spread is given for filegroup!")
            return

        self.init_filegroup()
        timer2 = make_timer(self.logger, 'Caching filegroups...')
        for row in self.grp.search(spread=self.spread_d['filegroup'],
                                   filter_expired=False):
            group_id = row['group_id']
            if group_id not in self.group2gid:
                self.logger.warn(
                    "Group id:{} has one of {} but no GID, skipping".format(
                        group_id,
                        getattr(cereconf,
                                'LDAP_FILEGROUP').get('spread'), []))
                continue
            self.create_group_object(group_id, row['name'],
                                     row['description'])
            self.create_filegroup_object(group_id)
            self.update_filegroup_entry(group_id)
        timer2('... done caching filegroups')
        self.cache_uncached_children()
        timer2 = make_timer(self.logger, 'Adding users and groups...')
        for group_id, entry in self.filegroupcache.iteritems():
            users = self.get_users(group_id, set())
            unames = self.userid2unames(users, group_id)
            entry['memberUid'] = unames
        timer2('... done adding users')
        timer2 = make_timer(self.logger, 'Writing group objects...')
        f = LDIFutils.ldif_outfile('FILEGROUP', filename, self.fd)
        f.write(LDIFutils.container_entry_string('FILEGROUP'))
        for group_id, entry in self.filegroupcache.iteritems():
            dn = ','.join(('cn=' + entry['cn'], self.fgrp_dn))
            f.write(LDIFutils.entry_string(dn, entry, False))
        timer2('... done writing group objects')
        self.filegroupcache = None
        LDIFutils.end_ldif_outfile('FILEGROUP', f, self.fd)

    def init_filegroup(self):
        """Initiate modules and constants for posixgroup"""
        from Cerebrum.modules import PosixGroup
        self.posgrp = PosixGroup.PosixGroup(self.db)
        self.fgrp_dn = LDIFutils.ldapconf('FILEGROUP', 'dn')
        self.filegroupcache = defaultdict(dict)
        self.cache_account2name()
        self.group2gid = self.user_exporter.make_posix_gid_cache()
        self.cache_groups_and_users()

    def create_filegroup_object(self, group_id):
        assert group_id not in self.filegroupcache
        cache = self.groupcache[group_id]
        entry = {
            'objectClass': ('top', 'posixGroup'),
            'cn': cache['name'],
            'gidNumber': text_type(self.group2gid[group_id]),
        }
        if 'description' in cache:
            entry['description'] = (cache['description'],)
        self.filegroupcache[group_id] = entry

    def update_filegroup_entry(self, group_id):
        """Future use of mixin-classes"""
        pass

    @clock_time
    def netgroup_ldif(self, filename=None):
        """Generate netgroup with only users."""

        if 'netgroup' not in self.spread_d:
            self.logger.warn("No valid netgroup-spread in cereconf or arg!")
            return

        self.init_netgroup()
        timer2 = make_timer(self.logger, 'Caching netgroups...')
        for row in self.grp.search(spread=self.spread_d['netgroup'],
                                   filter_expired=False):
            group_id = row['group_id']
            self.create_group_object(group_id, row['name'],
                                     row['description'])
            self.create_netgroup_object(group_id)
        timer2('... done caching filegroups')
        self.cache_uncached_children()
        timer2 = make_timer(self.logger, 'Adding users and groups...')
        for group_id, entry in self.netgroupcache.iteritems():
            users, groups = self.get_users_and_groups(group_id, set(), set(),
                                                      add_persons=True)
            unames = self.userid2unames(users, group_id)
            triple = []
            for uname in unames:
                if '_' in uname:
                    continue
                triple.append('(,%s,)' % uname)

            netgroup = []
            for g in groups:
                netgroup.append(self.netgroupcache[g]['cn'])

            entry['nisNetgroupTriple'] = triple
            entry['memberNisNetgroup'] = netgroup
        timer2('... done adding users and groups')
        timer2 = make_timer(self.logger, 'Writing group objects...')
        f = LDIFutils.ldif_outfile('NETGROUP', filename, self.fd)
        f.write(LDIFutils.container_entry_string('NETGROUP'))
        for group_id, entry in self.netgroupcache.iteritems():
            dn = ','.join(('cn=' + entry['cn'], self.ngrp_dn))
            f.write(LDIFutils.entry_string(dn, entry, False))
        LDIFutils.end_ldif_outfile('NETGROUP', f, self.fd)
        timer2('... done writing group objects')
        self.netgroupcache = None

    @clock_time
    def cache_uncached_children(self):
        children = set()
        map(children.update, self.group2groups.itervalues())
        extra = children.difference(self.groupcache.keys())
        if extra:
            for row in self.grp.search(group_id=extra):
                self.create_group_object(row['group_id'], row['name'],
                                         row['description'])

    def get_users_and_groups(self, group_id, users, groups, add_persons=False):
        """Recursive method to get members and groups in a group."""
        users.update(self.group2users[group_id])
        if add_persons:
            if group_id in self.group2persons:
                users.update(self.group2persons[group_id])

        for g_id in self.group2groups[group_id]:
            assert g_id in self.groupcache, "g_id %s in group_id %s missing" % \
                (g_id, group_id)
            if g_id in self.netgroupcache:
                groups.add(g_id)
            else:
                users, groups = self.get_users_and_groups(g_id, users, groups,
                                                          add_persons)

        return users, groups

    def get_users(self, group_id, users, add_persons=False):
        """Recursive method to get members from a group."""
        users.update(self.group2users[group_id])
        if add_persons:
            if group_id in self.group2persons:
                users.update(self.group2persons[group_id])

        for g_id in self.group2groups[group_id]:
            assert g_id in self.groupcache, "g_id %s in group_id %s missing" % \
                (g_id, group_id)
            users = self.get_users(g_id, users)

        return users

    def create_netgroup_object(self, group_id):
        assert group_id not in self.netgroupcache
        cache = self.groupcache[group_id]
        entry = {
            'objectClass': ('top', 'nisNetGroup'),
            'cn': cache['name'],
        }
        if 'description' in cache:
            entry['description'] = \
                transliterate.to_iso646_60(cache['description']).rstrip(),
        self.netgroupcache[group_id] = entry

    def init_netgroup(self):
        """Initiate modules, constants and cache"""
        self.ngrp_dn = LDIFutils.ldapconf('NETGROUP', 'dn')
        self.cache_account2name()
        self.cache_groups_and_users()
        self.cache_group2persons()
        self.netgroupcache = defaultdict(dict)

    def create_group_object(self, group_id, name, description):
        if group_id in self.groupcache:
            return

        self.groupcache[group_id] = {'name': name}

        if description:
            self.groupcache[group_id]['description'] = description

    def userid2unames(self, users, group_id):
        unames = []
        for user_id in users:
            if self.get_name:
                try:
                    uname = self.account2name[user_id]
                except Exception:
                    self.logger.info("account2name user id=%s in "
                                     "group id=%s not found",
                                     user_id, group_id)
                    continue
            else:
                try:
                    uname = self.id2uname[user_id]
                except Exception:
                    self.logger.info("Cache enabled but user id=%s in "
                                     "group id=%s not found",
                                     user_id, group_id)
                    continue
            unames.append(uname)
        return unames


class PosixLDIFRadius(PosixLDIF):
    """ General mixin for Radius type attributes. """

    def auth_methods(self, auth_meth=None):
        # Also fetch NT password, for attribute sambaNTPassword.
        meth = self.__super.auth_methods(auth_meth)
        meth.append(int(self.const.auth_type_md4_nt))
        return meth

    def update_user_entry(self, account_id, entry, owner_id):
        # sambaNTPassword (used by FreeRadius)
        try:
            hash = self.auth_data[account_id][int(self.const.auth_type_md4_nt)]
        except KeyError:
            pass
        else:
            skip = False
            if account_id in self.quarantines:
                self.qh.quarantines = self.quarantines[account_id]
                if self.qh.should_skip() or self.qh.is_locked():
                    skip = True
            if not skip:
                entry['sambaNTPassword'] = (hash,)
                # TODO: Remove sambaSamAccount and sambaSID after Radius-testing
                entry['objectClass'].append('sambaSamAccount')
                entry['sambaSID'] = entry['uidNumber']
        return self.__super.update_user_entry(account_id, entry, owner_id)


class PosixLDIFMail(PosixLDIF):
    """ PosixLDIF mixin for mail attributes. """

    def init_user(self, *args, **kwargs):
        self.__super.init_user(*args, **kwargs)
        timer = make_timer(self.logger, 'Starting PosixLDIFMail.init_user...')

        self.mail_attrs = cereconf.LDAP_USER.get('mail_attrs', ['mail'])

        from string import Template
        self.mail_template = Template(cereconf.LDAP_USER.get(
            'mail_default_template'))

        mail_spreads = LDIFutils.map_spreads(
            cereconf.LDAP_USER.get('mail_spreads'), list)
        self.accounts_with_email = set()
        for account_id, spread in self.posuser.list_entity_spreads(
                entity_types=self.const.entity_account):
            if spread in mail_spreads:
                self.accounts_with_email.add(account_id)

        timer('...done PosixLDIFMail.init_user')

    def update_user_entry(self, account_id, entry, owner_id):
        mail = None
        if account_id in self.accounts_with_email:
            mail = self.mail_template.substitute(uid=entry['uid'][0])
        else:
            contacts = self.posuser.list_contact_info(
                entity_id=account_id,
                source_system=self.const.system_manual,
                contact_type=self.const.contact_email)
            if contacts:
                mail = contacts[0]['contact_value']
        if mail:
            for attr in self.mail_attrs:
                entry[attr] = (mail, )
        else:
            self.logger.warn('Account %s is missing mail', entry['uid'][0])
        return self.__super.update_user_entry(account_id, entry, owner_id)
