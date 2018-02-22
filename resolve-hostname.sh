#!/bin/bash

# Iniciando uma nova instância no VPC geralmente resulta que `hostname' retornam algo como ' ip-10-1-1-24', que por sua vez é
# não resolvivel. O que leva a problemas com o SparkUI que não starta ao iniciar com esse nome de host
# Este script mapeia ip privado para esse nome de host via '/etc/hosts'.
#

MAC=`wget -q -O - http://169.254.169.254/latest/meta-data/mac`
VCP_ID=`wget -q -O - http://169.254.169.254/latest/meta-data/network/interfaces/macs/${MAC}/vpc-id`
if [ -z "${VCP_ID}" ]; then
    exit 0
fi

SHORT_HOSTNAME=`hostname`

PRIVATE_IP=`wget -q -O - http://169.254.169.254/latest/meta-data/local-ipv4`

ping -c 1 -q "${SHORT_HOSTNAME}" > /dev/null 2>&1
if [ $? -ne 0  ]; then
    echo -e "\n# fixado no resolve-hostname.sh \n${PRIVATE_IP} ${SHORT_HOSTNAME}\n" >> /etc/hosts

    ping -c 1 -q "${SHORT_HOSTNAME}" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        # returno de problemas
        echo "Possivel bug: nao consegue corrigir a resolucao do nome de host local (script: resolve-hostname.sh)"
        return 62
    fi

fi
