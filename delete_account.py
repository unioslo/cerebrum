#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
import getopt
import cerebrum_path
from Cerebrum.Utils import Factory

class delete:
    def delete_account(self,db,account_id,target_id=None):

        delete_tables=[]
        delete_tables.append({'entity_name':'entity_id'})
        delete_tables.append({'account_home':'account_id'})
        delete_tables.append({'account_type':'account_id'})
        delete_tables.append({'account_authentication':'account_id'})
        delete_tables.append({'posix_user':'account_id'})
        delete_tables.append({'homedir':'account_id'})
        delete_tables.append({'account_info':'account_id'})
        delete_tables.append({'group_member':'member_id'})
        delete_tables.append({'entity_spread':'entity_id'})

        delete_mail_tables=[]
        delete_mail_tables.append({'email_target_server':'target_id'})
        delete_mail_tables.append({'email_primary_address':'target_id'})
        delete_mail_tables.append({'email_address':'target_id'})
        delete_mail_tables.append({'email_target':'target_id'})

        for entry in delete_tables:
            value = entry.values()
            key= entry.keys()
            query="delete from %s where %s =%s"% (key[0],value[0],account_id)
            print "query=%s" % query
            try:
                db.query(query)
            except:
                print "error deleting account for account_id: %s" % account_id


        if target_id !=None:
            for delete_mail_entry in delete_mail_tables:
                value = delete_mail_entry .values()
                key = delete_mail_entry.keys()
                query="delete from %s where %s =%s" % (key[0],value[0],target_id)
                print "query=%s" % query
                try:
                    db.query(query)
                except:
                    print "error deleting email_data for account_id: %s" % account_id
            #query = "delete from %s where entity_id"
        #query="delete from entity_name where entity_id=%s" % account_id
        #res = db.query(query)
    #else:
    #    query=""


def main():
    db = Factory.get("Database")()
    execute = delete()
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:a:',['file=','account_id='])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    
    account_file=0
    account_id = 0
    for opt,val in opts:
        if opt in('-f','--file'):
            account_file = val
        if opt in('-a','--account_id'):
            account_id = val

    if (account_file == 0 and account_id == 0):
        usage()
        sys.exit(1)
    else:
        if (account_file != 0):
            print "account_file = %s" % account_file
            file_handle = open(account_file,"r")
        elif (account_id != 0):
            file_handle = []
            file_handle.append(account_id)
            
        for line in file_handle:
            if(line[0] != '\n'):
                account_id = line
                query ="select target_id from email_target where entity_id=%s" % account_id
                print "query =%s " % query
                try:
                    db_row=db.query_1(query)
                except:
                    print "error collecting target_id for account_id. only deleting account info" % account_id
                    res = delete_account(db,account_id)
                    continue

                target_id = db_row
                res = execute.delete_account(db,account_id,target_id)
    db.commit()
                
                


def usage():
    print """
    -f | --file       : reads a file containing the account_id of all accounts
                        to delete. 1 account_id on each line.
    -a | --account_id : reads account id from command lina and deletes only this account
                        and its related email info

    """
if __name__ == '__main__':
    main()

# arch-tag: c32eed0e-b431-11da-8813-60271a4aff4f
