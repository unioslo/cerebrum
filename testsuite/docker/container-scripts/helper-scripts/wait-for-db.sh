#!/usr/bin/env bash

until psql -U $DB_USER -h $DB_HOST -c "SELECT 1" > /dev/null 2>&1; do
  echo "Waiting for db service..."
  sleep 1
done
