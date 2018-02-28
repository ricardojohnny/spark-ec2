#!/bin/bash

# Download H2
wget --no-check-certificate https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/h2database/h2-2012-11-30.zip -P /tmp

# Unpacking H2 in /root
unzip /tmp/h2-2012-11-30.zip -d /root
