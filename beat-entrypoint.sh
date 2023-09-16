#!/bin/bash
set -o errexit
set -o nounset

celery -A app.celery beat -S sqlalchemy_celery_beat.schedulers:DatabaseScheduler -l info