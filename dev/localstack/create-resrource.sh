#!/bin/bash

echo "Creating AWS resources..."

awslocal --version

# If you change the bucket name, change the environment variable in docker-compose.yaml as well.
awslocal --debug --endpoint-url=http://localstack:4566 s3api create-bucket --bucket audit-local
