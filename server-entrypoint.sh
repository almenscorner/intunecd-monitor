#!/bin/bash
set -o nounset

# Upgrade the database and capture the output
dbUpgrade=$(flask db upgrade 2>&1)
# Check for updates to the database schema
dbCheck=$(flask db check 2>&1)
# Check the current version
currentVersion=$(flask db current)

if [[ $? -ne 0 ]]; then
    echo "INFO  [DB UPGRADE] Schema changes detected, upgrading database"
fi

# Check if the upgrade was successful or if there was an error due to duplicate column names
if [[ "$dbUpgrade" == *"Column names in each table must be unique"* ]]; then
    if [[ -z "$currentVersion" ]]; then
        echo "INFO  [DB UPGRADE] Database already up to date, stamping head"
        flask db stamp head
    fi
fi

currentVersion=$(flask db current)
echo "INFO  [DB UPGRADE] Current database version: $currentVersion"

gunicorn --bind :8080 --worker-class eventlet -w 1 run:app