#!/usr/bin/env python2.2

import sys
import crypt
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

def usage():
    print "usage: create_bootstrapuser.py [-v] <-P password>"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'P:v', ['password',
                                                         'verbose'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
        
    verbose = 0
    password = None
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-P', '--password'):
            password = val

    if None == password:
        usage()
        sys.exit(1)

    # Create hash
    salt = "\$1\$"
    hash = crypt.crypt(password, salt)

    # perl -le 'print crypt("password", "\$1\$")'
    #   $1$$I2o9Z7NcvQAKp7wyCTlia0

    # Store it account_authentication
    user = cereconf.BOFHD_SUPERUSER_GROUP[0]
    sql = """
INSERT INTO account_authentication (account_id, method, auth_data)
  VALUES ((SELECT entity_id from entity_name
                  WHERE entity_name = '%s'),
          (SELECT code FROM authentication_code WHERE code_str = 'MD5-crypt'),
          '%s');
          """ % (user, hash)
    if verbose > 0:
        print sql

    db = Factory.get('Database')()
    db.execute(sql)
    db.commit()

if __name__ == '__main__':
    main()
