import cerebrum_path
import cereconf
import string
import getopt
import sys

from Cerebrum.Utils import Factory

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

    in_file = 0
    help = 0
    for opt,val in opts:
        if opt in ('-f','--file'):
            in_file = val
        if opt in('-h','--help'):
            help = 1


    if(help == 1):
        usage()
        sys.exit(0)
    if((in_file != 0) and (help ==0)):
        data = process(in_file)

        
def usage():
    print """This program reads a stillingskode file and inserts the data
    into the person_stillingskode table in cerebrum

    Usage: [options]
    -f | --file : stillingskode file
    -h | --help : this text """


if __name__ == '__main__':
    main()

# arch-tag: b546ff98-b426-11da-9faa-30b1c25ba442
