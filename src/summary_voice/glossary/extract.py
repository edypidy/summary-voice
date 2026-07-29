"""레포에서 용어 후보를 뽑는 추출기들 (README 섹션 7.1).

| 소스           | 추출 대상                                  |
|----------------|-------------------------------------------|
| Python AST     | 클래스명, 함수명, 모듈명                    |
| config         | yaml/json 키 이름                          |
| .tex           | 수식 심볼, 메서드명, 반복 등장 명사구        |
| git log        | 커밋 메시지의 고유 명사                     |
| README/CLAUDE  | 프로젝트 고유 약어, 백틱 식별자             |

각 추출기는 `list[Term]`을 돌려주고, 병합·랭킹·상한(100개)은 `build.py`가 한다.
추출기는 실패해도 빈 리스트를 돌려주고 죽지 않는다. 레포는 언제나 지저분하다.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from summary_voice.glossary.models import Term
from summary_voice.glossary.stoplist import is_stopword
from summary_voice.glossary.variants import variants_of

# 훑지 않을 디렉터리. 남의 코드에서 용어를 뽑으면 안 된다.
SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "build", "dist", "site-packages", ".tox",
    "wandb", "checkpoints", "outputs", ".ipynb_checkpoints", ".assistant",
}

MAX_FILES = 2000  # 폭주 방지. 대형 레포에서 추출이 몇 분씩 걸리면 안 쓰게 된다.


def _walk(root: Path, suffixes: set[str]) -> list[Path]:
    """SKIP_DIRS를 제외하고 확장자가 맞는 파일을 모은다."""
    found: list[Path] = []
    for path in root.rglob("*"):
        if len(found) >= MAX_FILES:
            break
        if path.suffix.lower() not in suffixes or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        found.append(path)
    return found


# 용어가 아니라 경로·CLI 조각·코드 파편이라는 신호. 하나라도 있으면 버린다.
_JUNK_CHARS = re.compile(r"""[/\\=<>(){}\[\]*$|"',;:!?@#%^&+~\s]""")


def _keep(name: str, *, min_len: int = 3) -> bool:
    """용어 후보로 남길 만한 이름인가.

    사람이 **입으로 말할 수 있는 것**만 남긴다. `.nii.gz`, `outputs/<run_name>/`,
    `train.lr=2e-4` 같은 건 용어가 아니라 화면에서 읽는 것이다. 용어집 예산이
    100개뿐이라 이런 게 들어가면 진짜 용어가 밀려난다.
    """
    name = name.strip()
    if len(name) < min_len or len(name) > 60:
        return False
    if name.startswith("_"):  # private/dunder
        return False
    if name.startswith("."):  # 파일 확장자: .ckpt, .nii.gz, .safetensors
        return False
    if _JUNK_CHARS.search(name):  # 경로, CLI 조각, 코드 파편
        return False
    if is_stopword(name):
        return False
    # 글자가 아예 없거나(순수 숫자/기호) 숫자가 절반 이상이면 식별자가 아니다
    letters = sum(c.isalpha() for c in name)
    return letters >= 2 and letters >= len(name) // 2


def _terms_from_counter(counter: Counter[str], source: str) -> list[Term]:
    return [
        Term(canonical=name, variants=variants_of(name), sources=[source], count=n)
        for name, n in counter.items()
    ]


# ---------------------------------------------------------------- Python AST


def from_python(root: Path) -> list[Term]:
    """클래스명·함수명·모듈명. 문법 오류가 있는 파일은 건너뛴다."""
    classes: Counter[str] = Counter()
    functions: Counter[str] = Counter()
    modules: Counter[str] = Counter()

    for path in _walk(root, {".py"}):
        stem = path.stem
        if _keep(stem) and stem != "__init__":
            modules[stem] += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError, OSError):
            continue  # 레포는 지저분하다. 한 파일 때문에 멈추지 않는다.
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _keep(node.name):
                classes[node.name] += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _keep(node.name):
                functions[node.name] += 1

    return (
        _terms_from_counter(classes, "python:class")
        + _terms_from_counter(functions, "python:function")
        + _terms_from_counter(modules, "python:module")
    )


# ------------------------------------------------------------------- Config


def _yaml_keys(text: str) -> list[str]:
    """yaml 키를 정규식으로 훑는다.

    PyYAML로 파싱하면 hydra/omegaconf의 커스텀 태그(`!!python/object` 등)에서
    터진다. 우리는 값이 아니라 키 이름만 필요하므로 정규식이면 충분하다.
    """
    return re.findall(r"^\s*([A-Za-z_][\w.-]*)\s*:", text, flags=re.MULTILINE)


def _json_keys(obj, out: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            _json_keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _json_keys(v, out)


def from_config(root: Path) -> list[Term]:
    """yaml/json 설정 키와 argparse 플래그 이름."""
    keys: Counter[str] = Counter()

    for path in _walk(root, {".yaml", ".yml"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        keys.update(k for k in _yaml_keys(text) if _keep(k))

    for path in _walk(root, {".json"}):
        if path.name in {"package-lock.json", "package.json", "tsconfig.json"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            continue
        found: list[str] = []
        _json_keys(data, found)
        keys.update(k for k in found if _keep(k))

    # argparse: add_argument("--lora-rank", ...) 의 플래그 이름
    for path in _walk(root, {".py"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for flag in re.findall(r"""add_argument\(\s*["']--([\w-]+)["']""", text):
            if _keep(flag):
                keys[flag] += 1

    return _terms_from_counter(keys, "config")


# ---------------------------------------------------------------------- TeX


def from_tex(root: Path) -> list[Term]:
    """논문 초고에서 메서드명과 수식 심볼.

    논문에 이름이 붙은 것은 사용자가 말로 부를 가능성이 가장 높은 용어다.
    이 소스의 신호 대 잡음비가 제일 좋다.
    """
    names: Counter[str] = Counter()

    for path in _walk(root, {".tex"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        # \newcommand{\methodname}{LoRA-XS} 의 정의된 이름과 값 양쪽
        for macro, body in re.findall(r"\\newcommand\{\\(\w+)\}\{([^{}]{2,40})\}", text):
            if _keep(macro):
                names[macro] += 1
            body = body.strip()
            if _keep(body) and "\\" not in body:
                names[body] += 2  # 매크로 본문은 대개 진짜 메서드명이다

        # \textsc{...}, \method{...}, \emph{...} 안의 짧은 고유명
        for body in re.findall(r"\\(?:textsc|textbf|method|emph)\{([^{}]{2,40})\}", text):
            body = body.strip()
            if _keep(body) and "\\" not in body:
                names[body] += 1

        # 하이픈/대문자가 섞인 고유명사형 토큰: LoRA-XS, Sinkhorn, MedSAM
        for token in re.findall(r"\b([A-Z][A-Za-z]*(?:-[A-Za-z0-9]+)+|[A-Z][a-z]{3,})\b", text):
            if _keep(token):
                names[token] += 1

    return _terms_from_counter(names, "tex")


# ------------------------------------------------------------------ git log


def from_git(root: Path, max_commits: int = 500) -> list[Term]:
    """커밋 메시지의 고유 명사.

    사람이 쓴 문장이라 코드 식별자보다 사용자의 실제 어휘에 가깝다.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", f"-{max_commits}", "--pretty=%s%n%b"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []  # git 레포가 아니거나 커밋이 없음

    names: Counter[str] = Counter()
    for line in proc.stdout.splitlines():
        # 백틱 안의 식별자
        for token in re.findall(r"`([^`]{2,40})`", line):
            if _keep(token):
                names[token] += 2
        # CamelCase, 하이픈 결합 고유명, 전부 대문자 약어
        for token in re.findall(
            r"\b([A-Z][a-z]+[A-Z]\w*|[A-Za-z]+(?:-[A-Za-z0-9]+)+|[A-Z]{2,8})\b", line
        ):
            if _keep(token):
                names[token] += 1

    return _terms_from_counter(names, "git")


# ----------------------------------------------------------------- 문서/약어


def from_docs(root: Path) -> list[Term]:
    """README / CLAUDE.md 등에서 백틱 식별자와 대문자 약어."""
    names: Counter[str] = Counter()

    docs = [p for p in _walk(root, {".md", ".rst", ".txt"}) if p.stat().st_size < 500_000]
    for path in docs:
        text = path.read_text(encoding="utf-8", errors="ignore")
        # 코드 펜스는 통째로 빼낸다. 예제 코드에서 용어를 뽑으면 잡음만 는다.
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)

        for token in re.findall(r"`([^`\n]{2,40})`", text):
            token = token.strip()
            # 공백이 있으면 명령줄이지 용어가 아니다
            if " " not in token and _keep(token):
                names[token] += 2
        for token in re.findall(r"\b([A-Z]{2,8}|[A-Za-z]+(?:-[A-Za-z0-9]+)+)\b", text):
            if _keep(token):
                names[token] += 1

    return _terms_from_counter(names, "docs")


EXTRACTORS = {
    "python": from_python,
    "config": from_config,
    "tex": from_tex,
    "git": from_git,
    "docs": from_docs,
}
