#!/bin/bash

# Desabilitando o Transparent Huge Pages (THP)
if [[ -e /sys/kernel/mm/transparent_hugepage/enabled ]]; then
  echo never > /sys/kernel/mm/transparent_hugepage/enabled
fi

# Certificando se esteja no diretório spark-ec2
pushd /root/spark-ec2 > /dev/null

# Load the cluster variables set by the deploy script
# Carregando as variaveis do cluster setadas no script enviado
source ec2-variables.sh

# Setando hostname baseado no EC2 private DNS, e verificando se esta corretamente setado
PRIVATE_DNS=`wget -q -O - http://169.254.169.254/latest/meta-data/local-hostname`
hostname $PRIVATE_DNS
echo $PRIVATE_DNS > /etc/hostname
HOSTNAME=$PRIVATE_DNS

echo "checking/fixing resolution of hostname"
bash /root/spark-ec2/resolve-hostname.sh

# R3 ou I2 instancias pre formatadas com ext3 disks
instance_type=$(curl http://169.254.169.254/latest/meta-data/instance-type 2> /dev/null)

echo "Setting up slave on `hostname`... of type $instance_type"

if [[ $instance_type == r3* || $instance_type == i2* || $instance_type == hi1* ]]; then

  # Formato e montagem usando ext4, que possui o melhor desempenho entre ext3, ext4 e xfs
  EXT4_MOUNT_OPTS="defaults,noatime"
  rm -rf /mnt*
  mkdir /mnt

  # Para ativar o suporte TRIM, descomente a linha abaixo.
  #echo '/dev/sdb /mnt  ext4  defaults,noatime,discard 0 0' >> /etc/fstab
  mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0 /dev/sdb
  mount -o $EXT4_MOUNT_OPTS /dev/sdb /mnt

  if [[ $instance_type == "r3.8xlarge" || $instance_type == "hi1.4xlarge" ]]; then
    mkdir /mnt2
    # Para ativar o suporte TRIM, descomente a linha abaixo.
    #echo '/dev/sdc /mnt2  ext4  defaults,noatime,discard 0 0' >> /etc/fstab
    if [[ $instance_type == "r3.8xlarge" ]]; then
      mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0 /dev/sdc
      mount -o $EXT4_MOUNT_OPTS /dev/sdc /mnt2
    fi
    # Para ativar o suporte TRIM, descomente a seguinte linha
    #echo '/dev/sdf /mnt2  ext4  defaults,noatime,discard 0 0' >> /etc/fstab
    if [[ $instance_type == "hi1.4xlarge" ]]; then
      mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0 /dev/sdf
      mount -o $EXT4_MOUNT_OPTS /dev/sdf /mnt2
    fi
  fi
fi

# Aqui monta as opções para usar discos ext3 e xfs (os discos efemeral são ext3, mas usamos xfs para volumes EBS para formatá-los mais rapido)
XFS_MOUNT_OPTS="defaults,noatime,allocsize=8m"

function setup_ebs_volume {
  device=$1
  mount_point=$2
  if [[ -e $device ]]; then
    # Checa se o device mapper foi realmente formatado
    if ! blkid $device; then
      mkdir $mount_point
      yum install -q -y xfsprogs
      if mkfs.xfs -q $device; then
        mount -o $XFS_MOUNT_OPTS $device $mount_point
        chmod -R a+w $mount_point
      else
        # mkfs.xfs não esta instalado nesta maquina ou deu ruim;
        # delete o /vol
        rmdir $mount_point
      fi
    else
      # O volume EBS já formatado. Monte ele se ainda não estiver montado.
      if ! grep -qs '$mount_point' /proc/mounts; then
        mkdir $mount_point
        mount -o $XFS_MOUNT_OPTS $device $mount_point
        chmod -R a+w $mount_point
      fi
    fi
  fi
}

# Formatar e montar o EBS volume (/dev/sd[s, t, u, v, w, x, y, z]) as /vol[x] se o device mapper existir
setup_ebs_volume /dev/sds /vol0
setup_ebs_volume /dev/sdt /vol1
setup_ebs_volume /dev/sdu /vol2
setup_ebs_volume /dev/sdv /vol3
setup_ebs_volume /dev/sdw /vol4
setup_ebs_volume /dev/sdx /vol5
setup_ebs_volume /dev/sdy /vol6
setup_ebs_volume /dev/sdz /vol7

# Um EBS volume em /dev/sdv.
if [[ -e /vol3 && ! -e /vol ]]; then
  ln -s /vol3 /vol
fi

# Dando permissão de execução para os mounts no mnt
chmod -R a+w /mnt*

# Removendo ~/.ssh/known_hosts porque fica poluído quando comeca no / para muitos
# Clusters (novas máquinas vao surgir com nomes de host antigos)
rm -f /root/.ssh/known_hosts

# Criando Swap no /mnt
/root/spark-ec2/create-swap.sh $SWAP_MB

# Permitir que a memória seja comprometida. Ajuda no pyspark nos forkes dos nodes
# Essa config peguei dos Docs do Apache
echo 1 > /proc/sys/vm/overcommit_memory

cat /root/spark-ec2/github.hostkey >> /root/.ssh/known_hosts

# http://superuser.com/questions/771104/usr-bin-realpath-not-found-in-centos-6-5
echo '#!/bin/bash' > /usr/bin/realpath
echo 'readlink -e "$@"' >> /usr/bin/realpath
chmod a+x /usr/bin/realpath

popd > /dev/null

# Isto é para definir o ulimit para root e outros usuários
echo '* soft nofile 1000000' >> /etc/security/limits.conf
echo '* hard nofile 1000000' >> /etc/security/limits.conf

# Copia do dir H2 para o /root_dir nos slaves
cp -rf /root/spark-ec2/templates/root/h2 /root
