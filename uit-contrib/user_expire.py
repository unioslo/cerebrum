#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2005 University of Oslo, Norway
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

__doc__ = """
Usage: %s [options]
    --cache cache_file
    --generate-info info_file
    -l | --logger_name name
    -h | -? | --help 

    A cache file must always be specified. It can be non-existing or
    empty, but without record of earlier data a lot of warnings will
    be generated and expiring users might get duplicate warning mails.

    generate_info reads the cache from a cache file and generates a
    html file with info about expiring users. 

""" % (progname)

import getopt
import sys
import cPickle
import mx

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum import Errors

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)    
prs = Factory.get('Person')(db)    
grp = Factory.get('Group')(db)    
ou = Factory.get('OU')(db)
ef = Email.EmailForward(db)
entity2name = dict((x["entity_id"], x["entity_name"]) for x in 
                   grp.list_names(co.account_namespace))
entity2name.update((x["entity_id"], x["entity_name"]) for x in
                   grp.list_names(co.group_namespace))

logger = None
logger_name = cereconf.DEFAULT_LOGGER_TARGET
today = mx.DateTime.today()
num_sent=0

FIRST_WARNING= cereconf.USER_EXPIRE_CONF['FIRST_WARNING']
SECOND_WARNING=cereconf.USER_EXPIRE_CONF['SECOND_WARNING']


#
# user_expire will not send notification emails from cleomedes.
# these messages are still sendt from leetah
#
#def send_mail(uname, user_info, nr, forward=False):
#    return None

def send_mail(uname, user_info, nr, forward=False):
    """Get template file based on user_info and expiring action number
    to create Subject and body of mail. Get mail addresses based on
    type of account and expiring action number. If a critical error
    occurs or sending the actual mail fails return False, else return True.
    """
    global num_sent

    logger.debug("send_mail kalled with uname=%s, user_info=%s, nr=%s" % (uname, user_info,nr))

    ac.clear()
    ac.find_by_name(uname)
    # Do not send mail to quarantined accounts
    if ac.get_entity_quarantine():
        logger.info("Account is quarantened - no mail sent: %s"% uname)
        return False
    
    def compare(a, b):
        return cmp(a['type'], b['type']) or cmp(a['name'], b['name'])

    # Assume that there exists template files for the mail texts
    # and that cereconf.py has the dict USER_EXPIRE_MAIL
    key = 'mail' + str(nr)
    try:
        mailfile = cereconf.CB_SOURCEDATA_PATH + '/templates/' + cereconf.USER_EXPIRE_MAIL[key]
        f = open(mailfile)
    except (AttributeError, KeyError):
        logger.error("cereconf.py not set up correctly: " +
                    "USER_EXPIRE_MAIL must be a dict with key %s" % key)
        return False
    except:
        logger.error("Couldn't read template expire warning file %s" % mailfile)
        return False
    else:
        lines = f.readlines()
        f.close()

    msg = []
    for line in lines:            
        if line.strip().startswith('From:'):
            email_from = line.split(':')[1] 
        elif line.strip().startswith('Subject:'):
            subject = line.split(':', 1)[1]
            subject = subject.replace('$USER$', uname)
        else:                
            msg.append(unicode(line,'utf8'))
    body = ''.join(msg)
    body = body.replace('$USER$', uname)
    body = body.replace('$EXPIRE_DATE$', user_info['expire_date'].date)
    # OK, tenk p� hvordan dette skal gj�res pent.
    if user_info['ou']:
        body = body.replace('ved $OU$', 'ved %s' % user_info['ou'])    
        body = body.replace('at $OU$', 'at %s' % user_info['ou'])    

    email_addrs = []
    ac.clear()
    ac.find(user_info['account_id'])
    if ac.owner_type == co.entity_person:
        if nr != 3:    # Don't send mail to account that is expired
            try:
                email_addrs.append(ac.get_primary_mailaddress())
            except Errors.NotFoundError:
                # This account does not have an email address.
                # Return False to indicate no email to be sent
                logger.info("account:%s does not have an associated email address" % (user_info['account_id']))
                return False
        # Get account owner's primary mail address or use current account
        try:
            prs.clear()
            prs.find(ac.owner_id)

            ac_prim = prs.get_primary_account()
            if ac_prim:
                ac.clear()
                ac.find(ac_prim)
                
            email_addrs.append(ac.get_primary_mailaddress())
        except Errors.NotFoundError:
            logger.warn("Couldn't find acoount owner's primary mail adress: %s"%
                        uname)
    else:
        logger.debug("Impersonal account %s (%s, %s )" %
                     (uname, ac.owner_type, co.entity_person))
        # Aargh! Impersonal account. Get all direct members of group
        # that owns account.
        grp.clear()
        grp.find(ac.owner_id)
        members = []
        for row in grp.search_members(group_id=grp.entity_id,
                                      member_type=co.entity_account):
            member_id = int(row["member_id"])
            if member_id not in entity2name:
                logger.warn("No name for member id=%s in group %s %s",
                            member_id, grp.group_name, grp.entity_id)
                continue
            
            members.append({'id': member_id,
                            'type': str(row["member_type"]),
                            'name': entity2name[member_id]})
        members.sort(compare)
        # get email_addrs for members
        for m in members:
            ac.clear()
            try:
                ac.find(m['id'])
                email_addrs.append(ac.get_primary_mailaddress())
            except Errors.NotFoundError:
                logger.warn("Couldn't find member acoount %s " % m['id'] +
                            "or its primary mail adress")

    if forward:
        ef.clear()
        ef.find_by_target_entity(user_info['account_id'])
        for r in ef.get_forward():            
            logger.debug("Forwarding on" + str(r))
            if r['enable'] == 'T':
                email_addrs.append(r['forward_to'])                                   
    # Now send the mail
    email_addrs = remove_duplicates(email_addrs)
    #if len(email_addrs)==1:
    #    pass 
       #email_addrs = email_addrs[0]
   #else:
   #     logger.error("To many email addrs for %s: %s" % (uname, email_addrs))
   #     return False
    try:
        #for email in email_addrs:
        #logger.info("sending email to: %s" %(', '.join(email_addrs)))
        logger.info("Sending %d. mail To: %s" % (nr, ', '.join(email_addrs)))
        Utils.sendmail(', '.join(email_addrs), email_from, subject, body.encode("iso8859-1"))
        if(len(email_addrs) > 2):
            logger.error("%s - Should not have more than 2 email addresses" %(email_addrs))
            return False
        return True
    except Exception,m:
        logger.warn("Couldn't sent mail To: %s Reason: %s" %  (', '.join(email_addrs),m))
        return False

def decide_expiring_action(expire_date):
    """Decide what action to take about this user, based on date, user
    info, calendar exceptions or other types of exceptions.
    Return  0: User has no expire date set or expire_date > (today + FIRST_WARNING)
           -1: User is expired and expire_date < (today - EXPIRING_THREASHOLD)
            1: User has come within FIRST_WARNING days limit of expire date
            2: User has come within SECOND_WARNING days limit of expire date
            3: User has become or will be expired within a short period.
            4: Normally return value 3 should be returned, but an
               exception is valid.
            5: Unexpected event.
            """
    if not expire_date:
        return 0
    dt = cereconf.USER_EXPIRE_CONF['EXPIRING_THREASHOLD']
    ret = 0
    # Special case 1: Is today within summer semester (24.06 - 08.08)?
    # It should really be from start of last week of june - end of
    # first week of august, but that is a bit troublesome...
    ss_start = mx.DateTime.DateTime(today.year, 6, 24)
    ss_end = mx.DateTime.DateTime(today.year, 8, 8)
    summer = False
    if today > ss_start and today < ss_end:
        summer = True
    #             t    t+dt        SEC           FIRST
    #-------------|-----|------------|--------------------|-------
    #  -1         |  3  |     2      |         1          |   0   
    if expire_date > (today + FIRST_WARNING):
        ret = 0 
    elif expire_date <= today:
        ret = -1 
    elif expire_date <= (today + FIRST_WARNING) and expire_date > (today + SECOND_WARNING):
        ret = 1 
    elif expire_date <= (today + SECOND_WARNING) and expire_date > (today + dt):
        ret = 2 
    elif expire_date <= (today + dt) and expire_date > today:
        ret = 3 
    else:
        ret = 5
    # This should only be done for students, and students don't have
    # expire date. Possible future feature    
    #if summer and ret == 3:
    #    ret = 4
    return ret
    
def check_users(cache_file):
    """Get all cerebrum users and check their expire date. If
    expire_date is soon or is passed take the neccessary actions as
    specified in user-expire.rst."""

    def get_expiring_data(row, expire_date):
        home = row.get(['home'])
        if not home:
            home = ''
        try:
            ou_name = get_ou_name(ou_id=row['ou_id'])
        except (KeyError, Errors.NotFoundError):
            ou_name = ''
        return {'account_id': int(row['account_id']),
                'home': home,
                'expire_date': expire_date,
                'ou': ou_name,
                'mail1': None,
                'mail2': None,
                'mail3': None}
        
    try:
        expiring_data = cPickle.load(file(cache_file))
    except IOError:
        logger.warn("Could not read expire data from cache file %s." %
                    cache_file)
        expiring_data = {} 
  
    logger.debug("Check expiring info for all user accounts")
    for row in ac.list_all(filter_expired=False):
        uname = row['entity_name']
        #logger.debug('*************** %s *******************' % uname)
        ea_nr = decide_expiring_action(row['expire_date'])
        # Check if users expire_date has been changed since last run
        if expiring_data.has_key(uname) and row['expire_date']:
            user_info = expiring_data[uname]
            new_ed = row['expire_date']
            old_ed = user_info['expire_date']
            if new_ed != old_ed:
                logger.info("Expire date for user %s changed. " % uname +
                            "Old date: %s, new date: %s" % (old_ed, new_ed))
                user_info['expire_date']=row['expire_date']
                # If expire date is changed user_info['mail<n>'] might need
                # to be updated 
                if ea_nr == 0:
                    if user_info['mail1'] or user_info['mail2'] or user_info['mail3']:
                        # Tell user that expire_date has been reset and account is
                        # out of expire-warning time range
                        send_mail(uname, user_info, 4) 
                    user_info['mail1'] = None
                # Do not send mail in these cases. It will be too many
                # mails which might confuse user, IMO.
                if ea_nr in (0, 1, 2):
                    user_info['mail3'] = None
                if ea_nr in (0, 1):
                    user_info['mail2'] = None
                
        # Check if we need to create or update expiring info for user
        if ea_nr == 0:      # User not within expire threat range 
            continue
        elif ea_nr == -1:   # User is expired
            if not expiring_data.has_key(uname):
                logger.debug("User %s is expired, but no expiring info exists." %
                             uname + " Do nothing.")
            continue
        expire_date = row['expire_date']
        if ea_nr == 1:      # User within threat range 1
            if not expiring_data.has_key(uname):
                logger.info("Writing expiring info for %s with expire date: %s" %
                             (uname, str(expire_date)))
                expiring_data[uname] = get_expiring_data(row, expire_date)
            if not expiring_data[uname]['mail1']:
                if send_mail(uname, expiring_data[uname], 1):
                    expiring_data[uname]['mail1'] = today
        elif ea_nr == 2:    # User within threat range 2
            if expiring_data.has_key(uname):
                if not expiring_data[uname]['mail1']:
                    logger.warn("%s expire_date - today <= %s, " % (uname, SECOND_WARNING) +
                                "but first warning mail was not sent")
            else:
                logger.warn("expire_date - today <= %s, but no expiring info" % (SECOND_WARNING) +
                            " exists for %s. Create info and send mail." % (uname))
                expiring_data[uname] = get_expiring_data(row, expire_date)
            if not expiring_data[uname]['mail2']:
                if send_mail(uname, expiring_data[uname], 2):
                    expiring_data[uname]['mail2'] = today           
        elif ea_nr == 3:    # User is about to expire
            if expiring_data.has_key(uname):
                if not expiring_data[uname]['mail1']:
                    logger.warn("%s: expire date reached, " % uname +
                                "but first warning mail was not sent")
                if not expiring_data[uname]['mail2']:
                    logger.warn("%s: expire date reached, " % uname +
                                "but second warning mail was not sent")
                if not expiring_data[uname]['mail3']:
                    if send_mail(uname, expiring_data[uname], 3, forward=True):
                        expiring_data[uname]['mail3'] = today
            else:
                logger.warn("User %s is about to expire, but no " % uname +
                            "expiring info exists. Create info and send mail.")
                expiring_data[uname] = get_expiring_data(row, expire_date)
                if send_mail(uname, expiring_data[uname], 3, forward=True):
                    expiring_data[uname]['mail3'] = today
        elif ea_nr == 4:    # Summer exception
            # User should normally be expired but an exception is at hand
            # Extend expire_date with two months 
            ac.expire_date += mx.DateTime.RelativeDateTime(months=+2)
            ac.write_db()
            if expiring_data.has_key(uname):
                #send_mail(uname, expiring_data[uname], 4, forward=True)
                if expiring_data[uname]['mail2']:
                    expiring_data[uname]['mail2'] = None
        elif ea_nr == 5:    # Error situation
            logger.error("None of the tests in check_users matched.\n" +
                         "user_info: %s" % str(row))
    # We are finished. Cache user data
    cPickle.dump(expiring_data, file(cache_file, 'w+'))


# FIXME, vi kan muligens fjerne denne og bruke rapporteringsverkt�yet
# for � lage denne oversikten i stedet.
def generate_info(cache_file, info_file):
    "Generate info about expired users and create a web page"
    try:
        expiring_data = cPickle.load(file(cache_file))
    except IOError:
        logger.error("Could not read expire data from cache file %s." %
                     cache_file + " Cannot generate info file. Quitting.")
        return
    has_expired = []
    got_mail2 = []
    will_expire = []
    for uname, user_info in expiring_data.items():
        # Find users that has expired last FIRST_WARNING days
        if user_info['mail1'] and ((user_info['expire_date'] + FIRST_WARNING) > today):
            has_expired.append((uname, user_info['home']))
        # Find users that has been sent mail2 during the last SECOND_WARNING days
        if user_info['mail2'] and ((user_info['mail2'] + SECOND_WARNING) > today):
            got_mail2.append((uname, user_info['home']))
        # Find users that will expire the next 5 days
        if (user_info['expire_date'] - 5) <= today:
            will_expire.append((uname, user_info['home']))

    # Get web page template
    web_tmplate = cereconf.TEMPLATE_DIR + "/" + cereconf.USER_EXPIRE_INFO_PAGE
    try:
        f = open(web_tmplate)
        web_txt = f.read()
        f.close()
    except AttributeError:
        logger.error("cereconf.py not set up correctly: "
                     "USER_EXPIRE_INFO_PAGE must be defined.")
        return
    except IOError:
        logger.error("Could not read web page template file %s" % web_template)
        return
    # generate text
    web_txt = web_txt.replace("${HAS_EXPIRED}",
                              '\n'.join([', '.join(x) for x in has_expired]))
    web_txt = web_txt.replace("${WILL_EXPIRE}",
                              '\n'.join([', '.join(x) for x in will_expire]))
    web_txt = web_txt.replace("${GOT_MAIL}",
                              '\n'.join([', '.join(x) for x in got_mail2]))
    # Write file
    try:
        f = open(info_file, 'w+')
        f.write(web_txt)
        f.close()
    except IOError:
        logger.error("Could not write to info file %s" % info_file)


def remove_duplicates(l):
    "Simple list uniqifier"
    tmp = []
    for x in l:
        if x and x not in tmp:
            tmp.append(x)
    return tmp


def get_ou_name(self, ou_id):
    ou.clear()
    ou.find(ou_id)
    return "%s (%02i%02i%02i)" % (ou.get_name_with_language(co.ou_name_short,
                                                            co.language_nb),
                                  ou.fakultet, ou.institutt,
                                  ou.avdeling)

def usage(exitcode=0,msg=""):
    if exitcode==-1:
        print "%s\n" % (msg)
    print __doc__
    sys.exit(exitcode)

def main():
    global logger_name, logger
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h?l:', [
            'help', 'cache=', 'generate-info='])
    except getopt.GetoptError,m:
        usage(-1,m)
    if not opts:
        usage(-1,"No arguments given")

    cache_file = info_file = None
    for opt, val in opts:
        if opt in ('--help','-h','-?'):
            usage()
        elif opt in ('--cache',):
            cache_file = val
        elif opt in ('--generate-info',):
            info_file = val
        elif opt in ('--logger_name','-l'):
            logger_name=val
        else:
            usage(-1)

    logger = Factory.get_logger(logger_name)
    if cache_file:
        check_users(cache_file)
    if info_file and cache_file:
        generate_info(cache_file, info_file)
        
if __name__ == '__main__':
    main()
    
