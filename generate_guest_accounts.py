import getopt
import cerebrum_path
import urllib
import sys
import cereconf
import os



def main():
    guest_data_path = '/cerebrum/var/dumps/System_x/guest_data'
    urllib.urlretrieve("http://adb-php.uit.no/basweb/db_show_all_plain.php","/cerebrum/var/dumps/System_x/guest_data")
    ret = os.system("python /cerebrum/share/cerebrum/contrib/no/uit/slurp_x.py -s /cerebrum/var/dumps/System_x/guest_data")



if __name__ =='__main__':
    main()
