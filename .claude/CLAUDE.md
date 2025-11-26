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