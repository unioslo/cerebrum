#!/usr/bin/env bash
echo "Setting up database..."
psql -U $DB_USER -h $DB_HOST -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" \
| grep -q 1 && echo "Deleting old DB $DB_NAME." \
&& psql -U postgres -c "DROP DATABASE $DB_NAME" -h $DB_HOST
psql -U postgres -c "CREATE DATABASE $DB_NAME" -h $DB_HOST
echo "Database $DB_NAME created."

mkdir /db-auth
echo "Creating DB auth file..."
DB_AUTH_FILE_NAME=/db-auth/passwd-$DB_USER@$DB_NAME@$(echo "$DB_HOST" | awk '{print tolower($0)}')
echo -e "$DB_USER\t$DB_PASS" >> $DB_AUTH_FILE_NAME
echo "DB auth file $DB_AUTH_FILE_NAME created."