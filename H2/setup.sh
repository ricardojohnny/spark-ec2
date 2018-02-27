#!/bin/bash
# Arquitetura Cloud Wealthsystems

echo -e "...: Access directory H2 :...\n"
cd /root/h2

echo -e "...: Set permissions and executing :...\n"
chmod a+x bin/h2.sh
./bin/h2.sh -tcp >> /dev/null &
