# 테스트 가이드

## 테스트 실행

### 모든 테스트 실행

```bash
uv run pytest
```

### 상세한 출력과 함께 실행

```bash
uv run pytest -v
```

### 특정 테스트 파일만 실행

```bash
uv run pytest test/test_config.py
```

### 특정 테스트 클래스만 실행

```bash
uv run pytest test/test_config.py::TestConfigLoader
```

### 특정 테스트 메서드만 실행

```bash
uv run pytest test/test_config.py::TestConfigLoader::test_load_valid_config_file
```

### 커버리지와 함께 실행

```bash
uv run pytest --cov=src --cov-report=html
```

## 테스트 구조

### 테스트 파일 구성

```
test/
├── __init__.py
├── test_config.py           # 설정 모듈 테스트
├── test_youtube_client.py   # YouTube 클라이언트 테스트
├── test_downloader.py       # 다운로더 테스트
└── test_monitor.py          # 모니터 통합 테스트
```

## 테스트 케이스 설명

### test_config.py

**TestConfig 클래스**
- `test_valid_config`: 유효한 설정 생성 테스트
- `test_empty_channel_url_raises_error`: 빈 채널 URL 검증
- `test_invalid_check_interval_raises_error`: 잘못된 체크 간격 검증
- `test_empty_download_directory_raises_error`: 빈 다운로드 디렉토리 검증

**TestConfigLoader 클래스**
- `test_load_valid_config_file`: 유효한 설정 파일 로드
- `test_load_nonexistent_file_raises_error`: 존재하지 않는 파일 처리
- `test_load_invalid_json_raises_error`: 잘못된 JSON 처리
- `test_load_dict`: 딕셔너리에서 설정 로드
- `test_load_dict_with_defaults`: 기본값 병합 테스트

### test_youtube_client.py

**TestLiveStreamInfo 클래스**
- `test_create_with_full_url`: 전체 URL로 생성
- `test_create_with_partial_url`: 부분 URL 자동 변환
- `test_url_already_has_http`: URL 포맷 유지

**TestYouTubeClient 클래스**
- `test_initialization_with_logger`: 커스텀 로거로 초기화
- `test_initialization_without_logger`: 기본 로거로 초기화
- `test_check_if_live_endpoint_success`: /live 엔드포인트 감지 성공
- `test_check_if_live_not_live`: 라이브 없음 처리
- `test_check_if_live_streams_tab_success`: /streams 탭 감지 성공
- `test_check_if_live_all_methods_fail`: 모든 감지 방법 실패 처리
- `test_check_if_live_skips_invalid_entries`: 잘못된 항목 스킵

### test_downloader.py

**TestStreamDownloader 클래스**
- `test_initialization`: 다운로더 초기화
- `test_initialization_creates_directory`: 디렉토리 자동 생성
- `test_generate_output_path`: 출력 경로 생성
- `test_build_ydl_options`: yt-dlp 옵션 빌드
- `test_download_success`: 다운로드 성공
- `test_download_failure`: 다운로드 실패 처리
- `test_download_with_custom_prefix`: 커스텀 파일명 접두사
- `test_perform_download`: 다운로드 수행

### test_monitor.py

**TestLiveStreamMonitor 클래스**
- `test_initialization`: 모니터 초기화
- `test_initialization_with_custom_clients`: 커스텀 클라이언트로 초기화
- `test_monitor_cycle_no_live_stream`: 라이브 없는 경우
- `test_monitor_cycle_live_stream_found`: 라이브 감지 및 다운로드
- `test_monitor_cycle_skips_when_downloading`: 다운로드 중 체크 스킵
- `test_handle_live_stream_successful_download`: 성공적인 다운로드 처리
- `test_handle_live_stream_failed_download`: 실패한 다운로드 처리
- `test_handle_live_stream_exception_resets_flag`: 예외 발생 시 플래그 리셋
- `test_start_with_keyboard_interrupt`: 키보드 인터럽트 처리
- `test_start_handles_exception`: 예외 처리 및 계속 실행
- `test_log_startup_info`: 시작 정보 로깅

## 테스트 작성 가이드

### Fixture 사용

pytest fixture를 사용하여 테스트 데이터 및 객체 생성:

```python
@pytest.fixture
def config():
    """Create a test configuration."""
    return Config(
        channel_url="https://www.youtube.com/@test",
        check_interval_seconds=60,
        download_directory="./test_downloads",
        log_file="./test.log",
        video_quality="best",
        download_format="best"
    )
```

### Mock 사용

외부 의존성을 Mock으로 대체:

```python
@patch('src.yt_monitor.youtube_client.yt_dlp.YoutubeDL')
def test_check_if_live_endpoint_success(self, mock_ydl_class, client):
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = Mock(return_value=mock_ydl)
    mock_ydl.__exit__ = Mock(return_value=False)
    mock_ydl.extract_info.return_value = {
        'is_live': True,
        'id': 'abc123'
    }
    mock_ydl_class.return_value = mock_ydl

    is_live, info = client.check_if_live("https://www.youtube.com/@test")

    assert is_live is True
```

### 예외 테스트

pytest.raises를 사용하여 예외 테스트:

```python
def test_empty_channel_url_raises_error(self):
    with pytest.raises(ValueError, match="channel_url cannot be empty"):
        Config(
            channel_url="",
            check_interval_seconds=60,
            download_directory="./downloads",
            log_file="./test.log",
            video_quality="best",
            download_format="best"
        )
```

### 임시 파일 테스트

TemporaryDirectory 또는 NamedTemporaryFile 사용:

```python
from tempfile import TemporaryDirectory

@pytest.fixture
def temp_dir():
    with TemporaryDirectory() as tmpdir:
        yield tmpdir
```

## 테스트 모범 사례

### 1. AAA 패턴 사용

- **Arrange**: 테스트 설정
- **Act**: 테스트 실행
- **Assert**: 결과 검증

```python
def test_download_success(self, mock_ydl_class, downloader):
    # Arrange
    mock_ydl = MagicMock()
    mock_ydl.download.return_value = None
    mock_ydl_class.return_value = mock_ydl

    # Act
    result = downloader.download(
        stream_url="https://www.youtube.com/watch?v=test123",
        filename_prefix="test_stream"
    )

    # Assert
    assert result is True
```

### 2. 명확한 테스트 이름

테스트 이름만 보고도 무엇을 테스트하는지 알 수 있어야 함:

```python
def test_load_nonexistent_file_raises_error(self)
def test_check_if_live_endpoint_success(self)
def test_download_with_custom_prefix(self)
```

### 3. 하나의 개념만 테스트

각 테스트는 하나의 동작/개념만 검증:

```python
# Good
def test_config_validates_channel_url(self)
def test_config_validates_check_interval(self)

# Bad
def test_config_validates_all_fields(self)
```

### 4. 독립적인 테스트

테스트는 서로 독립적이어야 하며 실행 순서에 의존하지 않아야 함.

### 5. 테스트 격리

각 테스트는 격리된 환경에서 실행되어야 함:
- Fixture 사용
- Mock 사용
- 임시 디렉토리 사용

## CI/CD 통합

### GitHub Actions 예제

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv sync
      - name: Run tests
        run: uv run pytest
```

## 문제 해결

### 테스트 실패 디버깅

1. **상세 출력 확인**
   ```bash
   uv run pytest -vv
   ```

2. **특정 테스트만 실행**
   ```bash
   uv run pytest test/test_config.py -k test_load_valid_config_file
   ```

3. **로그 출력 확인**
   ```bash
   uv run pytest -s
   ```

4. **pdb로 디버깅**
   ```bash
   uv run pytest --pdb
   ```

### 일반적인 문제

1. **Import 에러**
   - PYTHONPATH 확인
   - 패키지 구조 확인

2. **Mock 문제**
   - Mock 경로가 정확한지 확인
   - 컨텍스트 매니저 Mock 시 `__enter__`와 `__exit__` 구현

3. **비동기 테스트**
   - pytest-asyncio 사용
   - async/await 구문 지원
