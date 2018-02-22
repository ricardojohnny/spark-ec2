#!/bin/bash
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>

# NOTE: Removendo todos os rrds que possam estar em torno de um run anterior
rm -rf /var/lib/ganglia/rrds/*
rm -rf /mnt/ganglia/rrds/*

# Criando e certificando se o diretório de armazenamento rrd tenha permissões corretas
mkdir -p /mnt/ganglia/rrds
chown -R nobody:nobody /mnt/ganglia/rrds

# Instalando ganglia
# TODO: Remove this once the AMI has ganglia by default

GANGLIA_PACKAGES="ganglia ganglia-web ganglia-gmond ganglia-gmetad"

if ! rpm --quiet -q $GANGLIA_PACKAGES; then
  yum install -q -y $GANGLIA_PACKAGES;
fi
for node in $SLAVES $OTHER_MASTERS; do
  ssh -t -t $SSH_OPTS root@$node "if ! rpm --quiet -q $GANGLIA_PACKAGES; then yum install -q -y $GANGLIA_PACKAGES; fi" & sleep 0.3
done
wait

# Post-package install : Symlink /var/lib/ganglia/rrds para /mnt/ganglia/rrds
rmdir /var/lib/ganglia/rrds
ln -s /mnt/ganglia/rrds /var/lib/ganglia/rrds
