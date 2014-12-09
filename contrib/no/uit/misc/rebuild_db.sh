#!/bin/bash

dropdb cerebrum
createdb -E unicode cerebrum
psql -U cerebrum < $1
psql < /cerebrum/share/cerebrum/contrib/no/uit/misc/analyze.sql

# not needed now
#python /cerebrum/share/cerebrum/contrib/migrate_cerebrum_database.py --from rel_0_9_5 --to rel_0_9_7 --makedb-path /cerebrum/sbin --design-path /cerebrum/share/doc/cerebrum/design

# create the ad_email table
#/cerebrum/sbin/makedb.py /home/cerebrum/cerebrum/design/mod_uit_ad_email.sql
# populate the ad_email table
#/cerebrum/share/cerebrum/contrib/no/uit/import_ad_email.py -i /cerebrum/var/source/ad/AD_Emaildump.cvs
#python fix_authdata.py
#python fix_homedir.py

