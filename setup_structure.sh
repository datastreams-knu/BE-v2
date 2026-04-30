#!/bin/bash

# AI 서버 디렉토리 구조 생성
mkdir -p ai/app/api/v1
mkdir -p ai/app/core
mkdir -p ai/app/services
mkdir -p ai/app/infrastructure/redis
mkdir -p ai/app/middleware
mkdir -p ai/tests

# ai/app 파일
touch ai/app/__init__.py
touch ai/app/main.py

# api
touch ai/app/api/v1/generate.py

# core
touch ai/app/core/config.py
touch ai/app/core/logging.py

# services
touch ai/app/services/retrieval.py
touch ai/app/services/embedding.py
touch ai/app/services/llm.py

# infrastructure
touch ai/app/infrastructure/pinecone.py
touch ai/app/infrastructure/redis/cache.py
touch ai/app/infrastructure/redis/publisher.py

# middleware
touch ai/app/middleware/correlation.py

# ai 루트 파일
touch ai/Dockerfile
touch ai/pyproject.toml
touch ai/poetry.lock

# infra
mkdir -p infra/jenkins
touch infra/jenkins/docker-compose.yml

# docs
mkdir -p docs/adr
touch docs/adr/0001-fastapi.md
touch docs/adr/0002-postgresql.md

echo "✅ 디렉토리 구조 생성 완료!"
tree . 2>/dev/null || find . -type f | sort
