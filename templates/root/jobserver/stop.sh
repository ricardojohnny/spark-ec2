#kill `lsof -i:8090 -t` 
pid=`lsof -i:8090 -t`
if [ "$pid" ]; then
	kill -9 $pid
else
	echo "no process running on port 8090"
fi
