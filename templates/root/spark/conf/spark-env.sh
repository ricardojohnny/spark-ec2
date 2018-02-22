#!/usr/bin/env bash

export SPARK_LOCAL_DIRS="{{spark_local_dirs}}"

<<<<<<< HEAD
# Standalone cluster options
=======
# Opções Standalone cluster
>>>>>>> origin/master
export SPARK_MASTER_OPTS="{{spark_master_opts}}"
if [ -n "{{spark_worker_instances}}" ]; then
  export SPARK_WORKER_INSTANCES={{spark_worker_instances}}
fi
export SPARK_WORKER_CORES={{spark_worker_cores}}

export HADOOP_HOME="/root/ephemeral-hdfs"
export SPARK_MASTER_IP={{active_master}}
export MASTER=`cat /root/spark-ec2/cluster-url`

export SPARK_SUBMIT_LIBRARY_PATH="$SPARK_SUBMIT_LIBRARY_PATH:/root/ephemeral-hdfs/lib/native/"
export SPARK_SUBMIT_CLASSPATH="$SPARK_CLASSPATH:$SPARK_SUBMIT_CLASSPATH:/root/ephemeral-hdfs/conf"

<<<<<<< HEAD
# Bind Spark's web UIs to this machine's public EC2 hostname otherwise fallback to private IP:
=======
# As interfaces de usuário da web da Bind Spark para o nome de host EC2 público desta máquina, de outra forma, retornam a IP privado:
>>>>>>> origin/master
export SPARK_PUBLIC_DNS=`
wget -q -O - http://169.254.169.254/latest/meta-data/public-hostname ||\
wget -q -O - http://169.254.169.254/latest/meta-data/local-ipv4`

<<<<<<< HEAD
# Used for YARN model
export YARN_CONF_DIR="/root/ephemeral-hdfs/conf"

# Set a high ulimit for large shuffles, only root can do this
=======
# Para modelo YARN
export YARN_CONF_DIR="/root/ephemeral-hdfs/conf"

# ulimit alto para large shufflers, apenas a raiz acessa
>>>>>>> origin/master
if [ $(id -u) == "0" ]
then
    ulimit -n 1000000
fi
