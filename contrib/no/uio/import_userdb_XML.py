#!/usr/bin/env python2.2

# Copyright 2002, 2003 University of Oslo, Norway
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

# $Id$

"""
Reads XML files with user and person data from file, and imports them
into cerebrum.  Contains some UREG specific parts, but attempt has
been made to isolate these so that this script also can be used with
other sources.
"""

import cerebrum_path

import pprint
import xml.sax
import sys
import getopt
import cereconf
from time import gmtime, strftime, time

from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules.no import Stedkode
from Cerebrum.Utils import Factory

default_personfile = ''
default_groupfile = ''
db = Factory.get('Database')()
db.cl_init(change_program='migrate_iux')
co = Factory.get('Constants')(db)
pp = pprint.PrettyPrinter(indent=4)
prev_msgtime = time()

user_creators = {}     # Store post-processing info for users
uname2entity_id = {}
deleted_users = {}
uid_taken = {}

namestr2const = {'lname': co.name_last, 'fname': co.name_first}
personObj = Factory.get('Person')(db)
posix_user = PosixUser.PosixUser(db)
disk2id = {}
account = Account.Account(db)
account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
acc_creator_id = account.entity_id
pwdhist = PasswordHistory.PasswordHistory(db)

shell2shellconst = {
    'bash': co.posix_shell_bash,
    'csh': co.posix_shell_csh,
    'false': co.posix_shell_false,
    'nologin': co.posix_shell_nologin,
    'nologin.autostud': co.posix_shell_nologin,  # TODO: more shells, (and their path)
    'nologin.brk': co.posix_shell_nologin,
    'nologin.chpwd': co.posix_shell_nologin,
    'nologin.ftpuser': co.posix_shell_nologin,
    'nologin.nystudent': co.posix_shell_nologin,
    'nologin.pwd': co.posix_shell_nologin,
    'nologin.sh': co.posix_shell_nologin,
    'nologin.sluttet': co.posix_shell_nologin,
    'nologin.stengt': co.posix_shell_nologin,
    'nologin.teppe': co.posix_shell_nologin,
    'puberos': co.posix_shell_nologin,
    'sftp-server': co.posix_shell_nologin,
    'sh': co.posix_shell_sh,
    'tcsh': co.posix_shell_tcsh,
    'zsh': co.posix_shell_zsh,
    }

class PersonUserParser(xml.sax.ContentHandler):
    """Parser for the users.xml file.  Stores recognized data in an
    internal datastructure"""

    def __init__(self, call_back_function):
        self.personer = []
        self.elementstack = []
        self.call_back_function = call_back_function

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
        if name == "persons":
            pass
        elif name == "person":
            self.person = {'bdate': tmp['bdate']}
        elif self.elementstack[-1] == "user":
            if name in ("auth", "spread", "name", "pwdhist"):
                self.user[name] = self.user.get(name, []) + [tmp]
            elif name in ("uio", "printerquota", "quarantine"):
                self.user[name] = tmp
            else:
                print "WARNING: unknown user element: %s" % name
        elif self.elementstack[-1] == "person":
            if name in ("contact", "name", "extid"):
                self.person[name] = self.person.get(name, []) + [tmp]
            elif name in ("uio",):
                self.person[name] = tmp
            elif name == "user":
                self.user = {}
                for k in tmp.keys():
                    self.user[k] = tmp[k]
            else:
                print "WARNING: unknown person element: %s" % name
        else:
            print "WARNING: unknown element: %s" % name
        self.elementstack.append(name)

    def endElement(self, name):
        if name == "person":
            self.call_back_function(self.person)
        elif name == "user":
            self.person['user'] = self.person.get('user', []) + [self.user]
        self.elementstack.pop()


class GroupData(object):
    """This class is used to iterate over all groups from ureg."""

    def __init__(self, filename):
        # Ugly memory-wasting, inflexible way:
        self.tp = GroupParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next group in ureg."""
        try:
            return self.tp.groups.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class GroupParser(xml.sax.ContentHandler):
    """Parser for the groups.xml file.  Stores recognized data in an
    internal datastructure"""

    def __init__(self):
        self.groups = []
        self.elementstack = []

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
        if name == "groups":
            pass
        elif name == "group":
            self.group = {}
            for k in attrs.keys():
                self.group[k] = tmp[k]
        elif self.elementstack[-1] == "group":
            if name == "member":
                self.group[name] = self.group.get(name, []) + [tmp]
            else:
                print "WARNING: unknown group element: %s" % name
        else:
            print "WARNING: unknown element: %s" % name
        self.elementstack.append(name)

    def endElement(self, name):
        if name == "group":
            self.groups.append(self.group)
        self.elementstack.pop()

def import_groups(groupfile, fill=0):
    account = Account.Account(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)

    print """Processing groups.  Progress indicators means:
    . : a group with members has been read from XML file
    G : a group in the file did not exist (when -M is used)
    A : an account was added as member to a group
    n : the member being populated was missing"""
    group_group = {}
    group_exists = {}
    group_has_member = {}
    tmpg = Group.Group(db)
    tmpg2 = Group.Group(db)
    for g in tmpg.list_all():
        tmpg2.clear()
        tmpg2.find(g['group_id'])
        u, i, d = tmpg2.list_members()
        group_has_member[g['group_id']] = {}
        for t, rows in ('union', u), ('inters.', i), ('diff', d):
            for r in rows:
                group_has_member[g['group_id']][r[1]] = 1

    # Note: File and netgroups are merged
    for group in GroupData(groupfile):
        # pp.pprint(group)
        print ".",
        sys.stdout.flush()
        if group['type'] == 'fg' and int(group['gid']) < 1:
            continue   # TODO: failes database constraint
        groupObj = Group.Group(db)
        pg = PosixGroup.PosixGroup(db)
        if not fill:
            if group['type'] == 'ng':
                group['comment'] = group['description']
            if not group_exists.has_key(group['name']):
                groupObj.populate(account.entity_id, co.group_visibility_all,
                                  group['name'], group['comment'])
                groupObj.write_db()
                group_exists[group['name']] = groupObj.entity_id
            else:
                groupObj.find(group_exists[group['name']])

            if group['type'] == 'fg':
                pg.populate(parent=groupObj, gid=group['gid'])
                pg.write_db()
                if group['uiospread'] in ('u', 'b'):
                    groupObj.add_spread(co.spread_uio_nis_fg)
                if group['uiospread'] in ('i', 'b'):
                    groupObj.add_spread(co.spread_ifi_nis_fg)
            elif group['type'] == 'ng':
                if group['uiospread'] in ('u', 'b'):
                    groupObj.add_spread(co.spread_uio_nis_ng)
                if group['uiospread'] in ('i', 'b'):
                    groupObj.add_spread(co.spread_ifi_nis_ng)
            elif group['type'] == 'ig':
                pass     # Nothing needs to be done for itgroups
        else:
            try:
                if group['type'] == 'fg':
                    pg.find_by_gid(group['gid'])
                    destination = pg
                else:
                    groupObj.find_by_name(group['name'])
                    destination = groupObj
            except Errors.NotFoundError:
                print "G",
                continue
            for m in group.get('member', []):
                try:
                    if m['type'] == 'user':
                        account.clear()
                        account.find_by_name(m['name'])
                    else:  # Delay insertion as group may not exist yet
                        group_group.setdefault(groupObj.entity_id, []).append(m['name'])
                        continue

                    if not group_has_member.get(destination.entity_id, {}
                                                ).has_key(account.entity_id):
                        destination.add_member(account.entity_id, account.entity_type,
                                               co.group_memberop_union);
                        group_has_member.setdefault(destination.entity_id, {}
                                                    )[account.entity_id] = 1
                    print "A",
                except Errors.NotFoundError:
                    print "n",
                    continue

    groupObj = Group.Group(db)
    tmp = Group.Group(db)
    for group in group_group.keys():
        groupObj.clear()
        groupObj.find(group)
        for m in group_group[group]:
            tmp.clear()
            try:
                tmp.find_by_name(m)
            except Errors.NotFoundError:
                print "E:%i/%s" % (group, m),
            groupObj.add_member(tmp.entity_id, tmp.entity_type, co.group_memberop_union)
    db.commit()

def import_person_users(personfile):
    global gid2entity_id, stedkode2ou_id

    showtime("Preparing")
    group=PosixGroup.PosixGroup(db)
    gid2entity_id = {}
    if 0:
        for row in group.list_all():
            group.clear()
            try:
                group.find(row['group_id'])
                gid2entity_id[int(group.posix_gid)] = group.entity_id
            except Errors.NotFoundError:
                pass  # Not a PosixGroup: OK
    else:
        for row in group.list_all_ext():
            gid2entity_id[int(row['posix_gid'])] = row['group_id']

    ou = Stedkode.Stedkode(db)
    stedkode2ou_id = {}
    if 0:  # TODO: set to 1 when debugging is reasonably complete
        for row in ou.list_all():
            ou.clear()
            ou.find(row['ou_id'])
            stedkode2ou_id["%02i%02i%02i" % (
                ou.fakultet, ou.institutt, ou.avdeling)] = ou.entity_id

    showtime("Parsing")
    try:
        xml.sax.parse(personfile, PersonUserParser(person_callback))
    except StopIteration:
        pass
    showtime("Post-processing")
    warned_uc = {}
    for uc in user_creators.keys():
        creator_id = uname2entity_id.get(user_creators[uc], None)
        if creator_id is None:
            if not warned_uc.has_key(user_creators[uc]):
                print "Warning: Unknown creator: %s" % user_creators[uc]
                warned_uc[user_creators[uc]] = 1
        else:
            account.clear()
            account.find(uc)
            account.creator_id = creator_id
            account.write_db()
    # Since the deleted users are sorted by deleted_date DESC and
    # grouped by person, we may end up building the wrong user.  This
    # is not critical.
    # If we move this code above the code that sets creator, we risk
    # setting the wrong creator
    for person_id in deleted_users.keys():
        for du in deleted_users[person_id]:
            if not uname2entity_id.has_key(du['uname']):
                account_id = create_account(du, person_id)
                uname2entity_id[du['uname']] = account_id
    db.commit()

def person_callback(person):
    # - Hvis personen har spread=u/i, bygg PosixUser.
    # - Hvis deleted_date ikke er satt, bygg Account.
    # - Hvis reserved="1", skal brukeren ikke ha spread.
    # Etter at hele filen er prosessert, gå gjennom alle som har
    # deleted_date, og bygg PosixUser til de, men sett
    # expire_date=deleted_date
    global max_cb
    if max_cb is not None:
        max_cb -= 1
        if max_cb < 0:
            raise StopIteration()
    personObj.clear()
    fnr = None
    for e in person['extid']:
        if e['type'] == 'fnr':
            if e['val'] <> '00000000000':
                fnr = e['val']
    person_id = None
    if fnr is not None:
        try:
            print "Fnr: %s" % fnr,
            personObj.find_by_external_id(co.externalid_fodselsnr, fnr)
            person_id = personObj.entity_id
            print " ********* OLD *************"
        except Errors.NotFoundError:
            print " ********* NEW *************"
            pass
    else:
        print "No fnr",
    if person_id is None:
        # Personen fantes ikke, lag den
        if person['bdate'] == '999999':
            bdate = None
        else:
            try:
                bdate = [int(x) for x in person['bdate'].split('-')]
                bdate = db.Date(*bdate)
            except:
                print "Warning, %s is an illegal date" % person['bdate']
                bdate = None
        personObj.populate(bdate,
                            co.gender_unknown)
        personObj.affect_names(co.system_ureg, *(namestr2const.values()))

        for k in person['name']:
            if namestr2const.has_key(k['type']):
                personObj.populate_name(namestr2const[k['type']], k['val'])
        if fnr is not None:
            personObj.populate_external_id(co.system_ureg,
                                           co.externalid_fodselsnr, fnr)
        for c in person['contact']:
            if c['type'] == 'workphone':
                personObj.populate_contact_info(co.system_ureg,
                                                co.contact_phone, c['val'],
                                                contact_pref=1)
            elif c['type'] == 'privphone':
                personObj.populate_contact_info(co.system_ureg,
                                                co.contact_phone, c['val'],
                                                contact_pref=2)
            elif c['type'] == 'workfax':
                personObj.populate_contact_info(co.system_ureg,
                                                co.contact_phone, c['val'])
            elif c['type'] == 'privaddress':
                a = c['val'].split('$', 2)
                personObj.populate_address(co.system_ureg, co.address_post,
                                           address_text="\n".join(a))
        if person.has_key('uio'):
            if person['uio'].has_key('psko'):
                # Typer v/uio: A B M S X a b s
                aff = co.affiliation_student   # TODO: define all const
                affstat = co.affiliation_status_student_valid
                if person['uio']['ptype'] in ('A', 'a'):
                    aff = co.affiliation_employee
                    affstat = co.affiliation_status_employee_valid

                try:
                    ou_id = stedkode2ou_id[ person['uio']['psko'] ]
                    personObj.populate_affiliation(co.system_ureg, ou_id,
                                                   aff, affstat)
                except KeyError:
                    print "Unknown stedkode: %s" % person['uio']['psko']

        personObj.write_db()
        person_id = personObj.entity_id

    # Build the persons users.  Delay building deleted users to avoid
    # username conflicts, and store creators uname as its entity_id is
    # not available yet.
    for u in person['user']:
        if u.has_key('deleted_date'):
            deleted_users.setdefault(person_id, []).append(u)
        else:
            account_id = create_account(u, person_id)
            if not u.has_key('reserved'):
                user_creators[account_id] = u['created_by']
            uname2entity_id[u['uname']] = account_id

def create_account(u, owner_id):
    is_posix = 0
    if u.has_key('deleted_date'):
        expire_date = [int(x) for x in u['deleted_date'].split('-')]
        expire_date = db.Date(*expire_date)
        if int(u['dfg']) > 0 and not uid_taken.has_key(int(u['uid'])):
            is_posix = 1
    else:
        expire_date = None  # TBD: what is the correct value for existing users?

        for tmp in u.get('spread', []):
            if tmp['domain'] in ('u', 'i'):
                is_posix = 1

    home = disk_id = None
    if is_posix:
        if not gid2entity_id.has_key(int(u['dfg'])):
            is_posix = 0
        else:
            gecos = None        # TODO
            shell = shell2shellconst[u['shell']]
            posix_user.clear()
            accountObj = posix_user
    if not is_posix:
        account.clear()
        accountObj = account

    if not u.has_key('reserved'):
        tmp = u['home'].split("/")
        if len(tmp) == 5:
            disk_id = disk2id.get("/".join(tmp[:4]), None)
            if disk_id is None:
                disk = tmp[3]
                host = tmp[2]
                disk_id = make_disk(host, disk, "/".join(tmp[:4]))
                disk2id["/".join(tmp[:4])] = disk_id
        if disk_id is not None:  # Only set home if not on a normal disk
            home = None

    accountObj.affect_auth_types(co.auth_type_md5_crypt,
                                 co.auth_type_crypt3_des)
    had_splat = 0
    for au in u.get('auth', []):
        if len(au['val']) == 0:
            continue
        if au['type'] in ('md5', 'crypt') and au['val'][0] == '*':
            had_splat = 1
            if au['val'] == '*invalid':
                continue
            au['val'] = au['val'][1:]
        if au['type'] == 'plaintext':   # TODO: Should be called last?
            accountObj.set_password(au['val'])
        elif au['type'] == 'md5':
            accountObj.populate_authentication_type(
                co.auth_type_md5_crypt, au['val'])
        elif au['type'] == 'crypt':
            accountObj.populate_authentication_type(
                co.auth_type_crypt3_des, au['val'])
    if is_posix:
        uid_taken[int(u['uid'])] = 1
        accountObj.populate(u['uid'],
                            gid2entity_id[int(u['dfg'])],
                            gecos,
                            shell,
                            home=home, # TODO: disk_id
                            name=u['uname'],
                            disk_id=disk_id,
                            owner_type=co.entity_person,
                            owner_id=owner_id,
                            creator_id=acc_creator_id,
                            expire_date=expire_date)
    else:
        accountObj.populate(u['uname'],
                            co.entity_person,
                            owner_id,
                            None,
                            acc_creator_id,
                            expire_date,
                            home,
                            disk_id)
    accountObj.write_db()
    if u.has_key('quarantine') or had_splat:
        if not u.has_key('quarantine'):
            if not u.has_key('deleted_date'):
                print "Warning, user %s had splat, but no quatantine" % u['uname']
            when = db.TimestampFromTicks(time())
            why = "Had splat on import from ureg2000"
        else:
            when = [int(x) for x in u['quarantine']['when'].split('-')]
            when = db.Date(*when)
            why = u['quarantine']['why']
        accountObj.add_entity_quarantine(int(co.quarantine_generell),
                                         acc_creator_id, # TODO: Set this
                                         description=why,
                                         start=when)

    for tmp in u.get('spread', []):
        if tmp['domain'] == 'u':
            accountObj.add_spread(co.spread_uio_nis_user)
        elif tmp['domain'] == 'i':
            accountObj.add_spread(co.spread_ifi_nis_user)
    for tmp in u.get('pwdhist', []):
        pwdhist.add_history(accountObj.entity_id, '', _csum=tmp['value'])
    return accountObj.entity_id

def make_disk(hostname, disk, diskname):
    host = Disk.Host(db)
    disk = Disk.Disk(db)
    try:
        host.clear()
        host.find_by_name(hostname)
    except Errors.NotFoundError:
        host.populate(hostname, 'uio host')
        host.write_db()
    try:
        disk.clear()
        disk.find_by_path(diskname, host_id=host.entity_id)
    except Errors.NotFoundError:
        disk.populate(host.entity_id, diskname, 'uio disk')
        disk.write_db()
    return disk.entity_id

def showtime(msg):
    global prev_msgtime
    print "[%s] %s (delta: %i)" % (strftime("%H:%M:%S", gmtime()), msg, (time()-prev_msgtime))
    prev_msgtime = time()

def usage():
    print """import_userdb_XML.py [-p file | -g file | -m num] {-P | -G | -M}

-G : generate the groups
-P : generate persons and accounts
-M : populate the groups with members

Normaly first run with -G, then -P and finally with -M.  The program
is not designed to be ran multiple times.

This script is designed to be ran on a database that contains no users
or groups.  ou and person tables should preferable be populated.  When
importing accounts, the persons will be created iff they cannot be
located by their extid (currently only fnr is supported).
    """

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:g:m:PGM",
                                   ["pfile=", "gfile=", "persons", "groups",
                                    "groupmembers", "max_cb="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    global max_cb
    max_cb = None
    pfile = default_personfile
    gfile = default_groupfile
    for o, a in opts:
        if o in ('-p', '--pfile'):
            pfile = a
        elif o in ('-g', '--gfile'):
            gfile = a
        elif o in ('-P', '--persons'):
            import_person_users(pfile)
        elif o in ('-G', '--groups'):
            import_groups(gfile, 0)
        elif o in ('-m', '--max_cb'):
            max_cb = int(a)
        elif o in ('-M', '--groupmembers'):
            import_groups(gfile, 1)
    if(len(opts) == 0):
        usage()
    else:
        showtime("all done")
