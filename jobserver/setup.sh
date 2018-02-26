#!/bin/bash
# Arquitetura Cloud Wealthsystems

# Permission files
chmod a+x /root/jobserver/server_start.sh
chmod a+x /root/jobserver/server_stop.sh

# Time do Job
sleep 90

# Start jobserver
./root/jobserver/server_start.sh
