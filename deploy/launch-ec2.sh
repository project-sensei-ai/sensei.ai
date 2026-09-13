#!/bin/bash
# One command from a laptop with AWS credentials to a running, HTTPS Sensei.
#
#   deploy/launch-ec2.sh [branch]
#
# Creates a security group (80/443/22), launches a t3.large Amazon Linux 2023
# instance, and hands it deploy/ec2-user-data.sh with backend/.env baked in.
# Prints the https:// URL when done. Re-running creates a second instance;
# terminate the old one in the console or with `aws ec2 terminate-instances`.
set -euo pipefail
cd "$(dirname "$0")/.."
BRANCH="${1:-main}"
REGION="${AWS_REGION:-us-east-1}"

AMI=$(aws ssm get-parameters --region "$REGION" \
  --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameters[0].Value' --output text)

SG=$(aws ec2 describe-security-groups --region "$REGION" --filters Name=group-name,Values=sensei-web \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)
if [ "$SG" = "None" ] || [ -z "$SG" ]; then
  SG=$(aws ec2 create-security-group --region "$REGION" --group-name sensei-web \
    --description "Sensei: HTTP, HTTPS, SSH" --query GroupId --output text)
  for p in 80 443 22; do
    aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG" \
      --protocol tcp --port "$p" --cidr 0.0.0.0/0 >/dev/null
  done
fi

ENV_B64=$(base64 < backend/.env | tr -d '\n')
sed -e "s|__ENV_B64__|$ENV_B64|" -e "s|__BRANCH__|$BRANCH|" deploy/ec2-user-data.sh > /tmp/sensei-user-data.sh

ID=$(aws ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type t3.large \
  --security-group-ids "$SG" --user-data file:///tmp/sensei-user-data.sh \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=sensei}]' \
  --query 'Instances[0].InstanceId' --output text)
rm -f /tmp/sensei-user-data.sh
echo "instance $ID — waiting for it to come up"
aws ec2 wait instance-running --region "$REGION" --instance-ids "$ID"
IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
HOST="${IP//./-}.sslip.io"
echo "Building on the instance (5–8 minutes). Then: https://$HOST"
echo "Set FRONTEND_ORIGIN for invite links if it differs: https://$HOST"
