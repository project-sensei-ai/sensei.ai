#!/bin/bash
# Boots a fresh Amazon Linux 2023 instance into a running Sensei.
#
# Expects two things substituted in before launch (deploy/launch-ec2.sh does it):
#   __ENV_B64__   base64 of backend/.env
#   __BRANCH__    git branch to deploy
set -euxo pipefail
dnf install -y docker git
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

cd /opt
git clone --branch __BRANCH__ --depth 1 https://github.com/project-sensei-ai/sensei.ai.git sensei
cd sensei
echo "__ENV_B64__" | base64 -d > backend/.env

# A public hostname that resolves to this box, with no DNS setup.
IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 \
     -H "X-aws-ec2-metadata-token: $(curl -sX PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')")
export SENSEI_HOST="${IP//./-}.sslip.io"
echo "SENSEI_HOST=$SENSEI_HOST" > deploy/.env
echo "$SENSEI_HOST" > /opt/sensei-host

docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up -d --build
