#!/bin/sh
# Use the loader belonging to the pinned PostgreSQL tools.
exec /opt/pg-tools/ld.so --library-path /opt/pg-tools/lib "/opt/pg-tools/${0##*/}" "$@"
