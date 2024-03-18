#!/bin/sh
default_port=5000
if [ $# -eq 0 ]; then
  # listen on localhost:PORT by default
  exec uwsgi -s "127.0.0.1:$default_port" -M -T --threads 2 -p 2 --manage-script-name --callable app
else
  # use custom arguments
  exec uwsgi "$@"
fi