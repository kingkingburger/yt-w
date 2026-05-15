# Project Coding Guidelines for Claude

You are an expert software engineer. **Consistency is the absolute priority.** When generating code, your primary goal is to maintain the uniformity of the existing codebase while adhering to the principles below.

## 0. Consistency & Uniformity (최우선: 통일성)
* **Match Existing Style:** Before writing new code, analyze the existing file structure, naming conventions, and patterns. Mimic them strictly.
* **Consistency over "Best Practice":** If a specific "best practice" contradicts the established style of the project, follow the project's established style unless explicitly instructed to refactor.
* **Uniform Formatting:** Stick to the existing indentation, quote styles (single vs double), and spacing rules.

## 1. Type Safety (타입 안정성 필수)
* **Explicit Typing:** All variables, function arguments, and return values must have explicit type annotations.
* **No `Any`:** Avoid `Any`. Use `Generic`, `Union`, or `TypeVar`.
* **Data Contracts:** Use strict schemas (e.g., `Pydantic` models, Interfaces) for data passing, not raw dictionaries.

## 2. Functional Core & Purity (순수 함수 지향)
* **Pure Functions:** Business logic must be implemented as Pure Functions.
    * Output depends **only** on input arguments.
    * No access to global state or external scope variables.
* **Side Effects Isolation:** Perform I/O (DB, API) only at the boundaries (controllers/entry points). Keep the core logic pure.
* **Immutability:** Prefer returning new instances over mutating arguments.

## 3. Low Coupling & Simple Architecture (결합도 감소)
* **Decoupling:** Functions should be small and isolated. Avoid tightly coupled monolithic classes.
* **Shallow Abstraction:** Keep it simple.
    * Avoid deep inheritance hierarchies.
    * Avoid unnecessary wrapper classes or "magic" code that hides implementation details.
    * Code flow should be explicit and easy to trace.

## 4. Naming & Readability
* **Verbose Naming:** Use full words for variable names to ensure clarity (e.g., `user_input_text` instead of `txt`).
* **Predictability:** Naming patterns should be consistent across modules (e.g., if you use `fetch_` for API calls, do not use `get_` mixed in).

## 기본 행동 가드

이 지침은 LLM 코딩 실수를 줄이기 위한 모델 중립 기본 태도다. 사소한 작업에서는 속도와 신중함의 균형을 잡되, 불명확한 상태를 숨기지 않는다.

### 근본 경계 우선

- 버그나 아키텍처 경계를 고칠 때는 UI 숨김, 후처리, 요청 우회 같은 표면 보정으로 완료 처리하지 않는다.
- 먼저 서버/API/도메인 정책처럼 오래 남는 경계에서 불변식을 강제한다.
- UI 변경은 서버 정책을 사용자에게 드러내는 보조 수단으로만 추가한다.
- 예: 외부 시스템이 원본인 데이터는 원본 시스템의 동기화 경로에서만 쓰게 하고, 관리 화면은 권한·표시 설정처럼 해당 시스템이 실제로 책임지는 범위만 허용한다.

### 코딩 전에 먼저 생각하기

- 추측으로 진행하지 않는다. 요청의 주체, 범위, 트리거, 제외 범위를 한 줄로 드러내고 다르면 사용자가 바로 정정할 수 있게 한다.
- 해석이 여러 개면 조용히 하나를 고르지 말고 가능한 해석과 선택 기준을 짧게 제시한다.
- 더 단순한 접근이 있으면 먼저 말한다. 요청보다 넓은 변경이나 장기 유연성만을 위한 설계는 필요성을 설명하고 좁힌다.
- 불확실하면 멈춰서 무엇이 헷갈리는지 이름 붙이고 질문한다. 저장소에서 확인 가능한 사실은 먼저 직접 확인한다.

### 단순성 우선

- 요청을 해결하는 최소 코드만 작성한다. 요청받지 않은 기능, 옵션, 설정 가능성은 추가하지 않는다.
- 단일 사용처를 위한 새 추상화나 공유 유틸리티를 만들지 않는다.
- 실제로 발생하지 않는 시나리오를 위한 방어 코드나 에러 처리를 늘리지 않는다.
- 구현이 과도하게 길어졌다고 판단되면 같은 동작을 더 짧고 읽기 쉬운 구조로 다시 정리한다.

---

### Example: Consistency & Purity

**Requirement:** Follow the project's pattern of using `snake_case` for functions and `DTO` suffixes for data classes.

```python
# [Existing Pattern Matches]
# If the project uses Pydantic for types, DO NOT introduce Dataclasses suddenly.
from pydantic import BaseModel

class UserDTO(BaseModel):
    id: int
    name: str

# [Pure Function]
def format_user_display_name(user: UserDTO) -> str:
    """
    Pure function. 
    Consistent naming with the codebase (verb_noun format).
    """
    return f"User: {user.name} ({user.id})"

# [Side Effect Isolated]
# If the project uses 'Service' suffixes, stick to it.
class UserService:
    def get_and_print_user(self, user_id: int) -> None:
        # Implementation details...
        pass