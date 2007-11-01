#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Disclaimer:
# Only to live until the old BDB-system is switched off - 
# since feideIds are populated outside BDB based on data from BDB.

import sys
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

import getopt
import logging
import time
import os
import traceback
import ldap

import locale
locale.setlocale(locale.LC_ALL,'nb_NO')

dryrun = verbose = False
db = Factory.get('Database')()
db.cl_init(change_program='import_feideid')
const = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)

logger = Factory.get_logger("console")

ldap_server = cereconf.LDAP_FEIDE_AUTH_BACKEND
ldap_base = cereconf.LDAP_FEIDE_BASE
ldap_filter = cereconf.LDAP_FEIDE_SEARCH_FILTER
ldap_binddn = cereconf.LDAP_FEIDE_BINDDN
ldap_bindpw = cereconf.LDAP_FEIDE_BINDPW

def get_edupersons():
    logger.info("Fetching FeideIDs from LDAP")
    result = []
    l = ldap.open(ldap_server)
    l.start_tls_s()
    l.simple_bind_s(ldap_binddn,ldap_bindpw)
    attrs = ['uid','edupersonprincipalname']
    result = l.search_s(ldap_base,ldap.SCOPE_ONELEVEL,ldap_filter,attrs)
    l.unbind_s()
    return result

def usage():
    print """ Usage: %s <options>
    Valid options:
        -h --help   (this)
        -d --dryrun (Don't commit changes to Cerebrum)
    """ % sys.argv[0]

def sync_feideid(feideperson):
    username = feideperson.get('uid')[0]
    logger.debug("Processing %s" % username)
    person.clear()
    account.clear()
    try:
        account.find_by_name(username)
    except Errors.NotFoundError:
        logger.warn("Username %s not in Cerebrum. Continuing.." % username)
        return
    person.find(account.owner_id)
    ldap_feideid = feideperson.get('eduPersonPrincipalName')[0]
    res = person.get_external_id(const.system_bdb,const.externalid_feideid)
    if len(res) == 0:
        person.affect_external_id( const.system_bdb, const.externalid_feideid)
        person.populate_external_id(const.system_bdb,const.externalid_feideid,ldap_feideid)
        person.write_db()
        logger.debug("Writing FeideID %s to database" % ldap_feideid)
    else:
        res = res[0]
        t,f,cerebrum_feide_id = res
        if cerebrum_feide_id != ldap_feideid:
            logger.info("FeideID was %s. Changing to %s" % (cerebrum_feide_id,ldap_feideid))
            # Remove old
            person._delete_external_id(const.system_bdb, const.externalid_feideid)
            person.write_db()
            # Add new
            person.affect_external_id(const.system_bdb, const.externalid_feideid)
            person.populate_external_id(const.system_bdb,const.externalid_feideid,ldap_feideid)
            person.write_db()
        else:
            logger.debug( "FeideID %s found but not changed" % cerebrum_feide_id)
    return

def main():
    global dryrun
    opts,args = getopt.getopt(sys.argv[1:],
                       'hd',['help','dryrun'])
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-d','--dryrun'):
            dryrun = True

    for dn,ldif in get_edupersons():
        sync_feideid(ldif)
        if dryrun:
            db.rollback()
        else:
            db.commit()

if __name__ == '__main__':
    main()
