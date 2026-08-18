"""root 경계 안으로만 경로를 해석하는 공용 검증.

병합·분할·업로드·다운로드 경로가 각자 손으로 쓰던 traversal 검사를 한곳에
모은다. 순수 함수로 두고, 호출부가 자기 도메인 예외로 감싸 쓴다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union


class PathOutsideRootError(ValueError):
    """해석된 경로가 root 밖으로 벗어났다."""


def resolve_within_root(root: Path, candidate: Union[str, Path]) -> Path:
    """candidate를 root 아래 절대 경로로 해석한다.

    candidate는 root 기준 상대 경로여도 되고 절대 경로여도 된다.
    `..`와 symlink를 먼저 정규화한 뒤 포함 여부를 확인하므로 link를 통한
    우회도 막는다. 파일 존재 여부와 확장자는 확인하지 않는다.
    """
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathOutsideRootError(f"root 밖의 경로입니다: {candidate}") from None
    return resolved
