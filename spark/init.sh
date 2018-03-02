#!/bin/bash

pushd /root > /dev/null

if [ -d "spark/sbin" ]; then
  echo "Spark seems to be installed. Exiting."
  return
fi

# Github tag:
if [[ "$SPARK_VERSION" == *\|* ]]
then
  mkdir spark
  pushd spark > /dev/null
  git init
  repo=`python -c "print '$SPARK_VERSION'.split('|')[0]"`
  git_hash=`python -c "print '$SPARK_VERSION'.split('|')[1]"`
  git remote add origin $repo
  git fetch origin
  git checkout $git_hash
  sbt/sbt clean assembly
  sbt/sbt publish-local
  popd > /dev/null

# Pre-packaged spark version:
else
  case "$SPARK_VERSION" in
    *)
      if [[ "$HADOOP_MAJOR_VERSION" == "2" ]]; then
        wget http://s3.amazonaws.com/spark-related-packages/spark-$SPARK_VERSION-bin-hadoop2.7.tgz
      else
        wget http://mirror.nbtelecom.com.br/apache/spark/spark-$SPARK_VERSION/spark-$SPARK_VERSION-bin-hadoop2.7.tgz
      fi
      if [ $? != 0 ]; then
        echo "ERROR: Unknown Spark version"
        return -1
      fi
  esac

  echo "Unpacking Spark"
  tar xvzf spark-*.tgz > /tmp/spark-ec2_spark.log
  rm spark-*.tgz
  mv `ls -d spark-* | grep -v ec2` spark
fi

popd > /dev/null
