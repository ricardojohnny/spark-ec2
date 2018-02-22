pid=`lsof -i:8090 -t`
if [ "$pid" ]; then
        echo "Server is already running"
else		
	GC_OPTS="-XX:+UseConcMarkSweepGC
        	 -verbose:gc -XX:+PrintGCTimeStamps -Xloggc:$(pwd)/gc.out
        	 -XX:+CMSClassUnloadingEnabled "

	JAVA_OPTS="-XX:+HeapDumpOnOutOfMemoryError -Djava.net.preferIPv4Stack=true"

	$SPARK_HOME/bin/spark-submit --class spark.jobserver.JobServer \
		 --driver-java-options "$GC_OPTS $JAVA_OPTS" spark-job-server.jar dse.conf > job.log 2>&1 < /dev/null &
fi
