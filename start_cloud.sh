#!/bin/bash

# Hetzner vps startup cron script

# Variables used in docker-compose.yml
# export APP_ENV="remote"
# export LETSENCRYPT_HOST_PATH="./letsencrypt"

FLOATING_IP="5.161.30.12"
PARTITION_NAMES="HC_Volume_103799742" 
S3_BUCKET_NAME="paypal-premium-manager"

export PARTITION_PATH=""

for pdir in ${PARTITION_NAMES}; do
    cur_local_path="/mnt/${pdir}"
    cur_external_path="/dev/disk/by-id/scsi-0${pdir}"

    if [[ -e "$cur_external_path" ]]; then
        echo "[${pdir}] Required external volume attached, attempting to mount..."
        mkdir -p "$cur_local_path"
        mount -o discard,defaults "$cur_external_path" "$cur_local_path"

        PARTITION_PATH="$cur_local_path"

        # set PARTITION_PATH as global env variable
        echo "export PARTITION_PATH=${PARTITION_PATH}" > /opt/shared_env.sh

        # Configure logging alias 
        # echo "alias flask-logs='tail -f -n 100 /mnt/${pdir}/log/container-flask/container-flask.log'" >> ~/.bashrc
        # echo "alias nginx-logs='tail -f -n 100 /mnt/${pdir}/log/container-nginx/container-nginx.log'" >> ~/.bashrc

        chmod +x /opt/shared_env.sh
        break
    fi
done

if [[ -z "$PARTITION_PATH" ]]; then
    echo "No volumes attached, waiting..."
    exit 0 
fi

if ! ip addr show dev eth0 | grep -q "$FLOATING_IP"; then
    echo "Floating ip ${FLOATING_IP} has not been added to network interface eth0, doing so now..."
    ip addr add "$FLOATING_IP" dev eth0
fi

if [[ -d "$PARTITION_PATH" && $(docker ps -q | wc -l) == 0 ]] && ip addr show dev eth0 | grep -q "$FLOATING_IP"; then
    echo "External volume detected, floating ip added, and containers are not running yet, starting up now!"
    
    # Configure SSL certs from S3
    source "${PARTITION_PATH}/.env"
    aws s3 cp "s3://${S3_BUCKET_NAME}/letsencrypt" "/opt/letsencrypt" --recursive

    cp /opt/letsencrypt/live/paypal-premium-manager.com/fullchain.pem /opt/paypal_premium_manager/certs/fullchain.pem
    cp /opt/letsencrypt/live/paypal-premium-manager.com/privkey.pem /opt/paypal_premium_manager/certs/privkey.pem

    cd /opt/paypal_premium_manager
    
    ./setup.sh "${PARTITION_PATH}/.env"

    echo "containers started up successfully, turning off cron..."
    crontab -l 2>/dev/null | sed '/start_cloud.sh/ s/^/#/' | crontab -
fi