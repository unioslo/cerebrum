import operator
import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum import Errors


db = Factory.get("Database")()
db.cl_init(change_program ='fix_homedir')
account = Factory.get("Account")(db)
oneAccount = Factory.get("Account")(db)
const = Factory.get("Constants")(db)

spreads_to_set = [13,9]  # 13= NIS_user@uit og 11=LDAP_person , 9 = IMAPuser elns
        
def get_all_accounts(account):
    return account.list()


def get_homedir_id(objAccount,spread):
    # sjekk om denne konto id har en konto for denne spread,
    # hvis ja, returner homedir_id
    # hvis nei returner None
    ret = None
    try:
        home = objAccount.get_home(spread)
        if (len(home)>0):
            ret = home['homedir_id']
    except Errors.NotFoundError:
        pass

    return ret

def set_home_dir(objAccount,spread):
    print "Calling set_home_dir with account %s %s" % (objAccount.account_name,spread)
    path_prefix = "/its/home"
    homeid = get_homedir_id(objAccount,spread)
    account_name = objAccount.account_name
    homepath = ('%s/%s/%s/%s') % (path_prefix,account_name[0],account_name[0:2],account_name)
    print "setting %s as home path for %s on homedir_id='%s', spread=%d" % (homepath,account_name,homeid,spread)
    newid = -1
    if (homeid == None):
        print "Inserting new homedir_id"
        newid = objAccount.set_homedir(home=homepath,status=const.home_status_not_created)
    else:
        print "Updating homedir_id=%s" % (homeid)
        newid = objAccount.set_homedir(current_id=homeid,home=homepath,status=const.home_status_not_created)
        newid = homeid

    print "Homedir_id before='%s' and after='%s'" % (homeid, newid)
    # update homedir for the spread
    objAccount.set_home(spread,newid)    
    


def updateOneAccount(account_id):
    oneAccount.clear()
    print "\nWorking on account_id=%d" % (account_id)
    oneAccount.find(account_id)
    for s in spreads_to_set:   # for hvert spread vi skal sette
        if (oneAccount.has_spread(s)): # har denne kontoen dette spread?
            set_home_dir(oneAccount,s)   # sett hjemmekatalog for denne kontoen og dette spread

                                                    
   

def main(aid = None):
    if (aid == None):
        accounts = get_all_accounts(account)
        i = 0
        for a in accounts:  # spring gjennom gjennom alle kontoer
            i += 1
            updateOneAccount(a['account_id'])
            if (operator.mod(i,1000) == 0):
                print "Committing after %i" % (i)
                db.commit()
    else:
        updateOneAccount(aid)
    
    db.commit()


if __name__ == '__main__':
    main()
    #main(110643)
#    main(1626)
                
 
# arch-tag: 40f1a58e-b42c-11da-994d-6a4c888f0a6f
