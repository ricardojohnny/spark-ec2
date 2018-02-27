#!/bin/bash
# Arquitetura Cloud Wealthsystems

# Permission files
echo -e "....: Setando as permissoes nos arquivos :....\n"
chmod a+x /root/jobserver/server_start.sh
chmod a+x /root/jobserver/server_stop.sh
echo -e "....: permissoes setadas! :....\n"

# Time do Job
echo -e "....: Time of inicializing :....\n"
sleep 60

# Time

# Start jobserver
sh /root/jobserver/server_start.sh

sleep 10

cat /var/log/job-server/spark-job-server.log
