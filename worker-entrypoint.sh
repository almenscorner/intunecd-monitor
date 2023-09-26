#!/bin/bash
set -o errexit
set -o nounset

celery -A app.celery worker --loglevel=info