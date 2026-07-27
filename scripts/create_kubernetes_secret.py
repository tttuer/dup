"""Convert ENV_VARS into a Kubernetes Secret manifest without exposing values."""

import json
import os
import sys
from pathlib import Path


def parse_env_vars(raw_value: str) -> dict[str, str]:
    values = {}
    for raw_line in raw_value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = raw_line.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"올바르지 않은 환경변수 줄입니다: {raw_line!r}")
        values[key.strip()] = value
    return values


def write_secret(output_path: Path, values: dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        file.write("apiVersion: v1\nkind: Secret\nmetadata:\n  name: dup-env\ntype: Opaque\nstringData:\n")
        for key, value in sorted(values.items()):
            file.write(f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)}\n")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python3 scripts/create_kubernetes_secret.py <출력-파일>")
    raw_value = os.environ.get("ENV_VARS", "")
    if not raw_value:
        raise SystemExit("ENV_VARS 시크릿이 비어 있습니다.")
    write_secret(Path(sys.argv[1]), parse_env_vars(raw_value))


if __name__ == "__main__":
    main()
