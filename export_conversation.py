#!/usr/bin/env python3
"""
GPT 대화 내보내기: 300MB+ JSON 파일을 스트리밍으로 파싱하여 HTML로 변환

사용법:
  python export_conversation.py input.json [--index N] [--output output.html]
"""

import argparse
import html
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import ijson
except ImportError:
    raise ImportError("ijson이 필요합니다. pip install ijson 로 설치하세요.")


def extract_messages_from_mapping(mapping):
    """
    mapping에서 메시지 트리를 순회하여 시간순으로 정렬된 메시지 리스트 반환.
    parent/children 구조를 따라 root에서 시작해 DFS로 순회.
    """
    if not mapping:
        return []

    # root 노드 찾기 (parent가 null인 노드)
    root_ids = [nid for nid, node in mapping.items() if node.get("parent") is None]
    if not root_ids:
        # fallback: children에만 등장하고 parent가 없는 노드
        all_ids = set(mapping.keys())
        child_ids = set()
        for node in mapping.values():
            child_ids.update(node.get("children") or [])
        root_ids = list(all_ids - child_ids) or list(all_ids)[:1]

    messages = []

    def traverse(node_id):
        node = mapping.get(node_id)
        if not node:
            return
        msg = node.get("message")
        if msg and msg.get("content", {}).get("content_type") == "text":
            messages.append(msg)
        for child_id in node.get("children") or []:
            traverse(child_id)

    for rid in root_ids:
        traverse(rid)

    return messages


def format_timestamp(ts):
    """Unix timestamp를 읽기 쉬운 문자열로 변환."""
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, TypeError):
        return str(ts)


def escape_html(text):
    """HTML 이스케이프."""
    return html.escape(text) if text else ""


def format_message_content(parts):
    """
    content.parts를 HTML로 변환.
    - 일반 텍스트는 줄바꿈 유지
    - 간단한 마크다운(코드블록, 인라인 코드) 처리
    """
    if not parts:
        return ""
    if isinstance(parts, str):
        parts = [parts]
    lines = []
    for p in parts:
        if not isinstance(p, str):
            continue
        # 플레이스홀더로 치환 후 나중에 복원 (이스케이프 시 태그가 깨지지 않도록)
        blocks = []
        inlines = []

        def replace_block(m):
            lang = escape_html(m.group(1))
            code = escape_html(m.group(2))
            idx = len(blocks)
            blocks.append(f'<pre class="code-block"><code class="{lang}">{code}</code></pre>')
            return f"\x00BLOCK{idx}\x00"

        def replace_inline(m):
            idx = len(inlines)
            inlines.append(f"<code>{escape_html(m.group(1))}</code>")
            return f"\x00INLINE{idx}\x00"

        p = re.sub(r"```(\w*)\n(.*?)```", replace_block, p, flags=re.DOTALL)
        p = re.sub(r"`([^`]+)`", replace_inline, p)
        p = escape_html(p).replace("\n", "<br>\n")
        for i, b in enumerate(blocks):
            p = p.replace(f"\x00BLOCK{i}\x00", b)
        for i, il in enumerate(inlines):
            p = p.replace(f"\x00INLINE{i}\x00", il)
        lines.append(p)
    return "\n".join(lines)


def build_html(conversation, messages, output_path):
    """대화를 보기 좋은 HTML로 렌더링."""
    title = escape_html(conversation.get("title") or "대화")
    create_time = format_timestamp(conversation.get("create_time"))
    update_time = format_timestamp(conversation.get("update_time"))

    role_labels = {
        "system": "시스템",
        "user": "사용자",
        "assistant": "어시스턴트",
    }

    msg_html_parts = []
    for msg in messages:
        author = msg.get("author") or {}
        role = author.get("role") or "user"
        content = msg.get("content") or {}
        parts = content.get("parts") or []
        create_time_msg = format_timestamp(msg.get("create_time"))
        label = role_labels.get(role, role)
        body = format_message_content(parts)
        css_role = role

        msg_html_parts.append(
            f"""
        <div class="message message-{css_role}">
            <div class="message-header">
                <span class="message-role">{label}</span>
                <span class="message-time">{create_time_msg}</span>
            </div>
            <div class="message-body">{body}</div>
        </div>
        """
        )

    messages_html = "\n".join(msg_html_parts)

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #0f0f12;
            --surface: #1a1a1f;
            --border: #2a2a32;
            --text: #e4e4e7;
            --text-muted: #71717a;
            --user-bg: #1e3a5f;
            --user-border: #2563eb;
            --assistant-bg: #1e1e24;
            --assistant-border: #3f3f46;
            --system-bg: #1a2e1a;
            --system-border: #22c55e;
            --code-bg: #27272a;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            margin: 0;
            padding: 2rem min(4rem, 5vw);
            width: 100%;
            max-width: 100%;
            margin-left: auto;
            margin-right: auto;
        }}
        .header {{
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
        }}
        .header h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0 0 0.5rem 0;
        }}
        .header .meta {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}
        .messages {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        .message {{
            border-radius: 12px;
            padding: 1rem 1.25rem;
            border-left: 4px solid;
        }}
        .message-system {{
            background: var(--system-bg);
            border-color: var(--system-border);
        }}
        .message-user {{
            background: var(--user-bg);
            border-color: var(--user-border);
        }}
        .message-assistant {{
            background: var(--assistant-bg);
            border-color: var(--assistant-border);
        }}
        .message-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}
        .message-role {{
            font-weight: 600;
            font-size: 0.875rem;
        }}
        .message-time {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        .message-body {{
            font-size: 0.95rem;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .message-body code {{
            background: var(--code-bg);
            padding: 0.15em 0.4em;
            border-radius: 4px;
            font-family: var(--font-mono);
            font-size: 0.9em;
        }}
        .message-body pre {{
            background: var(--code-bg);
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            margin: 0.5rem 0;
        }}
        .message-body pre code {{
            background: none;
            padding: 0;
        }}
        .code-block {{
            margin: 0.5rem 0;
        }}
    </style>
    <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
    <link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css" rel="stylesheet">
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <div class="meta">
            생성: {create_time} · 수정: {update_time} · 메시지 {len(messages)}개
        </div>
    </div>
    <div class="messages">
{messages_html}
    </div>
</body>
</html>
"""

    Path(output_path).write_text(html_content, encoding="utf-8")


def stream_conversations(json_path):
    """
    JSON 파일을 스트리밍으로 파싱하여 대화를 하나씩 yield.
    """
    with open(json_path, "rb") as f:
        for conv in ijson.items(f, "item"):
            yield conv


def get_conversation_time(conv):
    """대화의 create_time을 datetime으로 반환 (없으면 1970-01-01)."""
    ts = conv.get("create_time") or conv.get("update_time") or 0
    try:
        return datetime.fromtimestamp(float(ts))
    except (ValueError, OSError, TypeError):
        return datetime(1970, 1, 1)


def build_output_plan(conversations):
    """
    (index, create_time) 리스트를 시간순 정렬 후, 년/월별 폴더 구조로 매핑.
    반환: { index: (year, month, order_in_month) }
    """
    items = [(i, get_conversation_time(conv)) for i, conv in enumerate(conversations)]
    items.sort(key=lambda x: x[1])

    groups = defaultdict(list)
    for index, dt in items:
        groups[(dt.year, dt.month)].append(index)

    index_to_path = {}
    for (year, month), indices in sorted(groups.items(), reverse=True):
        year_str = str(year)
        month_str = f"{month:02d}"
        for order, index in enumerate(indices):
            index_to_path[index] = (year_str, month_str, order)
    return index_to_path


def main():
    parser = argparse.ArgumentParser(
        description="GPT 대화 JSON을 스트리밍으로 파싱하여 HTML로 내보내기"
    )
    parser.add_argument("input", help="입력 JSON 파일 경로")
    parser.add_argument(
        "--index",
        "-i",
        type=int,
        default=None,
        metavar="N",
        help="특정 인덱스만 내보내기 (미지정 시 전체 내보내기)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="Result",
        help="출력 디렉토리 (기본: Result)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {input_path}")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"파싱 중: {input_path}...")

    # 1차: 스트리밍으로 전체 수집 (인덱스 + create_time만) 후 정렬 계획 수립
    conversations = list(stream_conversations(input_path))
    if args.index is not None:
        if args.index >= len(conversations):
            print(f"오류: 인덱스 {args.index}에 해당하는 대화가 없습니다.")
            return 1
        conversations = [conversations[args.index]]
        index_to_path = {0: ("temp", "00", 0)}
        if conversations:
            dt = get_conversation_time(conversations[0])
            index_to_path = {0: (str(dt.year), f"{dt.month:02d}", 0)}
    else:
        index_to_path = build_output_plan(conversations)

    count = 0
    for i, conv in enumerate(conversations):
        if args.index is not None and i != 0:
            continue
        mapping = conv.get("mapping") or {}
        messages = extract_messages_from_mapping(mapping)
        year_str, month_str, order = index_to_path.get(i, ("temp", "00", 0))
        folder = output_dir / year_str / month_str
        folder.mkdir(parents=True, exist_ok=True)
        output_path = folder / f"conv_{order}.html"
        build_html(conv, messages, output_path)
        count += 1

    if count == 0:
        print("오류: 내보낼 대화가 없습니다.")
        return 1

    print(f"완료: {count}개 대화를 {output_dir}/ 에 저장했습니다.")
    return 0


if __name__ == "__main__":
    exit(main())
