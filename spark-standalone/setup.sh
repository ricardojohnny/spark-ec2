#!/bin/bash
<<<<<<< HEAD
=======
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>
>>>>>>> origin/master

BIN_FOLDER="/root/spark/sbin"

if [[ "0.7.3 0.8.0 0.8.1" =~ $SPARK_VERSION ]]; then
  BIN_FOLDER="/root/spark/bin"
fi

<<<<<<< HEAD
# Copy the slaves to spark conf
cp /root/spark-ec2/slaves /root/spark/conf/
/root/spark-ec2/copy-dir /root/spark/conf

# Set cluster-url to standalone master
echo "spark://""`cat /root/spark-ec2/masters`"":7077" > /root/spark-ec2/cluster-url
/root/spark-ec2/copy-dir /root/spark-ec2

# The Spark master seems to take time to start and workers crash if
# they start before the master. So start the master first, sleep and then start
# workers.

# Stop anything that is running
=======
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
>>>>>>> origin/master
$BIN_FOLDER/stop-all.sh

sleep 2

# Start Master
$BIN_FOLDER/start-master.sh

# Pause
sleep 20

# Start Workers
$BIN_FOLDER/start-slaves.sh
