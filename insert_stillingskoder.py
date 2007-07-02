import cerebrum_path
import cereconf
import string
import getopt
import sys
import os

from Cerebrum.Utils import Factory

# Define default file locations
sourcedir = cereconf.CB_SOURCEDATA_PATH
default_output_file = 'stillingskode_sorted.txt'
 

class process:
    def __init__(self,in_file):
        self.stillingskoder(in_file)
        
    def stillingskoder(self,in_file):
        db = Factory.get('Database')()
        file_handle = open(in_file,"r")
        for stilling in file_handle:
            if((stilling[0] != "#") and (stilling[0] != "\n")):
                stillingskode,stillingstittel,stillingstype = stilling.split(",")
                stillingstype = stillingstype.rstrip("\n")
                #print "%s,%s,%s" % (stillingskode,stillingstittel,stillingstype)
                query= "insert into person_stillingskoder (stillingskode,stillingstittel,stillingstype) values(%s,'%s','%s')" % (stillingskode,stillingstittel,stillingstype)
                #print "query = %s" % query
                try:
                    db_row = db.query(query)
                    db.commit()
                except:
                    print "stillingskode %s already inserted" % stillingskode


def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:',['file='])
    except getopt.GetoptError:
        usage()

    in_file = os.path.join(sourcedir, default_output_file)
    
    for opt,val in opts:
        if opt in ('-f','--file'):
            in_file = val
        if opt in('-h','--help'):
            usage()
            sys.exit(0)
    data = process(in_file)

def usage():
    print """This program reads a stillingskode file and inserts the data
    into the person_stillingskode table in cerebrum

    Usage: [options]
    -f | --file : stillingskode file
    -h | --help : this text """


if __name__ == '__main__':
    main()
