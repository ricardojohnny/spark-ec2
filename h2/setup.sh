#!/bin/bash
# Arquitetura Cloud Wealthsystems
# H2 Base

echo -e "...: Set permissions and executing :...\n"
sh /root/h2/bin/h2.sh -tcp -tcpAllowOthers >> /dev/null &

# Time pos-start
sleep 20
