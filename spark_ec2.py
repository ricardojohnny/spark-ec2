#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Wealthsystems [[BDD Project]]
# Ricardo Johnny <ricardo.jesus@wssim.com.br>

from __future__ import division, print_function, with_statement

import codecs
import hashlib
import itertools
import logging
import os
import os.path
import pipes
import random
import shutil
import string
from stat import S_IRUSR
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time
import warnings
import boto.ec2.networkinterface
from datetime import datetime
from optparse import OptionParser
from sys import stderr

if sys.version < "3":
    from urllib2 import urlopen, Request, HTTPError
else:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    raw_input = input
    xrange = range

SPARK_EC2_VERSION = "2.2.1"
SPARK_EC2_DIR = os.path.dirname(os.path.realpath(__file__))

VALID_SPARK_VERSIONS = set([
    "2.1.0",
    "2.1.1",
    "2.2.0",
    "2.2.1",
    "2.3.0"
])

DEFAULT_SPARK_VERSION = SPARK_EC2_VERSION
DEFAULT_SPARK_GITHUB_REPO = "https://github.com/apache/spark"

# Default location para pegar os scripts do projeto (e ami-list)
DEFAULT_SPARK_EC2_GITHUB_REPO = "https://github.com/ricardojohnny/spark-ec2"
DEFAULT_SPARK_EC2_BRANCH = "main"


def setup_external_libs(libs):
    """
    Download externo das libraries do PyPI no SPARK_EC2_DIR/lib/ e linkar para nosso PATH.
    """
    PYPI_URL_PREFIX = "https://pypi.python.org/packages/source"
    SPARK_EC2_LIB_DIR = os.path.join(SPARK_EC2_DIR, "lib")

    if not os.path.exists(SPARK_EC2_LIB_DIR):
        print("Fazendo o download de bibliotecas externas para o spark-ec2 necessarias para o PyPI em {path}...".format(
            path=SPARK_EC2_LIB_DIR
        ))
        print("Esta deve ser uma operacao unica.")
        os.mkdir(SPARK_EC2_LIB_DIR)

    for lib in libs:
        versioned_lib_name = "{n}-{v}".format(n=lib["name"], v=lib["version"])
        lib_dir = os.path.join(SPARK_EC2_LIB_DIR, versioned_lib_name)

        if not os.path.isdir(lib_dir):
            tgz_file_path = os.path.join(SPARK_EC2_LIB_DIR, versioned_lib_name + ".tar.gz")
            print(" - Downloading {lib}...".format(lib=lib["name"]))
            download_stream = urlopen(
                "{prefix}/{first_letter}/{lib_name}/{lib_name}-{lib_version}.tar.gz".format(
                    prefix=PYPI_URL_PREFIX,
                    first_letter=lib["name"][:1],
                    lib_name=lib["name"],
                    lib_version=lib["version"]
                )
            )
            with open(tgz_file_path, "wb") as tgz_file:
                tgz_file.write(download_stream.read())
            with open(tgz_file_path, "rb") as tar:
                if hashlib.md5(tar.read()).hexdigest() != lib["md5"]:
                    print("ERROR: Erro de md5sum para {lib}.".format(lib=lib["name"]), file=stderr)
                    sys.exit(1)
            tar = tarfile.open(tgz_file_path)
            tar.extractall(path=SPARK_EC2_LIB_DIR)
            tar.close()
            os.remove(tgz_file_path)
            print(" - Finalizando o download de {lib}.".format(lib=lib["name"]))
        sys.path.insert(1, lib_dir)


# Somente bibliotecas PyPI são suportadas.
external_libs = [
    {
        "name": "boto",
        "version": "2.34.0",
        "md5": "5556223d2d0cc4d06dd4829e671dcecd"
    }
]

setup_external_libs(external_libs)

import boto
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType, EBSBlockDeviceType
from boto import ec2


class UsageError(Exception):
    pass


# Argumentos da linha de comando para facilitar para a Monsanto
def parse_args():
    parser = OptionParser(
        prog="spark-ec2",
        version="%prog {v}".format(v=SPARK_EC2_VERSION),
        usage="%prog [options] <action> <cluster_name>\n\n"
        + "<action> pode ser: launch, destroy, login, stop, start, get-main, reboot-subordinates")

    parser.add_option(
        "-s", "--subordinates", type="int", default=1,
        help="Numero de subordinates a serem iniciados (padrao: %default)")
    parser.add_option(
        "-w", "--wait", type="int",
        help="DEPRECATED (remover o -- nao mais necessario) - Segundos para aguardar a criacao de nos")
    parser.add_option(
        "-k", "--key-pair",
        help="Key pair a ser usado nas instancias")
    parser.add_option(
        "-i", "--identity-file",
        help="SSH private key usado para login nas instancias")
    parser.add_option(
        "-p", "--profile", default=None,
        help="Se tiver outros perfis (AWS ou boto config), voce pode configurar " +
             "perfis adicionais, usando esta opcao (default: %default)")
    parser.add_option(
        "-t", "--instance-type", default="m1.large",
        help="Tipo da instancia a ser usada no cluster (default: %default). " +
             "WARNING: deve ser 64-bit; instancias small nao irao rodar")
    parser.add_option(
        "-m", "--main-instance-type", default="",
        help="Tipo de instancia do Main (deixe em branco para ser igual as outras)")
    parser.add_option(
        "-r", "--region", default="us-east-1",
        help="Region EC2 usada para iniciar instancias (default: %default)")
    parser.add_option(
        "-z", "--zone", default="",
        help="Zona de disponibilidade para iniciar instancias ou 'all' para espalhar " +
             "subordinates em multiplas zonas (um adicional de $0.01/Gb por bandwidth" +
             "sera aplicado entre as zonas) (default: unica zona escolhida aleatoriamente)")
    parser.add_option(
        "-a", "--ami",
        help="Amazon Machine Image ID (id da imagem a ser usada no cluster)")
    parser.add_option(
        "-v", "--spark-version", default=DEFAULT_SPARK_VERSION,
        help="Versao do Spark: 'X.Y.Z' ou um hash especifico no git (default: %default)")
    parser.add_option(
        "--spark-git-repo",
        default=DEFAULT_SPARK_GITHUB_REPO,
        help="Repo Oficial do Spark no Github, check-out fornecido no commit hash (default: %default)")
    parser.add_option(
        "--spark-ec2-git-repo",
        default=DEFAULT_SPARK_EC2_GITHUB_REPO,
        help="Repo oficial do projeto no Gitlab WSSIM (default: %default)")
    parser.add_option(
        "--spark-ec2-git-branch",
        default=DEFAULT_SPARK_EC2_BRANCH,
        help="Branch do projeto spark-ec2 no Gitlab (default: %default)")
    parser.add_option(
        "--deploy-root-dir",
        default=None,
        help="O deploy sera feito no / primeiro no main. " +
             "Observe esse local eh tratado como a rsync: " +
             "Se deixar em branco, o ultimo diretorio setado no parametro --deploy-root-dir path sera criado " +
             "no / antes de copiar o conteudo. Se informar a barra, " +
             "o diretorio nao sera criado e seus conteudos serao copiados diretamente no /. " +
             "(default: %default).")
    parser.add_option(
        "--hadoop-major-version", default="yarn",
        help="Versao principal do Hadoop. As opcoes validas sao 1 (Hadoop 1.0.4), 2 (CDH 4.2.0), yarn " +
             "(Hadoop 2.7.3) (default: %default)")
    parser.add_option(
        "-D", metavar="[ADDRESS:]PORT", dest="proxy_port",
        help="Usando SSH para encaminhamento de porta dinamica e criar um proxy SOCKS no " +
             "endereco local informado (para uso com login)")
    parser.add_option(
        "--resume", action="store_true", default=False,
        help="Reinicie a instalacao em um cluster previamente iniciado" +
             "(para debugging)")
    parser.add_option(
        "--ebs-vol-size", metavar="SIZE", type="int", default=80,
        help="Tamanho (em GB) de cada volume EBS.")
    parser.add_option(
        "--ebs-vol-type", default="gp2",
        help="Tipo do volume EBS (e.g. 'gp2', 'standard').")
    parser.add_option(
        "--ebs-vol-num", type="int", default=2,
        help="Numero de volumes EBS para anexar a cada node como /vol[x]. " +
             "Os volumes sera deletado quando a instancia terminar. " +
             "Somente possivel em EBS-backed AMIs. " +
             "Os volumes do EBS sao apenas anexados se informar --ebs-vol-size > 0. " +
             "Apenas suporta ate 8 volumes EBS, sendo que o primeiro pertence ao /root/spark.")
    parser.add_option(
        "--placement-group", type="string", default=None,
        help="Qual a regra de grupo que as instancias serao lancadas. " +
             "Assume que o grupo de colocation ja esta criado.")
    parser.add_option(
        "--swap", metavar="SWAP", type="int", default=1024,
        help="Setar a Swap que sera alocada por node, em MB (default: %default)")
    parser.add_option(
        "--spot-price", metavar="PRICE", type="float",
        help="Se especificado, inicie os subordinates como instancias Spots " +
             "preco maximo (em dolar)")
    parser.add_option(
        "--ganglia", action="store_true", default=True,
        help="Instalar o Ganglia monitoring no cluster (default: %default). NOTA: " +
             "a pagina do Ganglia sera acessivel ao publico (vericar isso somente para a rede da Wealthsystems)")
    parser.add_option(
        "--no-ganglia", action="store_false", dest="ganglia",
        help="Disabilitar o Ganglia monitoring no cluster")
    parser.add_option(
        "-u", "--user", default="root",
        help="Usuario SSH que deseja se conectar (default: %default)")
    parser.add_option(
        "--delete-groups", action="store_true", default=False,
        help="Ao destruir um cluster, exclua os grupos de seguranca criados")
    parser.add_option(
        "--use-existing-main", action="store_true", default=False,
        help="Iniciar novos workers, mas usar um Main parado ja existente")
    parser.add_option(
        "--worker-instances", type="int", default=1,
        help="Numero de instancias por worker: variable SPARK_WORKER_INSTANCES. Nao usado se o YARN " +
             "eh usado como a versao principal de Hadoop (default: %default)")
    parser.add_option(
        "--main-opts", type="string", default="",
        help="Opts extras para dar ao main atraves da variavel SPARK_MASTER_OPTS " +
             "(e.g -Dspark.worker.timeout=180)")
    parser.add_option(
        "--user-data", type="string", default="",
        help="Path do arquivo user-data (a maioria das AMIs interpreta isso como um script de inicializacao)")
    parser.add_option(
        "--authorized-address", type="string", default="0.0.0.0/0",
        help="Endereco para autorizar em grupos de seguranca criados (default: %default)")
    parser.add_option(
        "--additional-security-group", type="string", default="",
        help="Security group para as instancias")
    parser.add_option(
        "--additional-tags", type="string", default="",
        help="Tags adicionais para as instacias; as tags sao separadas por virgulas, enquanto o nome e " +
             "valores por dois pontos; ex: \"Task:BDDSparkProject,Env:production\"")
    parser.add_option(
        "--tag-volumes", action="store_true", default=False,
        help="Aplique as tags dadas em --additional-tags para os volumees EBS " +
             "anexados as instancias do cluster.")
    parser.add_option(
        "--copy-aws-credentials", action="store_true", default=False,
        help="Adicione credenciais AWS a configuracao do hadoop para permitir que o Spark acesse S3")
    parser.add_option(
        "--subnet-id", default=None,
        help="VPC Subnet ja criadas por voce, informe o ID dela aqui")
    parser.add_option(
        "--vpc-id", default=None,
        help="VPC ja criadas por voce, informe o ID dela aqui")
    parser.add_option(
        "--private-ips", action="store_true", default=False,
        help="Use IPs privados para instancias em vez de publico se VPC/subnet " +
             "exigir.")
    parser.add_option(
        "--instance-initiated-shutdown-behavior", default="stop",
        choices=["stop", "terminate"],
        help="Se as instancias devem terminar quando desligar ou simplesmente parar")
    parser.add_option(
        "--instance-profile-name", default=None,
        help="Nome do perfil IAM para iniciar nas instancias")

    (opts, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        sys.exit(1)
    (action, cluster_name) = args

    # Boto config check
    # http://boto.cloudhackers.com/en/latest/boto_config_tut.html
    # http://docs.pythonboto.org/en/latest/ec2_tut.html
    # http://docs.pythonboto.org/en/latest/emr_tut.html
    home_dir = os.getenv('HOME')
    if home_dir is None or not os.path.isfile(home_dir + '/.boto'):
        if not os.path.isfile('/etc/boto.cfg'):
            # Se não houver configuração do boto, verifique as credenciais do Aws
            if not os.path.isfile(home_dir + '/.aws/credentials'):
                if os.getenv('AWS_ACCESS_KEY_ID') is None:
                    print("ERROR: A variavel de ambiente AWS_ACCESS_KEY_ID nao foi setada, exporte ela no bashrc",
                          file=stderr)
                    sys.exit(1)
                if os.getenv('AWS_SECRET_ACCESS_KEY') is None:
                    print("ERROR: A variavel de ambiente AWS_SECRET_ACCESS_KEY nao foi setada, exporte ela no bashrc",
                          file=stderr)
                    sys.exit(1)
    return (opts, action, cluster_name)


# Obter o nome do grupo de segurança EC2 se existir, caso contrario crie um
def get_or_make_group(conn, name, vpc_id):
    groups = conn.get_all_security_groups()
    group = [g for g in groups if g.name == name]
    if len(group) > 0:
        return group[0]
    else:
        print("Criando security group " + name)
        return conn.create_security_group(name, "BDD Spark EC2", vpc_id)

def validate_spark_hadoop_version(spark_version, hadoop_version):
    if "." in spark_version:
        parts = spark_version.split(".")
        if parts[0].isdigit():
            spark_major_version = float(parts[0])
            if spark_major_version > 1.0 and hadoop_version != "yarn":
              print("Spark version: {v}, nao suporta essa versao do Hadoop: {hv}".
                    format(v=spark_version, hv=hadoop_version), file=stderr)
              sys.exit(1)
        else:
            print("Versao do Spark invalida: {v}".format(v=spark_version), file=stderr)
            sys.exit(1)

def get_validate_spark_version(version, repo):
    if "." in version:
        # Removendo os "v" do inicio das entradas como v1.5.0
        version = version.lstrip("v")
        if version not in VALID_SPARK_VERSIONS:
            print("Nada sobre essa versao do Spark: {v}".format(v=version), file=stderr)
            sys.exit(1)
        return version
    else:
        github_commit_url = "{repo}/commit/{commit_hash}".format(repo=repo, commit_hash=version)
        request = Request(github_commit_url)
        request.get_method = lambda: 'HEAD'
        try:
            response = urlopen(request)
        except HTTPError as e:
            print("Nao foi possível validar esse commit do Spark: {url}".format(url=github_commit_url),
                  file=stderr)
            print("Codigo de resposta HTTP recebido de {code}.".format(code=e.code), file=stderr)
            sys.exit(1)
        return version


# Source: http://aws.amazon.com/amazon-linux-ami/instance-type-matrix/
# Last Updated: 2017-12-05
# Para facilitar a manutenção, temos que manter este dicionário introduzido manualmente ordenado por chave.
EC2_INSTANCE_TYPES = {
    "c1.medium":   "pvm",
    "c1.xlarge":   "pvm",
    "c3.large":    "hvm",
    "c3.xlarge":   "hvm",
    "c3.2xlarge":  "hvm",
    "c3.4xlarge":  "hvm",
    "c3.8xlarge":  "hvm",
    "c4.large":    "hvm",
    "c4.xlarge":   "hvm",
    "c4.2xlarge":  "hvm",
    "c4.4xlarge":  "hvm",
    "c4.8xlarge":  "hvm",
    "cc1.4xlarge": "hvm",
    "cc2.8xlarge": "hvm",
    "cg1.4xlarge": "hvm",
    "cr1.8xlarge": "hvm",
    "d2.xlarge":   "hvm",
    "d2.2xlarge":  "hvm",
    "d2.4xlarge":  "hvm",
    "d2.8xlarge":  "hvm",
    "g2.2xlarge":  "hvm",
    "g2.8xlarge":  "hvm",
    "hi1.4xlarge": "pvm",
    "hs1.8xlarge": "pvm",
    "i2.xlarge":   "hvm",
    "i2.2xlarge":  "hvm",
    "i2.4xlarge":  "hvm",
    "i2.8xlarge":  "hvm",
    "m1.small":    "pvm",
    "m1.medium":   "pvm",
    "m1.large":    "pvm",
    "m1.xlarge":   "pvm",
    "m2.xlarge":   "pvm",
    "m2.2xlarge":  "pvm",
    "m2.4xlarge":  "pvm",
    "m3.medium":   "hvm",
    "m3.large":    "hvm",
    "m3.xlarge":   "hvm",
    "m3.2xlarge":  "hvm",
    "m4.large":    "hvm",
    "m4.xlarge":   "hvm",
    "m4.2xlarge":  "hvm",
    "m4.4xlarge":  "hvm",
    "m4.10xlarge": "hvm",
    "r3.large":    "hvm",
    "r3.xlarge":   "hvm",
    "r3.2xlarge":  "hvm",
    "r3.4xlarge":  "hvm",
    "r3.8xlarge":  "hvm",
    "t1.micro":    "pvm",
    "t2.micro":    "hvm",
    "t2.small":    "hvm",
    "t2.medium":   "hvm",
    "t2.large":    "hvm",
    "t2.xlarge":   "hvm",
}


# Tentando resolver uma imagem IAM adequada, dada a arquitetura e a região da solicitação.
# OBS: isso foi um cara que fez em cima da Rackspace, mas nao encontrei mais o link
def get_spark_ami(opts):
    if opts.instance_type in EC2_INSTANCE_TYPES:
        instance_type = EC2_INSTANCE_TYPES[opts.instance_type]
    else:
        instance_type = "pvm"
        print("Don't recognize %s, assuming type is pvm" % opts.instance_type, file=stderr)

    # Prefixo de URL a partir do qual obter informações AMI
    ami_prefix = "{r}/{b}/ami-list".format(
        r=opts.spark_ec2_git_repo.replace("https://github.com", "https://raw.github.com", 1),
        b=opts.spark_ec2_git_branch)

    ami_path = "%s/%s/%s" % (ami_prefix, opts.region, instance_type)
    reader = codecs.getreader("ascii")
    try:
        ami = reader(urlopen(ami_path)).read().strip()
    except:
        print("Nao foi possivel resolver essa AMI: " + ami_path, file=stderr)
        sys.exit(1)

    print("Spark AMI: " + ami)
    return ami


# Iniciando um cluster, configurando seus grupos de segurança,
# e então configura as novas instâncias neles.
# Retorna objetos de reserva EC2 para o Main e os Workers
# Falha se já existirem instâncias em grupos do cluster.
def launch_cluster(conn, opts, cluster_name):
    if opts.identity_file is None:
        print("ERROR: Deve fornecer um arquivo de identidade (-i) para conexoes ssh.", file=stderr)
        sys.exit(1)

    if opts.key_pair is None:
        print("ERROR: Deve fornecer um nome de par de chave (-k) para usar em instancias.", file=stderr)
        sys.exit(1)

    user_data_content = None
    if opts.user_data:
        with open(opts.user_data) as user_data_file:
            user_data_content = user_data_file.read()

    print("Configurando security groups...")
    main_group = get_or_make_group(conn, cluster_name + "-main", opts.vpc_id)
    subordinate_group = get_or_make_group(conn, cluster_name + "-subordinates", opts.vpc_id)
    authorized_address = opts.authorized_address
    if main_group.rules == []:  # Aqui o Grupo ja foi criado
        if opts.vpc_id is None:
            main_group.authorize(src_group=main_group)
            main_group.authorize(src_group=subordinate_group)
        else:
            main_group.authorize(ip_protocol='icmp', from_port=-1, to_port=-1,
                                   src_group=main_group)
            main_group.authorize(ip_protocol='tcp', from_port=0, to_port=65535,
                                   src_group=main_group)
            main_group.authorize(ip_protocol='udp', from_port=0, to_port=65535,
                                   src_group=main_group)
            main_group.authorize(ip_protocol='icmp', from_port=-1, to_port=-1,
                                   src_group=subordinate_group)
            main_group.authorize(ip_protocol='tcp', from_port=0, to_port=65535,
                                   src_group=subordinate_group)
            main_group.authorize(ip_protocol='udp', from_port=0, to_port=65535,
                                   src_group=subordinate_group)
        main_group.authorize('tcp', 22, 22, authorized_address)
        main_group.authorize('tcp', 8080, 8081, authorized_address)
        main_group.authorize('tcp', 18080, 18080, authorized_address)
        main_group.authorize('tcp', 19999, 19999, authorized_address)
        main_group.authorize('tcp', 50030, 50030, authorized_address)
        main_group.authorize('tcp', 50070, 50070, authorized_address)
        main_group.authorize('tcp', 60070, 60070, authorized_address)
        main_group.authorize('tcp', 4040, 4045, authorized_address)
        main_group.authorize('tcp', 8787, 8787, authorized_address)
        main_group.authorize('tcp', 8090, 8090, authorized_address)
        # HDFS NFS gateway requer as portas 111,2049,4242 para tcp & udp
        main_group.authorize('tcp', 111, 111, authorized_address)
        main_group.authorize('udp', 111, 111, authorized_address)
        main_group.authorize('tcp', 2049, 2049, authorized_address)
        main_group.authorize('udp', 2049, 2049, authorized_address)
        main_group.authorize('tcp', 4242, 4242, authorized_address)
        main_group.authorize('udp', 4242, 4242, authorized_address)
        # RM em YARN mode usa 8088
        main_group.authorize('tcp', 8088, 8088, authorized_address)
        if opts.ganglia:
            main_group.authorize('tcp', 5080, 5080, authorized_address)
    if subordinate_group.rules == []:  # Grupo de subordinates criado
        if opts.vpc_id is None:
            subordinate_group.authorize(src_group=main_group)
            subordinate_group.authorize(src_group=subordinate_group)
        else:
            subordinate_group.authorize(ip_protocol='icmp', from_port=-1, to_port=-1,
                                  src_group=main_group)
            subordinate_group.authorize(ip_protocol='tcp', from_port=0, to_port=65535,
                                  src_group=main_group)
            subordinate_group.authorize(ip_protocol='udp', from_port=0, to_port=65535,
                                  src_group=main_group)
            subordinate_group.authorize(ip_protocol='icmp', from_port=-1, to_port=-1,
                                  src_group=subordinate_group)
            subordinate_group.authorize(ip_protocol='tcp', from_port=0, to_port=65535,
                                  src_group=subordinate_group)
            subordinate_group.authorize(ip_protocol='udp', from_port=0, to_port=65535,
                                  src_group=subordinate_group)
        subordinate_group.authorize('tcp', 22, 22, authorized_address)
        subordinate_group.authorize('tcp', 8080, 8081, authorized_address)
        subordinate_group.authorize('tcp', 50060, 50060, authorized_address)
        subordinate_group.authorize('tcp', 50075, 50075, authorized_address)
        subordinate_group.authorize('tcp', 60060, 60060, authorized_address)
        subordinate_group.authorize('tcp', 60075, 60075, authorized_address)

    # Verifique se existem instâncias nos grupos
    existing_mains, existing_subordinates = get_existing_cluster(conn, opts, cluster_name,
                                                             die_on_error=False)
    if existing_subordinates or (existing_mains and not opts.use_existing_main):
        print("ERROR: Ja existe instancias rodando no grupo %s or %s" %
              (main_group.name, subordinate_group.name), file=stderr)
        sys.exit(1)

    # Explorando a Spark AMI
    if opts.ami is None:
        opts.ami = get_spark_ami(opts)

    # teve algumas resoluções achadas aqui https://github.com/boto/boto/issues/350
    additional_group_ids = []
    if opts.additional_security_group:
        additional_group_ids = [sg.id
                                for sg in conn.get_all_security_groups()
                                if opts.additional_security_group in (sg.name, sg.id)]
    print("Iniciando as instancias...")

    try:
        image = conn.get_all_images(image_ids=[opts.ami])[0]
    except:
        print("AMI nao encontrada " + opts.ami, file=stderr)
        sys.exit(1)

    # Cria um block device mapper para adicionar volumes EBS se solicitado.
    block_map = BlockDeviceMapping()
    if opts.ebs_vol_size > 0:
        for i in range(opts.ebs_vol_num):
            device = EBSBlockDeviceType()
            device.size = opts.ebs_vol_size
            device.volume_type = opts.ebs_vol_type
            device.delete_on_termination = True
            block_map["/dev/sd" + chr(ord('s') + i)] = device

    # AWS ignora o device mapper especificado pela nossa AMI nas instancias de modelo M3.
    if opts.instance_type.startswith('m3.'):
        for i in range(get_num_disks(opts.instance_type)):
            dev = BlockDeviceType()
            dev.ephemeral_name = 'ephemeral%d' % i
            # O primeiro ephemeral drive eh /dev/sdb.
            name = '/dev/sd' + string.ascii_letters[i + 1]
            block_map[name] = dev


    # Criando subordinates (testando instancias Spot)
    if opts.spot_price is not None:
        # Iniciar instâncias Spot com o preço solicitado
        print("Solicitando %d subordinates em instancias spot pelo valor $%.3f" %
              (opts.subordinates, opts.spot_price))
        zones = get_zones(conn, opts)
        num_zones = len(zones)
        i = 0
        my_req_ids = []
        for zone in zones:
            num_subordinates_this_zone = get_partition(opts.subordinates, num_zones, i)
            subordinate_reqs = conn.request_spot_instances(
                price=opts.spot_price,
                image_id=opts.ami,
                launch_group="launch-group-%s" % cluster_name,
                placement=zone,
                count=num_subordinates_this_zone,
                key_name=opts.key_pair,
                security_group_ids=[subordinate_group.id] + additional_group_ids,
                instance_type=opts.instance_type,
                block_device_map=block_map,
                subnet_id=opts.subnet_id,
                placement_group=opts.placement_group,
                user_data=user_data_content,
                instance_profile_name=opts.instance_profile_name)
            my_req_ids += [req.id for req in subordinate_reqs]
            i += 1

        print("Aguardando por instancias spot...")
        try:
            while True:
                time.sleep(10)
                reqs = conn.get_all_spot_instance_requests()
                id_to_req = {}
                for r in reqs:
                    id_to_req[r.id] = r
                active_instance_ids = []
                for i in my_req_ids:
                    if i in id_to_req and id_to_req[i].state == "active":
                        active_instance_ids.append(id_to_req[i].instance_id)
                if len(active_instance_ids) == opts.subordinates:
                    print("Todos os %d subordinates concedidos" % opts.subordinates)
                    reservations = conn.get_all_reservations(active_instance_ids)
                    subordinate_nodes = []
                    for r in reservations:
                        subordinate_nodes += r.instances
                    break
                else:
                    print("%d de %d subordinates concedidos, aguarde mais um pouco" % (
                        len(active_instance_ids), opts.subordinates))
        except:
            print("Cancelando instancias spot solicitadas")
            conn.cancel_spot_instance_requests(my_req_ids)
            # Manda um aviso se algum desses pedidos realmente lançou instâncias:
            (main_nodes, subordinate_nodes) = get_existing_cluster(
                conn, opts, cluster_name, die_on_error=False)
            running = len(main_nodes) + len(subordinate_nodes)
            if running:
                print(("WARNING: %d instancia(s) spot ainda estao rodando" % running), file=stderr)
            sys.exit(0)
    else:
        # Iniciando instancias non-spot
        zones = get_zones(conn, opts)
        num_zones = len(zones)
        i = 0
        subordinate_nodes = []
        for zone in zones:
            num_subordinates_this_zone = get_partition(opts.subordinates, num_zones, i)
            if num_subordinates_this_zone > 0:
                subordinate_res = image.run(
                    key_name=opts.key_pair,
                    security_group_ids=[subordinate_group.id] + additional_group_ids,
                    instance_type=opts.instance_type,
                    placement=zone,
                    min_count=num_subordinates_this_zone,
                    max_count=num_subordinates_this_zone,
                    block_device_map=block_map,
                    subnet_id=opts.subnet_id,
                    placement_group=opts.placement_group,
                    user_data=user_data_content,
                    instance_initiated_shutdown_behavior=opts.instance_initiated_shutdown_behavior,
                    instance_profile_name=opts.instance_profile_name)
                subordinate_nodes += subordinate_res.instances
                print("Criado {s} subordinate{plural_s} em {z}, regid = {r}".format(
                      s=num_subordinates_this_zone,
                      plural_s=('' if num_subordinates_this_zone == 1 else 's'),
                      z=zone,
                      r=subordinate_res.id))
            i += 1

    # Criando mains
    if existing_mains:
        print("Iniciando main...")
        for inst in existing_mains:
            if inst.state not in ["shutting-down", "terminated"]:
                inst.start()
        main_nodes = existing_mains
    else:
        main_type = opts.main_instance_type
        if main_type == "":
            main_type = opts.instance_type
        if opts.zone == 'all':
            opts.zone = random.choice(conn.get_all_zones()).name
        main_res = image.run(
            key_name=opts.key_pair,
            security_group_ids=[main_group.id] + additional_group_ids,
            instance_type=main_type,
            placement=opts.zone,
            min_count=1,
            max_count=1,
            block_device_map=block_map,
            subnet_id=opts.subnet_id,
            placement_group=opts.placement_group,
            user_data=user_data_content,
            instance_initiated_shutdown_behavior=opts.instance_initiated_shutdown_behavior,
            instance_profile_name=opts.instance_profile_name)

        main_nodes = main_res.instances
        print("Main criado na zona %s, regid = %s" % (zone, main_res.id))

    # Time de aguarde
    print("Aguardando propagacao da instancia na AWS...")
    time.sleep(15)

    # Fornece os nomes descritivos das instâncias e define as tags adicionais.
    additional_tags = {}
    if opts.additional_tags.strip():
        additional_tags = dict(
            map(str.strip, tag.split(':', 1)) for tag in opts.additional_tags.split(',')
        )

    print('Aplicando tags no node main')
    for main in main_nodes:
        main.add_tags(
            dict(additional_tags, Name='{cn}-main-{iid}'.format(cn=cluster_name, iid=main.id))
        )

    print('Aplicando tags nos nodes subordinates')
    for subordinate in subordinate_nodes:
        subordinate.add_tags(
            dict(additional_tags, Name='{cn}-subordinate-{iid}'.format(cn=cluster_name, iid=subordinate.id))
        )

    if opts.tag_volumes:
        if len(additional_tags) > 0:
            print('Aplicando tags nos volumes')
            all_instance_ids = [x.id for x in main_nodes + subordinate_nodes]
            volumes = conn.get_all_volumes(filters={'attachment.instance-id': all_instance_ids})
            for v in volumes:
                v.add_tags(additional_tags)
        else:
            print('--tag-volumes nao sera feito sem --additional-tags')

    # Retorno de todas as instancias
    return (main_nodes, subordinate_nodes)


def get_existing_cluster(conn, opts, cluster_name, die_on_error=True):
    """
        Obtenha as instâncias EC2 em um cluster existente, se disponível.
        Retorna uma tupla de listas de objetos de instância EC2 para os mestres e escravos.
    """
    print("Verificando se existe cluster {c} na regiao {r}...".format(
          c=cluster_name, r=opts.region))

    def get_instances(group_names):
        """
        Obter todas as instancias nao encerradas que pertencam a qualquer um dos grupos de segurança fornecidos.

         Os filtros de reserva EC2 e os estados de instancia estao documentados aqui:
            http://docs.aws.amazon.com/cli/latest/reference/ec2/describe-instances.html#options
        """
        reservations = conn.get_all_reservations(
            filters={"instance.group-name": group_names})
        instances = itertools.chain.from_iterable(r.instances for r in reservations)
        return [i for i in instances if i.state not in ["shutting-down", "terminated"]]

    main_instances = get_instances([cluster_name + "-main"])
    subordinate_instances = get_instances([cluster_name + "-subordinates"])

    if any((main_instances, subordinate_instances)):
        print("Encontrado {m} main{plural_m}, {s} subordinate{plural_s}.".format(
              m=len(main_instances),
              plural_m=('' if len(main_instances) == 1 else 's'),
              s=len(subordinate_instances),
              plural_s=('' if len(subordinate_instances) == 1 else 's')))

    if not main_instances and die_on_error:
        print("ERRO: Nao foi possivel encontrar um main para cluster {c} na regiao {r}.".format(
              c=cluster_name, r=opts.region), file=sys.stderr)
        sys.exit(1)

    return (main_instances, subordinate_instances)


# Aqui será implantando os arquivos de configuração e depois executar os scripts de instalação em um node recém-lançado.
# e verifcar se iniciou o cluster.
def setup_cluster(conn, main_nodes, subordinate_nodes, opts, deploy_ssh_key):
    main = get_dns_name(main_nodes[0], opts.private_ips)
    if deploy_ssh_key:
        print("Gerando SSH key para o main do cluster...")
        key_setup = """
          [ -f ~/.ssh/id_rsa ] ||
            (ssh-keygen -q -t rsa -N '' -f ~/.ssh/id_rsa &&
             cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys)
        """
        ssh(main, opts, key_setup)
        dot_ssh_tar = ssh_read(main, opts, ['tar', 'c', '.ssh'])
        print("Transferindo a mesma SSH key do cluster para os subordinates...")
        for subordinate in subordinate_nodes:
            subordinate_address = get_dns_name(subordinate, opts.private_ips)
            print(subordinate_address)
            ssh_write(subordinate_address, opts, ['tar', 'x'], dot_ssh_tar)

    modules = ['spark', 'ephemeral-hdfs', 'persistent-hdfs',
               'mapreduce', 'spark-standalone', 'h2', 'jobserver']

# REMOVER ESSA CONFIG NA ENTREGA!
# pois nao sera usado uma versao antiga do Hadoop...
# (verificar se sera necessario para o NIFI.: A/c Pedrolo)
    if opts.hadoop_major_version == "1":
        modules = list(filter(lambda x: x != "mapreduce", modules))

    if opts.ganglia:
        modules.append('ganglia')

    # Limpando SPARK_WORKER_INSTANCES se o YARN estiver rodando
    if opts.hadoop_major_version == "yarn":
        opts.worker_instances = ""

    # Tome NOTA Ricardo: Sera clonado o repositório via Github ou Gitlab.wssim.. antes de executar o deploy_files para
    # evitar que o script ec2-variables.sh seja substituido
    print("Clonando scripts spark-ec2 para {r}/tree/{b} no main...".format(
        r=opts.spark_ec2_git_repo, b=opts.spark_ec2_git_branch))
    ssh(
        host=main,
        opts=opts,
        command="rm -rf spark-ec2"
        + " && "
        + "git clone {r} -b {b} spark-ec2".format(r=opts.spark_ec2_git_repo,
                                                  b=opts.spark_ec2_git_branch)
    )

    print("Deploying arquivos para o main...")
    deploy_files(
        conn=conn,
        root_dir=SPARK_EC2_DIR + "/" + "deploy.generic",
        opts=opts,
        main_nodes=main_nodes,
        subordinate_nodes=subordinate_nodes,
        modules=modules
    )

    if opts.deploy_root_dir is not None:
        print("Deploying {s} para o main...".format(s=opts.deploy_root_dir))
        deploy_user_files(
            root_dir=opts.deploy_root_dir,
            opts=opts,
            main_nodes=main_nodes
        )

    print("Fazendo a instalacao no main...")
    setup_spark_cluster(main, opts)
    print("Feito!")


def setup_spark_cluster(main, opts):
    ssh(main, opts, "chmod u+x spark-ec2/setup.sh")
    ssh(main, opts, "spark-ec2/setup.sh")
    print("Spark standalone cluster iniciado em http://%s:8080" % main)

    if opts.ganglia:
        print("Ganglia iniciado em http://%s:5080/ganglia" % main)


def is_ssh_available(host, opts, print_ssh_output=True):
    """
    Checando se o SSH esta liberado no host.
    """
    s = subprocess.Popen(
        ssh_command(opts) + ['-t', '-t', '-o', 'ConnectTimeout=3',
                             '%s@%s' % (opts.user, host), stringify_command('true')],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT  # canalizando stderr atraves do stdout para preservar a ordem de saida
    )
    cmd_output = s.communicate()[0]  # [1] o stderr, que redireciona para stdout

    if s.returncode != 0 and print_ssh_output:
        # Essa newline somente para espacamento na funcao wait_for_cluster_state()
        print(textwrap.dedent("""\n
            Warning: Erro de conexao SSH. (pode ser temporario)
            Host: {h}
            SSH return code: {r}
            SSH output: {o}
        """).format(
            h=host,
            r=s.returncode,
            o=cmd_output.strip()
        ))

    return s.returncode == 0


def is_cluster_ssh_available(cluster_instances, opts):
    """
    Verificando se o SSH esta disponivel em todas as instancias do cluster.
    """
    for i in cluster_instances:
        dns_name = get_dns_name(i, opts.private_ips)
        if not is_ssh_available(host=dns_name, opts=opts):
            return False
    else:
        return True


def wait_for_cluster_state(conn, opts, cluster_instances, cluster_state):
    """
    Aguardando que todas as instancias do cluster atinjam um estado designado.

    cluster_instances: uma lista da boto.ec2.instance.Instance
    cluster_state: string que apresenta o estado desejado de todas as instancias no cluster
            O valor pode ser 'ssh-ready' ou um valor valido da funcao boto.ec2.instance.InstanceState, como
           'running', 'terminated', etc.
           (seria bom substituir isso por um enum apropriado: http://stackoverflow.com/a/1695250)
    """
    sys.stdout.write(
        "Aguardando que o cluster entre '{s}' state.".format(s=cluster_state)
    )
    sys.stdout.flush()

    start_time = datetime.now()
    num_attempts = 0

    while True:
        time.sleep(5 * num_attempts)  # seconds

        for i in cluster_instances:
            i.update()

        max_batch = 100
        statuses = []
        for j in xrange(0, len(cluster_instances), max_batch):
            batch = [i.id for i in cluster_instances[j:j + max_batch]]
            statuses.extend(conn.get_all_instance_status(instance_ids=batch))

        if cluster_state == 'ssh-ready':
            if all(i.state == 'running' for i in cluster_instances) and \
               all(s.system_status.status == 'ok' for s in statuses) and \
               all(s.instance_status.status == 'ok' for s in statuses) and \
               is_cluster_ssh_available(cluster_instances, opts):
                break
        else:
            if all(i.state == cluster_state for i in cluster_instances):
                break

        num_attempts += 1

        sys.stdout.write(".")
        sys.stdout.flush()

    sys.stdout.write("\n")

    end_time = datetime.now()
    print("Cluster esta agora em '{s}' estado. Esperou {t} segundos.".format(
        s=cluster_state,
        t=(end_time - start_time).seconds
    ))


# Pega o número de discos locais disponíveis para um dado tipo de instancia EC2.
def get_num_disks(instance_type):
    # Source: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html
    # Last Updated: 2015-06-19
    # Para facilitar a manutenção, mantenha este dicionário introduzido manualmente ordenado por chave.
    disks_by_instance = {
        "c1.medium":   1,
        "c1.xlarge":   4,
        "c3.large":    2,
        "c3.xlarge":   2,
        "c3.2xlarge":  2,
        "c3.4xlarge":  2,
        "c3.8xlarge":  2,
        "c4.large":    0,
        "c4.xlarge":   0,
        "c4.2xlarge":  0,
        "c4.4xlarge":  0,
        "c4.8xlarge":  0,
        "cc1.4xlarge": 2,
        "cc2.8xlarge": 4,
        "cg1.4xlarge": 2,
        "cr1.8xlarge": 2,
        "d2.xlarge":   3,
        "d2.2xlarge":  6,
        "d2.4xlarge":  12,
        "d2.8xlarge":  24,
        "g2.2xlarge":  1,
        "g2.8xlarge":  2,
        "hi1.4xlarge": 2,
        "hs1.8xlarge": 24,
        "i2.xlarge":   1,
        "i2.2xlarge":  2,
        "i2.4xlarge":  4,
        "i2.8xlarge":  8,
        "m1.small":    1,
        "m1.medium":   1,
        "m1.large":    2,
        "m1.xlarge":   4,
        "m2.xlarge":   1,
        "m2.2xlarge":  1,
        "m2.4xlarge":  2,
        "m3.medium":   1,
        "m3.large":    1,
        "m3.xlarge":   2,
        "m3.2xlarge":  2,
        "m4.large":    0,
        "m4.xlarge":   0,
        "m4.2xlarge":  0,
        "m4.4xlarge":  0,
        "m4.10xlarge": 0,
        "r3.large":    1,
        "r3.xlarge":   1,
        "r3.2xlarge":  1,
        "r3.4xlarge":  1,
        "r3.8xlarge":  2,
        "t1.micro":    0,
        "t2.micro":    0,
        "t2.small":    0,
        "t2.medium":   0,
        "t2.large":    0,
    }
    if instance_type in disks_by_instance:
        return disks_by_instance[instance_type]
    else:
        print("WARNING: Nao reconhecido o numero de discos para esse tipo de instancia %s; assumindo 1"
              % instance_type, file=stderr)
        return 1

# MODELO DE DISTRIBUICAO DE ATIVIDADES
# Depois de implementado os modelos de arquivos de configuração em um determinado diretorio local para
# o cluster, preenchendo todos os parametros do modelo com informacoes sobre o
# cluster (por exemplo, listas de mains e subordinates). Os arquivos sao enviados para
# a primeira instancia main do cluster, e aguardado a configuração aplicada no
# script ser aplicada nessa instância para copiá-los para os outros nodes.
#
# root_dir deve ser um caminho absoluto para o diretório com os arquivos de implantacao.
def deploy_files(conn, root_dir, opts, main_nodes, subordinate_nodes, modules):
    active_main = get_dns_name(main_nodes[0], opts.private_ips)

    num_disks = get_num_disks(opts.instance_type)
    hdfs_data_dirs = "/mnt/ephemeral-hdfs/data"
    mapred_local_dirs = "/mnt/hadoop/mrlocal"
    spark_local_dirs = "/mnt/spark"
    jobserver_local_dir = "/mnt/jobserver"
    h2_local_dir = "/mnt/h2"

    if num_disks > 1:
        for i in range(2, num_disks + 1):
            hdfs_data_dirs += ",/mnt%d/ephemeral-hdfs/data" % i
            mapred_local_dirs += ",/mnt%d/hadoop/mrlocal" % i
            spark_local_dirs += ",/mnt%d/spark" % i
            jobserver_local_dir += "/mnt%d/jobserver" % i
            h2_local_dir += "/mnt%d/h2" % i

    cluster_url = "%s:7077" % active_main

    if "." in opts.spark_version:
        # Pre-built Spark deploy
        spark_v = get_validate_spark_version(opts.spark_version, opts.spark_git_repo)
        validate_spark_hadoop_version(spark_v, opts.hadoop_major_version)
    else:
        # Spark-only deploy personalizado
        spark_v = "%s|%s" % (opts.spark_git_repo, opts.spark_version)

    main_addresses = [get_dns_name(i, opts.private_ips) for i in main_nodes]
    subordinate_addresses = [get_dns_name(i, opts.private_ips) for i in subordinate_nodes]
    worker_instances_str = "%d" % opts.worker_instances if opts.worker_instances else ""
    template_vars = {
        "main_list": '\n'.join(main_addresses),
        "active_main": active_main,
        "subordinate_list": '\n'.join(subordinate_addresses),
        "cluster_url": cluster_url,
        "hdfs_data_dirs": hdfs_data_dirs,
        "mapred_local_dirs": mapred_local_dirs,
        "spark_local_dirs": spark_local_dirs,
        "swap": str(opts.swap),
        "modules": '\n'.join(modules),
        "spark_version": spark_v,
        "hadoop_major_version": opts.hadoop_major_version,
        "spark_worker_instances": worker_instances_str,
        "spark_main_opts": opts.main_opts
    }

    if opts.copy_aws_credentials:
        template_vars["aws_access_key_id"] = conn.aws_access_key_id
        template_vars["aws_secret_access_key"] = conn.aws_secret_access_key
    else:
        template_vars["aws_access_key_id"] = ""
        template_vars["aws_secret_access_key"] = ""

# Crie um diretorio temporario no qual vamos colocar todos os arquivos para serem
# implantados e depois de substituimos os parametros do modelo neles
# OBS: Pegado do modelo do site cloudhackers.com
    tmp_dir = tempfile.mkdtemp()
    for path, dirs, files in os.walk(root_dir):
        if path.find(".svn") == -1:
            dest_dir = os.path.join('/', path[len(root_dir):])
            local_dir = tmp_dir + dest_dir
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
            for filename in files:
                if filename[0] not in '#.~' and filename[-1] != '~':
                    dest_file = os.path.join(dest_dir, filename)
                    local_file = tmp_dir + dest_file
                    with open(os.path.join(path, filename)) as src:
                        with open(local_file, "w") as dest:
                            text = src.read()
                            for key in template_vars:
                                text = text.replace("{{" + key + "}}", template_vars[key])
                            dest.write(text)
                            dest.close()

    # rsync de todo o diretario para a instancia Main
    command = [
        'rsync', '-rv',
        '-e', stringify_command(ssh_command(opts)),
        "%s/" % tmp_dir,
        "%s@%s:/" % (opts.user, active_main)
    ]
    subprocess.check_call(command)

    # Removendo o diretorio temporario criado acima
    shutil.rmtree(tmp_dir)


# Implantando um determinado diretorio local para um cluster, SEM substituicao de parametro.
# Note que, ao contrário de deploy_files, isso funciona para arquivos binarios.
# Alem disso, cabe ao usuario adicionar (ou nao) a barra final no root_dir.
# Os arquivos so sao implantados na primeira instancia mestre no cluster.
#
# root_dir deve ser um PATH absoluto. Ou seja, ele precisa existir mesmo. ;)
def deploy_user_files(root_dir, opts, main_nodes):
    active_main = get_dns_name(main_nodes[0], opts.private_ips)
    command = [
        'rsync', '-rv',
        '-e', stringify_command(ssh_command(opts)),
        "%s" % root_dir,
        "%s@%s:/" % (opts.user, active_main)
    ]
    subprocess.check_call(command)


def stringify_command(parts):
    if isinstance(parts, str):
        return parts
    else:
        return ' '.join(map(pipes.quote, parts))


def ssh_args(opts):
    parts = ['-o', 'StrictHostKeyChecking=no']
    parts += ['-o', 'UserKnownHostsFile=/dev/null']
    if opts.identity_file is not None:
        parts += ['-i', opts.identity_file]
    return parts


def ssh_command(opts):
    return ['ssh'] + ssh_args(opts)


# Sera executado um comando em um host através do ssh, tentando até cinco vezes
# e, em seguida, lançando uma exceção se o ssh continuar falhando.
def ssh(host, opts, command):
    tries = 0
    while True:
        try:
            return subprocess.check_call(
                ssh_command(opts) + ['-t', '-t', '%s@%s' % (opts.user, host),
                                     stringify_command(command)])
        except subprocess.CalledProcessError as e:
            if tries > 5:
                # Se for uma falha ssh, forneca dicas ao usuario da Monsanto.
                if e.returncode == 255:
                    raise UsageError(
                        "Falha de SSH no host {0}.\n"
                        "Verifique se voce forneceu corretamente os parametros no --identity-file e no "
                        "--key-pair e tente novamente.".format(host))
                else:
                    raise e
            print("Erro ao executar o comando remoto, tentando de novo apos 30 segundos: {0}".format(e),
                  file=stderr)
            time.sleep(30)
            tries = tries + 1

# Backported do Python 2.7 para compatibilidade com 2.6
# Isso foi achado no stackoverflow
def _check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('argumento stdout nao permitido, ele sera substituído.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise subprocess.CalledProcessError(retcode, cmd, output=output)
    return output


def ssh_read(host, opts, command):
    return _check_output(
        ssh_command(opts) + ['%s@%s' % (opts.user, host), stringify_command(command)])


def ssh_write(host, opts, command, arguments):
    tries = 0
    while True:
        proc = subprocess.Popen(
            ssh_command(opts) + ['%s@%s' % (opts.user, host), stringify_command(command)],
            stdin=subprocess.PIPE)
        proc.stdin.write(arguments)
        proc.stdin.close()
        status = proc.wait()
        if status == 0:
            break
        elif tries > 5:
            raise RuntimeError("ssh_write failed with error %s" % proc.returncode)
        else:
            print("Erro {0} enquanto executava o comando remotamente, tentando novamente apos 30 segundos".
                  format(status), file=stderr)
            time.sleep(30)
            tries = tries + 1


# Aqui ele obtem uma lista de zonas para iniciar instancias
def get_zones(conn, opts):
    if opts.zone == 'all':
        zones = [z.name for z in conn.get_all_zones()]
    else:
        zones = [opts.zone]
    return zones


# Obtem o numero de itens em uma particao
def get_partition(total, num_partitions, current_partitions):
    num_subordinates_this_zone = total // num_partitions
    if (total % num_partitions) - current_partitions > 0:
        num_subordinates_this_zone += 1
    return num_subordinates_this_zone


# Pega o IP, levando em consideracao o --private-ips flag
def get_ip_address(instance, private_ips=False):
    ip = instance.ip_address if not private_ips else \
        instance.private_ip_address
    return ip


# Pega o DNS, tendo em conta o --private-ips flag
def get_dns_name(instance, private_ips=False):
    dns = instance.public_dns_name if not private_ips else \
        instance.private_ip_address
    if not dns:
        raise UsageError("Nao foi possivel determinar o nome do host de {0}.\n"
                         "Verifique se voce forneceu --private-ips se "
                         "necessario".format(instance))
    return dns


def real_main():
    (opts, action, cluster_name) = parse_args()

    # Validacao de parametros de entrada
    spark_v = get_validate_spark_version(opts.spark_version, opts.spark_git_repo)
    validate_spark_hadoop_version(spark_v, opts.hadoop_major_version)

    if opts.wait is not None:
        # NOTE: DeprecationWarnings nao debuga na versao 2.7+ por padrao. E isso eh uma merda! demoro pra entender.
        #       Para debugar, execute Python com a opcao -Wdefault.
        # Achei aqui: https://docs.python.org/3.5/whatsnew/2.7.html
        warnings.warn(
            "Esta opcao esta obsoleta e nao tem efeito. "
            "spark-ec2 espera automaticamente enquanto necessário para que os clusters comecem.",
            DeprecationWarning
        )

    if opts.identity_file is not None:
        if not os.path.exists(opts.identity_file):
            print("ERRO: O arquivo de identidade '{f}' nao existe.".format(f=opts.identity_file),
                  file=stderr)
            sys.exit(1)

        file_mode = os.stat(opts.identity_file).st_mode
        if not (file_mode & S_IRUSR) or not oct(file_mode)[-2:] == '00':
            print("ERRO: O arquivo de identidade deve ser acessivel somente por voce.", file=stderr)
            print('Corrigi isso com: chmod 400 "{f}"'.format(f=opts.identity_file),
                  file=stderr)
            sys.exit(1)

    if opts.instance_type not in EC2_INSTANCE_TYPES:
        print("Atencao: Tipo de instancia EC2 nao reconhecido no instance-type: {t}".format(
              t=opts.instance_type), file=stderr)

    if opts.main_instance_type != "":
        if opts.main_instance_type not in EC2_INSTANCE_TYPES:
            print("Atencao: Tipo de instancia EC2 nao reconhecido no main-instance-type: {t}".format(
                  t=opts.main_instance_type), file=stderr)
# Aqui sera feito uma tentativa de reconhecimento de tipos de instância, mesmo que nao de para resolvê-los, verifica se a amazon resolve primeiro
# e, se o fizerem, veja se eles resolveram o mesmo tipo de virtualização.
        if opts.instance_type in EC2_INSTANCE_TYPES and \
           opts.main_instance_type in EC2_INSTANCE_TYPES:
            if EC2_INSTANCE_TYPES[opts.instance_type] != \
               EC2_INSTANCE_TYPES[opts.main_instance_type]:
                print("Erro: O spark-ec2 atualmente não suporta ter um main e subordinates "
                      "com diferentes tipos de virtualizacao AMI.", file=stderr)
                print("main com tipo de virtualizacao: {t}".format(
                      t=EC2_INSTANCE_TYPES[opts.main_instance_type]), file=stderr)
                print("subordinate com tipo de virtualizacao: {t}".format(
                      t=EC2_INSTANCE_TYPES[opts.instance_type]), file=stderr)
                sys.exit(1)

    if opts.ebs_vol_num > 8:
        print("ebs-vol-num nao pode ser maior que 8", file=stderr)
        sys.exit(1)

# Prevenção de quebra do ami_prefix que irei informar sempre no repo do Gitlab
# Evite forks com nomes diferente de spark-ec2 por enquanto.
    if opts.spark_ec2_git_repo.endswith("/") or \
            opts.spark_ec2_git_repo.endswith(".git") or \
            not opts.spark_ec2_git_repo.startswith("https://github.com") or \
            not opts.spark_ec2_git_repo.endswith("spark-ec2"):
        print("spark-ec2-git-repo deve ser um repo do Gitlab WSSIM no / ou no .git.", file=stderr)
        sys.exit(1)

    if not (opts.deploy_root_dir is None or
            (os.path.isabs(opts.deploy_root_dir) and
             os.path.isdir(opts.deploy_root_dir) and
             os.path.exists(opts.deploy_root_dir))):
        print("--deploy-root-dir deve ser um caminho absoluto, ou seja diretorio que existe "
              "no sistema de arquivos local", file=stderr)
        sys.exit(1)

    try:
        if opts.profile is None:
            conn = ec2.connect_to_region(opts.region)
        else:
            conn = ec2.connect_to_region(opts.region, profile_name=opts.profile)
    except Exception as e:
        print((e), file=stderr)
        sys.exit(1)

    # Selecione um AZ aleatoriamente se não for especificado.
    if opts.zone == "":
        opts.zone = random.choice(conn.get_all_zones()).name

    if action == "launch":
        if opts.subordinates <= 0:
            print("ERRO: Voce deve ter pelo menos 1 subordinate", file=sys.stderr)
            sys.exit(1)
        if opts.resume:
            (main_nodes, subordinate_nodes) = get_existing_cluster(conn, opts, cluster_name)
        else:
            (main_nodes, subordinate_nodes) = launch_cluster(conn, opts, cluster_name)
        wait_for_cluster_state(
            conn=conn,
            opts=opts,
            cluster_instances=(main_nodes + subordinate_nodes),
            cluster_state='ssh-ready'
        )
        setup_cluster(conn, main_nodes, subordinate_nodes, opts, True)

    elif action == "destroy":
        (main_nodes, subordinate_nodes) = get_existing_cluster(
            conn, opts, cluster_name, die_on_error=False)

        if any(main_nodes + subordinate_nodes):
            print("As seguintes instancias serao encerradas:")
            for inst in main_nodes + subordinate_nodes:
                print("> %s" % get_dns_name(inst, opts.private_ips))
            print("TODOS OS DADOS SOBRE TODOS OS NODES SERAO PERDIDOS!!")

        msg = "Tem certeza de que deseja matar o cluster {c}? (y/N) ".format(c=cluster_name)
        response = raw_input(msg)
        if response == "y":
            print("Terminando main...")
            for inst in main_nodes:
                inst.terminate()
            print("Terminando subordinates...")
            for inst in subordinate_nodes:
                inst.terminate()

            # Elimina grupos de seguranca tambem
            if opts.delete_groups:
                group_names = [cluster_name + "-main", cluster_name + "-subordinates"]
                wait_for_cluster_state(
                    conn=conn,
                    opts=opts,
                    cluster_instances=(main_nodes + subordinate_nodes),
                    cluster_state='terminated'
                )
                print("Excluindo grupos de seguranca (isso levara algum tempo)...")
                attempt = 1
                while attempt <= 3:
                    print("Attempt %d" % attempt)
                    groups = [g for g in conn.get_all_security_groups() if g.name in group_names]
                    success = True
# Sera feita a exclusao de regras individuais em todos os grupos antes de excluir grupos
# e remove as dependencias entre eles
                    for group in groups:
                        print("Apagando regras do security group " + group.name)
                        for rule in group.rules:
                            for grant in rule.grants:
                                success &= group.revoke(ip_protocol=rule.ip_protocol,
                                                        from_port=rule.from_port,
                                                        to_port=rule.to_port,
                                                        src_group=grant)

# Apenas um time para o AWS eventual-consistency
                    time.sleep(30)  # Aqui tem que ser longo (se rapido nao exclui direito) :-(
                    for group in groups:
                        try:
                            # Eh necessario usar o group_id para fazer funcionar com o VPC AWS-WS
                            conn.delete_security_group(group_id=group.id)
                            print("Security group excluido %s" % group.name)
                        except boto.exception.EC2ResponseError:
                            success = False
                            print("Falha ao deletar o security group %s" % group.name)

                    # Mano... Infelizmente o group.revoke() retorna True mesmo se uma regra não for
                    # apagada, entao isso precisa ser reiniciado se algo falhar
                    # preciso ver isso com o Evaristo ou Ivan
                    if success:
                        break

                    attempt += 1

                if not success:
                    print("Falha ao excluir todos os grupos de seguranca apos 3 tentativas.")
                    print("Tente voltar a rodar em alguns minutos.") # ter que falar pro cara tenta de novo eh trash

    elif action == "login":
        (main_nodes, subordinate_nodes) = get_existing_cluster(conn, opts, cluster_name)
        if not main_nodes[0].public_dns_name and not opts.private_ips:
            print("O Main nao possui um DNS publico. Talvez voce quisesse especificar --private-ips?")
        else:
            main = get_dns_name(main_nodes[0], opts.private_ips)
            print("Acessando o main " + main + "...")
            proxy_opt = []
            if opts.proxy_port is not None:
                proxy_opt = ['-D', opts.proxy_port]
            subprocess.check_call(
                ssh_command(opts) + proxy_opt + ['-t', '-t', "%s@%s" % (opts.user, main)])

    elif action == "reboot-subordinates":
        response = raw_input(
            "Tem certeza de que deseja reiniciar o cluster " +
            cluster_name + " subordinates?\n" +
            "Reiniciar cluster subordinates " + cluster_name + " (y/N): ")
        if response == "y":
            (main_nodes, subordinate_nodes) = get_existing_cluster(
                conn, opts, cluster_name, die_on_error=False)
            print("Reiniciando subordinates...")
            for inst in subordinate_nodes:
                if inst.state not in ["shutting-down", "terminated"]:
                    print("Reiniciando " + inst.id)
                    inst.reboot()

    elif action == "get-main":
        (main_nodes, subordinate_nodes) = get_existing_cluster(conn, opts, cluster_name)
        if not main_nodes[0].public_dns_name and not opts.private_ips:
            print("O Main nao possui um DNS publico. Talvez voce quisesse especificar --private-ips?")
        else:
            print(get_dns_name(main_nodes[0], opts.private_ips))

    elif action == "stop":
        response = raw_input(
            "Tem certeza de que deseja parar o cluster " +
            cluster_name + "?\nDADOS SOBRE DISCOS EPHEMERAL SERAO PERDIDOS, " +
            "MAS O CLUSTER GUARDARA USANDO O ESPACO SOBRE\n" +
            "A AMAZON EBS SE FOR ATRVES DE EBS-BACKED!!\n" +
            "Todos os dados nos subordinates em spot-instance serao perdidos.\n" +
            "Parar o cluster " + cluster_name + " (y/N): ")
        if response == "y":
            (main_nodes, subordinate_nodes) = get_existing_cluster(
                conn, opts, cluster_name, die_on_error=False)
            print("Parando main...")
            for inst in main_nodes:
                if inst.state not in ["shutting-down", "terminated"]:
                    inst.stop()
            print("Parando subordinates...")
            for inst in subordinate_nodes:
                if inst.state not in ["shutting-down", "terminated"]:
                    if inst.spot_instance_request_id:
                        inst.terminate()
                    else:
                        inst.stop()

    elif action == "start":
        (main_nodes, subordinate_nodes) = get_existing_cluster(conn, opts, cluster_name)
        print("Iniciando subordinates...")
        for inst in subordinate_nodes:
            if inst.state not in ["shutting-down", "terminated"]:
                inst.start()
        print("Iniciando main...")
        for inst in main_nodes:
            if inst.state not in ["shutting-down", "terminated"]:
                inst.start()
        wait_for_cluster_state(
            conn=conn,
            opts=opts,
            cluster_instances=(main_nodes + subordinate_nodes),
            cluster_state='ssh-ready'
        )

        # Determinando os tipos de instancias em execucao
        existing_main_type = main_nodes[0].instance_type
        existing_subordinate_type = subordinate_nodes[0].instance_type
        # Essa configuracao de opts.main_instance_type indica que os nodes
        # tem o mesmo tipo de instância tanto para o main qunto para os subordinates
        if existing_main_type == existing_subordinate_type:
            existing_main_type = ""
        opts.main_instance_type = existing_main_type
        opts.instance_type = existing_subordinate_type

        setup_cluster(conn, main_nodes, subordinate_nodes, opts, False)

    else:
        print("Acao Invalida: %s" % action, file=stderr)
        sys.exit(1)


def main():
    try:
        real_main()
    except UsageError as e:
        print("\nError:\n", e, file=stderr)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig()
    main()
