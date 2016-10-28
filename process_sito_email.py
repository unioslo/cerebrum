#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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


progname = __file__.split("/")[-1]
__doc__="""This script creates/updates email addresses for all accounts
in cerebrum that has a email spread

usage:: %s [options] 

options is    
    -h | --help     : show this
    -d | --dryrun   : do not change DB
    --logger-name name   : log name to use 
    --logger-level level : log level to use
""" % ( progname, )


import getopt
import sys
import os
import mx.DateTime


import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.Email import EmailDomain,EmailAddress

# kbj005/H2016
# Temporary addition to use while running old and new Cerebrum in parallel.
# TODO: revert/remove all things "labelled" with kbj005/H2016 when we no longer need this.
from Cerebrum.modules.no.uit.account_bridge import AccountBridge
# kbj005/H2016

#initialise Cerebrum objects
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
p = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program=progname)
logger=Factory.get_logger('cronjob')
em=Email.email_address(db,logger=logger)

# script variables
try_only_first=True
sito_addresses_in_use=list()
sito_addresses_new=list()

def _get_alternatives(account_name):
    ac.clear()
    ac.find_by_name(account_name)
    alternatives=list()
    first_choise=ac.get_email_cn_local_part(given_names=1, max_initials=1, keep_dash=True)
    alternatives.append(first_choise)
    # find other alternatives
    
#    # skip these for now. Never used and slow things down!
#    given_names=(3,2,1,0,-1)
#    max_initials=(1,2,0,3,4)
#    for nm in given_names:
#        for mlm in max_initials:
#            for dash in (True,False):
#                local_part = ac.get_email_cn_local_part(given_names=nm, max_initials=mlm, keep_dash=dash)
#                if "." not in local_part:
#                    continue
#                if local_part not in alternatives:
#                    alternatives.append(local_part)
    logger.debug("Alternatives for %s: %s" % (account_name,alternatives))
    return alternatives


def get_domainid(domain_part):
    domain = EmailDomain(db)
    domain.find_by_domain(domain_part)
    return domain.entity_id
get_domainid=memoize(get_domainid)


def is_cnaddr_free(local_part,domain_part):
    
    addr="@".join((local_part,domain_part))
    if addr in sito_addresses_in_use:
        logger.error("Address %s not free, in DB" % (addr,))
        return False
    elif addr in sito_addresses_new:
        logger.error("Addres %s not free, in new set" % (addr,))
        return False
    return True


def is_cnaddr_free_old(local_part,domain_part):
    
    domain_id=get_domainid(domain_part)
    ea =EmailAddress(db)
    logger.debug("Considering %s, %s" % (local_part,domain_part))
    try:
        ea.find_by_local_part_and_domain(local_part, domain_id)
    except Errors.NotFoundError:
        #emailaddress is free.
        logger.debug("Address %s@%s is free: " % (local_part,domain_part))
    else:
        logger.warn("Address %s@%s is not free!" % (local_part,domain_part))
        return False
    return True
    

# kbj005/H2016
# Temporary addition to use while running old and new Cerebrum in parallel.
# TODO: revert/remove all things "labelled" with kbj005/H2016 when we no longer need this.
def get_cn_addr_tmp(username):
    with AccountBridge() as bridge:
        email = bridge.get_email(username)
    if email == None:
        logger.warn("Cannot add email for sito account %s. Couldn't find email for this account in Caesar database." % uname)
        return None, None

    split_email = email.split('@')
    em_addr = split_email[0]
    dom_part = split_email[1]
    return (em_addr, dom_part)
# kbj005/H2016


def get_cn_addr(username,domain):
# kbj005/H2016
    return get_cn_addr_tmp(username)
# kbj005/H2016

    dom_part=domain
    
    alternatives=_get_alternatives(username)
    if try_only_first:
        logger.info("Trying only first alternative")
        alternatives = alternatives[:1]
        for em_addr in alternatives:
            if is_cnaddr_free(em_addr,dom_part):
                return (em_addr,dom_part)
    else:
        logger.error("NOT IMPLEMENTET. Using more than first suggested emailaddr")
    return None,dom_part


# kbj005/H2016
# Temporary addition to use while running old and new Cerebrum in parallel.
# TODO: revert/remove all things "labelled" with kbj005/H2016 when we no longer need this.
# Returns a list of tuples of uname and domain_name (e.g.: [('karina', 'driv.no'), ('karina', 'sito.no')])
def get_email_aliases_tmp(username):
    aliases = list()
    with AccountBridge() as bridge:
        email_aliases = bridge.get_email_aliases(username)
        for email in email_aliases:
            split_email = email.split('@')
            em_addr = split_email[0]
            dom_part = split_email[1]
            aliases.append((em_addr, dom_part))
    return aliases
# kbj005/H2016


def process_mail():

    logger.info("Get all SiTo persons")
    sito_persons=list()
    for row in p.list_affiliations(source_system=co.system_sito):
        sito_persons.append(row['person_id'])
    logger.info("Got %s sito persons" % (len(sito_persons)))

    logger.info("Get all accounts with exchange@uit spread from sito")
    exch_users=dict()
    uname2accid=dict()
    ownerid2uname=dict()
    count=0
    skipped=0
    
    #TBD: Use account affiliation = sito to get accounts instead of spread!
    for a in ac.search(spread=co.spread_exchange_account):
        if (a['name'].endswith(cereconf.USERNAME_POSTFIX.get('sito'))):
            logger.debug("caching sito account %s" % a['name'])
        else:
            skipped+=1
            #logger.debug("Skipping non sito account %s" % a['name'])
            continue

        if a['owner_id'] in sito_persons:
            count+=1
            exch_users[a['account_id']]= a['name']
            uname2accid[a['name']]=a['account_id']
            ownerid2uname.setdefault(a['owner_id'],list()).append(a['name'])
        #all_emails.setdefault(account_id,list()).append(uid_addr)
    keys=exch_users.keys()
    keys.sort()
    logger.info("got %d accounts (%s)" % (len(exch_users),count))
    logger.info("got %d account" % (len(uname2accid,)))
    logger.info("skipped %d account" % (skipped,))


    for owner,uname in ownerid2uname.iteritems():
        if len(uname)>1:
            logger.debug("Owner %s has %s accounts: %s" % (owner,len(uname),uname))

    sito_domainname=cereconf.SITO_PRIMARY_MAILDOMAIN
    logger.info("get all email targets for sito")
    sito_mails=dict()
    for uname,data in ac.getdict_uname2mailinfo().iteritems():
        #only sito
        if uname2accid.get(uname,None):
            # this is a sito user
            for me in data:
                if me['domain'] == sito_domainname:
                    sito_mails[uname]="@".join((me['local_part'],me['domain']))
                    sito_addresses_in_use="@".join((me['local_part'],me['domain']))


    #list to hold those we will build addresses for
    all_emails = dict()
    primary=dict()


    for account_id,uname in exch_users.iteritems():
        old_addr=sito_mails.get(uname,None)
        if old_addr:
            logger.debug("Got %s as existing mailaddress for %s" % (old_addr,uname))
        else:
            logger.info("user %s does not hava a sito address!, BUILD" % (uname))
            cn_addr=get_cn_addr(uname,sito_domainname)
            if cn_addr:
                logger.debug("Will use %s for %s"  % (cn_addr,uname))
                all_emails.setdefault(account_id,list()).append(cn_addr)
                sito_addresses_new.append(cn_addr)

# kbj005/H2016
                # Add email aliases
                email_aliases = get_email_aliases_tmp(uname)
                all_emails.setdefault(account_id,list()).extend(email_aliases)
# kbj005/H2016
            else:
                logger.error("Got NOADRESS for %s, check logs" %(uname,))


    # update all email addresses
    logger.debug("Ready to update %s sito addresses" % (len(all_emails)))
    for acc_id,emaillist in all_emails.iteritems():

# kbj005/H2016
        cnt = 0
# kbj005/H2016

        for addr in emaillist:
            #TBD: is_primary always set to True?   
            is_primary=True

# kbj005/H2016
            # if there is more than one email for this account only the first is primary
            if cnt > 0:
                is_primary = False
            cnt += 1
# kbj005/H2016

            addr="@".join((addr[0],addr[1]))
            logger.info("Set mailaddr: %s/%s, primary=%s" % (acc_id,addr,is_primary))
            em.process_mail(acc_id,addr, is_primary=is_primary)



def main():
    global persons,accounts

    starttime=mx.DateTime.now()
    try:
        opts,args = getopt.getopt(sys.argv[1:],'dh',
                                  ['dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    dryrun = False
    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        elif opt in ('-h','--help'):
            usage()

    process_mail()

    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")
        
    endtime=mx.DateTime.now()
    logger.debug("Started %s ended %s" %  (starttime,endtime))
    logger.debug("Script running time was %s " % ((endtime-starttime).strftime("%M minutes %S secs")))


def usage(exitcode=0,msg=None):
    if msg: print msg
    print __doc__
    sys.exit(exitcode)


if __name__=='__main__':
    main()

