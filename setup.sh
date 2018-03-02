#!/bin/bash
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>

sudo yum install -y -q pssh

echo_time_diff () {
  local format='%Hh %Mm %Ss'

  local diff_secs="$(($3-$2))"
  echo "[timing] $1: " "$(date -u -d@"$diff_secs" +"$format")"
}

# Certificando se esteja no diretório spark-ec2
pushd /root/spark-ec2 > /dev/null

# Carregando as variáveis de ambiente específicas para este AMI
source /root/.bash_profile

# Load the cluster variables set by the deploy script
# Carregando as variaveis do cluster setadas no script enviado
source ec2-variables.sh

# Setando hostname baseado no EC2 private DNS, e verificando se esta corretamente setado
PRIVATE_DNS=`wget -q -O - http://169.254.169.254/latest/meta-data/local-hostname`
PUBLIC_DNS=`wget -q -O - http://169.254.169.254/latest/meta-data/hostname`
hostname $PRIVATE_DNS
echo $PRIVATE_DNS > /etc/hostname
export HOSTNAME=$PRIVATE_DNS

echo "Setando o hostname do node Spark..."

# Setando as variaveis do cluster nos master e slaves
echo "$MASTERS" > masters
echo "$SLAVES" > slaves

MASTERS=`cat masters`
NUM_MASTERS=`cat masters | wc -l`
OTHER_MASTERS=`cat masters | sed '1d'`
SLAVES=`cat slaves`
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=5"

if [[ "x$JAVA_HOME" == "x" ]] ; then
    echo "Expected JAVA_HOME to be set in .bash_profile!"
    exit 1
fi

if [[ `tty` == "not a tty" ]] ; then
    echo "Expecting a tty or pty! (use the ssh -t option)."
    exit 1
fi

echo "Verificando as permissoes nos scripts..."
find . -regex "^.+.\(sh\|py\)" | xargs chmod a+x

echo "RSYNC'ing /root/spark-ec2 para outros nodes do cluster..."
rsync_start_time="$(date +'%s')"
for node in $SLAVES $OTHER_MASTERS; do
  echo $node
  rsync -e "ssh $SSH_OPTS" -az /root/spark-ec2 $node:/root &
  scp $SSH_OPTS ~/.ssh/id_rsa $node:.ssh &
  sleep 0.1
done
wait
rsync_end_time="$(date +'%s')"
echo_time_diff "rsync /root/spark-ec2" "$rsync_start_time" "$rsync_end_time"

echo "Rodando o setup-slave em todos os nodes do cluster para montar o sistema de arquivos, etc..."
setup_slave_start_time="$(date +'%s')"
pssh --inline \
    --host "$MASTERS $SLAVES" \
    --user root \
    --extra-args "-t -t $SSH_OPTS" \
    --timeout 0 \
    "spark-ec2/setup-slave.sh"
setup_slave_end_time="$(date +'%s')"
echo_time_diff "setup-slave" "$setup_slave_start_time" "$setup_slave_end_time"

# Sync H2 Base to Slaves
echo "RSYNC'ing /root/h2 para outros nodes do cluster..."
rsync_start_time="$(date +'%s')"
for node in $SLAVES $OTHER_MASTERS; do
  echo $node
  rsync -e "ssh $SSH_OPTS" -az /root/h2 $node:/root &
  scp $SSH_OPTS ~/.ssh/id_rsa $node:.ssh &
  sleep 0.1
done
wait

# Sempre incluir o modulo do 'scala'
if [[ ! $MODULES =~ *scala* ]]; then
  MODULES=$(printf "%s\n%s\n" "scala" $MODULES)
fi

# Install / Init module
for module in $MODULES; do
  echo "Initializing $module"
  module_init_start_time="$(date +'%s')"
  if [[ -e $module/init.sh ]]; then
    source $module/init.sh
  fi
  module_init_end_time="$(date +'%s')"
  echo_time_diff "$module init" "$module_init_start_time" "$module_init_end_time"
  cd /root/spark-ec2
done

# Deploy templates
# TODO: Mover os templates de configuracao do per-module ?
echo "Criando arquivos de configuracao local..."
./deploy_templates.py

# Copiando spark conf por default
echo "Enviando arquivos de configuracao do Spark..."
chmod u+x /root/spark/conf/spark-env.sh
/root/spark-ec2/copy-dir /root/spark/conf

# Instalar mais modulos
for module in $MODULES; do
  echo "Iniciando $module"
  module_setup_start_time="$(date +'%s')"
  source ./$module/setup.sh
  sleep 0.1
  module_setup_end_time="$(date +'%s')"
  echo_time_diff "$module setup" "$module_setup_start_time" "$module_setup_end_time"
  cd /root/spark-ec2
done

popd > /dev/null
