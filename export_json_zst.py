#!/usr/bin/env python3
"""
GPT 대화 JSON을 zstd 압축된 개별 파일로 내보내기

저장 구조: {YYYY}/{YYYY-MM}/{ISO_TIMESTAMP}__idx{N}.json.zst
예시: 2023/2023-02/20230220T103245Z__idx0001.json.zst

사용법:
  python export_json_zst.py conversations.json [-o json_result]
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

try:
    import ijson
except ImportError:
    raise ImportError("ijson이 필요합니다. pip install ijson 로 설치하세요.")

try:
    import zstandard as zstd
except ImportError:
    raise ImportError("zstandard가 필요합니다. pip install zstandard 로 설치하세요.")


def convert_for_json(obj):
    """ijson이 반환하는 Decimal 등을 JSON 직렬화 가능한 타입으로 변환."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_for_json(v) for v in obj]
    return obj


def epoch_to_utc_iso(ts):
    """epoch float → UTC ISO 포맷 YYYYMMDDTHHMMSSZ"""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    except (ValueError, OSError, TypeError):
        return "19700101T000000Z"


def stream_conversations(json_path):
    """JSON 파일을 스트리밍으로 파싱하여 대화를 하나씩 yield."""
    with open(json_path, "rb") as f:
        for conv in ijson.items(f, "item"):
            yield conv


def get_conversation_time(conv):
    """대화의 create_time을 epoch float로 반환."""
    ts = conv.get("create_time") or conv.get("update_time") or 0
    try:
        return float(ts)
    except (ValueError, TypeError):
        return 0.0


def main():
    parser = argparse.ArgumentParser(
        description="GPT 대화 JSON을 zstd 압축된 개별 파일로 내보내기"
    )
    parser.add_argument("input", help="입력 JSON 파일 경로")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="json_result",
        help="출력 디렉토리 (기본: json_result)",
    )
    parser.add_argument(
        "--index",
        "-i",
        type=int,
        default=None,
        metavar="N",
        help="특정 인덱스만 내보내기",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {input_path}")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"파싱 중: {input_path}...")

    conversations = list(stream_conversations(input_path))
    if args.index is not None:
        if args.index >= len(conversations):
            print(f"오류: 인덱스 {args.index}에 해당하는 대화가 없습니다.")
            return 1
        conversations = [conversations[args.index]]

    # 시간순 정렬 후 년/월별 그룹화
    items = [(i, get_conversation_time(conv), conv) for i, conv in enumerate(conversations)]
    items.sort(key=lambda x: x[1])

    groups = defaultdict(list)
    for orig_index, ts, conv in items:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        groups[(dt.year, dt.month)].append((ts, orig_index, conv))

    cctx = zstd.ZstdCompressor(level=3)
    count = 0

    for (year, month), group_items in sorted(groups.items(), reverse=True):
        year_str = str(year)
        month_str = f"{year}-{month:02d}"
        folder = output_dir / year_str / month_str
        folder.mkdir(parents=True, exist_ok=True)

        for order, (ts, orig_index, conv) in enumerate(group_items):
            iso_ts = epoch_to_utc_iso(ts)
            idx_padded = f"{order:04d}"
            filename = f"{iso_ts}__idx{idx_padded}.json.zst"
            output_path = folder / filename

            conv_clean = convert_for_json(conv)
            json_bytes = json.dumps(
                conv_clean,
                ensure_ascii=False,
                indent=None,
            ).encode("utf-8")
            compressed = cctx.compress(json_bytes)
            output_path.write_bytes(compressed)
            count += 1

    if count == 0:
        print("오류: 내보낼 대화가 없습니다.")
        return 1

    print(f"완료: {count}개 대화를 {output_dir}/ 에 JSON.zst로 저장했습니다.")
    return 0


if __name__ == "__main__":
    exit(main())
