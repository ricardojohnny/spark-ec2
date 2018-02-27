#!/bin/bash

# Dir Spark
/root/spark-ec2/copy-dir /root/spark

# fairscheduler (modo de enfileiramento dos jobs)
mv /root/spark/conf/fairscheduler.xml.template /root/spark/conf/fairscheduler.xml
