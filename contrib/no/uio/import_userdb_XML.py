#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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
from time import gmtime, strftime, time, localtime

from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PasswordHistory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.bofhd.auth \
     import BofhdAuthOpSet, BofhdAuthRole, BofhdAuthOpTarget
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email


default_personfile = ''
default_groupfile = ''
default_itpermfile = ''
default_emailfile = ''
db = Factory.get('Database')()
db.cl_init(change_program='migrate_iux')
co = Factory.get('Constants')(db)
pp = pprint.PrettyPrinter(indent=4)
prev_msgtime = time()
debug = 0

user_creators = {}     # Store post-processing info for users
uname2entity_id = {}
deleted_users = {}
uid_taken = {}
person_id2affs = {}
account_id2aff = {}
primary_users = {}

# Some caches for speedup
group2entity_id = {}
account2entity_id = {}

namestr2const = {'lname': co.name_last, 'fname': co.name_first}
personObj = Factory.get('Person')(db)
posix_user = PosixUser.PosixUser(db)
disk2id = {}
account = Account.Account(db)
account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
acc_creator_id = account.entity_id
pwdhist = PasswordHistory.PasswordHistory(db)
pquotas = PrinterQuotas.PrinterQuotas(db)

maildom = Email.EmailDomain(db)
mailtarg = Email.EmailTarget(db)
mailaddr = Email.EmailAddress(db)
mailprimaddr = Email.EmailPrimaryAddressTarget(db)

class AutoFlushStream(object):
    __slots__ = ('_stream',)
    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        ret = self._stream.write(data)
        self._stream.flush()
        return ret

progress = AutoFlushStream(sys.stdout)


shell2shellconst = {
    'bash': co.posix_shell_bash,
    'csh': co.posix_shell_csh,
    'false': co.posix_shell_false,
    'nologin': co.posix_shell_nologin,
    'nologin.autostud': co.posix_shell_nologin_autostud,  # TODO: more shells, (and their path)
    'nologin.brk': co.posix_shell_nologin_brk,
    'nologin.chpwd': co.posix_shell_nologin_chpwd,
    'nologin.ftpuser': co.posix_shell_nologin_ftpuser,
    'nologin.nystudent': co.posix_shell_nologin_nystudent,
    'nologin.pwd': co.posix_shell_nologin_pwd,
    'nologin.sh': co.posix_shell_nologin_sh,
    'nologin.sluttet': co.posix_shell_nologin_sluttet,
    'nologin.stengt': co.posix_shell_nologin_stengt,
    'nologin.teppe': co.posix_shell_nologin_teppe,
    'puberos': co.posix_shell_puberos,
    'sftp-server': co.posix_shell_sftp_server,
    'sh': co.posix_shell_sh,
    'tcsh': co.posix_shell_tcsh,
    'zsh': co.posix_shell_zsh,
    }

class PersonUserParser(xml.sax.ContentHandler):
    """Parser for the users.xml file.  Stores recognized data in an
    internal datastructure"""

    def __init__(self, person_call_back_function, group_call_back_function):
        self.personer = []
        self.elementstack = []
        self.person_call_back_function = person_call_back_function
        self.group_call_back_function = group_call_back_function
        self.group_owner = None
        # self.person = {
        #  'bdate': <person bdate="VALUE">,
        #  'ptype': [ <person><uio><ptype val="X1"/>, ...],
        #  'contact': [ {attr-dict from <person><contact>}, ...],
        #  'name': [ {attr-dict from <person><name>}, ...],
        #  'extid': [ {attr-dict from <person><extid>}, ...],
        #  'uio': {attr-dict from <person><uio>},
        #  'user': [self.user, ...]
        # }
        # self.user = {attr-dict from <person><user>}.update({
        #  'auth': [ {attr-dict from <person><user><auth>}, ...],
        #  'spread': [ {attr-dict from <spread>}, ...],
        #  'name': [ {attr-dict from <name>}, ...],
        #  'pwdhist': [ {attr-dict from <pwdhist>}, ...],
        #  'emailaddress': [ {attr-dict from <emailaddress>}, ...],
        #  'forwardaddress': [ {attr-dict from <forwardaddress>}, ...],
        #  'tripnote': [ {attr-dict from <tripnote>}, ...],
        #
        #  'uio': {attr-dict from <uio>},
        #  'printerquota': {attr-dict from <printerquota>},
        #  'quarantine': {attr-dict from <quarantine>},
        #  'useremail': {attr-dict from <useremail>},
        #  'emailfilter': {attr-dict from <emailfilter>},
        # })

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
        if name == "data":
            pass
        elif name == "persons":
            pass
        elif name == "nonpersons":
            pass
        elif name == "person":
            self.person = {'bdate': tmp.get('bdate', None), 'ptype': []}
        elif self.elementstack[-1] == "user":
            if name in ("auth", "spread", "name", "pwdhist",
                        "emailaddress", "forwardaddress", "tripnote"):
                self.user.setdefault(name, []).append(tmp)
            elif name in ("uio", "printerquota", "quarantine", "useremail",
                          "emailfilter"):
                self.user[name] = tmp
            else:
                print "WARNING: unknown user element: %s" % name
        elif name == "group_owned":
            self.group_owner = tmp['name']
        elif self.elementstack[-1] in ("person", "group_owned"):
            if name in ("contact", "name", "extid"):
                self.person.setdefault(name, []).append(tmp)
            elif name in ("uio",):
                self.person[name] = tmp
            elif name == "user":
                self.user = {}
                for k in tmp.keys():
                    self.user[k] = tmp[k]
            else:
                print "WARNING: unknown person element: %s" % name
        elif self.elementstack[-1] == "uio":
            if name in ("ptype", ):
                self.person[name].append(tmp['val'])
        else:
            print "WARNING: unknown element: %s" % name
        self.elementstack.append(name)

    def endElement(self, name):
        if name == "person":
            self.person_call_back_function(self.person)
        elif name == "user":
            if self.group_owner:
                self.group_call_back_function(self.group_owner, self.user)
            else:
                self.person.setdefault(name, []).append(self.user)
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

class MailDataParser(xml.sax.ContentHandler):

    def __init__(self, callback):
        self.callback = callback
        self.elementstack = []

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        if name == 'email':
            pass
        elif name in ('emaildomain', 'emailhost', 'emailaddresstype',
                      'emailalias'):
            self.callback(name, tmp)
        else:
            print "WARNING: Unknown email element: %s" % name
        self.elementstack.append(name)

    def endElement(self, name):
        self.elementstack.pop()


def import_email(filename):
    try:
        xml.sax.parse(filename, MailDataParser(create_email))
    except StopIteration:
        pass


ureg_domtyp2catgs = {
    'u': (co.email_domain_category_uidaddr,),
    'U': (co.email_domain_category_uidaddr,
          co.email_domain_category_include_all_uids),
    'p': (co.email_domain_category_cnaddr,),
    'P': (co.email_domain_category_cnaddr,
          co.email_domain_category_include_all_uids),
    'N': ()
    }
maildomain2eid = {}

def create_email(otype, data):
    if otype == 'emaildomain':
        maildom.clear()
        maildom.populate(data['domain'], data['description'])
        maildom.write_db()
        maildomain2eid[data['domain']] = maildom.email_domain_id
        progress.write('E')
        domtyp = data.get('addr_format', None)
        if ureg_domtyp2catgs.has_key(domtyp):
            for cat in ureg_domtyp2catgs[domtyp]:
                maildom.add_category(int(cat))
                progress.write('c')
        else:
            raise ValueError, "Unknown mail domain type: <%s>" % domtyp
    elif otype == 'emailhost':
        servername = data['host']
        servertype = {'spool': co.email_server_type_nfsmbox,
                      'imap': co.email_server_type_cyrus}[data['type']]
        serverdescr = 'Email server (%s)' % str(servertype)
        server = Email.EmailServer(db)
        try:
            server.find_by_name(servername)
        except Errors.NotFoundError:
            host = Disk.Host(db)
            try:
                host.find_by_name(servername)
            except Errors.NotFoundError:
                server.populate(servertype, servername, serverdescr)
            else:
                server.populate(servertype, parent=host)
        else:
            progress.write('=')
            return
        server.write_db()
        progress.write('S')
    elif otype == 'emailaddresstype':
        # TODO: How should we process these?
        pass
    elif otype == 'emailalias':
        # Find or create target of correct type
        mailtarg.clear()
        dt = data['desttype']
        dest = data['dest']
        typ = None
        e_id = None
        e_typ = None
        alias = None
        if dt == 'u':
            raise ValueError, \
                  "Destination of type 'u' found in non-personal email dump."
        elif dt == 'a':
            if dest.startswith('/') or dest.startswith('|'):
                if data.has_key('run_as'):
                    account.clear()
                    try:
                        account.find_by_name(data['run_as'])
                        e_id, e_typ = account.entity_id, account.entity_type
                    except Errors.NotFoundError:
                        # TODO: Rekkefølge-problem, run_as virker ikke
                        # med mindre man har importert brukere, mens
                        # bruker-import ikke virker med mindre
                        # maildomener etc. er ferdig opprettet.
                        pass
                typ = {'/': co.email_target_file,
                       '|': co.email_target_pipe}[dest[0]]
                alias = dest
            elif dest.startswith(":fail:"):
                typ = co.email_target_deleted
                alias = dest[6:].strip() or None
            elif dest.startswith(':include:'):
                # TODO: Usikker på hvordan dette bør gjøres; kanskje
                # med et 'multi' target.  Er også usikker på om
                # 'multi'-targets implementeres som grupper eller som
                # forward-adresser.
                print "WARNING: Not implemented: import of :include: targets"
                return
            elif '@' in dest and " " not in dest:
                typ = co.email_target_forward
                # TBD: Skal forward lagres i alias_value, eller skal
                # EmailTarget utvides til å også være EmailForward?
                alias = dest
            else:
                raise ValueError, \
                      "Don't know how to convert emailalias:" + repr(data)
            try:
                mailtarg.find_by_entity_and_alias(e_id, alias)
            except Errors.NotFoundError:
                mailtarg.populate(typ, e_id, e_typ, alias)
                mailtarg.write_db()
            progress.write('T')
        elif dt == 'l':
            return
        else:
            raise ValueError, "Unknown desttype: " + dt
        # Create address connected to target
        mailaddr.clear()
        lp, dom = data['addr'].split('@', 1)
        expire = None
        if data.has_key('exp_date'):
            expire = db.Date(*([int(x) for x in data['exp_date'].split('-')]))
        if not hasattr(mailtarg, 'email_target_id'):
            print repr(data)
        mailaddr.populate(lp, maildomain2eid[dom], mailtarg.email_target_id,
                          expire)
        mailaddr.write_db()
        progress.write('A')
                                  
        # Possibly state that address is primary for this target
        
    else:
        print "Warning: Unimplemented tag <%s> found." % otype

class ITPermData(xml.sax.ContentHandler):
    def __init__(self, filename):
        self.perms = []
        xml.sax.parse(filename, self)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next group in ureg."""
        try:
            return self.perms.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
        if name in ('group', 'disk'):
            tmp['type'] = name
            self.perms.append(tmp)

    def endElement(self, name):
        pass

def import_itperms(filename):
    # Create wanted BofhdAuthOpSet(s)
    baos = BofhdAuthOpSet(db)
    # - ureg_O
    baos.clear()
    baos.populate('ureg_O')
    baos.write_db()
    baos.add_operation(co.auth_set_password)
    baos.add_operation(co.auth_move_from_disk)
    ureg_O = baos.op_set_id
    # - ureg_P
    baos.clear()
    baos.populate('ureg_P')
    baos.write_db()
    baos.add_operation(co.auth_set_password)
    ureg_P = baos.op_set_id
    # - ureg_Y
    baos.clear()
    baos.populate('ureg_Y')
    baos.write_db()
    baos.add_operation(co.auth_set_password)
    baos.add_operation(co.auth_move_from_disk)
    baos.add_operation(co.auth_move_to_disk)
    ureg_Y = baos.op_set_id
    # - ureg_group
    baos.clear()
    baos.populate('ureg_group')
    baos.write_db()
    baos.add_operation(co.auth_alter_group_membership)
    ureg_group = baos.op_set_id

    role = BofhdAuthRole(db)
    ao_target = BofhdAuthOpTarget(db)
    # Cache some lookup data
    disk = Disk.Disk(db)
    hostname2id = {}
    diskname2diskid = {}
    for row in disk.list():
        parts = row['path'].split("/")
        hostname2id[parts[2]] = row['host_id']
        diskname2diskid[parts[2]+":"+parts[3]] = row['disk_id']

    # Process XML file
    for perm in ITPermData(filename):
        itg = None
        try:
            itg = _get_group(perm['itgroupname'])
        except Errors.NotFoundError:
            print "WARNING: missing itgroup: %s" % perm['itgroupname']
            continue
        if perm['type'] == 'group':
            dest_group = None
            try:
                dest_group = _get_group(perm['group'])
            except Errors.NotFoundError:
                print "WARNING: missing group: %s" % perm['group']
                continue

            # Even though target is a single entity, we have to create
            # a target for it.  One may argue that one should allow
            # auth_role.op_target_id to point to an entity_id
            owner = None
            if perm['personlig'] == '1':
                try:
                    owner = _get_account(perm['group'])
                except Errors.NotFoundError:
                    print "WARNING: missing user: %s" % perm['group']
                    continue
            else:
                owner = itg
            ao_target.clear()
            ao_target.populate(dest_group, 'group')
            ao_target.write_db()
            role.grant_auth(owner, ureg_group, ao_target.op_target_id)
        elif perm['type'] == 'disk':
            host = None
            try:
                host = hostname2id[perm['machine']]
            except KeyError:
                print "WARNING: unknown host: %s" % perm['machine'] 
                continue
            if perm['reg_ok'] == 'O':
                set = ureg_O
            elif  perm['reg_ok'] == 'Y':
                set = ureg_Y
            elif  perm['reg_ok'] == 'P':
                set = ureg_P
            try:
                idx = perm['disk'].index('*')
                ao_target.clear()
                ao_target.populate(host, 'host')
                ao_target.write_db()
                if perm['disk'] != '*':
                    perm['disk'] = perm['disk'].replace('*', '.*')
                    ao_target.add_op_target_attr(perm['disk'])
                    ao_target.write_db()
            except ValueError:
                disk = perm['machine']+":"+perm['disk']
                try:
                    disk = diskname2diskid[disk]
                except KeyError:
                    print "WARNING: unknown disk: %s" % disk
                    continue
                ao_target.clear()
                ao_target.populate(disk, 'disk')
                ao_target.write_db()                
            role.grant_auth(itg, set, ao_target.op_target_id)
    db.commit()

def _get_group(name):
    if not group2entity_id.has_key(name):
        tmpg = Group.Group(db)
        tmpg.find_by_name(name)
        group2entity_id[name] = int(tmpg.entity_id)
    return group2entity_id[name]

def _get_account(name):
    if not account2entity_id.has_key(name):
        tmpa = Account.Account(db)
        tmpa.find_by_name(name)
        account2entity_id[name] = int(tmpa.entity_id)
    return account2entity_id[name]

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
        group_has_member[int(g['group_id'])] = {}
        for t, rows in ('union', u), ('inters.', i), ('diff', d):
            for r in rows:
                group_has_member[int(g['group_id'])][int(r[1])] = 1

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
                        account_id = _get_account(m['name'])
                    else:  # Delay insertion as group may not exist yet
                        group_group.setdefault(int(groupObj.entity_id), []).append(m['name'])
                        continue

                    if not group_has_member.get(int(destination.entity_id), {}
                                                ).has_key(account_id):
                        destination.add_member(account_id, co.entity_account,
                                               co.group_memberop_union);
                        group_has_member.setdefault(int(destination.entity_id), {}
                                                    )[account_id] = 1
                    print "A",
                except Errors.NotFoundError:
                    print "n",
                    continue

    groupObj = Group.Group(db)
    for group in group_group.keys():
        groupObj.clear()
        groupObj.find(group)
        for m in group_group[group]:
            try:
                tmp = _get_group(m)
            except Errors.NotFoundError:
                print "E:%i/%s" % (group, m)
                continue
            if int(group) == tmp:
                print "Warning group memember of itself, skipping %s" % m
                continue
            groupObj.add_member(tmp, co.entity_group, co.group_memberop_union)
    db.commit()

def import_person_users(personfile):
    global gid2entity_id, stedkode2ou_id, default_ou, uname_exists

    group=PosixGroup.PosixGroup(db)
    gid2entity_id = {}
    # if False and not quick_test:
    if not quick_test:
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

    uname_exists = {}

    en = Entity.EntityName(db)
    for r in en.list_names(int(co.account_namespace)):
        uname_exists[r['entity_name']] = r['entity_id']

    ou = Stedkode.Stedkode(db)
    stedkode2ou_id = {}
    if not quick_test:
        for row in ou.list_all():
            ou.clear()
            ou.find(row['ou_id'])
            stedkode2ou_id["%02i%02i%02i" % (
                ou.fakultet, ou.institutt, ou.avdeling)] = ou.entity_id
    else:
        ou.clear()
        ou.find_stedkode(90, 1, 99)
        stedkode2ou_id["900199"] = ou.entity_id

    default_ou = stedkode2ou_id[default_ou]

    showtime("Parsing")
    try:
        xml.sax.parse(personfile, PersonUserParser(person_callback,
                                                   group_owned_callback))
    except StopIteration:
        pass
    showtime("Post-processing")
    warned_uc = {}
    
    # Populate person affiliations
    showtime("Populate person affiliations")
    for p_id in person_id2affs.keys():
        print "a",
        personObj.clear()
        personObj.find(p_id)
        for ou_id, aff, affstat in person_id2affs[p_id]:
            if verbose:
                print "  person.pop_aff (%s): %s, %s, %s" % (
                    p_id, ou_id, aff, affstat)
            personObj.__updated = True
            personObj.populate_affiliation(source_system, ou_id, aff, affstat)
        tmp = personObj.write_db()
        if verbose:
            print "  person.write_db (%s)-> %s" % (p_id, tmp)
    # Set user_creator and account affiliations.
    # user_creators and account_id2aff have atleast all keys in account_id2aff
    showtime("Setting user_creators")
    for uc in user_creators.keys():
        print "c",
        creator_id = uname2entity_id.get(user_creators[uc], None)
        account.clear()
        account.find(uc)
        if creator_id is not None:
            account.creator_id = creator_id
            account.write_db()
        else:
            if not warned_uc.has_key(user_creators[uc]):
                print "Warning: Unknown creator: %s" % user_creators[uc]
                warned_uc[user_creators[uc]] = 1
        if account_id2aff.has_key(uc):
            ou_id, aff, affstat = account_id2aff[uc]
            priority = primary_users.get(int(account.entity_id), None)
            if verbose:
                print "  add_acc_type: (%s / %s) -> %s, %s, %s, %s" % (
                    account.account_name, account.owner_id, ou_id, aff, affstat, priority)
            account.set_account_type(ou_id, aff, priority)

    # Since the deleted users are sorted by deleted_date DESC and
    # grouped by person, we may end up building the wrong user.  This
    # is not critical.
    # If we move this code above the code that sets creator, we risk
    # setting the wrong creator
    showtime("Creating deleted users")
    for person_id in deleted_users.keys():
        for du in deleted_users[person_id]:
            if not uname2entity_id.has_key(du['uname']):
                account_id = create_account(du, person_id, co.entity_person)
                if account_id is not None:
                    uname2entity_id[du['uname']] = account_id
    db.commit()

def group_owned_callback(owner_gname, user):
    create_account(user, _get_group(owner_gname), co.entity_group, int(co.account_program))

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
    for e in person.get('extid', []):
        if e['type'] == 'fnr':
            if e['val'] <> '00000000000':
                fnr = e['val']
    person_id = None
    if 1:    # This script is only intended to be ran on an empty database
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
    else:
        print "Fnr: %s" % fnr
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
        try:
            fodselsnr.personnr_ok(fnr)
            if fodselsnr.er_mann(fnr):
                gender = co.gender_male
            else:
                gender = co.gender_female                
        except fodselsnr.InvalidFnrError:
            gender = co.gender_unknown

        personObj.populate(bdate, gender)
        personObj.affect_names(source_system, *(namestr2const.values()))

        for k in person['name']:
            if namestr2const.has_key(k['type']):
                personObj.populate_name(namestr2const[k['type']], k['val'])
        if fnr is not None:
            personObj.affect_external_id(source_system, co.externalid_fodselsnr)
            personObj.populate_external_id(source_system,
                                           co.externalid_fodselsnr, fnr)
        for c in person.get('contact', []):
            if(len(c['val']) == 0):
                continue
            if c['type'] == 'workphone':
                personObj.populate_contact_info(source_system,
                                                co.contact_phone, c['val'],
                                                contact_pref=1)
            elif c['type'] == 'privphone':
                personObj.populate_contact_info(source_system,
                                                co.contact_phone, c['val'],
                                                contact_pref=2)
            elif c['type'] == 'workfax':
                personObj.populate_contact_info(source_system,
                                                co.contact_phone, c['val'])
            elif c['type'] == 'privaddress':
                a = c['val'].split('$', 2)
                personObj.populate_address(source_system, co.address_post,
                                           address_text="\n".join(a))
        new_affs = []
        if person.has_key('uio'):
            for ptype in person['ptype']:
                aff, affstat = person_aff_mapping[ptype]
                ou_id = stedkode2ou_id.get(person['uio']['psko'], default_ou)
                new_affs.append((ou_id, aff, affstat))
        personObj.write_db()
        person_id = personObj.entity_id
        person_id2affs[person_id] = new_affs
    else:
        for a in personObj.get_affiliations():
            person_id2affs.setdefault(person_id, []).append(
                (int(a['ou_id']), int(a['affiliation']), int(a['status'])))

    # Build the persons users.  Delay building deleted users to avoid
    # username conflicts, and store creators uname as its entity_id is
    # not available yet.
    for u in person['user']:
        if u.has_key('deleted_date'):
            deleted_users.setdefault(person_id, []).append(u)
        else:
            account_id = create_account(u, person_id, co.entity_person)
            if account_id is not None:
                if not u.has_key('reserved'):
                    user_creators[account_id] = u.get('created_by', 'bootstrap_account')
                uname2entity_id[u['uname']] = account_id
            
def create_account(u, owner_id, owner_type, np_type=None):
    if uname_exists.has_key(u['uname']):
        print "User %s already exists, skipping" % u['uname']
        return None
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

    if u.has_key('home'):
        home = u['home']
        tmp = home.split("/")
        if len(tmp) == 5:
            disk_id = disk2id.get("/".join(tmp[:4]), None)
            if disk_id is None:
                disk = tmp[3]
                host = tmp[2]
                disk_id = make_disk(host, disk, "/".join(tmp[:4]))
                disk2id["/".join(tmp[:4])] = disk_id
        if disk_id is not None:  # Only set home if not on a normal disk
            home = None
    if debug:
        print "%s: home=%s, disk_id=%s" % (u['uname'], home, disk_id)
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
                            owner_type=owner_type,
                            owner_id=owner_id,
                            creator_id=acc_creator_id,
                            expire_date=expire_date,
                            np_type=np_type)
    else:
        accountObj.populate(u['uname'],
                            owner_type,
                            owner_id,
                            np_type,
                            acc_creator_id,
                            expire_date,
                            home,
                            disk_id)
    accountObj.write_db()

    if u.has_key("useremail"):
        # Create EmailTarget
        mailtarg.clear()
        mailtarg.populate(co.email_target_account, accountObj.entity_id,
                          alias=u['useremail'].get('alias', None))
        mt_id = mailtarg.write_db()

        for tmp in u.get("emailaddress", []):
            lp, dom = tmp['addr'].split("@")
            dom_id = maildomain2id[dom]
            mailaddr.clear()
            expire_date = None
            if tmp.has_key("expire_date"):
                expire_date = [int(x) for x in tmp['expire_date'].split('-')]
                expire_date = db.Date(*expire_date)
            mailaddr.populate(lp, dom_id, mt_id, expire_date)
            ma_id = mailaddr.write_db()

            if tmp.get("primary", "no") == "yes":
                mailprimaddr.clear()
                mailprimaddr.populate(ma_id, parent=mailtarg)
                mailprimaddr.write_db()

    # Assign account affiliaitons by checking the
    # user_aff_mapping.  if subtype = '*unset*, try to find a
    # corresponding person affiliation, first at the same OU, then at
    # any OU (overriding the OU set for the user).
    #
    # If no corresponding person_affiliation was found, the
    # affiliation is IGNORED (with a warning).

    if u.get('uio', {}).has_key('utype'):
        utype = u['uio']['utype']
        ustype = u['uio'].get('ustype', '') or '*unset*'
        if ustype == 'F':
            accountObj.np_type = int(co.account_program)
            accountObj.write_db()
        else:
            aff, affstat = user_aff_mapping[utype][ustype]
            ou_id = stedkode2ou_id.get(u['uio']['usko'], default_ou)
            skip_affiliation = False
            if str(affstat) == '*unset*':
                for tmp_ou_id, tmp_aff, tmp_affstat in person_id2affs[owner_id]:
                    if (tmp_ou_id, tmp_aff) == (ou_id, aff):
                        affstat = tmp_affstat
                        break
            if str(affstat) == '*unset*':
                for tmp_ou_id, tmp_aff, tmp_affstat in person_id2affs[owner_id]:
                    if tmp_aff == aff:
                        affstat = tmp_affstat
                        ou_id = tmp_ou_id
                        break
            if str(affstat) <> '*unset*':
                account_id2aff[accountObj.entity_id] = (ou_id, aff, affstat)
                if not (ou_id, aff, affstat) in person_id2affs[owner_id]:
                    person_id2affs[owner_id].append((ou_id, aff, affstat))
            else:
                print "Warning: error mapping affiliation %s: %s/%s@%s" % (
                    u['uname'], aff, affstat, u['uio']['usko'])
        
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
    if u.has_key("printerquota"):
        p = u['printerquota']
        pquotas.clear()
        pquotas.populate(accountObj.entity_id, p['printer_quota'],
                         p['pages_printed'], p['pages_this_semester'],
                         p['termin_quota'], p['has_printerquota'],
                         p['weekly_quota'], p['max_quota'])
        pquotas.write_db()

    if u.get('is_primary', 0) and int(u['is_primary']):
        primary_users[int(accountObj.entity_id)] = 1
 
    for tmp in u.get('spread', []):
        if tmp['domain'] == 'u':
            accountObj.add_spread(co.spread_uio_nis_user)
        elif tmp['domain'] == 'i':
            accountObj.add_spread(co.spread_ifi_nis_user)
    for tmp in u.get('pwdhist', []):
        pwdhist.add_history(accountObj, '', _csum=tmp['value'])
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
    print "[%s] %s (delta: %i)" % (strftime("%H:%M:%S", localtime()), msg, (time()-prev_msgtime))
    prev_msgtime = time()

def read_config(fname):
    "Reads configuration from a python-script specified by filename"
    global person_aff_mapping, user_aff_mapping, default_ou

    globs = {}
    locs = {}
    execfile(fname, globs, locs)
    person_aff_mapping = locs.get('person_aff_mapping')
    user_aff_mapping = locs.get('user_aff_mapping')
    default_ou = locs.get('default_ou')

def usage():
    print """import_userdb_XML.py -c file -s system [{-g|-e|-p|-m|-i} file] [ -m num ] {-G|-E|-P|-M|-I}

-c file: manadatory configurationfile
-G : generate the groups
-E : import email domains and non-user email addresses
-P : generate persons, accounts and user email addresses
-M : populate the groups with members
-I : import it-group permissions
-s system: mandatory source-system

This program is normally run first with -G, then -E, -P, -M and
finally with -M.  It is not designed allow import multiple times to
the same database.

This script is designed import to a database that contains no users or
groups.  OU and person tables should preferably already have been
populated (by some other program(s)).  When importing accounts, the
persons will be created iff they cannot be located by their extid
(currently only fnr is supported).

"""

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:dp:g:m:vi:e:s:PGMIE",
                                   ["pfile=", "gfile=", "persons", "groups",
                                    "groupmembers", "verbose", "quick-test",
                                    "max_cb=", "emailfile=", "email", "config=",
                                    "source-system="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    global max_cb, verbose, quick_test, source_system
    verbose = 0
    quick_test = 0
    # global debug
    max_cb = None
    pfile = default_personfile
    gfile = default_groupfile
    ifile = default_itpermfile
    emfile = default_emailfile
    showtime("Started")
    for o, a in opts:
        if o in ('-p', '--pfile'):
            pfile = a
        elif o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('--quick-test',):
            quick_test = 1
        elif o in ('-g', '--gfile'):
            gfile = a
        elif o in ('-i',):
            ifile = a
        elif o in ('-P', '--persons'):
            import_person_users(pfile)
        elif o in ('-G', '--groups'):
            import_groups(gfile, 0)
        elif o in ('-I',):
            import_itperms(ifile)
        elif o in ('-m', '--max_cb'):
            max_cb = int(a)
        elif o in ('-d',):
            debug += 1
        elif o in ('-M', '--groupmembers'):
            import_groups(gfile, 1)
        elif o in ('-c', '--config',):
            read_config(a)
        elif o in ('-e', '--emailfile',):
            emfile = a
        elif o in ('-E', '--email',):
            import_email(emfile)
        elif o in ('-s', '--source-system',):
            source_system = getattr(co, a)
    if(len(opts) == 0):
        usage()
    else:
        showtime("all done")

# TODO:
# * Hvordan skal defaultgruppe for slettede brukere huskes?
# * Sette account_info.create_date til opprettelsesdato fra Ureg.
