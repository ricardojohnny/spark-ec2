#!/usr/bin/env bash

# Variaveis de ambiente para o funcionamento do script
export MASTERS="{{master_list}}"
export SLAVES="{{slave_list}}"
export HDFS_DATA_DIRS="{{hdfs_data_dirs}}"
export MAPRED_LOCAL_DIRS="{{mapred_local_dirs}}"
export SPARK_LOCAL_DIRS="{{spark_local_dirs}}"
export MODULES="{{modules}}"
export SPARK_VERSION="{{spark_version}}"
export TACHYON_VERSION="{{tachyon_version}}"
export HADOOP_MAJOR_VERSION="{{hadoop_major_version}}"
export SWAP_MB="{{swap}}"
export SPARK_WORKER_INSTANCES="{{spark_worker_instances}}"
export SPARK_MASTER_OPTS="{{spark_master_opts}}"
export AWS_ACCESS_KEY_ID="{{aws_access_key_id}}"
export AWS_SECRET_ACCESS_KEY="{{aws_secret_access_key}}"
