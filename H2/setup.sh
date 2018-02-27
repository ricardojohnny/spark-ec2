#!/bin/bash
# Arquitetura Cloud Wealthsystems

echo -e "...: Set permissions and executing :...\n"
chmod a+x /root/h2/bin/h2.sh
sh /root/h2/bin/h2.sh -tcp >> /dev/null & 
