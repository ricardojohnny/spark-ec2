#!/bin/bash
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>

pushd /root > /dev/null
case "$HADOOP_MAJOR_VERSION" in
  1)
    echo "Nada para iniciar o MapReduce no Hadoop 2"
    ;;
  2)
    wget http://s3.amazonaws.com/spark-related-packages/mr1-2.0.0-mr1-cdh4.2.0.tar.gz
    tar -xvzf mr1-*.tar.gz > /tmp/spark-ec2_mapreduce.log
    rm mr1-*.tar.gz
    mv hadoop-2.0.0-mr1-cdh4.2.0/ mapreduce/
    ;;
  yarn)
    echo "Nada para iniciar MapReduce no Hadoop 2 YARN"
    ;;

  *)
     echo "ERROR: Versão Hadoop nao existe"
     return -1
esac
/root/spark-ec2/copy-dir /root/mapreduce
popd > /dev/null
