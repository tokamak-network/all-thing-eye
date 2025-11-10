#!/bin/bash

# 개발 서버 실행 스크립트

set -e

echo "🚀 All-Thing-Eye 개발 서버 시작..."

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."

# 환경 변수 확인
if [ ! -f .env ]; then
    echo "⚠️  .env 파일이 없습니다. .env.example을 복사합니다..."
    cp .env.example .env
    echo "✅ .env 파일을 생성했습니다. API 키를 설정해주세요."
fi

# 가상환경 확인
if [ ! -d "venv" ]; then
    echo "📦 가상환경을 생성합니다..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "🔧 가상환경 활성화..."
source venv/bin/activate

# 의존성 설치
echo "📥 의존성 설치 중..."
pip install -r requirements.txt

# 데이터베이스 디렉토리 생성
mkdir -p data/databases logs

# 개발 서버 실행
echo "✨ FastAPI 서버를 시작합니다..."
echo "📍 API 문서: http://localhost:8000/docs"
echo ""

uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

