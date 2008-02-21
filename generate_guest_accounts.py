import getopt
import cerebrum_path
import urllib
import sys
import cereconf
import os



def main():
    guest_data_path = cereconf.DUMPDIR + '/System_x/guest_data'
    urllib.urlretrieve("http://adb-php.uit.no/basweb/db_show_all_plain.php" + cereconf.DUMPDIR + "/System_x/guest_data")
    ret = os.system("python "+ cereconf.CB_PREFIX +"/share/cerebrum/contrib/no/uit/slurp_x.py -s "+ cereconf.DUMPDIR +"/System_x/guest_data")



if __name__ =='__main__':
    main()

