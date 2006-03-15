# This file generates an export to SUT on the following format:
#fødselsdato§personnr§Navn§Brukernavn


import cerebrum_path
import Cerebrum.Utils
import getopt
import smtplib
import urllib

from Cerebrum import Errors
import os
import re
import ftplib
import time
import string
import cereconf
from Cerebrum.Utils import Factory
import sys
from Cerebrum.modules.no.uit import Email
#import locale
#locale.setlocale(locale.LC_ALL,"en_US.ISO-8859-1")
sys.path = ['/home/cerebrum/CVS','/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/lib'] + sys.path
#global ret_value
#global global_ret

#MinimumSizeWriter= Cerebrum.Utils.MinimumSizeWriter

class execute:
    
    def __init__(self,out_file=None):
        print "__init__"
        #global_ret is used to check the return value from all system commands
        # if it any time is != 0 an email will be sent to the developer showing the return value from
        # all system commands.
        self.global_ret = 0
        
    def start(self,out_file):
        self.send_sut_data(out_file)

    def import_from_fs(self,log_handle,message):
        print "importing from fs."
        message += "***importing from fs.***\n"
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/import_from_FS.py --db-user=fsbas --db-service=fsprod -s -o -p -r -e -u -U -f")
        self.global_ret +=ret
        message += "   import_from_FS.py %s\n" % ret
        
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command in import_from_fs.\n")
        else:
            log_handle.writelines("import_from_fs....done\n")
        return message

    def merge_xml_files(self,log_handle,message):
        print "mergin xml files"
        message +="***merging xml files***\n"
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/merge_xml_files.py -d fodselsdato:personnr -f /cerebrum/dumps/FS/person.xml -t person -o /cerebrum/dumps/FS/merged_persons.xml")
        self.global_ret +=ret
        message+="   merg_xml_files.py %s\n" % ret
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command in merge_xml_files.\n")
        else:
            log_handle.writelines("merge_xml_files....done\n")
        return message        

    def import_fs(self,log_handle,message):
        print "importing fs data to cerebrum"
        message +="***importing fs data to cerebrum***\n"
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/import_FS.py -s /cerebrum/dumps/FS/studieprog.xml -p /cerebrum/dumps/FS/merged_persons.xml -g")
        self.global_ret +=ret
        message +="   import_FS.py %s\n" % ret
        if ret != 0:
            log_handle.writelines( "    ERROR: unable to execute system command in import_fs.\n")
        else:
            log_handle.writelines("import_fs......done\n")
        return message
            
    def process_students(self,log_handle,message):
        print "process students"
        message +="***process students***\n"
        ret= os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_import/process_students.py -C /cerebrum/dumps/FS/studconfig.xml -S /cerebrum/dumps/FS/studieprog.xml -s /cerebrum/dumps/FS/merged_persons.xml -c -u -e /cerebrum/dumps/FS/emner.xml --only-dump-results result_file.txt --workdir .")
        self.global_ret +=ret
        message +="   process_students %s\n" % ret
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command in process_students.\n")
        else:
            log_handle.writelines("process_students....done\n")
        return message
    
    def populate_external_groups(self,log_handle,message):
        print "populating external groups"
        message +="***populating external groups\n"
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/populate_external_groups.py")
        self.global_ret +=ret
        message +="   populate_external_groups %s\n" % ret
        #for message in ret.readlines():
        #    log_handle.writelines("%s\n" % message)
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command in populate_external_groups.\n")
        else:
            log_handle.writelines("populate_external_groups....done\n")
        return message

    def fnr_update(self,log_handle,message):
        print "updating fnr"
        message +="***update fnr***\n"
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/fnr_update.py /cerebrum/dumps/FS/fnr_update.xml")
        self.global_ret +=ret
        message += "   fnr_update.py %s\n" % ret
        
        #for message in ret.readlines():
        #    log_handle.writelines("%s\n" % message)
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command in fnr_update.\n")
        else:
            log_handle.writelines("fnr_update.....done\n")
        return message
    
    def export_xml_fronter(self,log_handle,message):
        # in addition to creating the /cerebrum/dumps/fronter/test.xml file we need to rename it.
        # The format of the filename has to be:
        #uit_import<year><month><day_of_month>.xml
        # example:
        # uit_import20040813.xml
        # The file then needs to be copied to ftp.uit.no
        
        print "creating fronter xml"
        message +="***creating fronter xml***\n"
        ret= os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/export_xml_fronter.py")
        self.global_ret +=ret
        message +="   export_xml_fronter.py %s\n" % ret
        #for message in ret.readlines():
        #    log_handle.writelines("%s\n" % message)
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command in export_xml_fronter.\n")
        else:
            log_handle.writelines("export_xml_fronter....\n")
            

        # lets get todays date
        date = time.localtime()
        year = date[0]
        month = date[1]
        day = date[2]


        # lets create the filename
        file_path = "/cerebrum/dumps/Fronter/"
        filename = "uit_import%02d%02d%02d.xml" % (year,month,day)
        ret = os.system("mv /cerebrum/dumps/Fronter/test.xml /cerebrum/dumps/Fronter/%s" % filename)
        self.global_ret +=ret
        message +="   mv test.xml %s %s\n" % (filename,ret)
        if ret != 0:
            log_handle.writelines("    ERROR: unable to execute system command mv in import_from_fs.\n")

        file_handle = open("%s%s"% (file_path,filename))

        # lets ftp the file to ftp.uit.no
        try:
            ftp = ftplib.FTP("ftp.uit.no","lmseksport","Fr0nt3r")
            #ftp.set_debuglevel(1)
            ftp.storlines("STOR %s" % filename,file_handle)
            
        except ftplib.all_errors:
            print "% unable to ftp file: %s" % ftplib.all_errors
        
        
        log_handle.writelines("done\n")
        return message
            
    def send_sut_data(self,out_file,log_handle,message):
        db = Factory.get('Database')()
        print "sending data to sut."
        message +="***sending data to sut***\n"
        
        file_handle = open(out_file,"w")
        # we are to export the following data to SUT.
        # fodtdato,pnr,name,username

        query = "select e.entity_name, p.external_id, s.name \
        FROM person_affiliation pa, entity_name e, entity_external_id p, person_name s, account_info a \
        WHERE e.entity_id=a.account_id AND \
        a.owner_id = p.entity_id AND \
        s.person_id = a.owner_id AND \
        p.entity_id = pa.person_id AND \
        e.value_domain=77 AND \
        p.id_type=96 AND \
        s.name_variant=162 AND \
        pa.affiliation=190"

        db_row = db.query(query)
        for row in db_row:
            full_name = row['name']
            ssn = row['external_id']
            fodt = ssn[0:6]
            pnr = ssn[6:11]
            dag = fodt[0:1]
            mnd = fodt[2:4]
            aar = fodt[4:6]
            # unfortunately we have some fake ssn. these cannot be inserted into the export
            # file to SUT. We need to convert these by issuing the following
            # any months which have the first number = 5 or 6 must be changed to 0 or 1 respectively
            
            if(fodt[2] == "5"):
                #print "before:%s" % (fodt)
                fodt = "%s%s%s" % (fodt[0:2],"0",fodt[3:6])
                #print "after:%s" % (fodt)
            elif(fodt[2] == "6"):
                #print "before:%s" % (fodt)
                fodt = "%s%s%s" % (fodt[0:2],"1",fodt[3:6])
                #print "after:%s" % (fodt)
            
            entity_name = row['entity_name']
            #print "full name = %s" % full_name
            #print "ssn = %s" % ssn
            #print "fodt = %s" % fodt
            #print "pnr = %s" % pnr
            #print "entity_name = %s" % entity_name
            file_handle.writelines("%s:%s:%s:%s\n" % (fodt,pnr,full_name,entity_name))
        file_handle.close()
        print "copying file now"
        ret = os.system("/usr/bin/scp %s root@flam.student.uit.no:/its/apache/data/sliste.dta" % out_file)
        self.global_ret +=ret
        message +="   scp %s to sut %s\n" %(out_file,ret) 
        # lets write any outputs from the system command to our log file
        #for message in get.readlines():
        #    log_handle.writelines("%s\n" % message)
        return message
    
    # We need a temp undervenhet at 186:000000
    def insert_temp_undervenhet(self,undervenhet,log_handle,message):
        print "insert temp undervenhet."
        message +="***insert temp undervenhet***\n"
        file_handle = open(undervenhet,"r+")
        file_handle.seek(-15,2)

        # lets insert the following 2 lines at the end of the file
        file_handle.writelines("<undenhet institusjonsnr=\"186\" emnekode=\"FLS-007\" versjonskode=\"1\" emnenavnfork=\"Felles-007\" emnenavn_bokmal=\"Dette er en falsk undervisnings enhet\" faknr_kontroll=\"0\" instituttnr_kontroll=\"0\" gruppenr_kontroll=\"0\" terminnr=\"1\" terminkode=\"HØST\" arstall=\"2005\"/>\n")
        file_handle.writelines("</undervenhet>")
        file_handle.close()
        log_handle.writelines("insert_temp_undervenhet...done\n")
        return message
        
    def ldap_export(self,message):
        print " export ldap data to the ldap server."
        message += "***export ldap data to the ldap server.***\n"

        date = time.localtime()
        year = date[0]
        month = date[1]
        day = date[2]


        # 1. create the posix_user_ldif
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/generate_posix_ldif.py -U fronter_acc@uit,AD_account,NIS_user@uit,SUT@uit,fd@uit -u /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/users_ldif")
        self.global_ret +=ret
        message +="   generate_posix_ldif.py %s\n" % ret

        # 2 create the ou_ldif
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/generate_org_ldif.py -o /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/ou_ldif")
        self.global_ret +=ret
        message +="   generate_org_ldif.py %s\n" %ret

        # 3 concatenate the two files into a third called temp_uit_ldif
        ret = os.system("/bin/cat /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/ou_ldif /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/users_ldif > /cerebrum/dumps/LDAP/temp_uit_ldif")
        self.global_ret +=ret
        message +="   cat ou_ldif users_ldif > temp_uit_ldif %s\n" %ret

        # 4.create a new ldif file based on the difference between the old and new data from cerebrum
        # 
        ret = os.system("/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_export/ldif-diff.pl /cerebrum/dumps/LDAP/uit_ldif /cerebrum/dumps/LDAP/temp_uit_ldif > /cerebrum/dumps/LDAP/uit_diff_%02d%02d%02d" % (year,month,day))
        self.global_ret +=ret
        message +="   ldif-diff.pl %s\n" % ret


        #6 update the ldap server on ldap.uit.no
        ret = 0
        ret = os.system("ldapmodify -x -H ldap://ldap.uit.no -D \"cn=Manager,dc=uit,dc=no\" -w Fl4pDap -v -f /cerebrum/dumps/LDAP/uit_diff_%02d%02d%02d" % (year,month,day))
        #ret = os.system("/usr/bin/ssh kaj000@ruskesara.uit.no ldapmodify -H ldap:///ruskesara.uit.no -D \"cn=Manager,dc=uit,dc=no\" -w Fl4pDap -v -f /usr/home/kaj000/ldif/uit_diff_%02d%02d%02d" % (year,month,day))
        self.global_ret +=ret
        message +="   ldapmodify %s\n" %ret

        # 7 update the temp_uit_ldif to now be the new uit_ldif, but only if the ldapmodify worked
        if (ret ==0):
            ret = os.system("mv /cerebrum/dumps/LDAP/temp_uit_ldif /cerebrum/dumps/LDAP/uit_ldif")
            self.global_ret +=ret
            message +="   mv temp_uit_ldif uit_ldif %s\n" % ret

            # 8 copy the file to suppedragen.uit.no, but only if the ldapmodify worked
            ret = os.system("/usr/bin/scp /cerebrum/dumps/LDAP/uit_ldif kaj000@ruskesara.uit.no:/home/kaj000/ldif/")
            self.global_ret +=ret
            message +="   scp uit_ldif\n"
        return message


    #this function checks if it is able to talk to the ldap server.
    def ldap_controller(self,message):
        ret = os.system("ldapsearch -x -H ldaps://ldap.uit.no -b cn=organization,dc=uit,dc=no cn=organization")
        self.global_ret +=ret
        message += "Cheking if ldap server is responding: %s" % ret
        return message


    def update_affiliation(self,message,emner):
        #we need to parse the emner.xml file and remove all references to the stedkode 4902.
        # it must be replaced with 186
        message +="***updating stedkode for KUN***\n"
        file_handle = open(emner,"r+")
        file_handle_write = open("/cerebrum/dumps/FS/temp_emner","w")
        print "emne fil = %s" % emner
        for line in file_handle:

            foo = line.replace("institusjonsnr_reglement=\"4902\" faknr_reglement=\"1\" instituttnr_reglement=\"0\" gruppenr_reglement=\"0\"","institusjonsnr_reglement=\"186\" faknr_reglement=\"99\" instituttnr_reglement=\"30\" gruppenr_reglement=\"0\"")
            
            #print "foo = %s" % foo
            file_handle_write.writelines(foo)
        file_handle.close()
        file_handle_write.close()
        ret = os.system("mv /cerebrum/dumps/FS/temp_emner /cerebrum/dumps/FS/emner.xml")
        #print "line = %s" % foo
        message +="mv /cerebrum/dumps/FS/temp_emner /cerebrum/dumps/FS/emner.xml: %s" % ret
        return message
            
    def guest_account(self,message):
        # get latest dump from system_x database
        # create persons
        # create accounts
        print "guest"
        urllib.urlretrieve("http://adb-php.uit.no/basweb/db_show_all_plain.php","/cerebrum/dumps/System_x/guest_data")
        ret = os.system("python /home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/cerebrum_import/slurp_x.py -s /cerebrum/dumps/System_x/guest_data")

def send_mail(message,email_address):
    #this function sends an email to the system administrator in case any of the scheduled tasts fails.
    SENDMAIL = "/usr/sbin/sendmail" # sendmail location
    p = os.popen("%s -t" % SENDMAIL, "w")
    p.write("From: cerebrum@bas.uit.no\n")
    p.write("To: %s\n" % email_address)
    p.write("subject: run_all.py status\n")
    p.write("\n")
    p.write("%s" % message)
    sts = p.close()
    if sts != None:
        print "Sendmail exit status", sts



def main():
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:Cimfpgxsu:Flce:U:G',['Create_email','out_file=','import_from_fs','merge','fs_import','process_students','group_population','xml_export_fronter','sut_export','undervenhet=','fnr_update','ldap_export','control_ldap','email_address=','Update_affiliation=','Guest_account'])

    except getopt.GetoptError:
        usage()
        sys.exit()
    file = 0
    val = 0
    create_email = 0
    import_from_fs = 0
    merge = 0
    fs_import = 0
    process_students = 0
    group_population = 0
    xml_export_fronter = 0
    sut_export = 0
    undervenhet = 0
    fnr_update = 0
    ldap_export = 0
    control_ldap = 0
    guest_account = 0
    update_affiliation = 0
    foo = execute()
    message =''
    email_address = "kenneth.johansen@cc.uit.no"
    log_file="sut.log"
    log_handle = open (log_file,"w")
    
    for opt,val in opts:
        if opt in ('-C','--Create_email'):
            create_email = 1
        if opt in ('-o','--out_file'):
            file = val        
        if opt in ('-i','--import_from_fs'):
            import_from_fs = 1
        if opt in ('-m','--merge'):
            merge = 1
        if opt in ('-f','--fs_import'):
            fs_import = 1
        if opt in ('-p','--process_students'):
            process_students = 1
        if opt in ('-g','--group_population'):
            group_population = 1
        if opt in('-x','--xml_export_fronter'):
            xml_export_fronter = 1
        if opt in ('-s','--sut_export'):
            sut_export = 1
        if opt in('-u','--undervenhet'):
            undervenhet = val
        if opt in('-F','--fnr_update'):
            fnr_update = 1
        if opt in('-l','--ldap_export'):
            ldap_export = 1
        if opt in('-c','--control_ldap'):
            control_ldap = 1
        if opt in('-e','--email_address'):
            email_address = val
        if opt in('-U','--Update_affiliation'):
            update_affiliation = 1
            emner = val
        if opt in('-G','--Guest_account'):
            guest_account = 1
        
    #self.start(out_file)

    if((import_from_fs == 0) and (merge == 0) and (fs_import ==0) and (process_students == 0) and(group_population == 0) and (xml_export_fronter == 0) and(ldap_export ==0) and(sut_export == 0) and (undervenhet == 0) and (undervenhet == 0) and (control_ldap == 0) and(update_affiliation == 0) and (create_email ==0) and(guest_account==0)):
        usage()
        sys.exit(0)
        
    if(import_from_fs ==1):
        message = foo.import_from_fs(log_handle,message)
    if(fnr_update == 1):
        message = foo.fnr_update(log_handle,message)
    if(undervenhet != 0):
        message = foo.insert_temp_undervenhet(undervenhet,log_handle,message)
    if(update_affiliation != 0):
        message = foo.update_affiliation(message,emner)
    if(merge == 1):
        message = foo.merge_xml_files(log_handle,message)
    if(fs_import ==1):
        message = foo.import_fs(log_handle,message)
    if(process_students == 1):
        message = foo.process_students(log_handle,message)
    if(group_population == 1):
        message = foo.populate_external_groups(log_handle,message)
    if(xml_export_fronter == 1):
        message = foo.export_xml_fronter(log_handle,message)
    if(sut_export == 1):
        message = foo.send_sut_data(file,log_handle,message)
    if(ldap_export ==1):
        message = foo.ldap_export(message)
    if(control_ldap==1):
        message = foo.ldap_controller(message)
    if(guest_account ==1):
        message = foo.guest_account(message)
    if(create_email ==1):
        my_email = Email.email_address()
        email_list = my_email.build_email_list()
        for pers in my_email.person.list_persons():
            my_email.person.find(pers['person_id'])
            for accounts in my_email.person.get_accounts():
                email = my_email.account_id2email_address(accounts['account_id'],email_list)
                my_email.process_mail(accounts['account_id'],"defaultmail",email)
            my_email.person.clear()
        my_email.db.commit()

        
    log_handle.close()

    if(foo.global_ret !=0):
        print "ERROR in run_all.py, sending email"
        foo = send_mail(message,email_address)
    else:
        print "run_all.py executed successfully"


   


def usage():
    print """Usage: python run_all.py -o <out_file> | -e | -U | -c | -i | -F | -u | -m | -f | -p | -g | -s | -l | -C | -G | -o sut_person
    This script can do various functions towards cererum. it can import data to cerebrum, export data
    from cerebrum and check if the ldap server is running. Email will be sent to the email address spesified
    (default kenneth.johansen@cc.uit.no) if an error occures. There are several features missing in this
    script, f.eks import employee data and export to FRIDA. It's on my todo list.
    

    This file can execute several commands:
    -e | --email_address:      Email address to send report to.   
    -c | --control_ldap:       Check of the ldap server is. running.
    -o | --out_file :          log file
    -U | --Update_affiliation  updates KUN's 4902 stedkode to 186 in the emner.xml file
    -i | --import_from_fs :    executes the import_from_fs.py script with uit extensions.
    -m | --merge:              executes the merge_xml_files.py with uit extensions
    -l | --ldap_export :       creates an ldif file which is exported to the ldap/AT server
    -f | --fs_import:          executes the import_FS.py with uit extensions
    -p | --process_students:   executes the process_students.py with uit extensions
    -g | --group_population:   executes the populate_external_groups.py script with uit extensions
    -x | --xml_export_fronter: executes the export_xml_fronter.py script with uit extensions
    -s | --sut_export:         creates a dump to sut with user info
    -u | --undervenhet:        inserts a temp undervenhet into the file given
    -F | --fnr_update:         updates fnr inconsistensies between cerebrum and FS
    -C | --Create_email:       creates email address for all users
    -G | --Guest_account:      Creates guest accounts in cerebrum
    """
if __name__=='__main__':
    main()
