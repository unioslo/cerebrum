#! /bin/env python
# -*- coding: utf-8 -*-
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


#
# UiT specific extension to Cerebrum
#

from __future__ import unicode_literals
progname = __file__.split("/")[-1]
__doc__ = """
    
    Usage: %s [options]
    Options are:
    -f | --file   : use this file as source for contact infodata.
                    default is user_yyyymmdd.txt in dumps/telefoni folder 
    -h | --help   : this text
    -d | --dryrun : do not change DB, default is do change DB.
    -F | --force : force write ignoring cereconf.MAX_NUM_ALLOWED_CHANGES
    -e | --no-email : do not notify cereconf.TELEFONIERRORS_RECEIVER with log messages
    --checknames  : turn on check of name spelling. default is off
    --logger-name=name   : use this logger, default is cronjob
    --logger-level=level : use this log level, default is debug
    

    This program imports data from the phone system and populates 
    entity_contact_info tables in Cerebrum.
    
""" % progname 

import sys
import time
import csv
import getopt
import csv
import datetime
import mx.DateTime
from sets import Set

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _SpreadCode


# CSV field positions
FNAME=0
LNAME=1
PHONE=2
FAX=3
MOB=4
PHONE_2=5
MAIL=6
USERID=7
ROOM=8
BUILDING=9
RESERVATION=10

db=Factory.get('Database')()
db.cl_init(change_program='import_tlf')
p=Factory.get('Person')(db)
co=Factory.get('Constants')(db)
ac=Factory.get('Account')(db)
ac_phone = Factory.get('Account')(db)
logger=Factory.get_logger("cronjob")
num_changes = 0
max_changes_allowed = int(cereconf.MAX_NUM_ALLOWED_CHANGES)
def str_upper_no(string, encoding='iso-8859-1'):
    '''Converts Norwegian iso strings to upper correctly. Eg. ��� -> ���
    Ex. Usage: my_string = str_upper_no('a�e��')'''
    return unicode(string, encoding).upper().encode(encoding)

def init_cache(checknames,checkmail):
    global uname2mail,uname2ownerid,person2contact,uname2expire,name_cache

    if checkmail:
        logger.info("Caching account email addresses")
        uname2mail = ac.getdict_uname2mailaddr(filter_expired=False)
    logger.info("Caching account owners")
    uname2ownerid=dict()
    uname2expire=dict()
    for a in ac.search(expire_start=None,expire_stop=mx.DateTime.DateTime(datetime.MAXYEAR,12,31)):
        uname2ownerid[a['name']]=a['owner_id']
        uname2expire[a['name']]=a['expire_date']
    if checknames:
        logger.info("Caching person names")
        name_cache = p.getdict_persons_names(name_types=(co.name_first, \
            co.name_last, co.name_work_title))
    logger.info("Caching contact info")
    person2contact=dict()
    for c in p.list_contact_info(source_system=co.system_tlf,
                                 entity_type=co.entity_person):
        idx= "%s:%s" % (c['contact_type'],c['contact_pref'])
        tmp = person2contact.get(c['entity_id'],dict())
        tmp[idx] = c['contact_value']
        person2contact[c['entity_id']]=tmp
    logger.info("Caching finished")


def handle_changes(p_id,changes):
    """ 
    process a change list of contact info for given person id.
    """
    global num_changes
    p.clear()
    try:
        p.find(p_id)
    except Errors.NotFoundError,m:
        logger.error("User '%s' (ownerid=%s in cache) not found in database!" \
                     % (userid,ownerid))
        return

    for change in changes:
        num_changes += 1
        chg_code=change[0]
        chg_val=change[1]
        idx,value=chg_val
        [type,pref]=[int(x) for x in idx.split(':')]
        if chg_code=='add_contact':
            #imitate an p.update_contact_info() 
            for c in p.get_contact_info(source=co.system_tlf,type=type):
                if pref==c['contact_pref']:
                    p.delete_contact_info(co.system_tlf,type,c['contact_pref'])
            p.add_contact_info(co.system_tlf, type, value=value, pref=pref)
            logger.debug("add: new: %d:%d:%d=%s" % (co.system_tlf,type,
                                                    pref,value))
        elif chg_code=='del_contact':
            #type,pref = chg_val.split(':')
            p.delete_contact_info(co.system_tlf, int(type), int(pref))
            logger.info("Delete %s, %s" % (chg_code,chg_val))
        else:
            logger.error("Unknown chg_code=%s, value=&s" % (chg_code,chg_val))
    op = p.write_db()


s_errors=dict()
processed = list()
def process_contact(userid,data,checknames,checkmail):
    global source_errors,processed,notify_queue 
    
    ownerid=uname2ownerid.get(userid,None)
    if ownerid is None:
        logger.error("UserID=%s not found in Cerebrum!?" % (userid))
        s_errors.setdefault(userid,list()).append("Account %s not found in BAS"\
            %userid ) 
        return

    if uname2expire.get(userid,mx.DateTime.today())<mx.DateTime.today():
        s_errors.setdefault(userid,list()).append( \
            "WARN: account %s expired %s in BAS"   \
            % (userid, uname2expire.get(userid).Format('%Y-%m-%d')))

    cinfo=person2contact.get(ownerid,dict())
    logger.debug("Process userid=%s (owner=%s) CBData=%s" % \
        (userid,ownerid,cinfo))

    changes=list()
    idxlist=list()
    contact_pref=0
    for item in data:
        contact_pref+=1
        phone=item['phone']
        phone_2=item['phone_2']
        mobile=item['mobile']
        mail=item['mail']
        fax=item['fax']
        room=item['room']
        tlf_fname=item['firstname']
        tlf_lname=item['lastname']
        building=item['building']
        
        #check contact info fields
        for value,type in ( (phone,int(co.contact_phone)),
                            (mobile,int(co.contact_mobile_phone)),
                            (fax,int(co.contact_fax)),
                            (phone_2,int(co.contact_workphone2)),
                            (room,int(co.contact_room)),
                            (building,int(co.contact_building))):
            idx="%s:%s" % (type,contact_pref)
            idxlist.append(idx)
            if value:
                if value != cinfo.get(idx):
                    if type == int(co.contact_phone): 
                        # only add contact_phone if it really is a new phone number
                        if is_new_number(value, ownerid):
                            changes.append(('add_contact',(idx,value)))
                    else:
                        changes.append(('add_contact',(idx,value)))
            else:
                if cinfo.get(idx):
                    changes.append(('del_contact',(idx,None)))
               
        # check if sourcesys has same mailaddr as we do
        if checkmail and mail and uname2mail.get(userid,"").lower()!=mail.lower():
            s_errors.setdefault(userid,list()).append( \
                "Email wrong: yours=%s, ours=%s" % (mail,
                                                    uname2mail.get(userid)))
        # check name spelling.
        if checknames:
            namelist= name_cache.get(ownerid,None)
            if namelist:  
                cb_fname = namelist.get(int(co.name_first),"")
                cb_lname = namelist.get(int(co.name_last),"")

                worktitle = namelist.get(int(co.name_work_title),"")
                if cb_fname != tlf_fname or cb_lname != tlf_lname:
                    s_errors.setdefault(userid,list()).append( \
                        "Name spelling differ: yours=%s %s, ours=%s %s" % \
                        (tlf_fname,tlf_lname,cb_fname,cb_lname))

    db_idx = Set(cinfo.keys())
    src_idx= Set(idxlist)
    for idx in db_idx-src_idx:
        changes.append(('del_contact', (idx,None)))
    
    if changes:
        logger.info("Changes [%s/%s]: %s" % (userid,ownerid,changes))
        handle_changes(ownerid,changes)
        logger.info("Update contact and write_db done")
    processed.append(ownerid)

#
# write back modified phonenr to database. Do not update the database
# if the phone/contact info already exists in the database
#
def update_phonenr(uid,phone):
    ac_phone.clear()
    try:
        ac_phone.find_by_name(uid)
    except:
        logger.error("unable to find user:%s. Continue with next user" % (uid))
        return
    logger.debug("writeback: uid: %s - %s" % (uid,phone))
    ac_phone.populate_contact_info(co.system_tlf,co.contact_phone,phone)
    ac_phone.write_db()
    

#
# Delete the (work) phonenumber for the given uid with source = telefoni
#
def delete_phonenr(uid,phone):
    ac_phone.clear()
    try:
        ac_phone.find_by_name(uid)
    except Errors.NotFoundError:
        logger.error("unable to find user:'%s' Continue with next user" %(uid))
        return
    logger.debug("%s has account id:%s" % (uid,ac_phone.entity_id))
    if(len(phone) == 5):
        # sanity check. only delete 5digit numbers
        logger.debug("deleting phonenumber:%s" % phone) 
        ac_phone.delete_contact_info(source=co.system_tlf,contact_type=co.contact_phone)
        ac_phone.write_db()
    else:
        logger.debug("Not deleting phonenumber: %s" % phone)

# 
# Returns true if this phonenumber is new for this ownerid
# (i.e. it is not registered to this ownerid in the database)
# 
# Note: Only checks for phonenumbers of type co.contact_phone.
# 
def is_new_number(phonenumber, ownerid):
    number_found = False
    is_new_number = False
    data_phone_len = len(phonenumber)

    if ownerid in person2contact.keys():
        for key, val in person2contact[ownerid].iteritems():
            contact_type = int(key[:3])

            if contact_type == int(co.contact_phone):
                num_to_compare = val

                if len(num_to_compare) > data_phone_len:
                    num_to_compare = num_to_compare[-data_phone_len:]

                if num_to_compare == phonenumber:
                    number_found = True

    if not number_found:
        is_new_number = True

    return is_new_number

def convert(input, encoding='utf-8'):
    if isinstance(input, dict):
        return {convert(key): convert(value, encoding) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [convert(element, encoding) for element in input]
    elif isinstance(input, bytes):
        #print "check:%s" %input
        #return unicode(input)
        #print "check2:%s" % input.encode("iso-8859-1")
        return input.decode(encoding)
    else:
        return input

def process_telefoni(filename,checknames,checkmail,notify_recipient):
    #
    # we will add a prefix to internal phone numbers based on their first digits.
    # and we will mark some numbers for deletion, also based on prefix.
    #
    prefix_table = [
        # (internal number first digits, prefix to add or "DELETE")
        ("207", "776"),
        ("208", "776"),
        ("209", "776"),
        ("231", "776"),
        ("232", "776"),
        ("233", "776"),
        ("251", "776"),
        ("252", "776"),
        ("26",  "DELETE"),
        ("27",  "DELETE"),
        ("28",  "DELETE"),
        ("44",  "776"),
        ("45",  "776"),
        ("46",  "776"),
        ("483", "776"),
        ("490", "776"),
        ("491", "776"),
        ("492", "776"),
        ("50",  "784"),
        ("505",  "784"),
        ("55",  "DELETE"),
        ("58",  "770"),
        ("602", "776"),
        ("603", "776"),
        ("604", "776"),
        ("605", "776"),
        ("606", "776"),
        ("607", "776"),
        ("608", "776"),
        ("609", "776"),
        ("62",  "769"),
        ("660", "769"),
        ("661", "769"),
        ("662", "769"),
        ("663", "769"),
        ("664", "769"),
        ("665", "769"),
        ("66",  "769"),
        ("69",  "DELETE"),
    ]

    reader=csv.reader(open(filename,'r'), delimiter=str(';'))
    phonedata=dict()


    for row in reader:
        # convert to unicode
        row = convert(row,'iso-8859-1')
        #print type(row)
        

        if row[RESERVATION].lower()=='kat' and row[USERID].strip():

            if row[USERID].strip() <> row[USERID]:
                logger.error("Userid %s has blanks in it - notify telefoni!" % (row[USERID]))
            data = {'phone': row[PHONE],'mobile': row[MOB], 'room': row[ROOM],
                    'mail':row[MAIL], 'fax':row[FAX],'phone_2':row[PHONE_2],
                    'firstname': row[FNAME], 'lastname': row[LNAME],
                    'building': row[BUILDING]}


            if row[USERID] not in uname2ownerid:
                logger.warn("Unknown user:%s, continue with next user" % row[USERID])
                continue

            #
            # Set phone extension or mark for deletion based on the first internal number's digits
            #
            added_prefix = False
            changed_phone = False
            for internal_first_digits, prefix in prefix_table:
                if len(data['phone']) == 5 and data['phone'].startswith(internal_first_digits):
                    if prefix == "DELETE":
                        logger.debug("DELETE: %s - %s" % (row[USERID], data['phone']))
                        # Delete the phonenumber from the database
                        delete_phonenr(row[USERID],data['phone'])
                    else:
                        logger.debug('unmodified phone:%s' % (data['phone']))
                        data['phone'] = "%s%s" % (prefix, data['phone'])
                        logger.debug('modified phone:%s' % (data['phone']))

                        if is_new_number(data['phone'], uname2ownerid[row[USERID]]):
                            changed_phone = True
                    added_prefix = True
                    break
            if (data['phone']) and (not added_prefix):
                logger.warning('Userid %s has a malformed internal phone number '
                               'or a number that does not have a match '
                               'in our number prefix table:%s' % (row[USERID], data))
                logger.debug("INVALID: %s - %s" % (row[USERID], data['phone']))

            # add "+47" phone number prefix
            if (data['phone']) and (is_new_number(data['phone'], uname2ownerid[row[USERID]])):
                changed_phone = True
                if not data['phone'].startswith('+47'):
                    data['phone'] = "%s%s" % ("+47", data['phone'])
                logger.debug("%s's phone number with +47 prefix: %s" % (row[USERID], data['phone']))

            if changed_phone:
                update_phonenr(row[USERID], data['phone'])
            phonedata.setdefault(row[USERID].strip(),list()).append(data)

    for userid,pdata in phonedata.items():
        process_contact(userid, pdata,checknames,checkmail)

    unprocessed = Set(person2contact.keys()) - Set(processed)
    for p_id in unprocessed:
        changes=list()
        contact_info=person2contact[p_id]
        for idx,value in contact_info.items():
            changes.append(('del_contact',(idx,None)))
        logger.debug("person(id=%s) not in srcdata, changes=%s" % (p_id,changes))
        handle_changes(p_id,changes)
    
    if s_errors:
        msg=dict()
        for userid, error in s_errors.items():
            fname = phonedata[userid][0]['firstname']
            lname = phonedata[userid][0]['lastname']
            key = '%s %s (%s)' % (fname,lname,userid)
            msg[key] = list()
            for i in error:
                msg[key].append("\t%s\n" % (i,))

        keys = msg.keys()
        keys.sort()
        mailmsg=""
        for k in keys:
            mailmsg+=k+'\n'
            for i in msg[k]:
                mailmsg+=i

        notify_phoneadmin(mailmsg,notify_recipient)


def notify_phoneadmin(msg,notify_recipient):    
    recipient=cereconf.TELEFONIERRORS_RECEIVER
    sender=cereconf.SYSX_EMAIL_NOTFICATION_SENDER
    subject="Import telefoni errors from Cerebrum %s" % time.strftime("%Y%m%d")
    body=msg
    debug=dryrun    
    ret =''
    # finally, send the message    
    if notify_recipient == True:
        ret=sendmail(recipient,sender,subject,body,debug=debug)
    else:
        logger.warn("do NOT notify phoneadmin with email")
    if debug:
        print "DRYRUN: mailmsg=\n%s" % ret

def usage(exitcode=0,msg=None):

    if msg:
        print msg
    print __doc__
    sys.exit(exitcode)


def main():
    global dryrun
    force = False
    notify_recipient = True
    default_phonefile='%s/telefoni/user_%s.txt' % (cereconf.DUMPDIR,
                                                   time.strftime("%Y%m%d"))
    phonefile=dryrun=checknames=checkmail=False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dh?f:Fe',
                                   ['help','dryrun','file','checknames','checkmail','force','no-email'])
    except getopt.GetoptError,m:
        usage(1,m)

    for opt, val in opts:
        if opt in ['-h', '-?','--help']:
            usage(0)
        elif opt in ['--dryrun','-d']:
            dryrun=True
        elif opt in ['--checknames']:
            checknames=True
        elif opt in ['--checkmail']:
            checkmail=True
        elif opt in ['-f', '--file']:
            phonefile=val
        elif opt in ['-F','--force']:
            force = True
        elif opt in ['-e','--no-email']:
            notify_recipient = False

    init_cache(checknames,checkmail)
    logger.info("Using sourcefile '%s'" % (phonefile or default_phonefile))
    process_telefoni(phonefile or default_phonefile,checknames,checkmail,notify_recipient)
    logger.debug("Max number of allowed changes:%s" % (max_changes_allowed))
    logger.debug("Number of changes:%s" % num_changes)
    if dryrun:
        db.rollback()
        logger.info("Dryrun, rollback changes")
    
    else:
        if ((force == False) and (num_changes <= max_changes_allowed)):
            db.commit()
            logger.info("Commited all changes")
        elif ((num_changes > max_changes_allowed) and (force == False)):
            db.rollback()
            logger.error("too many changes:%s. rollback" % (num_changes))
        elif(force == True):
            db.commit()
            logger.warning("Forced writing: %s changes in phone processing")

if __name__=="__main__":
    main()
