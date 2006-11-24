#!/bin/bash

today=`date +"%Y%m%d"`

cd /cerebrum/share/cerebrum/contrib/no/uit
#python get_user_info.py 
python get_slp4_data.py 
#python parse_user_info.py -e 
python import_ad_email.py -i /cerebrum/var/dumps/email/AD_Emaildump.cvs

# source tables
python insert_stillingskoder.py -f  /cerebrum/var/source/stillingskode_sorted.txt
python generate_OU.py -r -f /cerebrum/var/source/fs-sted.txt -o /cerebrum/var/source/stedkoder_v2.txt -O /cerebrum/var/dumps/ou/uit_ou_$today.xml 
python import_OU.py -v -o /cerebrum/var/dumps/ou/uit_ou_$today.xml --perspective=perspective_fs --source-system=system_fs 

# generate persons
python generate_persons.py -t AD
python import_LT.py -p /cerebrum/var/dumps/employees/uit_persons_$today.xml


# finally generate accounts
python process_employees.py -f /cerebrum/var/dumps/employees/uit_persons_$today.xml

# arch-tag: b9f98060-b426-11da-87cc-a78423d7022d
