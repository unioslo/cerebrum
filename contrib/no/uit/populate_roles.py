#!/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003, 2004, 2019 University of Oslo, Norway
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
"""
Populate role groups from SystemY

rolenames=role:<rolename from xml>

if rolename has admin attr=yes
  build an admin accont ( 999-style)
"""

import argparse
import logging
import os
import time
import xml.sax

import Cerebrum.logutils
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit.Account import UsernamePolicy
from Cerebrum.utils import transliterate
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)

db = Factory.get('Database')()
db.cl_init(change_program='pop_itroles')
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
const = Factory.get('Constants')(db)

account2name = dict((x["entity_id"], x["entity_name"]) for x in
                    Factory.get("Group")(db).list_names(
                        const.account_namespace))
name_gen = UsernamePolicy(db)

TODAY = time.strftime("%Y%m%d")
sys_y_default_file = os.path.join(cereconf.DUMPDIR,
                                  'sysY', 'sysY_%s.xml' % TODAY)


class RolesXmlParser(xml.sax.ContentHandler):
    """Parserklasse for it_roles.xml."""

    elements = {'roles': False,
                'role': True,
                'member': True,
                }

    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name == 'roles':
            pass
        elif name == 'role':
            self.role_attrs = {}
            self.role_members = []
            for k in attrs.keys():
                self.role_attrs[k] = attrs.get(k)
        elif name == 'member':
            self._elemdata = []
        else:
            logger.error("UNKNOWN ELEMENT: %s", name)

    def characters(self, ch):
        self.var = None
        tmp = ch.encode('iso8859-1').strip()  # TODO: Should this be changed?
        if tmp:
            self.var = tmp
            self._elemdata.append(tmp)

    def endElement(self, name):
        if name == 'role':
            self.call_back_function(self, name)
        elif name == 'member':
            self.call_back_function(self, name)
        elif name == 'roles':
            pass
        else:
            logger.error("UNKNOWN ELEMENT: %s", name)


account_cache = {}


def get_account(name):
    cache_hit = account_cache.get(name)
    if cache_hit:
        return cache_hit
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    account_cache[name] = ac
    return ac


def get_group(id):
    gr = PosixGroup.PosixGroup(db)
    if isinstance(id, int):
        gr.find(id)
    else:
        gr.find_by_name(id)
    return gr


class ITRole(object):

    def __init__(self, role_name, admin, members):
        self.group_name = role_name
        self.buildadmins = admin
        self.group_members = members

    def group_creator(self):
        creator_ac = get_account(cereconf.INITIAL_ACCOUNTNAME)
        return creator_ac.entity_id

    def maybe_create(self, group_name):
        try:
            return get_group(group_name)
        except Errors.NotFoundError:
            description = "IT role group (%s)" % group_name
            pg = PosixGroup.PosixGroup(db)
            pg.populate(self.group_creator(),
                        const.group_visibility_internal,
                        self.group_name,
                        description=description)
            pg.write_db()
            logger.info("Created group: name=%s, id=%d, gid=%d, desc='%s'",
                        pg.group_name, pg.entity_id, pg.posix_gid,
                        pg.description)

            if self.buildadmins:
                pg.add_spread(const.spread_uit_ad_lit_admingroup)
            else:
                pg.add_spread(const.spread_uit_ad_group)
            return pg

    def maybe_create_admin(self, person_id):
        # this person should have two accounts.
        # a primary account, eg bto001
        # and a admin account, eg bto999
        new_ac = PosixUser.PosixUser(db)
        pri_ac = PosixUser.PosixUser(db)
        person.clear()
        person.find(person_id)
        pri_account_id = person.get_primary_account()
        if pri_account_id is None:
            logger.warn("Primary account for person_id=%r not found, "
                        "account expired?", person_id)
            return
        pri_ac.find(pri_account_id)
        existing_acc_types = pri_ac.get_account_types(owner_id=person_id,
                                                      filter_expired=False)
        default_expire_date = pri_ac.expire_date
        admin_priority = 920
        accounts = new_ac.search(spread=const.spread_uit_ad_lit_admin,
                                 owner_id=person_id,
                                 expire_start=None)
        if len(accounts) == 0:
            # does not have account in spread ad_lit_admin, create and set
            # spread
            logger.debug("Create admin account for %s", person_id)
            ext_id = person.get_external_id(id_type=const.externalid_fodselsnr)
            # FIXME: may bang if person only from sysX !??
            ssn = ext_id[0]['external_id']
            full_name = person.get_name(const.system_cached, const.name_full)
            new_username = name_gen.get_uit_uname(ssn, full_name,
                                                  regime='ADMIN')
            logger.debug("GOT account_name=%r", new_username)
            creator = get_account(cereconf.INITIAL_ACCOUNTNAME)
            creator_id = creator.entity_id
            new_ac.clear()
            new_ac.populate(
                name=new_username,
                owner_id=person.entity_id,
                owner_type=const.entity_person,
                np_type=None,
                creator_id=creator_id,
                expire_date=default_expire_date,
                posix_uid=new_ac.get_free_uid(),
                gid_id=1623,  # int(group.entity_id),
                gecos=transliterate.for_gecos(full_name),
                shell=const.posix_shell_bash,
            )
            new_ac.write_db()

            # AD litadmin spread
            new_ac.add_spread(const.spread_uit_ad_lit_admin)
            new_ac.set_home_dir(const.spread_uit_ad_lit_admin)

            # Set spread expire date
            new_ac.set_spread_expire(spread=const.spread_uit_ad_lit_admin,
                                     expire_date=default_expire_date)

            password = new_ac.make_passwd(new_username)
            new_ac.set_password(password)

            new_ac.set_account_type(existing_acc_types[0]['ou_id'],
                                    existing_acc_types[0]['affiliation'],
                                    admin_priority)

            new_ac.write_db()
            return new_ac.account_name
        elif len(accounts) == 1:
            # sync account to person's primary account. expire date that is...
            new_ac.clear()
            new_ac.find(accounts[0]['account_id'])
            new_ac.expire_date = default_expire_date

            # Set spread expire date
            new_ac.set_spread_expire(spread=const.spread_uit_ad_lit_admin,
                                     expire_date=default_expire_date)

            new_ac.write_db()
            return accounts[0]['name']
        else:
            logger.error("TOO MANY ACCOUNTS FOUND for with "
                         "spread_uit_ad_lit_admin for %s!", person_id)
            raise db.IntegrityError

    def translate2admins(self, accountList):
        admlist = []
        for a in accountList:
            try:
                parent = get_account(a)
            except Errors.NotFoundError:
                logger.error(
                    "Account %s not found. Cannot create admin account!", a)
                continue
            admin = self.maybe_create_admin(parent.owner_id)
            if admin:
                admlist.append(admin)
        return admlist

    def sync_members(self):
        group = self.maybe_create(self.group_name)
        current_members = []
        for member in group.search_members(group_id=group.entity_id,
                                           indirect_members=True,
                                           member_type=const.entity_account,
                                           member_filter_expired=False):
            member_id = int(member["member_id"])
            if member_id not in account2name:
                continue
            current_members.append(account2name[member_id])

        current = set(current_members)
        logger.debug("CURRENT MEMBERS: %s", current)
        if self.buildadmins == 'yes':
            new = set(self.translate2admins(self.group_members))
        else:
            new = set(self.group_members)

        logger.info("group: %s, members should be %s", self.group_name, new)
        toAdd = new - current
        toRemove = current - new

        logger.info("TO ADD: %s", toAdd)
        logger.info("TO REM: %s", toRemove)

        for name in toRemove:
            acc = get_account(name)
            group.remove_member(acc.entity_id)

        for name in toAdd:
            logger.info("Trying to add %s", name)
            try:
                acc = get_account(name)
                group.add_member(acc.entity_id)
            except Errors.NotFoundError:
                logger.error("Could not add %s to %s, account not found",
                             name, group.group_name)
                continue


def process_role(name, attrs, members):
    logger.info(
        "PROCESS ROLE: name=%s, attrs=%s,members=%s", name, attrs, members)

    role_prefix = 'role'
    role_name = "%s:%s" % (role_prefix, attrs.get('name'))
    admin = attrs.get('admin')
    work = ITRole(role_name, admin, members)
    work.sync_members()


def rolle_helper(obj, el_name):
    if el_name == 'role':
        process_role(el_name, obj.role_attrs, obj.role_members)
        pass
    elif el_name == 'member':
        attribute = obj._elemdata
        member_name = ''.join(attribute)
        obj.role_members.append(member_name)
    return


def main(inargs=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('-r', '--role_file',
                        help='role filename',
                        default=sys_y_default_file)
    parser = add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    RolesXmlParser(args.role_file, rolle_helper)

    if args.commit:
        logger.info("Commiting changes")
        db.commit()
    else:
        logger.info("Dryrun, rollback changes")
        db.rollback()


if __name__ == '__main__':
    main()
