# GPT 대화 내보내기

300MB 이상의 GPT 대화 JSON 파일을 스트리밍으로 파싱하여 HTML 또는 zstd 압축 JSON으로 변환합니다.

## 설치

```bash
pip install -r requirements.txt
```

## 스크립트

| 스크립트 | 용도 |
|---------|------|
| `export_conversation.py` | HTML로 내보내기 (Result/) |
| `export_json_zst.py` | zstd 압축 JSON으로 내보내기 (json_result/) |

## 사용법

### HTML 내보내기

```bash
# 전체 대화를 Result/ 폴더에 HTML로 내보내기
# 폴더 구조: Result/년도/월/conv_N.html (예: Result/2025/01/, Result/2024/12/)
# 같은 달 내 대화는 시간순으로 conv_0, conv_1, ... 정렬
python export_conversation.py conversations.json

# 출력 디렉토리 지정
python export_conversation.py conversations.json -o my_exports

# 특정 인덱스의 대화만 내보내기
python export_conversation.py conversations.json --index 5
```

### JSON (zstd) 내보내기

```bash
# 전체 대화를 json_result/ 폴더에 zstd 압축 JSON으로 내보내기
# 폴더 구조: {YYYY}/{YYYY-MM}/{ISO_TIMESTAMP}__idx{N}.json.zst
# 예: 2024/2024-02/20240220T103245Z__idx0001.json.zst
python export_json_zst.py conversations.json

# 출력 디렉토리 지정
python export_json_zst.py conversations.json -o my_json_result

# 특정 인덱스만
python export_json_zst.py conversations.json --index 5
```

## 입력 형식

GPT에서 내보낸 JSON 형식:

- `title`, `create_time`, `update_time`
- `mapping`: 노드 ID → `{ id, message, parent, children }`
- `message`: `author.role` (system/user/assistant), `content.parts` (텍스트 배열)

## 출력

- 다크 테마 HTML
- 역할별 색상 구분 (시스템/사용자/어시스턴트)
- 코드블록 및 인라인 코드 스타일링
- 타임스탬프 표시
