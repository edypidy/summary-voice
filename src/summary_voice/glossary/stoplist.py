"""용어집에서 걸러낼 흔한 이름들.

`train`, `forward`, `main` 같은 이름은 레포에 수백 번 나오지만 프로젝트 고유
용어가 아니다. STT 바이어싱에 넣으면 정확도가 떨어지고 100개 예산만 먹는다.

여기 없더라도 살리언스 랭킹(`Term.salience`)이 대부분 걸러낸다. 이 목록은
빈도가 너무 높아 랭킹만으로는 못 막는 것들을 잡는 안전망이다.
"""

# 파이썬/프레임워크 관용어
GENERIC_CODE = {
    "abstractmethod", "add", "args", "argparse", "arg", "assert", "base", "build",
    "call", "check", "class", "cleanup", "cli", "close", "config", "constants",
    "core", "count", "create", "data", "dataclass", "dataset", "debug", "decode",
    "default", "delete", "dict", "encode", "enum", "env", "error", "eval",
    "evaluate", "exception", "exceptions", "execute", "exists", "fit", "forward",
    "get", "handler", "helper", "helpers", "index", "info", "init", "input",
    "install", "item", "items", "iter", "key", "keys", "list", "load", "loader",
    "log", "logger", "logging", "main", "make", "manager", "map", "metrics",
    "model", "models", "module", "modules", "name", "network", "new", "next",
    "open", "optimizer", "option", "options", "output", "parse", "parser", "path",
    "paths", "pipeline", "predict", "prepare", "process", "property", "read",
    "remove", "repr", "reset", "result", "results", "run", "runner", "sample",
    "save", "scheduler", "script", "scripts", "seed", "set", "settings", "setup",
    "size", "source", "split", "src", "start", "state", "step", "stop", "str",
    "test", "tests", "to", "tool", "tools", "train", "trainer", "training",
    "transform", "type", "update", "util", "utils", "val", "validate", "value",
    "values", "version", "wrapper", "write",
}

# 흔한 라이브러리 이름. 프로젝트 고유가 아니다.
LIBRARIES = {
    "numpy", "torch", "pytorch", "pandas", "scipy", "sklearn", "matplotlib",
    "tensorflow", "keras", "jax", "transformers", "datasets", "accelerate",
    "wandb", "tqdm", "hydra", "omegaconf", "pytest", "pydantic", "fastapi",
    "flask", "django", "requests", "httpx", "pillow", "opencv", "cv2", "einops",
    "lightning", "timm", "monai", "nibabel", "pydicom", "yaml", "json", "os",
    "sys", "re", "pathlib", "typing", "collections", "itertools", "functools",
}

# 커밋 메시지 관용어
COMMIT_WORDS = {
    "add", "added", "adds", "bump", "chore", "cleanup", "docs", "fix", "fixed",
    "fixes", "feat", "feature", "initial", "merge", "move", "refactor", "release",
    "remove", "removed", "rename", "revert", "style", "test", "tests", "update",
    "updated", "updates", "wip", "commit", "branch", "pull", "request", "pr",
}

# 어느 프로젝트에나 있는 설정 키. 프로젝트를 식별해주지 않는다.
# 주의: `batch_size`, `num_workers`처럼 사용자가 실제로 입으로 말하는
# 하이퍼파라미터는 일부러 남겨둔다. STT가 오인식하기 쉬운 대상이다.
CONFIG_GENERIC = {
    "augment", "channels", "defaults", "family", "group", "hydra", "job_type",
    "mean", "normalize", "notes", "num_classes", "out_dir", "output_dir",
    "project", "root", "run_name", "save_dir", "std", "tags", "verbose",
}

# 이 도구 자체가 남기는 흔적. 대상 레포의 용어가 아니다.
TOOLING = {"claude", "co-authored-by", "noreply", "anthropic", "generated"}

STOPLIST = GENERIC_CODE | LIBRARIES | COMMIT_WORDS | CONFIG_GENERIC | TOOLING


def is_stopword(name: str) -> bool:
    """단일 단어이면서 스톱리스트에 있으면 True.

    복합어는 통과시킨다. `train`은 버리지만 `train_lora_xs`는 남긴다.
    """
    return name.strip().lower() in STOPLIST
