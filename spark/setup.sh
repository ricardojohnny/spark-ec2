#!/bin/bash

# Dir Spark
/root/spark-ec2/copy-dir /root/spark

# fairscheduler (modo de enfileiramento dos jobs)
mv /root/spark/conf/fairscheduler.xml.template /root/spark/conf/fairscheduler.xml

# Export envs customizadas
echo - e "Set Envs Customizadas..."
export "$(/root/spark-ec2/export.bash)"
