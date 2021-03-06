#!/bin/bash
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>

BIN_FOLDER="/root/spark/sbin"

if [[ "0.7.3 0.8.0 0.8.1" =~ $SPARK_VERSION ]]; then
  BIN_FOLDER="/root/spark/bin"
fi

# Copiando para os slaves o spark conf
cp /root/spark-ec2/slaves /root/spark/conf/
/root/spark-ec2/copy-dir /root/spark/conf

# Setando cluster-url no standalone do master
echo "spark://""`cat /root/spark-ec2/masters`"":7077" > /root/spark-ec2/cluster-url
/root/spark-ec2/copy-dir /root/spark-ec2

# O Spark Master com time para iniciar e os workers falharem se
# eles começam antes do Master. Então, comece o Master primeiro, e depois inicie os
# workers.

# Stop qualquer job rodando
$BIN_FOLDER/stop-all.sh

sleep 30

# Start Master
$BIN_FOLDER/start-master.sh

# Pause
sleep 30

# Start Workers
$BIN_FOLDER/start-slaves.sh
