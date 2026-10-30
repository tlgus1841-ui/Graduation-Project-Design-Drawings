# 🚀 [구현 계획서] [Phase 6-B] 올인원 Docker Compose 패키징 & 프로덕션 서빙

> **문서 상태**: 구현 계획 수립 완료 (승인 대기)  
> **대상 단계**: Phase 6-B (운영 안정화 및 프로덕션 서빙 패키징)  
> **기반 문서**: [종합 로드맵 (ROADMAP.md)](ROADMAP.md#phase-6-b), [운영자 매뉴얼 (operator_manual.md)](../manual/operator_manual.md)

---

## 1. 개요 및 추진 배경

### 1.1 해결하고자 하는 문제 (현행 구조 한계점)
현재 Self-Defending SDN Tower 시스템은 Phase 6-A를 통해 Native OVS 커널 토폴로지 구축 및 검증을 완료하였으나, 관제 스택의 실행 및 운영 구조에 다음과 같은 프로덕션 수준의 한계가 존재합니다.

1. **tmux 백그라운드 세션 의존성**:
   - `FastAPI`(관제 백엔드), `AI Worker`(이상 탐지 엔진), `UI`(React 프론트엔드)가 각각 분리된 tmux 세션(`backend`, `ai-worker`, `frontend`)에서 수동 스크립트로 기동됨.
   - 호스트 또는 프로세스 비정상 종료 시 자동 재기동(Auto-Restart / Self-Healing)이 불가능하며, 프로세스 모니터링이 부재함.
2. **Vite 개발 서버(`npm run dev`)의 프로덕션 노출**:
   - Node.js 기반 Vite Dev Server(포트 `5173`)가 외부에 직접 노출되어 있어 메모리 누수, 단일 스레드 병목, 불필요한 HMR(Hot Module Replacement) 웹소켓 부하 발생.
   - 정적 리소스에 대한 압축(gzip/brotli), 브라우저 캐싱, HTTP 최적화가 전무하여 실사용 트래픽 인가 시 취약.
3. **다중 포트 노출 및 보안/네트워크 복잡도**:
   - UI(`5173`), API(`8000`), Ryu OpenFlow(`6653`), Ryu REST(`8080`), Redis(`6379`) 등이 호스트 포트로 산재되어 GCP/방화벽 규칙 관리 비용 증가 및 브라우저 CORS 문제 유발.
4. **호스트 환경 오염 및 재현성 부족**:
   - 호스트 OS의 Node.js/npm, uv/Python 패키지 버전 등에 의존하여 새로운 환경(신규 VM, 온프레미스 서버) 배포 시 종속성 오류 위험 존재.

### 1.2 Phase 6-B 핵심 목표
* **원클릭 올인원 배포**: `docker compose up -d` 단 한 줄로 Redis, Ryu, FastAPI, AI Worker, Nginx(UI) 전체 관제 스택 완전 자동 기동.
* **프로덕션 서빙 최적화**: Vite 개발 서버를 탈피하고, Multi-stage 빌드된 React SPA 정적 번들을 Nginx 1.25 Alpine에서 초경량·고속 서빙.
* **단일 엔드포인트 리버스 프록시 (Single Entrypoint)**:
  - Nginx가 포트 `80` (운영 표준 포트)을 전담 수신하여 정적 파일, `/api/` REST API, `/ws` WebSocket을 일원화 프록시 처리.
  - 외부 노출 포트를 단일화하고 브라우저 CORS 완벽 제거.
* **헬스체크 기반 오케스트레이션 및 자율 복구**:
  - 각 컨테이너별 정밀 헬스체크 정의 및 `condition: service_healthy`를 통한 엄격한 기동 순서 보장.
  - 컨테이너 크래시 시 Docker Daemon 수준의 자동 재시작(`restart: unless-stopped`) 보장.

---

## 2. 올인원 프로덕션 아키텍처 설계

### 2.1 전체 시스템 배치도

```mermaid
flowchart TD
    subgraph Client["외부 클라이언트 (관리자 브라우저)"]
        Browser["웹 브라우저 (포트 80 접속)"]
    end

    subgraph DockerCompose["Docker Compose 단일 네트워크 환경 (sdn-net)"]
        subgraph FrontendProxy["[sdn-ui] Nginx 1.25 Alpine (Reverse Proxy)"]
            StaticFiles["React SPA 정적 파일 (dist)"]
            ProxyRule1["/ -> 정적 파일 서빙"]
            ProxyRule2["/api/ -> http://sdn-api:8000"]
            ProxyRule3["/ws -> ws://sdn-api:8000"]
        end

        subgraph Backend["[sdn-api] FastAPI Backend (Python 3.10)"]
            APIServer["Uvicorn ASGI Server"]
            WSHub["WebSocket Client Hub"]
            RedisConn["Redis Pub/Sub Subscriber"]
        end

        subgraph AI["[sdn-ai-worker] AI Engine (Python 3.10)"]
            Detector["Isolation Forest & 6종 분류기"]
            Ewma["EWMA Baseline & Criteria Engine"]
        end

        subgraph Controller["[sdn-ryu] SDN Controller (Python 3.8)"]
            RyuApp["Ryu 4.34 / OpenFlow 1.3"]
            FSM["FSM 방어 & 선제적 우회 라우팅"]
        end

        subgraph Broker["[sdn-redis] Redis 7.2 Broker"]
            RedisCore["Redis IPC Pub/Sub"]
        end
    end

    subgraph HostDataPlane["호스트 Linux Kernel (Data Plane)"]
        OVS["Native OVS 2.17 (s1, s2, s3, s4)"]
        Netns["Linux ip netns (ns_legit, ns_attacker, ns_server)"]
    end

    Browser -->|HTTP 80 / WS 80| FrontendProxy
    ProxyRule2 -->|내부 프록시| Backend
    ProxyRule3 -->|WebSocket 프록시| Backend
    
    Backend <-->|Pub/Sub & State| Broker
    AI <-->|Stats 수신 / Alert·Command 발행| Broker
    Controller <-->|Telemetry 발행 / Rule 수신| Broker
    
    OVS <-->|OpenFlow 1.3 (포트 6653)| Controller
```

### 2.2 서비스 구성 명세표

| 서비스명 (Service) | 컨테이너명 | 기반 이미지 | 주요 역할 | 노출 포트 | 의존성 (Depends On) |
|---|---|---|---|:---:|---|
| **`redis-broker`** | `sdn-redis` | `redis:7.2-alpine` | IPC 메시지 브로커 (stats, alert, command, flowcount) | `6379:6379` | 없음 (최우선 기동) |
| **`ryu-controller`**| `sdn-ryu` | `Dockerfile.ryu` (Python 3.8) | OpenFlow 1.3 제어, Dijkstra 우회, FSM 상태 관리 | `6653:6653`<br>`8080:8080` | `redis-broker` (healthy) |
| **`control-api`** | `sdn-api` | `Dockerfile.api` (Python 3.10-slim) | WebSocket 브로드캐스팅, REST 수동 제어, Redis 브릿지 | 내부 8000 | `redis-broker` (healthy) |
| **`ai-worker`** | `sdn-ai-worker` | `Dockerfile.ai` (Python 3.10-slim) | 1초 실측 이상 탐지(Isolation Forest), 6종 공격 정밀 분류 | 내부 전용 | `redis-broker` (healthy)<br>`ryu-controller` (started) |
| **`control-ui`** | `sdn-ui` | `Dockerfile.ui` (Node 20 + Nginx) | React 정적 서빙 + Nginx API/WebSocket 리버스 프록시 | **`80:80`**<br>(옵션 `5173:80`) | `control-api` (healthy) |

---

## 3. 세부 컴포넌트별 구현 명세

### 3.1 프론트엔드 프로덕션 빌드 & Nginx 리버스 프록시 (`Dockerfile.ui` & `nginx.conf`)

#### A. Multi-stage Dockerfile (`ui/Dockerfile.ui`)
* **Stage 1 (Builder)**: `node:20-alpine` 환경에서 `npm ci` 후 `npm run build` 수행 (TypeScript/Rollup 번들링 최적화).
* **Stage 2 (Runner)**: `nginx:1.25-alpine` 경량 이미지에 빌드 결과물(`dist/`) 및 커스텀 `nginx.conf` 복사. 이미지 크기 **25MB 이하** 달성.

#### B. Nginx 리버스 프록시 설정 (`ui/nginx.conf`)
* **SPA 라우팅 지원**: `try_files $uri $uri/ /index.html;` 로 404 방지.
* **WebSocket 역방향 프록시**:
  ```nginx
  location /ws {
      proxy_pass http://sdn-api:8000/ws;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_set_header Host $host;
      proxy_read_timeout 86400s;
  }
  ```
* **REST API 프록시**:
  ```nginx
  location /api/ {
      proxy_pass http://sdn-api:8000/api/;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
  ```
* **정적 에셋 압축 및 캐싱**: `.js`, `.css`, `.svg` 파일에 `gzip on` 및 `Cache-Control: public, max-age=31536000` 적용.

#### C. 프론트엔드 API/WebSocket 접속 로직 개선
* 현행 `ui/src/lib/api.js` 및 `ui/src/hooks/useControlTowerSocket.js`는 `window.location.hostname:8000`으로 포트를 하드코딩 중.
* Nginx 리버스 프록시 도입에 맞춰 **동일 포트(Origin) 접속**을 우선 지원하도록 리팩토링:
  - 별도 포트 지정 없이 `window.location.host` (포트 포함 Origin)를 사용하도록 하여, 80 포트 단일 진입점 완벽 호환.

---

### 3.2 백엔드 API & AI Worker 컨테이너화 (`Dockerfile.api`, `Dockerfile.ai`)

#### A. 관제 백엔드 (`Dockerfile.api`)
* **기반 이미지**: `python:3.10-slim`
* **빌드 도구**: 빠른 의존성 설치를 위해 `uv` 활용 또는 표준 `pip install` (컨테이너 캐시 최적화).
* **의존성**: `fastapi`, `uvicorn[standard]`, `redis`, `pydantic`, `networkx`, `websockets`.
* **실행 명령**: `uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 --loop uvloop`
* **헬스체크 엔드포인트**: `curl -f http://localhost:8000/api/health || exit 1`

#### B. AI 이상 탐지 엔진 (`Dockerfile.ai`)
* **기반 이미지**: `python:3.10-slim`
* **의존성**: `scikit-learn==1.3.2`, `joblib==1.3.2`, `numpy==1.24.3`, `redis==5.0.1`, `pydantic`.
* **학습 모델 파일**: `model/isolation_forest.joblib` 볼륨 마운트 또는 이미지 내장.
* **실행 명령**: `python -m model.inference_worker --model /app/model/isolation_forest.joblib --redis-url redis://sdn-redis:6379/0`
* **자율 회복력(Resilience)**: Redis 연결 단절 시 지수 백오프(Exponential Backoff) 재시도 로직 보강.

---

### 3.3 All-in-One `docker-compose.yml` 최종 설계

```yaml
version: '3.8'

services:
  # 1. 메시지 브로커 (Redis 7.2)
  redis-broker:
    image: redis:7.2-alpine
    container_name: sdn-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --port 6379 --appendonly no
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 2s
      retries: 5
    networks:
      - sdn-net

  # 2. SDN 제어 평면 (Ryu Controller 4.34)
  ryu-controller:
    build:
      context: ./ryu
      dockerfile: Dockerfile.ryu
    container_name: sdn-ryu
    restart: unless-stopped
    ports:
      - "6653:6653"
      - "8080:8080"
    environment:
      - PYTHONPATH=/app:/workspace
      - REDIS_URL=redis://sdn-redis:6379/0
    volumes:
      - ./ryu/app:/app
      - ./harness:/workspace/harness
    command: ryu-manager --ofp-tcp-listen-port 6653 --observe-links /app/controller.py
    depends_on:
      redis-broker:
        condition: service_healthy
    networks:
      - sdn-net

  # 3. 관제 API 백엔드 (FastAPI)
  control-api:
    build:
      context: .
      dockerfile: api/Dockerfile.api
    container_name: sdn-api
    restart: unless-stopped
    ports:
      - "8000:8000"  # 직접 디버깅 및 하위 호환용 포트 매핑 유지
    environment:
      - SDN_MOCK=0
      - REDIS_URL=redis://sdn-redis:6379/0
      - LOG_LEVEL=INFO
    depends_on:
      redis-broker:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - sdn-net

  # 4. AI 이상 탐지 및 분류 워커
  ai-worker:
    build:
      context: .
      dockerfile: model/Dockerfile.ai
    container_name: sdn-ai-worker
    restart: unless-stopped
    environment:
      - REDIS_URL=redis://sdn-redis:6379/0
      - PYTHONUNBUFFERED=1
    volumes:
      - ./model:/app/model
    command: python -m model.inference_worker --model /app/model/isolation_forest.joblib --redis-url redis://sdn-redis:6379/0
    depends_on:
      redis-broker:
        condition: service_healthy
      control-api:
        condition: service_healthy
    networks:
      - sdn-net

  # 5. 웹 프론트엔드 & 리버스 프록시 (Nginx 1.25 + React SPA)
  control-ui:
    build:
      context: ./ui
      dockerfile: Dockerfile.ui
    container_name: sdn-ui
    restart: unless-stopped
    ports:
      - "80:80"      # 프로덕션 표준 단일 진입 포트
      - "5173:80"    # 기존 5173 포트 접속 사용자 하위 호환 리다이렉션/서빙
    depends_on:
      control-api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1/"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - sdn-net

networks:
  sdn-net:
    name: sdn-net
    driver: bridge
```

---

## 4. Native Data Plane 연계 및 운영 자동화

### 4.1 Native OVS와 Docker Compose 간 통신 구조
* OVS는 리눅스 커널 모듈(`openvswitch.ko`) 및 veth 페어를 직접 제어하므로, 호스트 네이티브 환경에서 `setup_native_ovs.sh`로 구동되는 구조가 지연시간(0.07ms) 및 최대 처리량(952k PPS) 측면에서 최적입니다.
* OVS 스위치(`s1~s4`)는 `127.0.0.1:6653` (또는 Docker Gateway IP)을 통해 컨테이너의 포트 `6653`으로 안전하게 OpenFlow 세션을 맺습니다.

### 4.2 올인원 운영 스크립트 고도화 (`scripts/vm_demo_controller.sh` 및 `prod_stack.sh`)
* 기존의 `tmux` 기반 런처 로직을 Docker Compose 통합 명령으로 전환:
  - `start-all` / `restart-all`:
    1. `setup_native_ovs.sh` (OVS 4-스위치 토폴로지 구축)
    2. `docker compose up -d --build` (전체 관제 스택 자동 기동 및 헬스체크 대기)
    3. `ns_legit` 백그라운드 핑 가동 (`ping -i 0.5 10.0.0.4`)
  - `stop`:
    1. 백그라운드 핑 종료
    2. `docker compose down` (전체 관제 컨테이너 정지 및 정리)
    3. `teardown_native_ovs.sh` (OVS 토폴로지 및 netns 완벽 정리)
  - `status`:
    1. `docker compose ps` (5개 서비스 헬스 상태 한눈에 출력)
    2. OVS 브릿지 연결 상태 출력
    3. API 헬스체크 및 핑 로그 상태 출력

---

## 5. 단계별 실행 마일스톤 (Milestones)

```
[Milestone 1] 컨테이너 도커파일 구현 (M1)
  ├── api/Dockerfile.api (FastAPI 경량 이미지)
  ├── model/Dockerfile.ai (AI Worker 경량 이미지)
  └── ui/Dockerfile.ui (Node 멀티스테이지 + Nginx 1.25 Alpine)

[Milestone 2] Nginx 리버스 프록시 및 프론트엔드 엔드포인트 최적화 (M2)
  ├── ui/nginx.conf (정적 파일, /api/, /ws 일원화 라우팅)
  └── ui/src/lib/api.js & useControlTowerSocket.js (동적 Origin 호환 패치)

[Milestone 3] All-in-One docker-compose.yml 전면 개편 (M3)
  ├── 5개 서비스(Redis, Ryu, API, AI, UI) 통합 정의
  ├── 헬스체크 및 의존성 파이프라인(condition: service_healthy) 적용
  └── 리소스 한계 및 환경변수 템플릿(.env.example) 정비

[Milestone 4] 원클릭 운영 스크립트 개편 및 기존 도구 동기화 (M4)
  ├── scripts/prod_stack.sh 신설 (up / down / restart / status / logs)
  ├── scripts/vm_demo_controller.sh 내 tmux 의존성 완전 제거 및 Docker 통합
  └── docs/manual/operator_manual.md 운영 절차 최신화

[Milestone 5] 통합 E2E 검증 및 회귀 테스트 (M5)
  ├── 원클릭 기동 시간 및 메모리 풋프린트 실측
  ├── Nginx 리버스 프록시 WebSocket / API 응답 성능 검증
  ├── 6종 공격 주입 시 자동 우회/차단 실시간 연동 테스트 (267개 테스트 무결성 확인)
  └── 결과 보고서 작성
```

---

## 6. 검증 계획 및 합격 기준 (Acceptance Criteria)

| 검증 항목 | 검증 방식 | 합격 기준 (Acceptance Criteria) |
|---|---|---|
| **1. 원클릭 기동 및 자율 헬스체크** | `docker compose up -d` 실행 후 `docker compose ps` 상태 점검 | 5개 서비스 전원 30초 이내 `healthy` 상태 진입 |
| **2. Nginx 단일 진입점 동작** | 포트 `80` 브라우저 접속 및 `curl http://localhost/api/health` | HTTP 200 반환, UI 정상 로딩, WebSocket 연결 성공 |
| **3. WebSocket 실시간 브로드캐스팅** | UI 토폴로지 화면에서 패킷 카운트 실시간 업데이트 확인 | 60 FPS 렌더링 유지, 지연시간 < 50ms |
| **4. 이상 탐지 및 자동 방어 연동** | `scripts/native_attack.sh syn 10 500` 공격 주입 | AI 탐지 -> Alert 발행 -> 선제 우회 및 차단 정상 발동 |
| **5. 자동 복구(Self-Healing)** | `docker kill sdn-api` 강제 종료 후 동작 관찰 | 5초 이내 Docker에 의해 자동 재기동 및 세션 복구 |
| **6. 기존 테스트 회귀 방지** | `pytest tests/` 로컬 실행 | 267개 테스트 **100% Pass** 유지 |

---

## 7. 향후 Phase 6-B-2(동적 망 분리)와의 연계성

본 Phase 6-B가 완료되면:
1. 복잡한 다중 프로세스(tmux) 관리 부담이 제거되어, **Phase 6-B-2 (소프트웨어 정의 제로 트러스트 망 분리)**의 4-Table OpenFlow 파이프라인 개편 및 `ZONE_DENY` 엔진 확장을 훨씬 깨끗하고 격리된 환경에서 안전하게 개발 및 테스트할 수 있습니다.
2. 관제탑 UI에 망 분리 현황(USER/SERVER/ADMIN/QUARANTINE 4-Zone) 대시보드 및 수동 격리 복구 버튼을 서빙할 때도 별도의 웹 서버 설정 변경 없이 즉시 반영할 수 있는 탄탄한 배포 기반이 확립됩니다.
