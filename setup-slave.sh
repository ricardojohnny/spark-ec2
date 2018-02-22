#!/bin/bash

<<<<<<< HEAD
# Disable Transparent Huge Pages (THP)
# THP can result in system thrashing (high sys usage) due to frequent defrags of memory.
# Most systems recommends turning THP off.
=======
# Desabilitando o Transparent Huge Pages (THP)
>>>>>>> origin/master
if [[ -e /sys/kernel/mm/transparent_hugepage/enabled ]]; then
  echo never > /sys/kernel/mm/transparent_hugepage/enabled
fi

<<<<<<< HEAD
# Make sure we are in the spark-ec2 directory
pushd /root/spark-ec2 > /dev/null

source ec2-variables.sh

# Set hostname based on EC2 private DNS name, so that it is set correctly
# even if the instance is restarted with a different private DNS name
PRIVATE_DNS=`wget -q -O - http://169.254.169.254/latest/meta-data/local-hostname`
hostname $PRIVATE_DNS
echo $PRIVATE_DNS > /etc/hostname
HOSTNAME=$PRIVATE_DNS  # Fix the bash built-in hostname variable too
=======
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
>>>>>>> origin/master

echo "checking/fixing resolution of hostname"
bash /root/spark-ec2/resolve-hostname.sh

<<<<<<< HEAD
# Work around for R3 or I2 instances without pre-formatted ext3 disks
=======
# R3 ou I2 instancias pre formatadas com ext3 disks
>>>>>>> origin/master
instance_type=$(curl http://169.254.169.254/latest/meta-data/instance-type 2> /dev/null)

echo "Setting up slave on `hostname`... of type $instance_type"

if [[ $instance_type == r3* || $instance_type == i2* || $instance_type == hi1* ]]; then
<<<<<<< HEAD
  # Format & mount using ext4, which has the best performance among ext3, ext4, and xfs based
  # on our shuffle heavy benchmark
  EXT4_MOUNT_OPTS="defaults,noatime"
  rm -rf /mnt*
  mkdir /mnt
  # To turn TRIM support on, uncomment the following line.
=======
  # Formato e montagem usando ext4, que possui o melhor desempenho entre ext3, ext4 e xfs
  EXT4_MOUNT_OPTS="defaults,noatime"
  rm -rf /mnt*
  mkdir /mnt
  # Para ativar o suporte TRIM, descomente a linha abaixo.
>>>>>>> origin/master
  #echo '/dev/sdb /mnt  ext4  defaults,noatime,discard 0 0' >> /etc/fstab
  mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0 /dev/sdb
  mount -o $EXT4_MOUNT_OPTS /dev/sdb /mnt

  if [[ $instance_type == "r3.8xlarge" || $instance_type == "hi1.4xlarge" ]]; then
    mkdir /mnt2
<<<<<<< HEAD
    # To turn TRIM support on, uncomment the following line.
    #echo '/dev/sdc /mnt2  ext4  defaults,noatime,discard 0 0' >> /etc/fstab
    if [[ $instance_type == "r3.8xlarge" ]]; then
      mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0 /dev/sdc      
      mount -o $EXT4_MOUNT_OPTS /dev/sdc /mnt2
    fi
    # To turn TRIM support on, uncomment the following line.
    #echo '/dev/sdf /mnt2  ext4  defaults,noatime,discard 0 0' >> /etc/fstab
    if [[ $instance_type == "hi1.4xlarge" ]]; then
      mkfs.ext4 -E lazy_itable_init=0,lazy_journal_init=0 /dev/sdf      
      mount -o $EXT4_MOUNT_OPTS /dev/sdf /mnt2
    fi    
  fi
fi

# Mount options to use for ext3 and xfs disks (the ephemeral disks
# are ext3, but we use xfs for EBS volumes to format them faster)
=======
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
>>>>>>> origin/master
XFS_MOUNT_OPTS="defaults,noatime,allocsize=8m"

function setup_ebs_volume {
  device=$1
  mount_point=$2
  if [[ -e $device ]]; then
<<<<<<< HEAD
    # Check if device is already formatted
=======
    # Checa se o device mapper foi realmente formatado
>>>>>>> origin/master
    if ! blkid $device; then
      mkdir $mount_point
      yum install -q -y xfsprogs
      if mkfs.xfs -q $device; then
        mount -o $XFS_MOUNT_OPTS $device $mount_point
        chmod -R a+w $mount_point
      else
<<<<<<< HEAD
        # mkfs.xfs is not installed on this machine or has failed;
        # delete /vol so that the user doesn't think we successfully
        # mounted the EBS volume
        rmdir $mount_point
      fi
    else
      # EBS volume is already formatted. Mount it if its not mounted yet.
=======
        # mkfs.xfs não esta instalado nesta maquina ou deu ruim;
        # delete o /vol
        rmdir $mount_point
      fi
    else
      # O volume EBS já formatado. Monte ele se ainda não estiver montado.
>>>>>>> origin/master
      if ! grep -qs '$mount_point' /proc/mounts; then
        mkdir $mount_point
        mount -o $XFS_MOUNT_OPTS $device $mount_point
        chmod -R a+w $mount_point
      fi
    fi
  fi
}

<<<<<<< HEAD
# Format and mount EBS volume (/dev/sd[s, t, u, v, w, x, y, z]) as /vol[x] if the device exists
=======
# Formatar e montar o EBS volume (/dev/sd[s, t, u, v, w, x, y, z]) as /vol[x] se o device mapper existir
>>>>>>> origin/master
setup_ebs_volume /dev/sds /vol0
setup_ebs_volume /dev/sdt /vol1
setup_ebs_volume /dev/sdu /vol2
setup_ebs_volume /dev/sdv /vol3
setup_ebs_volume /dev/sdw /vol4
setup_ebs_volume /dev/sdx /vol5
setup_ebs_volume /dev/sdy /vol6
setup_ebs_volume /dev/sdz /vol7

<<<<<<< HEAD
# Alias vol to vol3 for backward compatibility: the old spark-ec2 script supports only attaching
# one EBS volume at /dev/sdv.
=======
# Um EBS volume em /dev/sdv.
>>>>>>> origin/master
if [[ -e /vol3 && ! -e /vol ]]; then
  ln -s /vol3 /vol
fi

<<<<<<< HEAD
# Make data dirs writable by non-root users, such as CDH's hadoop user
chmod -R a+w /mnt*

# Remove ~/.ssh/known_hosts because it gets polluted as you start/stop many
# clusters (new machines tend to come up under old hostnames)
rm -f /root/.ssh/known_hosts

# Create swap space on /mnt
/root/spark-ec2/create-swap.sh $SWAP_MB

# Allow memory to be over committed. Helps in pyspark where we fork
echo 1 > /proc/sys/vm/overcommit_memory

# Add github to known hosts to get git@github.com clone to work
# TODO(shivaram): Avoid duplicate entries ?
cat /root/spark-ec2/github.hostkey >> /root/.ssh/known_hosts

# Create /usr/bin/realpath which is used by R to find Java installations
# NOTE: /usr/bin/realpath is missing in CentOS AMIs. See
=======
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

>>>>>>> origin/master
# http://superuser.com/questions/771104/usr-bin-realpath-not-found-in-centos-6-5
echo '#!/bin/bash' > /usr/bin/realpath
echo 'readlink -e "$@"' >> /usr/bin/realpath
chmod a+x /usr/bin/realpath

popd > /dev/null

<<<<<<< HEAD
# this is to set the ulimit for root and other users
echo '* soft nofile 1000000' >> /etc/security/limits.conf
echo '* hard nofile 1000000' >> /etc/security/limits.conf
=======
# Isto é para definir o ulimit para root e outros usuários
echo '* soft nofile 1000000' >> /etc/security/limits.conf
echo '* hard nofile 1000000' >> /etc/security/limits.conf
>>>>>>> origin/master
