from Cerebrum.Utils import Factory
from Cerebrum import Errors

class nsd:
    
    # get nsd code based on fakultet,institut and avdeling
    def get_nsd(self,fakultet,institutt,avdeling,db):
        my_old_ou_id = "%s%s%s"  % (fakultet,institutt,avdeling) 
        query = "select new_ou_id from ou_history where old_ou_id='%s'" % my_old_ou_id
        db_row = db.query(query)
        if len(db_row) != 0:
            aux, = db_row[0]
            aux = str(aux)
            fakultet  = aux[0:1]
            institutt = aux[2:3]
            avdeling  = aux[4:5]
            #print "STEDKODE after conversion from ou_history = %s%s%s" % (fakultet,institutt,avdeling)
        query = "select nsd from nsd_koder where fakultet=%s and institutt=%s and avdeling=%s" % (fakultet,institutt,avdeling)
        #print "query = '%s'" % query
        db_row = db.query(query)
        return db_row

    # get stedkode based on nsd_code
    def get_stedkode(self,nsd_code,db):
        query = "select fakultet,institutt,avdeling from nsd_koder where nsd=%s" % nsd_code
        db_row = db.query(query)
        return db_row
    
        
    # insert new entry into the nsd_table
    def insert_data(self,fakultet,institutt,avdeling,nsd_code,db):
        query = "insert into nsd_koder (fakultet,institutt,avdeling,nsd) values(%s,%s,%s,'%s')" % (fakultet,institutt,avdeling,nsd_code)
        print "query = %s" % query
        try:
            db.query(query)
            #db.commit()      # let the caller do the commits!
        except:# Errors.DatabaseException():
            print "already inserted %s" % query
        
# arch-tag: 8673830e-b4f2-11da-94f8-e0e97f4a22bc
