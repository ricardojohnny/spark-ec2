<<<<<<< HEAD
EC2 Cluster Apache Spark [BDD Project]
Iniciando o Cluster
Rodar ./spark-ec2 -k <keypair> -i <key-file> -s <num-slaves> launch <cluster-name>,

por exemplo:

bash export AWS_SECRET_ACCESS_KEY=AaBbCcDdEeFGgHhIiJjKkLlMmNnOoPpQqRrSsTtU export AWS_ACCESS_KEY_ID=ABCDEFG1234567890123 ./spark-ec2 --key-pair=awskey --identity-file=awskey.pem --region=us-west-1 --zone=us-west-1a launch my-spark-cluster 
=======
# EC2 Cluster Apache Spark [BDD Project]

## Iniciando o Cluster

-   Rodar
    `./spark-ec2 -k <keypair> -i <key-file> -s <num-slaves> launch <cluster-name>`,

    por exemplo:

    ```bash
    export AWS_SECRET_ACCESS_KEY=AaBbCcDdEeFGgHhIiJjKkLlMmNnOoPpQqRrSsTtU
export AWS_ACCESS_KEY_ID=ABCDEFG1234567890123
./spark-ec2 --key-pair=awskey --identity-file=awskey.pem --region=us-west-1 --zone=us-west-1a launch my-spark-cluster
    ```
>>>>>>> origin/master
