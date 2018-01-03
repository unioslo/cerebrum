#!/usr/bin/env bash
echo "Setting up database."
psql -U $DB_USER -h $DB_HOST -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" \
| grep -q 1 && echo "Deleting old DB $DB_NAME." \
&& psql -U postgres -c "DROP DATABASE $DB_NAME" -h $DB_HOST
psql -U postgres -c "CREATE DATABASE $DB_NAME" -h $DB_HOST
echo "Database $DB_NAME created."

cp /src/testsuite/docker/cerebrum_path.py /usr/local/lib/python2.7
cd /src
python setup.py install
cd /usr/local/share/cerebrum/design
python /usr/local/sbin/makedb.py $(cat $INST_DIR/extra_db_files.txt)

echo "Placing GPG-keys in /gnupghome/.gnupg."
mkdir -p /gnupghome/.gnupg
cp /src/testsuite/docker/*.gpg /gnupghome/.gnupg
chmod -R 700 /gnupghome/.gnupg
/usr/bin/gpg2 -q --homedir /gnupghome/.gnupg -K removes=/usr/bin/gpg2
