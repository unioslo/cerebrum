#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import cerebrum_path
import getopt
import time
import sys
import cereconf
import string
import locale
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.no import fodselsnr

import pprint

db = Factory.get('Database')()
logger = Factory.get_logger('cronjob')



class process:

    # initialize the class global data
    def __init__(self,out):
        self.username_dict = {} 
        self.ssn_dict = {}
        self.parse_static_users(out)

        #pp=pprint.PrettyPrinter(indent=2)
        #print "*************************** DEBUG ***************************"
        #pp.pprint(self.username_dict)
        #print "----------------------------"
        #pp.pprint(self.ssn_dict)
        #sys.exit(1)


    def parse_static_users(self,filename):
        out_handle = open(filename,"r")
        lines = out_handle.readlines()
        out_handle.close()

        tech = "default"
        i = 0
        for person in lines:
            i += 1
            person = person.rstrip()
            #print "person = %s" % person.
            comment = ""
            username = ""
            name = ""
            ssn = ""
            
            if(person == '# MARTIN'):
                tech = "MARTIN"
            if((person != '') and (person[0] != "#")):
                if(tech == "MARTIN"):
                    try: 
                        username,ssn,name,comment = person.split(",",3)
                    except Exception,msg:
                        logger.critical("Error on line %d in %s\nError was: %s" % (i,filename,msg))
                        sys.exit(1)
                    # removes whitespace in ssn
                    username = username.strip()
                    ssn = ssn.strip()
                    name=name.strip()
                    comment = comment.strip()
                    #print "MARTIN personnr = %s" % ssn
                elif(tech =="default"):
                    logger.critical("ERROR in parsing static_user_info.txt. EXITING")
                    sys.exit(1)


                # data in lower part of file takes priority as new data from ASP is appended to static file.
                if (self.username_dict.has_key(username)):
                    logger.debug( "DUPLICATE USERNAME '%s' on line %d" % (username,i))
                logger.debug("caching UNAME %s: ['%s','%s','%s']" % (username,ssn,name,comment))
                self.username_dict[username] = {'personnr':ssn, 'name':name,'comment':comment}

                if (ssn != ""):
                    self.ssn_valid(ssn)
                    logger.debug("caching SSN %s: [%s,%s]" % (ssn,username,comment))
                    self.ssn_dict[ssn] = username
                else:
                    logger.debug("cache SSN drop: Blank ssn for %s comment:%s" %(username,comment))
                    
        # end parse_static_users


        


    def ssn_valid(self,ssn):
        # is the ssn  valid?

        ret_ok = False
        ret_text = ""
        try:
            ret_ok = fodselsnr.personnr_ok(ssn)
        except fodselsnr.InvalidFnrError,msg:
            ret_text = "%s" % msg
            ret_ok = False
        except Exception,msg:
            ret_text = "unknown error: %s" % msg
            ret_ok = False
            
        #print "Cheking ssn: %s , valid=%s %s" % (ssn, ret_ok, ret_text)
        return ret_ok, ret_text
    
       
    # read the source data and get the relevant data
    def inn_data(self,file_dict,out):
        person_list = []

        for file in file_dict.values():
            #print "file = %s" % file
            fname = file.split('/')[-1]
            file_handle = open(file,"r")
            i =0
            for line in file_handle:
                i=i+1
                #print "line = %s" % i
                if((line[0] != '\n') and (line[0] != "#") and (len(line)> 4)):
                    #print "line = '%s'" % line
                    foravn = etternavn = brukernavn = personnr = rest = comment = ""
                    ssn_valid = False
                    fornavn,etternavn,brukernavn,personnr,rest = line.split(";",4)
                    personnr = personnr.rstrip()
                    if (brukernavn != ''):
                        if (personnr.replace(' ','').isdigit()):                        
                            ssn_valid, comment = self.ssn_valid(personnr)
                        else:
                            comment = personnr
                            personnr = ""
                        
                        if (not ssn_valid):
                            #don't add an invalid pnr, errmsg is in comment
                            personnr = ""
                        else:
                            # personnr was valid, ssn_valid now contains a correctly formattet 11 digit norwegian ssn
                            personnr = ssn_valid

                        fullname = "%s %s" % (fornavn.strip(),etternavn.strip())
                        brukernavn = brukernavn.strip()

                        check_uname = False
                        #if (self.ssn_dict.has_key(personnr)):
                        #    print "Dropping %s, ssn exists in static file" % personnr
                        #    check_ssn=False
                        if (self.username_dict.has_key(brukernavn)):
                            #print "Username %s exists in static data" % brukernavn
                            dict = self.username_dict[brukernavn]
                            if ( (dict['name'] != fullname)):                            
                                #print "UPDATE trigger %s: '%s'!='%s'" % (brukernavn,dict['name'],fullname)
                                check_uname = True
                            elif (dict['personnr'] != personnr):
                                #print "UPDATE trigger %s: '%s'!='%s'" % (brukernavn,dict['personnr'],personnr)
                                check_uname = True
                            elif (dict['comment'] != comment):
                                #print "UPDATE trigger %s: '%s'!='%s'" % (brukernavn,dict['comment'],comment)
                                check_uname= True
                            else:    
                                #print "Dropping %s, username exists with equal data in static file" % brukernavn
                                check_uname=False
                        else:
                            #print "NEW: username %s does not exist in static" % brukernavn
                            check_uname=True
                            
                        #print "DEBUG:  ssn_validationMsg: %s" % comment

                        if (check_uname):                            
                            logger.debug("INSERTING uname='%s', pnr='%s', name='%s' comment='%s'" % (brukernavn,personnr,fullname,comment))
                            person_dict = {'brukernavn':brukernavn,
                                       'personnr':personnr,
                                       'name': fullname,
                                       'comment':comment}
                            #print "appending %as" % (person_dict['personnr'])
                            person_list.append(person_dict)
                    else:
                        logger.warning("INVALID data in file '%s' line %d: %s NOT inserted" % (fname,i,line))
            file_handle.close()
        return person_list


    # concatenate the data in the given file
    def out_data(self,data,out):
        date = time.localtime()
        year = date[0]
        month = date[1]
        day = date[2]
        hour = date[3]
        minute = date[4]        
        stamp =  "%d%02d%02d_%02d%02d" % (year,month,day,hour,minute)
        
        #print "out data = %s" % out
        out_handle = open(out,"a")
        #out_handle.writelines("# MARTIN\n")
        out_handle.writelines("# IMPORTED AT %s\n" % stamp)
        for person in data:
            line_to_write = "%s, %s, %s, %s" % (person['brukernavn'],person['personnr'],person['name'],person['comment'])
            #print "Writing: %s" % line_to_write
            out_handle.writelines(line_to_write + "\n" )
        out_handle.close()

def main():

    source_path = cereconf.CB_PREFIX + "/var/source"

    default_akademisk = source_path + "/ad/akademisk.csv"
    default_humfak = source_path + "/ad/humfak.csv"
    default_ita = source_path + "/ad/ita.csv"
    default_jurfak = source_path + "/ad/jurfak.csv"
    default_kun = source_path + "/ad/kun.csv"
    default_matnat = source_path + "/ad/matnat.csv"
    default_medfak = source_path + "/ad/medfak.csv"
    default_nfh = source_path + "/ad/nfh.csv"
    default_nuv = source_path + "/ad/nuv.csv"
    default_orakel = source_path + "/ad/orakel.csv"
    default_plp = source_path + "/ad/plp.csv"
    default_sadm = source_path + "/ad/sadm.csv"
    default_sito = source_path + "/ad/sito.csv"
    default_svfak = source_path + "/ad/svfak.csv"
    default_TMU = source_path + "/ad/TMU.csv"
    default_ub = source_path + "/ad/ub.csv"
    default_utdanning_no = source_path + "/ad/utdanning_no.csv"
    default_uvett = source_path + "/ad/uvett.csv"

    # lets generate the name of the default outfile
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    file_path = source_path
    file_name = '%s/static_user_info.txt' % file_path
    #print "file_name = %s" % file_name
    out = file_name 

    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:a:h:I:j:k:m:M:n:N:O:p:s:S:t:u:U:v:V:',['out=','akademisk=','humfak=','Ita=','jurfak=','kun=','matnat=','Medfak=','nfh=','Nuv=','Orakel=','plp=','sadm=','Sito=','tmu=','ub=','utdanning_no=','uvett=','svfak='])

    except getopt.GetoptError:
        usage()

    for opt,val in opts:
        if opt in('-a','--akademisk'):
            default_akademisk = val
        if opt in('-h','--humfak'):
            default_humfak = val
        if opt in('-I','--Ita'):
            default_ita = val
        if opt in('-j','--jurfak'):
            default_jurfak = val
        if opt in('-k','--kun'):
            default_kun = val
        if opt in('-m','--matnat'):
            default_matnat = val
        if opt in('-M','--Medfak'):
            default_medfak = val
        if opt in('-n','--nfh'):
            default_nfh = val
        if opt in('-N','--Nuv'):
            default_nuv = val
        if opt in('-O','--Orakel'):
            default_orakel = val
        if opt in('-p','--plp'):
            default_plp = val
        if opt in('-s','--sadm'):
            default_sadm = val
        if opt in('-S','--Sito'):
            default_sito = val
        if opt in('-t','--tmu'):
            default_tmu = val
        if opt in('-u','--ub'):
            default_ub = val
        if opt in('-U','--utdanning_no'):
            default_utdanning_no = val
        if opt in('-v','--uvett'):
            default_uvett = val
        if opt in('-V','--svfak'):
            default_svfak = val
        if opt in('-o','--out'):
            out = val
    #if out == 0:
    #    usage()
    #else:
    file_dict={'akademisk': default_akademisk,
               'humfak': default_humfak,
               'ita': default_ita,
               'jurfak': default_jurfak,
               'kun': default_kun,
               'matnat': default_matnat,
               'medfak': default_medfak,
               'nfh': default_nfh,
               'nuv': default_nuv,
               'orakel': default_orakel,
               'plp': default_plp,
               'sadm': default_sadm,
               'sito': default_sito,
               'svfak': default_svfak,
               'TMU': default_TMU,
               'ub': default_ub,
               'utdanning_no': default_utdanning_no,
               'uvett' : default_uvett}
    instance = process(out)
    data = instance.inn_data(file_dict,out)
    #pp = pprint.PrettyPrinter(indent=2)
    #pp.pprint(data)
    ret = instance.out_data(data,out)
        
def usage():

    print """
    This script reads a file with user information, and copies
    this info to the out file. The rationale behind this script is
    to keep an updated list over all usernames:ssn in AD
    unless otherwise spesified the files will be read from:
    /home/cerebrum/CVS/cerebrum/contrib/no/uit/create_import_data/source_date/ad

    
             usage: python get_user_info.py

             -a | --akademisk : academic file to read
             -h | --humfak    : humfak file to read
             -I | --Ita       : ita file to read
             -j | --jurfak    : jurfak file to read
             -k | --kun       : kun file to read
             -m | --matnat    : matnat file to read
             -M | --Medfak    : medfak file to read
             -n | --nfh       : nfh file to read
             -N | --Nuv       : nuv file to read
             -O | --Orakel    : orakel file to read
             -p | --plp       : plp file to read
             -s | --sadm      : sadm file to read
             -S | --Sito      : sito file to read
             -t | --tmu       : tmu file to read
             -u | --ub        : ub file to read
             -U | --utdanning_no : utdanning_no file to read
             -v | --uvett     : uvett file to read
             -V | --svfak     | svfak file to read
             -o | --out : optional file to store the converted data in
             """

if __name__=='__main__':
    main()
