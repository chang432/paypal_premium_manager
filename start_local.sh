#!/bin/bash

LOCAL_ENV_PATH=".env"
S3_BUCKET_NAME="paypal-premium-manager"

# Configure SSL certs from S3

if [[ ! -f "./paypal_premium_manager/certs/fullchain.pem" ]]; then
    source ${LOCAL_ENV_PATH}
    aws s3 cp "s3://${S3_BUCKET_NAME}/letsencrypt" "/tmp/letsencrypt" --recursive

    mkdir -p ./paypal_premium_manager/certs
    cp /tmp/letsencrypt/live/paypal-premium-manager.com/fullchain.pem ./certs/fullchain.pem
    cp /tmp/letsencrypt/live/paypal-premium-manager.com/privkey.pem ./certs/privkey.pem
fi

chmod +x ./start_docker.sh
./start_docker.sh --rebuild

echo "containers started"