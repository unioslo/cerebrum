#!/usr/bin/env python2.2

import getopt
import sys
import os

import cereconf
from time import gmtime, strftime, time

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.templates.letters import TemplateHandler

db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)
all_passwords = {}
person_affiliations = {}
debug = 0

def bootstrap():
    global default_creator_id, default_expire_date, default_shell
    account = Factory.get('Account')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    default_expire_date = None
    default_shell = const.posix_shell_bash

def create_user(fnr, profile, reserve=0):
    logger.info2("CREATE")
    person = Person.Person(db)
    try:
        person.find_by_external_id(const.externalid_fodselsnr, fnr, const.system_fs)
    except Errors.NotFoundError:
        logger.warn("OUCH! person %s not found" % fnr)
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
    password = posix_user.make_passwd(uname)
    account.set_password(password)
    # TODO: må også lage brev-info fra profil (språk?)
    show_update('a', account.write_db())
    all_passwords[int(account.entity_id)] = [password, reserve]
    if not reserve:
        update_account(profile, [account.entity_id])
    return account.entity_id

def update_account(profile, account_ids, do_move=0, rem_grp=0, account_info={}):
    """Update the account by checking that group, disk and
    affiliations are correct.  For existing accounts, account_info
    should be filled with affiliation info """
    
    group = Group.Group(db)
    posix_user = PosixUser.PosixUser(db)
    person = Person.Person(db)
        
    for account_id in account_ids:
        logger.info2(" UPDATE:%s" % account_id)
        try:
            posix_user.find(account_id)
            # populate logic asserts that db-write is only done if needed
            disk = profile.get_disk(posix_user.disk_id)
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
        for r in group.list_groups_with_entity(account_id):
            if r['operation'] == const.group_memberop_union:
                already_member[int(r['group_id'])] = 1
        for g in profile.get_grupper():  # TODO: Vil antagelig være get_groups()
            if not already_member.get(g, 0):
                group.clear()
                group.find(g)
                group.add_member(account_id, const.entity_account,
                                 const.group_memberop_union)
            else:
                del(already_member[g])
        if rem_grp:
            for g in already_member.keys():
                if g in autostud.autogroups:
                    pass  # TODO:  studxonfig.xml should have the list...

        # Speedup: Only fetch person obj from DB if it is modified
        changed = 0
        paffs = person_affiliations.get(int(posix_user.owner_id), [])
        for ou_id in profile.get_stedkoder():
            try:
                idx = paffs.index((const.system_fs, ou_id, const.affiliation_student,
                                   const.affiliation_status_student_valid))
                del(paffs[idx])
            except ValueError:
                changed = 1
                pass
        if len(paffs) > 0:
            changed = 1
        if changed:
            person.find(posix_user.owner_id)
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
    if fast_test:
        return {}
    account = Account.Account(db)
    person = Person.Person(db)
    for p in person.list_affiliations(source_system=const.system_fs,
                                      affiliation=const.affiliation_student):
        person_affiliations.setdefault(int(p['person_id']), []).append(
            (int(p['source_system']), int(p['ou_id']), int(p['affiliation']), int(p['status'])))
    ret = {}
    logger.info("Finding student accounts...")
    pid2fnr = {}
    for p in person.list_external_ids(source_system=const.system_fs,
                                      id_type=const.externalid_fodselsnr):
        pid2fnr[int(p['person_id'])] = p['external_id']
    for a in account.list_accounts_by_type(affiliation=const.affiliation_student):
        if not pid2fnr.has_key(int(a['person_id'])):
            continue
        ret.setdefault(pid2fnr[int(a['person_id'])], {}).setdefault(
            int(a['account_id']), []).append([ int(a['ou_id']), int(a['affiliation']) ])
    logger.info(" found %i entires" % len(ret))
    return ret

def make_letters(data_file=None, type=None, range=None):
    if data_file is not None:  # Load info on letters to print from file
        f=open(data_file, 'r')
        tmp_passwords = pickle.load(f)
        f.close()
        for r in [int(x) for x in range.split(",")]:
            tmp = tmp_passwords["%s-%i" % (type, r)]
            tmp[1].append(r)
            all_passwords[tmp[0]] = tmp[1]
    person = Person.Person(db)
    account = Account.Account(db)
    dta = {}
    for account_id in all_passwords.keys():
        try:
            account.clear()
            account.find(account_id)
            person.clear()
            person.find(account.owner_id)  # should be account.owner_id
        except Errors.NotFoundError:
            logger.warn("NotFoundError for account_id=%s" % account_id)
            continue
        tpl = {}
        address = person.get_entity_address(source=const.system_fs,
                                            type=const.address_post)
        if address is None:
            logger.warn("Bad address for %s" % account_id)
            continue
        address = address[0]
        alines = address['address_text'].split("\n")+[""]
        tpl['address_line1'] = alines[0]
        tpl['address_line2'] = alines[1]
        tpl['address_line3'] = address['p_o_box']
        tpl['zip'] = address['postal_number']
        tpl['city'] = address['city']
        tpl['country'] = address['country']

        tpl['uname'] = account.account_name
        tpl['password'] =  all_passwords[account_id][0]
        tpl['fullname'] =  person.get_name(const.system_fs, const.name_full)
        tmp = person.get_external_id(id_type=const.externalid_fodselsnr,
                                     source_system=const.system_fs)
        tpl['birthno'] =  tmp[0]['external_id']
        tpl['emailadr'] =  "TODO"  # We probably don't need to support this...
        dta[account_id] = tpl

    keys = dta.keys()
    keys.sort(lambda x,y: cmp(dta[x]['zip'], dta[y]['zip']))
    letter_info = {}
    tmp = ('reservert', 'konto')
    if data_file is not None:
        tmp = (type,)
    for run_no in tmp:
        num = 1
        out = file("letter-%s.%i" % (run_no, time()), "w")
        if run_no == 'reservert':
            th = TemplateHandler('no', 'new_user', 'txt')
        else:
            th = TemplateHandler('no', 'new_user', 'txt')
        if th._hdr is not None:
            out.write(th._hdr)
        for k in keys:
            if all_passwords[k][1] != run_no:
                continue
            letter_info["%s-%i" % (run_no, num)] = [k, all_passwords[k]]
            if data_file is not None:
                dta[k]['lopenr'] = all_passwords[k][2]
            else:
                dta[k]['lopenr'] = num
            out.write(th.apply_template('body', dta[k]))
            num += 1
        if th._footer is not None:
            out.write(th._footer)
        out.close()
    # Save passwords for created users so that letters may be
    # re-printed at a later time in case of print-jam etc.
    if data_file is not None:
        f=open("letters.info", 'w')
        pickle.dump(letter_info, f)
        f.close()

def process_students_callback(person_info):
    fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                              int(person_info['personnr'])))
    logger.set_indent(0)
    logger.debug("Callback for %s" % fnr)
    logger.set_indent(3)
    logger.debug2(logger.pformat(person_info))
    try:
        profile = autostud.get_profile(person_info)
    except Errors.NotFoundError, msg:
        logger.warn("  Error for %s: %s" %  (fnr, msg))
        logger.set_indent(0)
        return
    if fast_test:
        logger.debug(profile.debug_dump())
        logger.set_indent(0)
        return
    try:
        logger.debug(" disk=%s, dfg=%s, fg=%s sko=%s" % \
                     (profile.get_disk(), profile.get_dfg(),
                      profile.get_grupper(),
                      profile.get_stedkoder()))
        if create_users and not students.has_key(fnr):
            account_id = create_user(fnr, profile)
            if account_id is None:
                logger.set_indent(0)
                return
            students.setdefault(fnr, []).append(account_id)
        if update_accounts and students.has_key(fnr):
            update_account(profile, students[fnr].keys(),
                           account_info=students[fnr])
    except ValueError, msg:  # TODO: Bad disk should throw a spesific class
        logger.error("  Error for %s: %s" % (fnr, msg))
    logger.set_indent(0)
    
def process_students():
    global autostud, students

    logger.info("process_students started")
    students = get_student_accounts()
    logger.info("got student accounts")
    autostud = AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file)
    logger.info("config processed")
    autostud.start_student_callbacks(student_info_file,
                                     process_students_callback)
    logger.set_indent(0)
    logger.info("student_info_file processed")
    db.commit()
    logger.info("making letters")
    make_letters()
    logger.info("process_students finished")

def main():
    opts, args = getopt.getopt(sys.argv[1:], 'dcus:C:',
                               ['debug', 'create-users', 'update-accounts',
                                'student-info-file=',
                                'studconfig-file=', 'fast-test',
                                'workdir', 'type', 'reprint'])

    global debug, fast_test, create_users, update_accounts, logger
    global student_info_file, studconfig_file
    
    update_accounts = create_users = 0
    fast_test = False
    workdir = None
    range = None
    bootstrap()
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('-c', '--create-users'):
            create_users = 1
        elif opt in ('-u', '--update-accounts'):
            update_accounts = 1
        elif opt in ('-s', '--student-info-file'):
            student_info_file = val
        elif opt in ('-C', '--studconfig-file'):
            studconfig_file = val
        elif opt in ('--fast-test',):  # Internal debug use ONLY!
            fast_test = True
        elif opt in ('--workdir',):
            workdir = val
        elif opt in ('--type',):
            type = val
        elif opt in ('--reprint',):
            range = val
        else:
            usage()
    if(not update_accounts and not create_users and range is None):
        usage()
    if workdir is None:
        workdir = "%s/ps-%s.%i" % (cereconf.AUTOADMIN_LOG_DIR,
                                   strftime("%Y-%m-%d", gmtime()), os.getpid())
        os.mkdir(workdir)
    os.chdir(workdir)
    logger = AutoStud.Util.ProgressReporter(
        "%s/run.log.%i" % (workdir, os.getpid()))
    if range is not None:
        make_letters("letters.info", type=type, range=val)
    else:
        process_students()
    
def usage():
    print """Usage: process_students.py -d | -c | -u
    -d | --debug: increases debug verbosity
    -c | -create-use : create new users
    -u | --update-accounts : update existing accounts
    -s | --student-info-file file:
    -C | --studconfig-file file:
    --workdir dir:  set workdir for --reprint
    --type type: set type for --reprint
    --reprint range:  Re-print letters in case of paper-jam etc.

./contrib/no/uio/process_students.py --fast-test -d -d -C ../uiocerebrum/etc/config/studconfig.xml -s ~/.usit.cerebrum.etc/fsprod/merged_info.xml -c

    """
    sys.exit(0)

if __name__ == '__main__':
    # AutoStud.AutoStud(db, debug=3, cfg_file="/home/runefro/usit/uiocerebrum/etc/config/studconfig.xml")

    main()
