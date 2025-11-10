#!/bin/bash

# 데이터 수집 스크립트

set -e

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."

# 가상환경 활성화
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 파라미터 처리
SOURCE=${1:-all}
DAYS=${2:-7}

echo "📊 데이터 수집 시작..."
echo "- 소스: $SOURCE"
echo "- 기간: 최근 $DAYS 일"
echo ""

# TODO: 실제 데이터 수집 스크립트 구현
# python -m src.cli collect --source $SOURCE --days $DAYS

echo "✅ 데이터 수집 완료!"

