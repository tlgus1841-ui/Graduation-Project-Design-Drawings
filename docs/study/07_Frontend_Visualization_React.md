# 🖥️ [제7편] 웹 관제탑 프론트엔드 (React + vis-network + 실시간 차트)

> ⬅️ [제6편: 분산 IPC & FastAPI WebSocket](./06_Distributed_System_and_FastAPI.md) | 🏠 [목차](./README.md) | ➡️ [제8편: 환경 설정 & 실전 트러블슈팅](./08_Environment_and_Troubleshooting.md)

본 문서는 실시간 사이버 보안 관제 센터(SOC: Security Operations Center) 느낌의 다크 테마 대시보드를 구축하기 위한 **React 18**, **vis-network(동적 토폴로지)**, **ApexCharts(실시간 시계열 메트릭)**의 연동 원리를 학습합니다.

---

## 1. 프론트엔드 기술 스택과 아키텍처

| 기술 / 라이브러리 | 버전 | 선정 사유 및 핵심 역할 |
|---|---|---|
| **React** | **18.2.0** | 컴포넌트 기반 선언형 UI, 고성능 상태 동기화 |
| **Vite** | **5.1.x** | 초고속 HMR(Hot Module Replacement) 지원 번들러 |
| **Tailwind CSS** | **3.4.1** | 사이버펑크/다크 테마 유틸리티 퍼스트 스타일링 |
| **vis-network** | **9.1.9** | Canvas 기반 고성능 대화형 네트워크 토폴로지 렌더링 |
| **ApexCharts** | **3.46.0** | 실시간 트래픽(PPS/BPS) 슬라이딩 윈도우 시계열 차트 |
| **Lucide React** | 최신 | 직관적인 보안 관제탑 아이콘 세트 |

---

## 2. `vis-network` 기반 실시간 토폴로지 시각화

텍스트 터미널에서 `ping` 결과만 보던 기존 방식에서 벗어나, 스위치와 링크의 상태 변화를 웹에서 직관적으로 파악할 수 있도록 시각화합니다.

### 2.1 물리 엔진(Physics) 안정화의 중요성
`vis-network`는 기본적으로 물리 엔진(Force-directed graph)이 켜져 있어 노드들이 자석처럼 밀고 당깁니다.
- 실시간으로 1초마다 트래픽 상태(색상, 굵기)를 업데이트할 때 물리 연산이 계속 켜져 있으면 **화면의 스위치들이 덜덜 떨리거나 위치가 제멋대로 튀는 현상**이 발생합니다.
- **해결책:** 초기 렌더링 후 좌표가 잡히면 물리 엔진을 끄거나(`physics: { enabled: false }`), 각 노드의 좌표를 명시적으로 고정(`fixed: true`)해야 합니다.

### 2.2 노드 및 링크의 상태별 시각화 색상 규격

```javascript
// 노드 및 링크 색상 테마 규격
const STATUS_COLORS = {
  NORMAL: { border: "#10B981", background: "#064E3B", label: "정상 (Normal)" },      // 녹색
  CONGESTED: { border: "#F59E0B", background: "#78350F", label: "혼잡 (Warning)" },   // 황색
  ATTACK: { border: "#EF4444", background: "#7F1D1D", label: "공격/차단 (Blocked)" }, // 적색
  DETOUR: { border: "#3B82F6", background: "#1E3A8A", label: "우회 경로 (Rerouted)" } // 청색
};
```

- **스위치 S1, S2, S3, S4:** 사각형(Box) 또는 스위치 아이콘으로 표시
- **호스트 H_legit, H_attacker, H_server:** 단말기 형태로 표시
- **링크(Edge) 애니메이션:**
  - 평상시: S1 $\to$ S2 $\to$ S4 링크가 실선 녹색
  - 공격 발생 시: S1-S2 링크는 적색으로 점멸, 트래픽은 S1 $\to$ S3 $\to$ S4 우회 링크(청색 점선 애니메이션)로 흐름 변경

---

## 3. 실시간 시계열 트래픽 차트 (ApexCharts)

### 3.1 슬라이딩 윈도우 (Sliding Window) 버퍼링
초당 1~2회 들어오는 PPS/BPS 데이터를 차트에 무한히 쌓으면 브라우저의 DOM 메모리가 폭증하여 브라우저 탭이 멈추게 됩니다.
따라서 **최근 30~60개의 데이터 포인트만 유지**하고 가장 오래된 데이터를 밀어내는 큐(Queue) 구조를 사용합니다:

```javascript
// 최근 30개 데이터만 유지하는 상태 업데이트 패턴
setTrafficData(prevData => {
  const newTime = new Date().toLocaleTimeString();
  const nextData = [...prevData, { x: newTime, y: incomingPps }];
  if (nextData.length > 30) {
    nextData.shift(); // 오래된 첫 번째 데이터 제거
  }
  return nextData;
});
```

### 3.2 이상치 스코어(Anomaly Score) 게이지
- AI Worker가 계산한 이상치 점수($0.0 \sim 1.0$)를 RadialBar(방사형 게이지) 차트로 표시합니다.
- `0.0 ~ 0.5`: 안전 (녹색)
- `0.5 ~ 0.7`: 주의 (황색)
- `0.7 ~ 1.0`: 침입 감지 (적색 경보 발생)

---

## 4. React 컴포넌트 구조와 실시간 WebSocket 연동

```
[ App.jsx ]
   ├── [ Navbar ]: 시스템 상태 배지 (CONNECTED / DISCONNECTED), 비상 정지 버튼
   ├── [ DashboardGrid ]
   │      ├── [ TopologyPanel ]: vis-network 기반 실시간 토폴로지 지도
   │      ├── [ MetricsPanel ]: 실시간 PPS / BPS 시계열 차트 & 게이지
   │      ├── [ AlertTimeline ]: 실시간 침입 탐지 & 차단 이벤트 로그
   │      └── [ ManualControlPanel ]: 관리자 수동 포트 격리/복원 제어기
```

### 4.1 React WebSocket 커스텀 훅 (자동 재연결)
네트워크 순단이나 백엔드 재시작 시 자동으로 재연결을 시도하는 복원력 있는 소켓 리스너를 구현합니다:

```javascript
import { useState, useEffect, useRef } from "react";

export function useSdnWebSocket(url) {
  const [data, setData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    let reconnectTimeout = null;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setIsConnected(true);
      
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        setData(payload);
      };

      ws.onclose = () => {
        setIsConnected(false);
        // 연결 종료 시 2초 후 자동 재시도
        reconnectTimeout = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [url]);

  return { data, isConnected };
}
```

---

> ⬅️ [제6편: 분산 IPC & FastAPI WebSocket](./06_Distributed_System_and_FastAPI.md) | 🏠 [목차](./README.md) | ➡️ [제8편: 환경 설정 & 실전 트러블슈팅](./08_Environment_and_Troubleshooting.md)
