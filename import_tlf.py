#! /bin/env python
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


#
# UiT specific extension to Cerebrum
#


progname = __file__.split("/")[-1]
__doc__ = """
    
    Usage: %s [options]
    Options are:
    -f | --file   : use this file as source for contact infodata.
                    default is user_yyyymmdd.txt in dumps/telefoni folder 
    -h | --help   : this text
    -d | --dryrun : do not change DB, default is do change DB.
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
import mx.DateTime
import datetime

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Utils import sendmail
from Cerebrum import Errors
from Cerebrum.modules.no.Stedkode import Stedkode
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
logger=Factory.get_logger("cronjob")


def str_upper_no(string, encoding='iso-8859-1'):
    '''Converts Norwegian iso strings to upper correctly. Eg. æøå -> ÆØÅ
    Ex. Usage: my_string = str_upper_no('aæeøå')'''
    return unicode(string, encoding).upper().encode(encoding)

def init_cache(checknames,checkmail):
    global uname2mail,uname2ownerid,person2contact,uname2expire,name_cache

    if checkmail:
        logger.info("Caching account email addresses")
        uname2mail = ac.getdict_uname2mailaddr(filter_expired=False)
    logger.info("Caching account owners")
    uname2ownerid=dict()
    uname2expire=dict()
    
    # for a in ac.search(expire_start=None,expire_stop=mx.DateTime.MaxDateTime):
    # KEB: replaced the above line with the line below as there is a problem with using 
    #      mx.DateTime.MaxDateTime on metius.
    for a in ac.search(expire_start=None,expire_stop=mx.DateTime.DateTime(datetime.MAXYEAR,12,31)):
        uname2ownerid[a['name']]=a['owner_id']
        uname2expire[a['name']]=a['expire_date']
    if checknames:
        logger.info("Caching person names")
        name_cache = p.getdict_persons_names(name_types=(co.name_first,
                                                         co.name_last,))
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

    p.clear()
    try:
        p.find(p_id)
    except Errors.NotFoundError,m:
        logger.error("User '%s' (ownerid=%s in cache) not found in database!" \
                     % (userid,ownerid))
        return

    for change in changes:
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
                if value !=cinfo.get(idx):
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
                cb_fname = str_upper_no(namelist.get(int(co.name_first),""))
                cb_lname = str_upper_no( namelist.get(int(co.name_last),""))
                if cb_fname != tlf_fname or cb_lname != tlf_lname:
                    s_errors.setdefault(userid, list()).append(
                        "Name spelling differ: yours=%s %s, ours=%s %s" %
                        (tlf_fname,tlf_lname,cb_fname,cb_lname))

    db_idx = set(cinfo.keys())
    src_idx= set(idxlist)
    for idx in db_idx-src_idx:
        changes.append(('del_contact', (idx,None)))
    
    if changes:
        logger.info("Changes [%s/%s]: %s" % (userid,ownerid,changes))
        handle_changes(ownerid,changes)
        logger.info("Update contact and write_db done")
    processed.append(ownerid)

def process_telefoni(filename,checknames,checkmail):
    reader=csv.reader(open(filename,'r'), delimiter=';')
    phonedata=dict()
    for row in reader:
        if row[RESERVATION].lower()=='kat' and row[USERID].strip():
            data = {'phone': row[PHONE],'mobile': row[MOB], 'room': row[ROOM],
                    'mail':row[MAIL], 'fax':row[FAX],'phone_2':row[PHONE_2],
                    'firstname': row[FNAME], 'lastname': row[LNAME],
                    'building': row[BUILDING]}
            phonedata.setdefault(row[USERID],list()).append(data)

    for userid,pdata in phonedata.items():
        process_contact(userid, pdata,checknames,checkmail)

    unprocessed = set(person2contact.keys()) - set(processed)
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

        notify_phoneadmin(mailmsg)


def notify_phoneadmin(msg):    
    recipient=cereconf.TELEFONIERRORS_RECEIVER
    sender=cereconf.SYSX_EMAIL_NOTFICATION_SENDER
    subject="Import telefoni errors from Cerebrum %s" % time.strftime("%Y%m%d")
    body=msg
    debug=dryrun    
    # finally, send the message    
    ret=sendmail(recipient,sender,subject,body,debug=debug)
    if debug:
        print "DRYRUN: mailmsg=\n%s" % ret

def usage(exitcode=0,msg=None):

    if msg:
        print msg
    print __doc__
    sys.exit(exitcode)


def main():
    global dryrun

    default_phonefile='%s/telefoni/user_%s.txt' % (cereconf.DUMPDIR,
                                                   time.strftime("%Y%m%d"))
    phonefile=dryrun=checknames=checkmail=False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dh?f:',
                                   ['help','dryrun','file','checknames','checkmail'])
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
    
    init_cache(checknames,checkmail)
    logger.info("Using sourcefile '%s'" % (phonefile or default_phonefile))
    process_telefoni(phonefile or default_phonefile,checknames,checkmail)

    if dryrun:
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Commited all changes")


if __name__=="__main__":
    main()
