# -*- Mode: Python; tab-width: 4 -*-
#
# Copyright (C) 2003-2006 Gianluigi Tiesi <sherpya@netfarm.it>
# Copyright (C) 2003-2006 NetFarm S.r.l.  [http://www.netfarm.it]
#
# Requires python >= 2.3
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
# ======================================================================

__version__ = '0.6'
__all__ = [ 'CYRUS' ]
__doc__ = """Cyrus admin wrapper
Adds cyrus-specific commands to imaplib IMAP4 Class
and defines new CYRUS class for cyrus imapd commands"""

from sys import stdout
import imaplib
import re

### Missing commands
# SETANNOTATION "" "/type" ("value.shared" "value")
# type can be motd|comment|admin|shutdown|expire|squat

# GETANNOTATION "" "*" "value.shared"
# result: ANNOTATION "" "/admin" ("value.shared" "admin_value")
# (1 type for each line)

Commands = {
    'SETQUOTA'     : ('AUTH',),
    'CREATE'       : ('AUTH',), # Override for partitions
    'RENAME'       : ('AUTH',), # Override for partitions
    'RECONSTRUCT'  : ('AUTH',),
    'NAMESPACE'    : ('AUTH',),
    'DUMP'         : ('AUTH',), # To check admin status
    'ID'           : ('AUTH',), # Only one ID allowed in non auth mode
    'GETANNOTATION': ('AUTH',),
    'SETANNOTATION': ('AUTH',)
    }

DEFAULT_SEP = '.'
QUOTE       = '"'
DQUOTE      = '""'

imaplib.Commands.update(Commands)

re_ns = re.compile(r'.*\(\(\".*(\.|/)\"\)\).*')
re_q  = re.compile(r'(.*)\s\(STORAGE (\d+) (\d+)\)')
re_mb = re.compile(r'\((.*)\)\s\".\"\s(.*)')

def imap_ok(res):
    return res.upper().startswith('OK')

def quote(text, qchar=QUOTE):
    return text.join([qchar, qchar])

def unquote(text, qchar=QUOTE):
    return ''.join(text.split(qchar))

def getflags(test):
    flags = []
    for flag in test.split('\\'):
        flag = flag.strip()
        if len(flag): flags.append(flag)
    return flags

### A smart function to return an array of splitted strings
### and honours quoted strings
def splitquote(text):
    data = text.split(QUOTE)
    if len(data) == 1: # no quotes
        res = data[0].split()
    else:
        res = []
        for match in data:
            if len(match.strip()) == 0: continue
            if match[0] == ' ':
                res = res + match.strip().split()
            else:
                res.append(match)
    return res

### return a dictionary from a cyrus info response
def res2dict(data):
    data = splitquote(data)
    datalen = len(data)
    if datalen % 2: # Unmatched pair
        return False, {}
    res = {}
    for i in range(0, datalen, 2):
        res[data[i]] = data[i+1]
    return True, res

### Wrapped new/overloaded IMAP function
### returning False instead of raising an exception
class IMAP4(imaplib.IMAP4):
    def getsep(self):
        """Get mailbox separator"""
        ### yes, ugly but cyradm does it in the same way
        ### also more realable then calling NAMESPACE
        ### and it should be also compatibile with other servers
        try:
            return unquote(self.list(DQUOTE, DQUOTE)[1][0]).split()[1]
        except:
            return DEFAULT_SEP

    def isadmin(self):
        ### A trick to check if the user is admin or not
        ### normal users cannot use dump command
        try:
            res, msg = self._simple_command('DUMP', 'NIL')
            if msg[0].lower().find('denied') == -1:
                return True
        except:
            pass
        return False

    def id(self):
        name = 'ID'
        try:
            typ, dat = self._simple_command(name, 'NIL')
            res, dat = self._untagged_response(typ, dat, name)
        except:
            return False, dat[0]
        return imap_ok(res), dat[0]

    def getannotation(self, mailbox, pattern='*'):
        typ, dat = self._simple_command('GETANNOTATION', mailbox, quote(pattern), quote('value.shared'))
        return self._untagged_response(typ, dat, 'ANNOTATION')

    def setquota(self, mailbox, limit):
        """Set quota of a mailbox"""
        quota = '(STORAGE %s)' % limit
        return self._simple_command('SETQUOTA', mailbox, quota)

    ### Overridden to support partition
    ### Pychecker will complain about non matching signature
    def create(self, mailbox, partition=None):
        """Create a mailbox, partition is optional"""
        if partition is not None:
            return self._simple_command('CREATE', mailbox, partition)
        else:
            return self._simple_command('CREATE', mailbox)

    ### Overridden to support partition
    ### Pychecker: same here
    def rename(self, from_mailbox, to_mailbox, partition=None):
        """Rename a from_mailbox to to_mailbox, partition is optional"""
        if partition is not None:
            return self._simple_command('RENAME', from_mailbox, to_mailbox, partition)
        else:
            return self._simple_command('RENAME', from_mailbox, to_mailbox)

    def reconstruct(self, mailbox):
        return self._simple_command('RECONSTRUCT', mailbox)

class CYRUS:
    def __init__(self, host = '', port = imaplib.IMAP4_PORT):
        self.m = IMAP4(host, port)
        self.auth = False
        self.verbose = False
        self.admin = None
        self.sep = DEFAULT_SEP
        self.logfd = stdout

    def __del__(self):
        if self.auth:
            if self.verbose: print >> self.logfd, 'Connection still in AUTH state, calling logout()'
            self.logout()

    ### Login and store in self.admin admin userid
    def login(self, username, password):
        try:
            res, msg = self.m.login(username, password)
            self.auth = True
            if self.m.isadmin():
                self.admin = username
            else:
                self.admin = None
            self.admin_acl = 'c'
            self.sep = self.m.getsep()
            if self.verbose: print >> self.logfd, '[LOGIN %s] %s: %s' % (username, res, msg[0])
            return True
        except Exception, info:
            error = info.args[0].split(':').pop().strip()
            if self.verbose: print >> self.logfd, '[LOGIN %s] BAD: %s' % (username, error)
            self.auth = False
            return False

    ### Logout
    def logout(self):
        self.auth = False
        self.admin = None
        try:
            res, msg = self.m.logout()
        except Exception, info:
            error = info.args[0].split(':').pop().strip()
            if self.verbose: print >> self.logfd, '[LOGOUT] BAD: %s' % error
            return False
        if self.verbose: print >> self.logfd, '[LOGOUT] %s: %s' % (res, msg[0])
        return True

    ### Message for no auth
    def _noauth(self, command, result=False):
        if self.verbose: print >> self.logfd, '[%s] Not in AUTH state' % command.upper()
        return result

    ### Wrapper to catch exceptions
    def _docommand(self, function, *args):
        wrapped = getattr(self.m, function, None)
        if wrapped is None: return ['BAD', '%s command not implemented' % function.upper()]
        try:
            return wrapped(*args)
        except Exception, info:
            error = info.args[0].split(':').pop().strip()
            if error.upper().startswith('BAD'):
                error = error.split('BAD', 1).pop().strip()
                error = unquote(error[1:-1], '\'')
            return ['BAD', '%s command failed: %s' % (function.upper(), error)]

    ### Info about server
    def id(self):
        if not self.auth: return self._noauth('id')

        res, data = self.m.id()
        data = data.strip()
        if not res or (len(data) < 3): return False, {}
        data = data[1:-1] # Strip ()
        res, rdata = res2dict(data)
        if not res:
            if self.verbose: print >> self.logfd, '[ID] Umatched pairs in result'

        return res, rdata

    ### Get annotation of mailboxes, returns an hash of an hash of hash :P
    def getannotation(self, group, user, pattern='*'):
        if not self.auth: return self._noauth('getannotation')

        if group is None or (len(group.strip()) == 0):
            mailbox = user
        else:
            mailbox = self.sep.join([group, user])

        res, data = self._docommand('getannotation', mailbox, pattern)

        if not imap_ok(res):
            if self.verbose: print >> self.logfd, '[%s] %s' % (res, data)
            return False, {}

        if (len(data) == 1) and data[0] is None:
            if self.verbose: print >> self.logfd, '[GETANNOTATION] No results'
            return False, {}

        ann = {}
        for entry in data:
            entry = entry.split(' ', 2)
            if len(entry) != 3:
                if self.verbose: print >> self.logfd, '[GETANNOTATION] Invalid annotation entry'
                continue
            mbe = unquote(entry[0])
            key = unquote(entry[1])
            value = unquote(entry[2].split(' ', 1).pop()[:-1]).strip()

            if group is not None and mbe.startswith(group + self.sep):
                group, mailbox = mbe.split(self.sep, 1)
            else:
                group, mailbox = ('all', mbe)

            if not ann.has_key(group):
                ann[group] = {}

            if not ann[group].has_key(mailbox):
                ann[group][mailbox] = {}

            if not ann[group][mailbox].has_key(key):
                ann[group][mailbox][key] = value

        return True, ann

    ### Rename a mailbox or move to another partition
    def rename(self, from_group, from_user, to_group, to_user, partition=None):
        if not self.auth: return self._noauth('rename')

        if from_group is None:
            from_mailbox = from_user
        else:
            from_mailbox = self.sep.join([from_group, from_user])

        if to_group is None:
            to_mailbox = to_user
        else:
            to_mailbox = self.sep.join([to_group, to_user])

        res, msg = self.m.rename(from_mailbox, to_mailbox, partition)

        if self.verbose:
            print >> self.logfd, '[RENAME %s %s] %s: %s' % (from_mailbox, to_mailbox, res, msg[0])

        return imap_ok(res)

    ### Reconstruct a mailbox/shared malbox
    ### For shared mailbox use reconstruct(None, 'shared_mbname')
    ### TODO: recursive reconstruction is not supported by server?
    def reconstruct(self, group, user):
        if not self.auth: return self._noauth('reconstruct')

        if group is None:
            mailbox = user
        else:
            mailbox = self.sep.join([group, user])

        res, msg = self.m.reconstruct(mailbox)

        if self.verbose:
            print >> self.logfd, '[RECONSTRUCT %s] %s: %s' % (mailbox, res, msg[0])

        return imap_ok(res)

    ### Create mailbox
    def cm(self, group, user, partition=None):
        if not self.auth: return self._noauth('cm')

        if group is None:
            mailbox = user
        else:
            mailbox = self.sep.join([group, user])

        res, msg = self.m.create(mailbox, partition)

        if self.verbose:
            print >> self.logfd, '[CREATE %s partition=%s] %s: %s' % (mailbox, partition, res, msg[0])

        if not imap_ok(res): return False
        if self.admin: self.sam(group, user, self.admin, self.admin_acl)
        return True

    ### Delete mailbox
    def dm(self, group, user):
        if not self.auth: return self._noauth('dm')

        if group is None:
            mailbox = user
        else:
            mailbox = self.sep.join([group, user])

        if self.admin: self.m.setacl(mailbox, self.admin, self.admin_acl)
        res, msg = self.m.delete(mailbox)
        if self.verbose: print >> self.logfd, '[DELETE %s] %s: %s' % (mailbox, res, msg[0])
        return imap_ok(res)

    def lm(self, group='user', pattern='%'):
        """
        List mailboxes, returns dict with list of mailboxes for given group

        List users in a group
        To list mailusers:                   lm()
        To list all top folder (also shared) lm(None)
        To list a mailuser's folders         lm('user', 'mailuser*')

        as normal user: lm() to list all folders/shared/INBOX
        """
        if not self.auth: return self._noauth('lm', {})

        if self.admin is None: group = None # Namespace is different

        if group is None or (len(group.strip()) == 0):
            group = None
            query = pattern
        else:
            query = self.sep.join([group, pattern])

        res, ml = self._docommand('list', '*', query)

        if not imap_ok(res):
            if self.verbose: print >> self.logfd, '[%s] %s' % (res, ml)
            return {}

        if (len(ml) == 1) and ml[0] is None:
            if self.verbose: print >> self.logfd, '[LIST] No results'
            return {}

        mb = {}
        for entry in ml:
            res = re_mb.match(entry)
            if res is None: continue
            flags = getflags(res.group(1))
            mbe = unquote(res.group(2))
            if 'Noselect' in flags: continue
            if group is not None and mbe.startswith(group + self.sep):
                group, mailbox = mbe.split(self.sep, 1)
            else:
                group, mailbox = ('all', mbe)

            if not mb.has_key(group):
                mb[group] = []
            mb[group].append(mailbox)
        return mb

    def lam(self, group, user):
        if not self.auth: return self._noauth('lam', {})

        mailbox = self.sep.join([group, user])
        res, acl = self.m.getacl(mailbox)

        if not imap_ok(res): return None
        acls = {}

        acl_list = splitquote(acl.pop().strip())
        del acl_list[0] # user/username

        for i in range(0, len(acl_list), 2):
            try:
                userid = acl_list[i]
                rights = acl_list[i + 1]
            except Exception, info:
                print >> self.logfd, '[GETACL %s] BAD: %s' % (mailbox, info.args[0])
                continue
            if self.verbose:
                print >> self.logfd, '[GETACL %s] %s %s' % (mailbox, userid, rights)
            acls[userid] = rights

        return acls

    def sam(self, group, user, userid, rights):
        if not self.auth: return self._noauth('sam')

        mailbox = self.sep.join([group, user])
        res, msg = self.m.setacl(mailbox, userid, rights)
        if self.verbose:
            print >> self.logfd, '[SETACL %s %s %s] %s: %s' % (mailbox, userid, rights, res, msg[0])
        return imap_ok(res)

    def lq(self, group, user):
        if not self.auth: return self._noauth('lq', (-1, -1))

        mailbox = self.sep.join([group, user])
        res, msg = self.m.getquota(mailbox)

        if not imap_ok(res):
            if self.verbose:
                print >> self.logfd, '[GETQUOTA %s] %s: %s' % (mailbox, res, msg[0])
            return -1, -1

        match = re_q.match(msg[0])
        if match is None:
            if self.verbose:
                print >> self.logfd, '[GETQUOTA %s] BAD: RegExp not matched, please report' % mailbox
            return -1, -1

        try:
            used = int(match.group(2))
            quota = int(match.group(3))
            if self.verbose:
                print >> self.logfd, '[GETQUOTA %s] %s: QUOTA %d/%d' % (mailbox, res, used, quota)
            return used, quota
        except:
            if self.verbose:
                print >> self.logfd, '[GETQUOTA %s] BAD: Error while parsing values' % mailbox
            return -1, -1

    def sq(self, group, user, limit):
        if not self.auth: return self._noauth('sq')

        mailbox = self.sep.join([group, user])
        try:
            limit = int(limit)
        except:
            if self.verbose:
                print >> self.logfd, '[SETQUOTA %s] BAD: Invalid argument %s' % (mailbox, limit)
            return False

        res, msg = self.m.setquota(mailbox, limit)
        if self.verbose:
            print >> self.logfd, '[SETQUOTA %s] %s: %s' % (mailbox, res, msg[0])
        return imap_ok(res)
