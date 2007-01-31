import getopt
import string
import cerebrum_path
import cereconf
import sys
from Cerebrum import Utils
from Cerebrum import Account
from Cerebrum.modules.no.uit import Account
from Cerebrum.Utils import Factory
sys.path = ['/home/cerebrum/CVS/cerebrum/contrib/no/uit/cerebrum_import/']+sys.path


class process:
    def __init__(self,db):
        print "init"
        self.db=db

    def find_uname(self,ssn,name,cstart):
        uname = get_uit_uname(ssn,name,cstart)
        print "uname suggested = %s" % uname
        return uname
        
    def store_user(self,uname,ssn,name):
        print "Name: %s" % name
        print "SSN: %s" % ssn
        print "username: %s" % uname
        print "type: P (Personal)" 
        print "source: Manual"
        type = 'P'
        source = "MANUAL"
        resp = raw_input("Are you sure you want to store this information legacy table y/[N]:")
        resp = resp.capitalize()
        while ((resp !='Y') and (resp !='N')):
            resp = raw_input("Please answer Y or N: ")
        if (resp == 'Y'):
            # we are to store the information into the legacy table
            query = "insert into legacy_users (user_name,ssn,source,type) values ('%s','%s','%s','%s')" % (uname,ssn,source,type)
            db_row = self.db.query(query)
            self.db.commit()
            print "Person stored in legacy_users. Do not forget to notify SUT (paal) about the new user"
        else:
            print "Nothing done"




def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:], 's:n:t:',['ssn=','name=','type='])
    except getopt.GetoptError, e:
        usage(str(e))

    ssn = ''
    name = ''
    cstart =-1
    for opt,val in opts:
        if opt in ('-s','--ssn'):
            ssn = val
            print "got ssn = %s" % ssn
        if opt in ('-n','--name'):
            name = val
            print "got name = %s" % name
        if opt in ('-t','--type'):
            if val == 'S':
                cstart = 0
            elif val =='E':
                cstart =0
            
    if ((ssn =='') or (name=='') or(cstart==-1)):
        usage()
    else:
        db = Factory.get('Database')()
        account = Factory.get('Account')(db) 
        #ac_inst = Account(db) #.AccountUiTMixin(Account)
        inits = account.get_uit_inits(name)
        new_uname=account.get_serial(inits,cstart)
        do = process(db)
        #uname = do.find_uname(ssn,name,cstart)
        do.store_user(new_uname,ssn,name)
        

def usage():
    print """usage: find_potential_username -n -s
    -n | --name : name of person, use \"\" if name has spaces in it
    -s | --ssn : ssn of person (personnummer, 11 siffer)
    -t | --type: account type [S]tudent/[E]mployee
    The script will then return the username that person would have got
    if an account was created at this time. The script will also store
    the username in the legacy table if a reservation is required
    """

if __name__ =='__main__':
    main()
