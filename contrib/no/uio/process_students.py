#!/usr/bin/env python2.2

import getopt
import sys
import cereconf
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud

import pprint
pp = pprint.PrettyPrinter(indent=4)

db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)

debug = 0

def bootstrap():
    global default_creator_id, default_expire_date, default_shell
    account = Factory.get('Account')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    default_expire_date = None
    default_shell = const.posix_shell_bash

def create_user(fnr, profile, reserve=0):
    print " CREATE", 
    person = Person.Person(db)
    try:
        person.find_by_external_id(const.externalid_fodselsnr, fnr, const.system_fs)
    except Errors.NotFoundError:
        print "OUCH! person %s not found" % fnr
        return None
    posix_user = PosixUser.PosixUser(db)
    full_name = person.get_name(const.system_fs, const.name_full)
    first_name, last_name = full_name.split(" ", 1) # TODO: fs-import bør lagre begge navn
    uname = posix_user.suggest_unames(const.account_namespace,
                                      first_name, last_name)[0]
    account = Factory.get('Account')(db)
    account.populate(uname,
                     const.entity_person,
                     person.entity_id,
                     None,
                     default_creator_id, default_expire_date)
    # TODO: Brukernavn + passord må lagres slik at vi kan lage passord ark
    password = posix_user.make_passwd(uname)
    account.set_password(password)
    show_update('a', account.write_db())
    if not reserve:
        update_account(profile, [account.entity_id])
    return account.entity_id

def update_account(profile, account_ids, do_move=0, rem_grp=0, account_info={}):
    """Update the account by checking that group, disk and
    affiliations are correct.  For existing accounts, account_info
    should be filled with affiliation info """
    
    account = Account.Account(db)
    group = Group.Group(db)
    posix_user = PosixUser.PosixUser(db)
    person = Person.Person(db)
        
    for account_id in account_ids:
        print " UPDATE:%s" % account_id,
        account.clear()
        account.find(account_id)
        person.find(account.owner_id)
        try:
            posix_user.find(account_id)
            # populate logic asserts that db-write is only done if needed
            disk = profile.get_disk()
            if posix_user.disk_id <> disk:
                profile.notify_used_disk(old=posix_user.disk_id, new=disk)
                posix_user.disk_id = disk
            posix_user.gid = profile.get_dfg()
            show_update('u', posix_user.write_db())
        except Errors.NotFoundError:
            disk_id=profile.get_disk()
            profile.notify_used_disk(old=None, new=disk_id)
            uid = posix_user.get_free_uid()
            gid = profile.get_dfg()
            shell = default_shell
            posix_user.populate(uid, gid, None, shell, disk_id=disk_id,
                                parent=account_id)
            show_update('U', posix_user.write_db())
        already_member = {}
        for r in group.list_groups_with_entity(account.entity_id):
            if r['operation'] == const.group_memberop_union:
                already_member[int(r['group_id'])] = 1
        for g in profile.get_filgrupper():  # TODO: Vil antagelig være get_groups()
            if not already_member.get(g, 0):
                group.clear()
                group.find(g)
                group.add_member(account.entity_id, account.entity_type,
                                 const.group_memberop_union)
            else:
                del(already_member[g])
        if rem_grp:
            for g in already_member.keys():
                if g in autostud.autogroups:
                    pass  # TODO:  studxonfig.xml should have the list...
        for ou_id in profile.get_stedkoder():
            person.populate_affiliation(const.system_fs, ou_id, const.affiliation_student,
                                        const.affiliation_status_student_valid)
        show_update('p', person.write_db())
        for ou_id in profile.get_stedkoder():
            has = 0
            for has_ou, has_aff in account_info.get(account_id, []):
                if has_ou == ou_id and has_aff == const.affiliation_student:
                    has = 1
            if not has:
                posix_user.add_account_type(person.entity_id, ou_id, const.affiliation_student)
        # TODO: update default e-mail address
        # TODO: spread

def get_student_accounts():
    account = Account.Account(db)
    person = Person.Person(db)
    ret = {}
    for a in account.list_accounts_by_type(affiliation=const.affiliation_student):
        person.clear()
        person.find(a['person_id'])
        for it, ss, eid in person.get_external_id(id_type=const.externalid_fodselsnr):
            eid = fodselsnr.personnr_ok(eid)
            ret.setdefault(eid, {}).setdefault(int(a['account_id']), []).append([ int(a['ou_id']), int(a['affiliation']) ])
    return ret

def show_update(char, func_ret):
    if func_ret is None:
        print "%s=" % char,
    elif func_ret:
        print "%s+" % char,
    else:
        print "%sM" % char,

    

def process_students(update_accounts=0, create_users=0):
    students = get_student_accounts()
    global autostud
    autostud = AutoStud.AutoStud(db, debug=debug)

    # First process active students
    for t in autostud.get_topics_list(topics_file=topics_file):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(t[0]['fodselsdato']),
                                                  int(t[0]['personnr'])))
        if debug:
            print "%s" % fnr,
        try:
            profile = autostud.get_profile(t)
        except Errors.NotFoundError, msg:
            print "  Error for %s: %s" %  (fnr, msg)
            continue
        if debug:
            print " disk=%s, dfg=%s, def_sko=%s, fg=%s sko=%s" % \
                  (profile._disk, profile.get_dfg(),
                  profile.get_email_sko(), profile.get_filgrupper(),
                  profile.get_stedkoder())
        try:
            if create_users and not students.has_key(fnr):
                students.setdefault(fnr, []).append(create_user(fnr, profile))
            elif update_account and students.has_key(fnr):
                update_account(profile, students[fnr].keys(), account_info=students[fnr])
            if debug:
                print
        except ValueError, msg:  # TODO: Bad disk should throw a spesific class
            print "  Error for %s: %s" % (fnr, msg)
    db.commit()
    return
    # Deretter de som bare har et gyldig opptak
    for s in autostud.get_studprog_students():
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(s[0]['fodselsdato']),
                                                  int(s[0]['personnr'])))
        if create_users and not students.has_key(fnr):
            try:
                create_user(fnr, profile, reserve=1)
            except ValueError, msg:  # TODO: Bad disk should throw a spesific class
                print "Error for %s: %s" % (fnr, msg)
            
def main():
    opts, args = getopt.getopt(sys.argv[1:], 'dcut:',
                               ['debug', 'create-users', 'update-accounts', 'topics_file='])
    global debug, topics_file
    update_accounts = create_users = 0
    topics_file = None
    bootstrap()
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('-c', '--create-users'):
            create_users = 1
        elif opt in ('-u', '--update-accounts'):
            update_accounts = 1
        elif opt in ('-t', '--topics-file'):
            topics_file = val
        else:
            usage()
    if(not update_accounts and not create_users):
        usage()
    process_students(update_accounts, create_users)
    
def usage():
    print """Usage: process_students.py -d | -c | -u
    -d | --debug: increases debug verbosity
    -c | -create-use : create new users
    -u | --update-accounts : update existing accounts
    """
    sys.exit(0)

if __name__ == '__main__':
    main()
