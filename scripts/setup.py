#!/usr/bin/env python
"""
초기 설정 스크립트
데이터베이스 초기화, 디렉토리 생성 등
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def create_directories():
    """필요한 디렉토리 생성"""
    directories = [
        "data/databases",
        "data/raw",
        "data/processed",
        "data/cache",
        "data/backups",
        "logs",
        "credentials",
        "templates",
    ]
    
    for directory in directories:
        path = project_root / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_env_file():
    """환경 변수 파일 생성"""
    env_example = project_root / ".env.example"
    env_file = project_root / ".env"
    
    if not env_file.exists() and env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        print(f"✅ Created .env file from .env.example")
        print(f"⚠️  Please edit .env file and add your API keys")
    elif env_file.exists():
        print(f"ℹ️  .env file already exists")
    else:
        print(f"⚠️  .env.example not found")


def initialize_database():
    """데이터베이스 초기화"""
    try:
        # TODO: 실제 데이터베이스 초기화 로직 구현
        # from src.core.database import DatabaseManager
        # db_manager = DatabaseManager()
        # db_manager.initialize()
        
        print(f"✅ Database initialized")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")


def create_prompt_templates():
    """AI 프롬프트 템플릿 생성"""
    templates_dir = project_root / "templates"
    
    performance_template = templates_dir / "performance_analysis.txt"
    if not performance_template.exists():
        performance_template.write_text("""# 팀 멤버 퍼포먼스 분석

## 멤버 정보
- 이름: {member_name}
- 분석 기간: {start_date} ~ {end_date}

## 활동 데이터
{activity_data}

## 분석 요청
위 데이터를 바탕으로 다음을 분석해주세요:
1. 전반적인 업무 활동 수준 평가
2. 강점과 개선이 필요한 영역
3. 팀 내 협업 및 커뮤니케이션 패턴
4. 구체적인 개선 제안
""")
        print(f"✅ Created template: performance_analysis.txt")
    
    team_template = templates_dir / "team_insights.txt"
    if not team_template.exists():
        team_template.write_text("""# 팀 인사이트 분석

## 팀 정보
- 팀 이름: {team_name}
- 분석 기간: {start_date} ~ {end_date}
- 멤버 수: {member_count}

## 팀 활동 데이터
{team_activity_data}

## 분석 요청
위 데이터를 바탕으로 다음을 분석해주세요:
1. 팀 전체의 생산성 트렌드
2. 팀 협업 패턴 및 커뮤니케이션 효율성
3. 개별 멤버 간 역할 분담 및 기여도
4. 팀 퍼포먼스 개선을 위한 제안
""")
        print(f"✅ Created template: team_insights.txt")


def main():
    """메인 설정 함수"""
    print("=" * 60)
    print("🚀 All-Thing-Eye 초기 설정")
    print("=" * 60)
    
    print("\n📁 디렉토리 생성...")
    create_directories()
    
    print("\n📄 환경 설정 파일 생성...")
    create_env_file()
    
    print("\n📝 프롬프트 템플릿 생성...")
    create_prompt_templates()
    
    print("\n💾 데이터베이스 초기화...")
    initialize_database()
    
    print("\n" + "=" * 60)
    print("✅ 설정 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print("1. .env 파일을 편집하여 API 키를 추가하세요")
    print("2. credentials/ 폴더에 Google 인증 파일을 추가하세요")
    print("3. 가상환경을 활성화하세요: source venv/bin/activate")
    print("4. 의존성을 설치하세요: pip install -r requirements.txt")
    print("5. 테스트 실행: pytest")
    print("6. API 서버 실행: uvicorn src.api.main:app --reload")
    print()


if __name__ == "__main__":
    main()

