#!/bin/sh
set -e

# Only the api container should apply migrations and collect static files;
# workers set RUN_MIGRATIONS=0 so they don't race with it.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

exec "$@"
