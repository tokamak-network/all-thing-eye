# 🚀 AWS 배포 가이드

IAM 계정을 사용한 All-Thing-Eye AWS EC2 배포 완전 가이드

---

## 📋 목차

1. [사전 준비](#1-사전-준비)
2. [AWS 설정](#2-aws-설정)
3. [EC2 인스턴스 생성](#3-ec2-인스턴스-생성)
4. [서버 초기 설정](#4-서버-초기-설정)
5. [애플리케이션 배포](#5-애플리케이션-배포)
6. [도메인 및 HTTPS 설정](#6-도메인-및-https-설정)
7. [모니터링 및 유지보수](#7-모니터링-및-유지보수)
8. [트러블슈팅](#8-트러블슈팅)

---

## 1. 사전 준비

### ✅ 필수 요구사항

- AWS IAM 계정 (EC2FullAccess 권한)
- 로컬에 AWS CLI 설치
- Git 저장소 (GitHub/GitLab)
- 도메인 (선택사항)

### 💰 예상 비용

| 리소스 | 사양 | 월 예상 비용 |
|--------|------|--------------|
| EC2 (t3.medium) | 2 vCPU, 4GB RAM | ~$30 |
| EBS (30GB gp3) | 스토리지 | ~$3 |
| 데이터 전송 | ~10GB/월 | ~$1 |
| **총계** | | **~$34/월** |

---

## 2. AWS 설정

### A. AWS CLI 설정

```bash
# Mac
brew install awscli

# AWS 자격 증명 설정
aws configure
# Access Key ID: [IAM 키]
# Secret Access Key: [IAM 시크릿]
# Region: ap-northeast-2 (서울)
# Output: json

# 확인
aws sts get-caller-identity
```

### B. Secrets Manager에 환경 변수 저장

```bash
aws secretsmanager create-secret \
    --name all-thing-eye/prod/env \
    --secret-string '{
        "GITHUB_TOKEN": "ghp_xxxxx",
        "SLACK_BOT_TOKEN": "xoxb-xxxxx",
        "NOTION_TOKEN": "secret_xxxxx",
        "NEXT_PUBLIC_API_URL": "http://your-ip:80"
    }'
```

---

## 3. EC2 인스턴스 생성

### A. 보안 그룹 생성

```bash
# 보안 그룹 생성
SG_ID=$(aws ec2 create-security-group \
    --group-name all-thing-eye-sg \
    --description "All-Thing-Eye Security Group" \
    --query 'GroupId' \
    --output text)

echo "Security Group ID: $SG_ID"

# SSH (22)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0

# HTTP (80)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0

# HTTPS (443)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0
```

### B. 키 페어 생성

```bash
aws ec2 create-key-pair \
    --key-name all-thing-eye-key \
    --query 'KeyMaterial' \
    --output text > ~/.ssh/all-thing-eye-key.pem

chmod 400 ~/.ssh/all-thing-eye-key.pem
```

### C. EC2 인스턴스 시작

```bash
# Ubuntu 22.04 AMI (서울 리전)
AMI_ID="ami-0c9c942bd7bf113a2"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type t3.medium \
    --key-name all-thing-eye-key \
    --security-group-ids $SG_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=all-thing-eye-prod}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance ID: $INSTANCE_ID"

# 퍼블릭 IP 확인 (인스턴스 시작 대기)
sleep 30

PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "Public IP: $PUBLIC_IP"
```

---

## 4. 서버 초기 설정

### A. SSH 접속

```bash
ssh -i ~/.ssh/all-thing-eye-key.pem ubuntu@$PUBLIC_IP
```

### B. Docker 설치

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Docker 설치
curl -fsSL https://get.docker.com | sudo sh

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
newgrp docker

# 확인
docker --version
docker-compose --version
```

### C. 기타 도구 설치

```bash
sudo apt install -y \
    git \
    curl \
    wget \
    vim \
    htop \
    awscli \
    certbot \
    python3-certbot-nginx
```

---

## 5. 애플리케이션 배포

### A. 코드 클론

```bash
cd ~
git clone https://github.com/your-username/all-thing-eye.git
cd all-thing-eye
```

### B. 환경 변수 설정

```bash
# Secrets Manager에서 가져오기
aws secretsmanager get-secret-value \
    --secret-id all-thing-eye/prod/env \
    --query SecretString \
    --output text | jq -r 'to_entries|map("\(.key)=\(.value|tostring)")|.[]' > .env

# 또는 수동 생성
cat > .env << 'EOF'
GITHUB_TOKEN=ghp_xxxxx
GITHUB_ORG=tokamak-network
SLACK_BOT_TOKEN=xoxb-xxxxx
NOTION_TOKEN=secret_xxxxx
NEXT_PUBLIC_API_URL=http://your-ip
EOF
```

### C. Google Drive 인증 파일 업로드

**로컬에서 실행:**

```bash
scp -i ~/.ssh/all-thing-eye-key.pem \
    config/google_drive/* \
    ubuntu@$PUBLIC_IP:~/all-thing-eye/config/google_drive/
```

### D. 배포 스크립트 실행

```bash
# 실행 권한 부여
chmod +x scripts/deploy.sh

# 초기 배포
./scripts/deploy.sh init
```

**배포 스크립트가 자동으로 수행:**
1. Docker 이미지 빌드
2. 컨테이너 시작
3. 초기 데이터 수집 (GitHub, Slack, Google Drive, Notion)
4. Health check

### E. 배포 확인

```bash
# 컨테이너 상태 확인
docker-compose -f docker-compose.prod.yml ps

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f backend

# 웹 접속
curl http://localhost
```

**브라우저에서 접속:**
```
http://[EC2-PUBLIC-IP]
```

---

## 6. 도메인 및 HTTPS 설정

### A. Route 53에서 도메인 연결 (선택사항)

```bash
# A 레코드 생성
aws route53 change-resource-record-sets \
    --hosted-zone-id Z1234567890ABC \
    --change-batch '{
        "Changes": [{
            "Action": "CREATE",
            "ResourceRecordSet": {
                "Name": "analytics.yourdomain.com",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "'$PUBLIC_IP'"}]
            }
        }]
    }'
```

### B. Let's Encrypt SSL 인증서 발급

```bash
# Certbot으로 인증서 발급
sudo certbot certonly --standalone \
    --preferred-challenges http \
    -d analytics.yourdomain.com

# 인증서를 nginx 디렉토리로 복사
sudo cp /etc/letsencrypt/live/analytics.yourdomain.com/fullchain.pem ~/all-thing-eye/nginx/ssl/
sudo cp /etc/letsencrypt/live/analytics.yourdomain.com/privkey.pem ~/all-thing-eye/nginx/ssl/
sudo chown $USER:$USER ~/all-thing-eye/nginx/ssl/*
```

### C. Nginx HTTPS 활성화

```bash
# nginx.prod.conf에서 HTTPS 설정 주석 해제
vim nginx/nginx.prod.conf

# Nginx 재시작
docker-compose -f docker-compose.prod.yml restart nginx
```

### D. SSL 자동 갱신 설정

```bash
# Cron job 추가
sudo crontab -e

# 매일 자정 인증서 갱신 시도
0 0 * * * certbot renew --quiet && cp /etc/letsencrypt/live/analytics.yourdomain.com/*.pem ~/all-thing-eye/nginx/ssl/ && docker-compose -f ~/all-thing-eye/docker-compose.prod.yml restart nginx
```

---

## 7. 모니터링 및 유지보수

### A. 로그 확인

```bash
# 모든 서비스 로그
./scripts/deploy.sh logs

# 특정 서비스 로그
./scripts/deploy.sh logs backend
./scripts/deploy.sh logs frontend
./scripts/deploy.sh logs celery-beat

# Nginx 로그
tail -f data/logs/nginx/access.log
tail -f data/logs/nginx/error.log
```

### B. 데이터베이스 백업

```bash
# 수동 백업
./scripts/deploy.sh backup

# 자동 백업 (Cron)
crontab -e

# 매일 오전 3시 백업
0 3 * * * cd ~/all-thing-eye && ./scripts/deploy.sh backup
```

### C. 코드 업데이트

```bash
# 최신 코드로 업데이트
./scripts/deploy.sh update
```

### D. 서비스 재시작

```bash
./scripts/deploy.sh restart
```

---

## 8. 트러블슈팅

### 🔍 일반적인 문제

#### 1. 컨테이너가 시작되지 않음

```bash
# 컨테이너 상태 확인
docker ps -a

# 로그 확인
docker logs all-thing-eye-backend

# 컨테이너 재빌드
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

#### 2. 데이터베이스 연결 실패

```bash
# 파일 권한 확인
ls -la data/databases/

# 볼륨 마운트 확인
docker inspect all-thing-eye-backend | grep Mounts -A 20
```

#### 3. API 응답 없음

```bash
# 백엔드 Health Check
curl http://localhost:8000/health

# 포트 확인
sudo netstat -tulpn | grep LISTEN
```

#### 4. 메모리 부족

```bash
# 메모리 사용량 확인
docker stats

# 인스턴스 타입 업그레이드
# t3.medium → t3.large
```

---

## 🎯 배포 체크리스트

**배포 전:**
- [ ] AWS IAM 자격 증명 설정
- [ ] Secrets Manager에 환경 변수 저장
- [ ] Google Drive 인증 파일 준비
- [ ] 도메인 구입 (선택사항)

**배포 중:**
- [ ] EC2 인스턴스 생성
- [ ] 보안 그룹 설정 (22, 80, 443)
- [ ] Docker 설치
- [ ] 코드 클론 및 환경 변수 설정
- [ ] 초기 배포 실행

**배포 후:**
- [ ] 웹 접속 테스트
- [ ] 데이터 수집 확인
- [ ] HTTPS 설정
- [ ] 모니터링 설정
- [ ] 백업 Cron job 설정

---

## 📚 유용한 명령어

```bash
# 서비스 상태 확인
./scripts/deploy.sh status

# 로그 실시간 모니터링
./scripts/deploy.sh logs

# 데이터베이스 백업
./scripts/deploy.sh backup

# 서비스 재시작
./scripts/deploy.sh restart

# 서비스 중지
./scripts/deploy.sh stop

# 디스크 사용량 확인
df -h

# Docker 리소스 정리
docker system prune -a --volumes
```

---

## 💡 추가 최적화

### CloudWatch 모니터링

```bash
# CloudWatch 에이전트 설치
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb
```

### Auto Scaling (선택사항)

- Load Balancer 설정
- Auto Scaling Group 구성
- RDS로 데이터베이스 분리

---

## 📞 문의

문제가 발생하면:
1. 로그 확인
2. GitHub Issues 등록
3. Slack 채널 문의

**Last Updated:** 2025-11-12  
**Version:** 1.0.0

