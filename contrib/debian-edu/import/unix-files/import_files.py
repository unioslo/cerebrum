#!/usr/bin/python
#
# this is a program for importing flat files into cerebrum
# those files are /etc/group /etc/password and /etc/shadow
# or other, specificly specified files of the same format
#
"""
supervises and calls the different file import modules
"""

import getopt
import sys


import cerebrum_path
import cereconf

from Cerebrum.Database import Errors
from Cerebrum.Utils    import Factory

#import import.general
import Import


# this should kill us if something is wrong


    
db = Factory.get('Database')()
db.cl_init(change_program='import_files')
logger= Factory.get_logger("console")

def check_consistency(files):

    import_data = {}
    import_data['members'], import_data['groups'] = \
                            g.checkFileConsistency( files['group'] ) 
    import_data['passwd'] = p.checkFileConsistency( files['passwd'] ) 
    import_data['shadow'] = s.checkFileConsistency( files['shadow'] )
#    print user_dicts
    cross_check_files(import_data)

    return import_data

def cross_check_files(users):
    corrupt = False

    # check if passwd and shadow have the same users
    shadow = users["shadow"].copy() # do we need the original later?
    for user_tup in users["passwd"].items():
        user_name, line_number = user_tup
        if not shadow.has_key(user_name):
            print "user %s mentioned in line %s of the password file \
                   is not in shadow file" % (
                user_name, line_number)
            corrupt = True
        else:
            del shadow[user_name]
    # do we have entries in shadow missing from passwd?
    if shadow:
        corrupt = True        
        for user_tup in shadow.items():
            user_name, line_number = user_tup
            print "user %s mentioned in line %s of the shadow file \
            is not in passwd file" % (
                user_name, line_number)
        
    # are there users in the group file missing from the passwd file?
    for user in users["members"].items():
        user_name, line_number = user
        if not users["passwd"].has_key(user_name):
            print "user %s mentioned in line %s of the\
            group file is not defined" % (
                user_name, line_number)
            corrupt = True

    if corrupt:
        sys.exit()
             

def import_files(data ): 

    g.createGroups      ( data['groups'] ) 
    p.createUsers       ( data['passwd'] ) 
    s.addUserPasswd     ( data['shadow'] )
    g.addMembersToGroups( data['groups'] )

    g.attemptCommit()
    s.attemptCommit()
    p.attemptCommit()

def usage():
    print """Usage: import_filegroups.py -p|--passwd FILE
                                         -s|--shadow FILE
                                         -g|--group  FILE
                                         [-d|--dryrun]
                                         [--spread]
    -d, --dryrun  : Run a fake Import. Rollback after run.
    -g, --group   : group file
    -p, --passwd  : password file
    -s, --shadow  : shadow file
        --spread  : must be a defined one
    """
# end usage

def main():
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'g:d:s:p',
                                   ['group=',
                                    'shadow=',
                                    'passwd=',
                                    'dryrun',
                                    'spread='])
    except getopt.GetoptError:
        usage()
        return 1
    # yrt
    
    dryrun = False
    files = {}
    spread = None
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-g', '--group'):
            files['group'] = val
        elif opt in ('-s', '--shadow'):
            files['shadow'] = val
        elif opt in ('-p', '--passwd'):
            files['passwd'] = val
        elif opt in ('--spread'):
            spread = val
            if not ( Import.group.verify_spread( spread ) ):
                usage()
                return 1
        # fi
    # opt
    
    global g, p, s
    
    g = Import.group.GroupImport  (db,dryrun, spread)
    p = Import.password.PasswdImport(db,dryrun)
    s = Import.shadow.ShadowImport(db,dryrun)


    import_data = check_consistency(files)    
    import_files( import_data )

# end main


if __name__ == '__main__':
    main()
# fi
