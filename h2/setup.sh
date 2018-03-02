#!/bin/bash
# Arquitetura Cloud Wealthsystems
# H2 Base

# Time pre-start
sleep 20

echo -e "...: Executing H2 Base:...\n"
sh /root/h2/bin/h2.sh -tcp -tcpAllowOthers >> /dev/null &

# Time pos-start
sleep 10
