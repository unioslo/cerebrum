#!/usr/bin/python2.2

import getopt
import sys
import os

# Simple definition of legal commands.  In the future this should be
# read from a configuration file.
# Format: 'key': ['path', 'number-of-args']
# future versions could provide more restrictions on the legal arguments
commands = {
    # uname, uid, gid, old_disk, new_disk, mailto, receipt
    'mvuser': [cereconf.MVUSER_SCRIPT, 7],
    'rmuser': [cereconf.RMUSER_SCRIPT, 3], # uname, operator, old_home
    # uname, home_path, uid, gid, tpl_dir, usermod_script_dir, gecos
    'adduser': [cereconf.CREATE_USER_SCRIPT, 7],
    }

def usage(exitcode=0):
    print """Usage: run_privilleged_command.py [-c cmd | -h] args
    -c | --command cmd: run the command with specified args
    -h | --help: this message

    This script works as a small wrapper to other scripts.  A
    configuration file defines what commands a user may run, and to
    some extent what arguments may be provided.  It is not designed to
    be bulletproof, but rather as a method to avoid shooting oneself
    in the foot, as well as avoiding multiple complex lines in
    /etc/sudoers.

    Add something like this to /etc/sudoers:
    cerebrum  localhost=NOPASSWD: /path/to/run_privilleged_command.py
    """
    
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:',
                                   ['help', 'command='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    command = None
    for opt, val in opts:
        if opt in ('-c', '--command'):
            command = val
        elif opt in ('-h', '--help'):
            usage(0)
    if command is not None:
        if not commands.has_key(command):
            print "Bad command: %s" % command
            sys.exit(1)
        if len(args) != commands[command][1]:
            print "Bad # args for %s (%i/%i)" % (
                command, len(args), commands[command][1])
            sys.exit(1)
        args.insert(0, commands[command][0])
        os.execv(commands[command][0], args)

if __name__ == '__main__':
    main()
