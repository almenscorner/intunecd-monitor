#!/bin/bash
set -o errexit
set -o nounset

flask db upgrade
gunicorn --bind :8080 --worker-class eventlet -w 1 run:app