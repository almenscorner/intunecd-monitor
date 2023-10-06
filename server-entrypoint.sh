#!/bin/bash
set -o nounset

# check current db version
current=$(flask db current | grep "head" | awk '{print $2}')
# if current is null then check for migrations
if [ -z "$current" ]; then
    echo "INFO [DB MIGRATION] No current version found, setting to initial"
    flask db stamp "3a8c28fde990"
fi

# Check for migrations
migrate=$(flask db check 2>&1)
# If migrate is null then set to latest
if [[ $? -eq 0 ]]; then
    if [ -n "$current" ] && [ "$current" != "head" ]; then
      if [ "$current" != "(head)" ]; then
        echo "INFO [DB MIGRATION] No migrations found, setting to latest"
        latest=$(flask db heads)
        flask db stamp "$latest"
      fi
    fi
else
    echo "INFO [DB MIGRATION] Migrations found, upgrading"
    flask db upgrade
fi

gunicorn --bind :8080 --worker-class eventlet -w 1 run:app