#!/bin/bash

# instalando ephemeral-hdfs
mkdir -p /mnt/ephemeral-hdfs/logs
mkdir -p /mnt/hadoop-logs

# instalando yarn logs, local dirs
mkdir -p /mnt/yarn-local
mkdir -p /mnt/yarn-logs

# Criando diretorios para o Hadoop e HDFS
# (por exemplo /mnt, /mnt2)
function create_hadoop_dirs {
  location=$1
  if [[ -e $location ]]; then
    mkdir -p $location/ephemeral-hdfs $location/hadoop/tmp
    chmod -R 755 $location/ephemeral-hdfs
    mkdir -p $location/hadoop/mrlocal $location/hadoop/mrlocal2
  fi
}

# Setando diretorios do Hadoop e Mesos no /mnt
create_hadoop_dirs /mnt
create_hadoop_dirs /mnt2
create_hadoop_dirs /mnt3
create_hadoop_dirs /mnt4
