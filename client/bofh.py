#!/local/python-2.2.1/bin/python
# #!/usr/bin/env python2.2

# Copyright 2002 University of Oslo, Norway
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

import xmlrpclib
import getpass
import sys
import readline
import traceback
import pprint

pp = pprint.PrettyPrinter(indent=4)

def ext_prompt(msg, type, default=None):
    if(default != None):
        msg = "%s [%s]" % (msg, default)
    msg = msg + " >"
    ret = ''
    while ret == '':
        if (type == 'passwd'):
            ret = getpass.getpass(msg)
        elif (type == 'string'):
            ret = raw_input(msg)
        if(ret == '' and default != None):
            ret = default
#    return unicode(ret, 'iso8859-1')
    return ret

def run_command(sessid, cmd):
    # - Check parameters in commands tuple
    # - Send commands as specified in commands tuple
    # - If <something magical>, run the command in a seperate thread,
    #   returning controll to the user

    ok_cmd = 0
    ret = None
    format = ''
    for k in commands.keys():
        if commands[k][0] == cmd[0] and commands[k][1] == cmd[1]:
            ok_cmd = 1
            try:
                format = testsvr.get_format_suggestion(k)
                ret = testsvr.run_command(sessid, k, *cmd[2:])
                # print "Ret: %s" % len(ret)
                # pp.pprint(ret)
                if isinstance(ret, list) or isinstance(ret, tuple):
                    for x in range(len(ret)):
                        if isinstance(ret[x], unicode):
                            ret[x] = ret[x].encode('iso8859-1')
                elif isinstance(ret, dict):
                    for x in ret.keys():
                        if isinstance(ret[x], unicode):
                            ret[x] = ret[x].encode('iso8859-1')
            except xmlrpclib.Fault, m:
                if(m.faultCode == 666):
                    print "Remote stack trace:\n%s" % m.faultString
                else:
                    print "Error: %s %s %s" % sys.exc_info()
                    traceback.print_tb(sys.exc_info()[2])
                return
                #                print dir(sys.exc_info()[2])
    if not ok_cmd:
        print "Unknown command: %s" % cmd
        return

    # Check ret, it may indicate:
    # - exception (is thrown)
    # - command response
    # - optionally: tell client to update (restart should suffice) itself. 
    if format != '' and len(ret) != 0:
        format = format.encode('iso8859-1')
        format, fields = format.split('¤')
        # print "f: %s\nx:%s\n" % (format, fields)
        if isinstance(ret, dict):
            ret = (ret,)
        for l in ret:
            dta = ()
            for f in fields.split(';'): dta += (l[f], )
            print format % dta
            #    return ret, format
    else:
        print ret

port = 8000
if len(sys.argv) == 2:
    port = int(sys.argv[1])
testsvr = xmlrpclib.Server("http://localhost:%d" % port, encoding='iso8859-1') #, verbose=1)

# user = ext_prompt('User', 'string', getpass.getuser())
# passwd = ext_prompt('Password', 'passwd')
user = 'runefro'
passwd = 'foo'
try:
    sessid = testsvr.login(user, passwd)
except xmlrpclib.Fault, msg:
    print "Error: %s" % msg
    sys.exit()
    
print "Sessid: %s" % sessid
commands = testsvr.get_commands(sessid)
print "My commands: %s" % commands


while 1:
    cmd = ext_prompt('PyBofh', 'string').split()
    #    print "Cmd: %s" % cmd
    if(cmd[0] == 'help'):
        if(len(cmd) == 1):
            print testsvr.help('').encode('iso8859-1')
        else:
            print testsvr.help(cmd[1]).encode('iso8859-1')
    else:
        run_command(sessid, cmd)
