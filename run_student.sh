#!/bin/bash

cd /cerebrum/share/cerebrum/contrib/no/uit
python import_from_FS.py --db-user=fsbas --db-service=fsprod -s -o -p -f -e -u -U -r
python fnr_update.py /cerebrum/var/dumps/FS/fnr_update.xml 
python undervenhet_update.py  -u /cerebrum/var/dumps/FS/underv_enhet.xml 
python institution_update.py -E /cerebrum/var/dumps/FS/emner.xml -S /cerebrum/var/dumps/FS/studieprog.xml
python merge_xml_files.py -d fodselsdato:personnr -f /cerebrum/var/dumps/FS/person.xml -t person -o /cerebrum/var/dumps/FS/merged_persons.xml 
python import_FS.py -s /cerebrum/var/dumps/FS/studieprog.xml -p /cerebrum/var/dumps/FS/merged_persons.xml -g 


# Create student accounts
python process_students.py -C /cerebrum/etc/cerebrum/studconfig.xml -S /cerebrum/var/dumps/FS/studieprog.xml -s /cerebrum/var/dumps/FS/merged_persons.xml -c -u -e /cerebrum/var/dumps/FS/emner.xml --only-dump-results result_file.txt --workdir /cerebrum/var/log
