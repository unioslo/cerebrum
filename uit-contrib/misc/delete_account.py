#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
import time
import getopt
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Utils import Factory
import cereconf
from Cerebrum import Errors
from Cerebrum.modules.legacy_users import LegacyUsers


class delete:
    def delete_account(self, db, account_id, target_id=None, dryrun=False):
        mailto_rt = False
        mailto_ad = False
        replacement_username = ""
        print "processing acocunt:%s" % account_id

        ac = Factory.get('Account')(db)
        lu = LegacyUsers(db)
        try:
            ac.find(account_id)
        except Errors.NotFoundError,m:
            print "error:%s unable to find account:%s" %(m,account_id)
            return
        pe = Factory.get('Person')(db)
        pe.find(ac.owner_id)
        co = Factory.get('Constants')(db)

        legacy_info = {}
        legacy_info['user_name'] = ac.account_name
        try:
            legacy_info['ssn'] = pe.get_external_id(id_type=co.externalid_fodselsnr)[0]['external_id']
        except:
            legacy_info['ssn'] = None
        legacy_info['source'] = 'MANUELL'
        legacy_info['type'] = 'P'
        legacy_info['comment'] = '%s - Deleted by delete_account.py script.' % (time.strftime('%Y%m%d')) # Will try to get primary account for SSN later on...
        legacy_info['name'] = pe.get_name(co.system_cached, co.name_full)

        try:
            for spread in ac.get_spread():
                if spread['spread'] == co.spread_uit_ad_account:
                    mailto_ad = True
                    break
        except:
            pass
        
        # need to delete any entries in bofhd_session_state
        # for this account_id before deleting other things
        query = "select session_id from bofhd_session where account_id = %s" % account_id
        session_ids = db.query(query)
        if len(session_ids) > 0:
            for s_id in session_ids:
                query = "delete from bofhd_session_state where session_id = '%s'" % s_id['session_id']
                print "query= %s" % query
                try:
                    db.query(query)
                except:
                    print "error deleting bofhd_session_state data for account_id: %s" % account_id
                    sys.exit()

        delete_tables=[]
        try:
            delete_tables.append({'change_log': 'change_by'})
            delete_tables.append({'entity_name':'entity_id'})
            delete_tables.append({'account_home':'account_id'})
            delete_tables.append({'account_type':'account_id'})
            delete_tables.append({'account_authentication':'account_id'})
            delete_tables.append({'posix_user':'account_id'})
            delete_tables.append({'homedir':'account_id'})
            delete_tables.append({'group_member':'member_id'})
            delete_tables.append({'bofhd_session':'account_id'})
            delete_tables.append({'account_info':'account_id'})
            delete_tables.append({'spread_expire':'entity_id'})
            delete_tables.append({'entity_spread':'entity_id'})
            delete_tables.append({'entity_quarantine':'entity_id'})
            delete_tables.append({'entity_trait':'entity_id'})
            delete_tables.append({'entity_contact_info' : 'entity_id'})
            delete_tables.append({'entity_info':'entity_id'})
            delete_tables.append({'entity_contact_info':'entity_id'})
            
            delete_mail_tables=[]
            delete_mail_tables.append({'mailq':'entity_id'})
            delete_mail_tables.append({'email_forward':'target_id'})
            delete_mail_tables.append({'email_primary_address':'target_id'})
            delete_mail_tables.append({'email_address':'target_id'})
            delete_mail_tables.append({'email_target':'target_id'})
        except Errors.NotFoundError,m:
            print "ERROR:%s unable to delete entry." % m
        if target_id !=None:
            for delete_mail_entry in delete_mail_tables:
                value = delete_mail_entry.values()
                key = delete_mail_entry.keys()
                query="delete from %s where %s =%s" % (key[0],value[0],target_id)
                print "query=%s" % query
                try:
                    db.query(query)
                except:
                    print "error deleting email_data for account_id: %s" % account_id
                    sys.exit()

        for entry in delete_tables:
            value = entry.values()
            key= entry.keys()
            query="delete from %s where %s =%s"% (key[0],value[0],account_id)
            print "query=%s" % query
            try:
                db.query(query)
            except:
                print "error deleting account for account_id: %s" % account_id
                sys.exit()

        # Done deleting, now writing legacy info after trying to find (new) primary account for person
        try:
            ac.clear()
            aux = pe.entity_id
            pe.clear()
            pe.find(aux)
            aux = pe.get_accounts(filter_expired=False)[0]['account_id']
            ac.find(aux)
            legacy_info['comment'] = '%s - Duplicate of %s' % (time.strftime('%Y%m%d'), ac.account_name)
            mailto_rt = True
        except:
            print "Could not find primary account"
            
        try:
            lu.set(**legacy_info)
            print("Updated legacy table\n")
        except Exception as m:
            print("Could not write to legacy_users: %s\n" % m)
            sys.exit(1)

        # Sending email to SUT queue in RT if necessary
        if mailto_rt and not dryrun:
            account_expired = '';
            if ac.is_expired():
                account_expired = ' Imidlertid vil ikke den korrekte kontoen bli reaktivert før i morgen.'

            
#            Utils.sendmail('star-gru@orakel.uit.no', #TO
#                          'bas-admin@cc.uit.no', #SENDER
#                           'Brukernavn slettet (%s erstattes av %s)' % (legacy_info['user_name'], ac.account_name), #TITLE
#                          'Brukernavnet %s skal erstattes av %s. Videresend e-post, flytt filer, e-post, osv. fra %s til %s.%s' %
#                            (legacy_info['user_name'], ac.account_name, legacy_info['user_name'], ac.account_name, account_expired), #BODY
#                        cc=None,
#                       charset='iso-8859-1',
#                      debug=False)
#      print "mail sent to star-gru@orakel.uit.no\n"


        # Sending email to Portal queue in RT if necessary
        if False and mailto_rt and not dryrun:
            account_expired = '';
            if ac.is_expired():
                account_expired = ' Imidlertid vil ikke den korrekte kontoen bli reaktivert før i morgen.'


            Utils.sendmail('vevportal@rt.uit.no', #TO
                           'bas-admin@cc.uit.no', #SENDER
                           'Brukernavn slettet (%s erstattes av %s)' % (legacy_info['user_name'], ac.account_name), #TITLE
                           'Brukernavnet %s skal erstattes av %s.' %
                              (legacy_info['user_name'], ac.account_name), #BODY
                           cc=None,
                           charset='iso-8859-1',
                           debug=False)
            print "mail sent to vevportal@rt.uit.no\n"

                 
        # Sending email to AD nybrukere if necessary
        if False and mailto_ad and not dryrun:

            # Inform about new username, if new username has AD spread
            riktig_brukernavn = ''
            if mailto_rt:
                try:
                    for spread in ac.get_spread():
                        if spread['spread'] == co.spread_uit_ad_account:
                            riktig_brukernavn = ' Riktig brukernavn er %s.' % (ac.account_name)
                            if ac.is_expired():
                                riktig_brukernavn += ' Imidlertid vil ikke den korrekte kontoen bli reaktivert før i morgen.'
                            break
                except:
                    print "Fant ikke AD spread på primary (riktig) account."
                    pass                
                
            Utils.sendmail('nybruker2@asp.uit.no', #TO
                           'bas-admin@cc.uit.no', #SENDER
                           'Brukernavn slettet', #TITLE
                           'Brukernavnet %s er slettet i BAS.%s' %
                              (legacy_info['user_name'], riktig_brukernavn), #BODY
                           cc=None,
                           charset='iso-8859-1',
                           debug=False)
            print "mail sent to nybruker2@asp.uit.no\n"

       

def main():
    db = Factory.get("Database")()
    execute = delete()
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:a:d',['file=', 'account=','dryrun'])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    
    account_file=0
    account_id = None
    dryrun = False
    for opt,val in opts:
        if opt in('-f','--file'):
            account_file = val
        elif opt in('-a','--account'):
            account_id = val
        elif opt in('-d', '--dryrun'):
            dryrun = True

    if account_file == 0 and account_id is None:
        usage()
        sys.exit(1)

    if account_id is not None:
        print "processing single account %s" % account_id
        accounts = [account_id, ]
    else:
       print "account_file = %s" % account_file
       accounts = open(account_file,"r")


    for line in accounts:
        if(line[0] != '\n'):
            line = line.strip()
            foo=line.split(",")
            #print "foo=%s" % foo
            account_id = foo[0]
            print "ac=%s" % account_id
            query ="select target_id from email_target where target_entity_id=%s" % account_id
            print "query =%s " % query
            try:
                db_row=db.query_1(query)
            except:
                print "error collecting target_id for account_id:%s. only deleting account info" % account_id
                res = execute.delete_account(db, account_id=account_id, dryrun=dryrun)
                continue

            target_id = db_row
            res = execute.delete_account(db, account_id, target_id, dryrun)

    
    if dryrun:
        print "Rollback changes"
        db.rollback()
    else:
        print "Commit changes"
        db.commit()
        #db.rollback()
        


def usage():
    print """
    -f | --file : reads a file containing the account_id of all accounts
                  to delete. 1 account_id on each line.
    -A | --affiliation : transfer account affiliation from deleted account to other account if it exists.
    -a | --account: entity_id of account to delete from command line
    -d | --dryrun:roll back changes in the end
                  """
if __name__ == '__main__':
    main()

