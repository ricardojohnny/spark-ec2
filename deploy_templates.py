#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>

from __future__ import with_statement

import os
import sys

# Deploy do diretorio com os arquivos de templates de configuração spark-ec2/templates
# Encontra a memória do sistema em KB e calcula o limite padrão da Spark
mem_command = "cat /proc/meminfo | grep MemTotal | awk '{print $2}'"
cpu_command = "nproc"

main_ram_kb = int(
  os.popen(mem_command).read().strip())

# Memória do Main. Tem que verificar também a memória dos Subordinates
first_subordinate = os.popen("cat /root/spark-ec2/subordinates | head -1").read().strip()

subordinate_mem_command = "ssh -t -o StrictHostKeyChecking=no %s %s" %\
        (first_subordinate, mem_command)

subordinate_cpu_command = "ssh -t -o StrictHostKeyChecking=no %s %s" %\
        (first_subordinate, cpu_command)

subordinate_ram_kb = int(os.popen(subordinate_mem_command).read().strip())

subordinate_cpus = int(os.popen(subordinate_cpu_command).read().strip())

system_ram_kb = min(subordinate_ram_kb, main_ram_kb)

system_ram_mb = system_ram_kb / 1024
subordinate_ram_mb = subordinate_ram_kb / 1024

# Tem que deixar alguma RAM para o sistema operacional, pras daemons do Hadoop e caches do sistema
if subordinate_ram_mb > 100*1024:
  subordinate_ram_mb = subordinate_ram_mb - 15 * 1024 # Saida de 15 GB RAM
elif subordinate_ram_mb > 60*1024:
  subordinate_ram_mb = subordinate_ram_mb - 10 * 1024 # Saida de 10 GB RAM
elif subordinate_ram_mb > 40*1024:
  subordinate_ram_mb = subordinate_ram_mb - 6 * 1024 # Saida de 6 GB RAM
elif subordinate_ram_mb > 20*1024:
  subordinate_ram_mb = subordinate_ram_mb - 3 * 1024 # Saida de 3 GB RAM
elif subordinate_ram_mb > 10*1024:
  subordinate_ram_mb = subordinate_ram_mb - 2 * 1024 # Saida de 2 GB RAM
else:
  subordinate_ram_mb = max(512, subordinate_ram_mb - 1300) # Saida de 1.3 GB RAM

# Fazendo o tachyon_mb como subordinate_ram_mb.
tachyon_mb = subordinate_ram_mb

worker_instances_str = ""
worker_cores = subordinate_cpus

if os.getenv("SPARK_WORKER_INSTANCES") != "":
  worker_instances = int(os.getenv("SPARK_WORKER_INSTANCES", 1))
  worker_instances_str = "%d" % worker_instances

  # Distribui igualmente os núcleos da CPU entre as instâncias dos Workers
  worker_cores = max(subordinate_cpus / worker_instances, 1)

template_vars = {
  "main_list": os.getenv("MASTERS"),
  "active_main": os.getenv("MASTERS").split("\n")[0],
  "subordinate_list": os.getenv("SLAVES"),
  "hdfs_data_dirs": os.getenv("HDFS_DATA_DIRS"),
  "mapred_local_dirs": os.getenv("MAPRED_LOCAL_DIRS"),
  "spark_local_dirs": os.getenv("SPARK_LOCAL_DIRS"),
  "spark_worker_mem": "%dm" % subordinate_ram_mb,
  "spark_worker_instances": worker_instances_str,
  "spark_worker_cores": "%d" %  worker_cores,
  "spark_main_opts": os.getenv("SPARK_MASTER_OPTS", ""),
  "spark_version": os.getenv("SPARK_VERSION"),
  "tachyon_version": os.getenv("TACHYON_VERSION"),
  "hadoop_major_version": os.getenv("HADOOP_MAJOR_VERSION"),
  "java_home": os.getenv("JAVA_HOME"),
  "default_tachyon_mem": "%dMB" % tachyon_mb,
  "system_ram_mb": "%d" % system_ram_mb,
  "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
  "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
}

template_dir="/root/spark-ec2/templates"

for path, dirs, files in os.walk(template_dir):
  if path.find(".svn") == -1:
    dest_dir = os.path.join('/', path[len(template_dir):])
    if not os.path.exists(dest_dir):
      os.makedirs(dest_dir)
    for filename in files:
      if filename[0] not in '#.~' and filename[-1] != '~':
        dest_file = os.path.join(dest_dir, filename)
        with open(os.path.join(path, filename)) as src:
          with open(dest_file, "w") as dest:
            print("Configurando " + dest_file)
            text = src.read()
            for key in template_vars:
              text = text.replace("{{" + key + "}}", template_vars[key] or '')
            dest.write(text)
            dest.close()
