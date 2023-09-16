#!/bin/bash
set -o errexit
set -o nounset

flask db upgrade
gunicorn --bind :8080 --threads 100 run:app