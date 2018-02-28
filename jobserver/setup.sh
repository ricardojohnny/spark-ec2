#!/bin/bash
# Arquitetura Cloud Wealthsystems

# Permission files
echo -e "....: Setando as permissoes nos arquivos :....\n"
chmod a+x /root/jobserver/server_start.sh
chmod a+x /root/jobserver/server_stop.sh
echo -e "....: permissoes setadas! :....\n"

# Time do Job
echo -e "....: Aguandando para iniciar o Jobserver :....\n"

# Time Start
sleep 60

# Start jobserver
sh /root/jobserver/server_start.sh

sleep 10

cat /mnt/spark-jobserver/log/spark-job-server.log
