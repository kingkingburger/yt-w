# 프로젝트 아키텍처

## 개요

이 프로젝트는 클린 코드 원칙과 SOLID 원칙을 적용하여 모듈화된 구조로 설계되었습니다.

## 프로젝트 구조

```
yt-w/
├── src/
│   └── yt_monitor/          # 메인 패키지
│       ├── __init__.py      # 패키지 초기화
│       ├── config.py        # 설정 관리 모듈
│       ├── logger.py        # 로깅 설정 모듈
│       ├── youtube_client.py # YouTube API 클라이언트
│       ├── downloader.py    # 스트림 다운로더
│       └── monitor.py       # 라이브 스트림 모니터
├── test/                    # 테스트 디렉토리
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_youtube_client.py
│   ├── test_downloader.py
│   └── test_monitor.py
├── main.py                  # 엔트리포인트
├── config.json              # 설정 파일
└── pyproject.toml          # 프로젝트 메타데이터
```

## 모듈 설명

### 1. config.py - 설정 관리

**책임**: 설정 파일 로드 및 검증

**클래스**:
- `Config`: 설정 데이터 클래스 (dataclass)
- `ConfigLoader`: 설정 파일 로더

**주요 기능**:
- JSON 설정 파일 로드
- 설정값 검증
- 기본값 제공

**클린 코드 원칙**:
- 단일 책임 원칙 (SRP): 설정 관리만 담당
- 데이터 클래스 사용으로 명확한 타입 정의
- 검증 로직 분리

### 2. logger.py - 로깅 설정

**책임**: 로깅 시스템 설정

**함수**:
- `setup_logger()`: 로거 인스턴스 생성 및 설정

**주요 기능**:
- 파일 및 콘솔 핸들러 설정
- 로그 포맷 지정
- 로그 디렉토리 자동 생성

**클린 코드 원칙**:
- 함수형 접근으로 간단한 API 제공
- 재사용 가능한 설정

### 3. youtube_client.py - YouTube 클라이언트

**책임**: YouTube 채널의 라이브 스트림 감지

**클래스**:
- `LiveStreamInfo`: 라이브 스트림 정보 데이터 클래스
- `YouTubeClient`: YouTube API 클라이언트

**주요 기능**:
- 다중 전략으로 라이브 스트림 감지
  - /live 엔드포인트
  - /streams 탭
  - 채널 메인 페이지
- 오류 처리 및 폴백

**클린 코드 원칙**:
- 전략 패턴: 여러 감지 방법 시도
- 메서드 분리로 가독성 향상
- 명확한 반환 타입 (Tuple[bool, Optional[LiveStreamInfo]])

### 4. downloader.py - 스트림 다운로더

**책임**: 라이브 스트림 다운로드

**클래스**:
- `StreamDownloader`: 스트림 다운로드 담당

**주요 기능**:
- yt-dlp를 사용한 스트림 다운로드
- 자동 파일명 생성 (타임스탬프 포함)
- MP4 형식으로 변환

**클린 코드 원칙**:
- 단일 책임 원칙: 다운로드만 담당
- 설정 분리 (yt-dlp 옵션 빌더)
- 명확한 성공/실패 반환

### 5. monitor.py - 라이브 스트림 모니터

**책임**: 전체 모니터링 프로세스 조율

**클래스**:
- `LiveStreamMonitor`: 모니터링 오케스트레이터

**주요 기능**:
- 주기적인 라이브 스트림 확인
- 감지 시 자동 다운로드
- 다운로드 상태 관리

**클린 코드 원칙**:
- 의존성 주입 (DI): YouTubeClient, StreamDownloader 주입 가능
- 단일 책임 원칙: 조율만 담당
- 명확한 상태 관리 (is_downloading)

## 설계 원칙

### SOLID 원칙 적용

1. **Single Responsibility Principle (SRP)**
   - 각 클래스는 하나의 책임만 가짐
   - ConfigLoader: 설정 로드
   - YouTubeClient: 라이브 감지
   - StreamDownloader: 다운로드
   - LiveStreamMonitor: 조율

2. **Open/Closed Principle (OCP)**
   - 확장에는 열려있고 수정에는 닫혀있음
   - 새로운 감지 방법 추가 가능
   - 새로운 다운로드 전략 추가 가능

3. **Liskov Substitution Principle (LSP)**
   - 인터페이스 기반 설계로 대체 가능성 보장

4. **Interface Segregation Principle (ISP)**
   - 작고 명확한 인터페이스 제공

5. **Dependency Inversion Principle (DIP)**
   - 의존성 주입으로 느슨한 결합
   - LiveStreamMonitor는 구체 클래스가 아닌 추상화에 의존

### 클린 코드 원칙

1. **의미 있는 이름**
   - 명확한 클래스/메서드/변수 이름
   - 축약어 최소화

2. **함수는 작게**
   - 각 메서드는 한 가지 일만 수행
   - 메서드 길이 최소화

3. **주석보다 코드로 설명**
   - 자기 설명적인 코드 작성
   - docstring으로 API 문서화

4. **에러 처리**
   - 명확한 예외 처리
   - 적절한 로깅

5. **테스트 가능한 설계**
   - 의존성 주입으로 모킹 가능
   - 각 모듈 독립적으로 테스트 가능

## 테스트 전략

### 단위 테스트

- 각 모듈별로 독립적인 테스트
- Mock 사용으로 외부 의존성 제거
- 엣지 케이스 및 에러 시나리오 테스트

### 테스트 커버리지

- Config 모듈: 검증 로직 테스트
- YouTubeClient: 감지 로직 및 폴백 테스트
- StreamDownloader: 다운로드 로직 테스트
- LiveStreamMonitor: 통합 시나리오 테스트

## 확장 가능성

### 새로운 감지 방법 추가

`YouTubeClient` 클래스에 새로운 `_check_*` 메서드 추가

### 다른 플랫폼 지원

- 새로운 클라이언트 클래스 생성
- 동일한 인터페이스 구현

### 다운로드 전략 변경

- StreamDownloader 클래스 확장 또는 대체
- 의존성 주입으로 쉽게 교체 가능

## 성능 고려사항

1. **비동기 처리 가능성**
   - 현재는 동기 방식
   - 필요 시 asyncio로 변환 가능

2. **메모리 관리**
   - 컨텍스트 매니저 사용 (with 문)
   - 리소스 자동 정리

3. **로깅 최적화**
   - 파일 핸들러 버퍼링
   - 로그 레벨 조정 가능
