# BE-v2
기존 백엔드 서버의 리팩토링 버전입니다.

## 1. 배경

v1은 백엔드 시스템의 첫 구현이었다. MongoDB + Express 기반으로 빠르게
완성에 집중했고, 동작은 했다. 하지만 다음과 같은 문제가 있었다.

- 트랜잭션 보장이 없어 데이터 정합성 이슈 발생 가능
- 비즈니스 로직이 라우트 핸들러에 흩어져 테스트, 유지보수 어려움
- 인증이 단순 JWT 단일 토큰 방식으로 보안 취약점 존재
- 응답이 동기 처리라 사용자가 5초 이상 대기

v2는 위 문제들을 체계적으로 해결하는 것을 목표로 했다.

## 2. v1의 한계

### 2.1 데이터 정합성 — MongoDB의 트랜잭션 부재

문제 시나리오: 사용자가 메시지 전송 > answer 저장 > chat의
last_message_at 업데이트가 두 단계로 진행. 둘 사이 실패 시
데이터 불일치. 하나의 라우트 안에 

해결 방향: PostgreSQL의 ACID 트랜잭션 + ON DELETE CASCADE.

### 2.2 인증 — 단일 JWT의 보안 한계

문제 시나리오: 7일 수명 access token만 사용. 탈취 시
7일간 무력. blacklist 메커니즘 없어 즉시 무효화 불가.

해결 방향: Access Token (15분) + Refresh Token (14일) 분리.
Refresh Rotation으로 탈취 탐지.

### 2.3 

## 3. v2의 핵심 결정

### 3.1 PostgreSQL + SQLAlchemy 2.0 (ADR-001)

선택: MongoDB → PostgreSQL.
이유: ACID, 외래키 제약, 마이그레이션 도구.
대안 검토: PostgreSQL + Prisma도 고려했으나 SQLAlchemy의
타입 힌트 통합과 비동기 지원이 더 성숙.

### 3.2 OAuth + JWT + Refresh Rotation (ADR-005)

(짧게)

### 3.3 Repository + Service 패턴 (ADR-013)

(짧게)

(이런 식으로 3~5개)

### 결정의 큰 흐름

ADR 14개를 작성하면서 모든 결정에 이유를 붙이는 습관을 들였다.
"왜 이걸 선택했나"보다 "왜 다른 것을 선택하지 않았나"를
명시하는 게 본인에게도 학습이 됐다.

## 4. 가장 어려웠던 문제 — AI 응답의 동기 처리 한계

### 4.1 문제 발견

Stage 2에서 AI 호출을 동기 방식으로 구현했다 (`POST → AI 5초
대기 → 응답`). curl로 실제 응답 시간을 측정했다.

POST /messages: 5.2초

이 시간 동안 사용자는 빈 화면을 본다. ChatGPT 같은
사용자 경험이 불가능했다.

### 4.2 시도한 접근들

**접근 1: BE에서 응답을 chunk로 분할 (가짜 스트리밍)**

AI 서버에서 한 번에 받은 응답을 BE가 글자 단위로 쪼개서
보낸다. 코드 변경 적지만 사용자가 5초 대기는 동일
(받은 후 흘려보낼 뿐).

**접근 2: 진짜 엔드투엔드 SSE 스트리밍**

AI 서버 자체를 SSE로 전환. AI가 토큰 생성하는 즉시
BE를 거쳐 클라이언트로 전달.

후자를 선택. 사용자 체감 시간을 **5초 → 100ms**로 줄임.

### 4.3 구현 — Redis Pub/Sub의 도입 동기

처음엔 BE 단일 인스턴스에서 SSE만 처리했다. 단순했다.
하지만 다음 문제를 인지했다:

- 멀티 인스턴스 BE 환경에서 사용자가 다른 인스턴스로
  라우팅되면 SSE 받을 수 없음
- 같은 사용자의 다른 디바이스에서 같은 답변을 동기화 불가

해결: Redis Pub/Sub으로 채널 분리. 어느 BE 인스턴스든
같은 채널 구독. 멀티 디바이스 동기화도 자연스럽게.

### 4.4 한계와 다음 단계

Redis Pub/Sub은 fire-and-forget 모델이라 publish 시점에
구독 중이 아닌 클라이언트는 메시지를 못 받는다.

정상 흐름(POST 직후 SSE 구독)에서는 문제없지만,
연결 끊김 후 재구독은 답변을 못 받는 한계.

해결 방안 (v3 후속):
- Redis Streams로 마이그레이션 (메시지 영속성)
- 또는 chunk를 일시 캐시하고 catchup 로직 추가

본 프로젝트는 학습·검증 목적으로 단순 Pub/Sub 채택.


## 5. 의식적으로 미룬 것들 (v3 후속)

### 5.1 OAuth state Redis 저장

현재 in-memory dict로 구현. 단일 인스턴스에서 동작하지만
멀티 인스턴스 환경에서는 인스턴스 A가 시작한 OAuth를
인스턴스 B가 콜백 처리할 때 실패.

ADR-007에서 결정했지만 본 프로젝트에서는 Phase 5의
Redis Pub/Sub 구현을 우선했다. v3에서 0.3일이면 추가 가능.

### 5.2 분산 작업 큐

현재 백그라운드 작업은 asyncio.create_task로 BE 프로세스 안.
멀티 인스턴스 + 작업 분산이 필요하면 Celery, RQ 같은 별도
큐가 필요. 본 프로젝트는 단일 인스턴스라 미도입.

### 5.3 Refresh Token Rotation의 grace period

현재 Refresh 사용 즉시 rotation. 네트워크 재시도 시나리오에서
같은 토큰을 두 번 보내면 두 번째가 reuse로 탐지되어 강제 로그아웃.

해결책: rotation 후 짧은 grace period(5초) 안의 재사용은
허용. 본 프로젝트에서는 미구현.

### 5.4 통합 테스트 부재

현재 단위 테스트 (Repository, Service)와 manual curl 테스트만.
TestClient + httpx 기반 통합 테스트 미작성.

이유: 시간 제약. 향후 추가 예정.

## 5. 의식적으로 미룬 것들 (v3 후속)

### 5.1 OAuth state Redis 저장

현재 in-memory dict로 구현. 단일 인스턴스에서 동작하지만
멀티 인스턴스 환경에서는 인스턴스 A가 시작한 OAuth를
인스턴스 B가 콜백 처리할 때 실패.

ADR-007에서 결정했지만 본 프로젝트에서는 Phase 5의
Redis Pub/Sub 구현을 우선했다. v3에서 0.3일이면 추가 가능.

### 5.2 분산 작업 큐

현재 백그라운드 작업은 asyncio.create_task로 BE 프로세스 안.
멀티 인스턴스 + 작업 분산이 필요하면 Celery, RQ 같은 별도
큐가 필요. 본 프로젝트는 단일 인스턴스라 미도입.

### 5.3 Refresh Token Rotation의 grace period

현재 Refresh 사용 즉시 rotation. 네트워크 재시도 시나리오에서
같은 토큰을 두 번 보내면 두 번째가 reuse로 탐지되어 강제 로그아웃.

해결책: rotation 후 짧은 grace period(5초) 안의 재사용은
허용. 본 프로젝트에서는 미구현.

### 5.4 통합 테스트 부재

현재 단위 테스트 (Repository, Service)와 manual curl 테스트만.
TestClient + httpx 기반 통합 테스트 미작성.

이유: 시간 제약. 향후 추가 예정.