#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
import getopt
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Utils import Factory
import cereconf

class delete:
    def delete_account(self, db, account_id, target_id=None, dryrun=False):
        mailto_rt = False
        mailto_ad = False
        replacement_username = ""


        ac = Factory.get('Account')(db)
        ac.find(account_id)
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
        legacy_info['comment'] = '%s - Deleted by delete_account.py script.' % (cereconf._TODAY) # Will try to get primary account for SSN later on...
        legacy_info['name'] = pe.get_name(co.system_cached, co.name_full)

        try:
            for spread in ac.get_spread():
                if spread['spread'] == co.spread_uit_ad_account:
                    mailto_ad = True
                    break
        except:
            pass
        

        delete_tables=[]
        delete_tables.append({'entity_name':'entity_id'})
        delete_tables.append({'account_home':'account_id'})
        delete_tables.append({'account_type':'account_id'})
        delete_tables.append({'account_authentication':'account_id'})
        delete_tables.append({'posix_user':'account_id'})
        delete_tables.append({'homedir':'account_id'})
        delete_tables.append({'group_member':'member_id'})
        delete_tables.append({'account_info':'account_id'})
        delete_tables.append({'entity_spread':'entity_id'})
        delete_tables.append({'entity_quarantine':'entity_id'})
        delete_tables.append({'entity_trait':'entity_id'})
        delete_tables.append({'entity_info':'entity_id'})

        delete_mail_tables=[]

        delete_mail_tables.append({'email_primary_address':'target_id'})
        delete_mail_tables.append({'email_address':'target_id'})
        delete_mail_tables.append({'email_target':'target_id'})

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

        for entry in delete_tables:
            value = entry.values()
            key= entry.keys()
            query="delete from %s where %s =%s"% (key[0],value[0],account_id)
            print "query=%s" % query
            try:
                db.query(query)
            except:
                print "error deleting account for account_id: %s" % account_id

        # Done deleting, now writing legacy info after trying to find (new) primary account for person
        try:
            ac.clear()
            aux = pe.entity_id
            pe.clear()
            pe.find(aux)
            aux = pe.get_accounts(filter_expired=False)[0]['account_id']
            ac.find(aux)
            legacy_info['comment'] = '%s - Duplicate of %s' % (cereconf._TODAY, ac.account_name)
            mailto_rt = True
        except:
            print "Could not find primary account"
            
        try:
            query = "insert into legacy_users values ('%s', '%s', '%s', '%s', '%s', '%s')" % (legacy_info['user_name'],
                                                                                              legacy_info['ssn'],
                                                                                              legacy_info['source'],
                                                                                              legacy_info['type'],
                                                                                              legacy_info['comment'],
                                                                                              legacy_info['name'])
            print "query=%s\n" % query
            db.query(query)
        except:
            print "Could not write to legacy_users. Username is probably already reserved.\n"


        # Sending email to SUT queue in RT if necessary
        if mailto_rt and not dryrun:
            account_expired = '';
            if ac.is_expired():
                account_expired = ' Imidlertid vil ikke den korrekte kontoen bli reaktivert før i morgen.'

            
            Utils.sendmail('sut@rt.uit.no', #TO
                           'bas-admin@cc.uit.no', #SENDER
                           'Brukernavn slettet', #TITLE
                           'Brukernavnet %s skal erstattes av %s. Videresend e-post, flytt filer, e-post, osv. fra %s til %s.%s' %
                              (legacy_info['user_name'], ac.account_name, legacy_info['user_name'], ac.account_name, account_expired), #BODY
                           cc=None,
                           charset='iso-8859-1',
                           debug=False)
            print "mail sent to sut@rt.uit.no\n"
                 
        # Sending email to AD nybrukere if necessary
        if mailto_ad and not dryrun:

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
        opts,args = getopt.getopt(sys.argv[1:],'f:d',['file=','dryrun'])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    
    account_file=0
    dryrun = False
    for opt,val in opts:
        if opt in('-f','--file'):
            account_file = val
        elif opt in('-d', '--dryrun'):
            dryrun = True

    if account_file == 0:
        usage()
        sys.exit(1)
    else:
        print "account_file = %s" % account_file
        file_handle = open(account_file,"r")
        for line in file_handle:
            if(line[0] != '\n'):
                foo=line.split(",")
                #print "foo=%s" % foo
                account_id = foo[0]
                print "ac=%s" % account_id
                query ="select target_id from email_target where entity_id=%s" % account_id
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
    -d | --dryrun:roll back changes in the end
                  """
if __name__ == '__main__':
    main()

