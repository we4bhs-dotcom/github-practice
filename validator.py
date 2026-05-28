import json
import re
from database import NarrativeDB
from llm import OllamaLLM

class Validator:
    # 외부(main.py)에서 이미 만들어진 db 객체를 넘겨받도록 변경
    def __init__(self, db_instance):
        self.db = db_instance
        self.llm = OllamaLLM()

    def validate(self, character_name: str, scene: str) -> dict:
        results = {"status": "pass", "reason": "", "failed_at": None}

        # [보안] 세계관 설정은 전 단계 검증에서 공통으로 쓰이므로 미리 확실하게 확보
        w_docs = self.db.search(self.db.world, scene)
        w_context = w_docs if w_docs else "등록된 특별한 세계관 규칙 없음"

        # 1. W 검증 (세계관 모순 체크)
        if w_docs:
            prompt = f"다음 장면이 세계관 설정과 논리적으로 모순되는지 판단해줘.\n세계관 설정: {w_context}\n장면: {scene}\n모순이 있으면 '비정합', 없으면 '정합' 으로만 답해줘."
            result = self.llm.generate(prompt)
            if "비정합" in result:
                results.update({"status": "fail", "reason": result, "failed_at": "W"})
                return results

        # 캐릭터 데이터가 DB에 없으면 이후 검증은 패스
        if character_name not in self.db.characters:
            return results

        # 2. K 검증 + 제1원칙
        k_docs = self.db.search(self.db.characters[character_name]["k"], scene)
        if k_docs:
            prompt = f"다음 장면이 캐릭터의 기존 지식과 논리적으로 모순되는지 판단해줘.\n지식: {k_docs}\n장면: {scene}\n모순이 있으면 '비정합', 없으면 '정합' 으로만 답해줘."
            result = self.llm.generate(prompt)
            if "비정합" in result:
                # 제1원칙: 세계관 규칙에 부합하면 수용 (K 업데이트 예정)
                prompt = f"다음 장면이 세계관 설정에 부합하는지 판단해줘.\n세계관 설정: {w_context}\n장면: {scene}\n부합하면 '예외', 아니면 '비예외' 로만 답해줘."
                exception = self.llm.generate(prompt)
                if "예외" in exception:
                    pass  # TODO: K 업데이트 로직 구현
                else:
                    results.update({"status": "fail", "reason": result, "failed_at": "K"})
                    return results

        # 3. P, B 검증 + 제2원칙
        for attr in ["p", "b"]:
            docs = self.db.search(self.db.characters[character_name][attr], scene)
            if docs:
                prompt = f"다음 장면이 캐릭터 설정과 논리적으로 모순되는지 판단해줘.\n캐릭터 설정: {docs}\n장면: {scene}\n모순이 있으면 '비정합', 없으면 '정합' 으로만 답해줘."
                result = self.llm.generate(prompt)
                if "비정합" in result:
                    # 제2원칙: 욕망/결핍에 부합하면 수용 (P, B 업데이트 예정)
                    d_docs = self.db.search(self.db.characters[character_name]["d"], scene)
                    prompt = f"다음 장면이 캐릭터의 욕망이나 목적 달성을 위한 합리적 선택인지 판단해줘.\n욕망/목적: {d_docs}\n장면: {scene}\n합리적이면 '예외', 아니면 '비예외' 로만 답해줘."
                    exception = self.llm.generate(prompt)
                    if "예외" in exception:
                        pass  # TODO: P, B 업데이트 로직 구현
                    else:
                        results.update({"status": "fail", "reason": result, "failed_at": attr.upper()})
                        return results

        return results

    # 💡 형이 수정한 main.py에 맞춰서 char_info 딕셔너리 구조를 받도록 수정!
    def classify(self, scene: str, char_info: dict) -> str:
        # 1. 파이썬이 정규식으로 문장을 완벽하게 분리 (원문 100% 보존)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', scene) if s.strip()]
        
        # 2. 라마에게 줄 프롬프트에 문장 번호를 매겨서 제공
        numbered_sentences = ""
        for idx, sent in enumerate(sentences):
            numbered_sentences += f"[{idx}] {sent}\n"
            
        # 등장 캐릭터들의 실명 리스트 추출
        character_names = list(char_info.keys())
        sample_char = character_names[0] if character_names else "Siegfried"
        
        # 💡 라마에게 캐릭터별 실명과 등록된 호칭/알리아스 맵핑 정보를 친절하게 설명해 줌
        char_meta_desc = ""
        for name, aliases in char_info.items():
            alias_str = ", ".join([f"'{a}'" for a in aliases]) if aliases else "없음"
            char_meta_desc += f"- 본명: {name} (소설 속 다른 호칭/별명: {alias_str})\n"

        # 💡 뇌절 차단: 설명용 메타 텍스트를 정답으로 오해하지 않게 실제 정답 목록을 파이썬이 동적 생성
        allowed_tags = ["W"]
        for name in character_names:
            for attr in ["P", "B", "K", "D"]:
                allowed_tags.append(f"{name}_{attr}")
        
        allowed_tags_str = ", ".join([f'"{t}"' for t in allowed_tags])

        prompt = f"""너는 소설 문장 분류기야. 제공된 '장면'의 전체 맥락과 대명사, 그리고 각 캐릭터의 호칭을 파악해서 각 문장 번호(id)에 맞는 분류 태그를 선택해라. 다른 설명 없이 오직 JSON 배열만 반환해.

[등장 캐릭터 및 호칭 정보]
{char_meta_desc}
[중요] '그', '그의' 같은 대명사나 위의 다른 호칭(별명)이 나오면 맥락상 어떤 캐릭터를 뜻하는지 본명을 찾아 파악해라.

[선택 가능한 '분류' 태그 목록]
{allowed_tags_str}

[분류 매칭 규칙]
- 특정 캐릭터와 무관한 내용, 세계관 규칙, 지리, 역사, 혹은 캐릭터의 신체적 특징/흉터/외양 설정은 무조건 "W"를 선택한다.
- 캐릭터의 성격/기질/행동 방식이 나타나면 뒤에 "_P"가 붙은 태그를 선택한다.
- 캐릭터의 가치관/신념이 나타나면 뒤에 "_B"가 붙은 태그를 선택한다.
- 캐릭터가 알고 있는 지식/정보가 나타나면 뒤에 "_K"가 붙은 태그를 선택한다.
- 캐릭터의 목표/욕망이 나타나면 뒤에 "_D"가 붙은 태그를 선택한다.

장면:
{numbered_sentences}

출력 형식 (반드시 이 형태를 지키고, 태그 목록에 없는 값이나 '또는', 'or', 'hoặc' 같은 가이드 문구는 절대 쓰지 마):
[
  {{"id": 0, "분류": "W"}},
  {{"id": 1, "분류": "{sample_char}_P"}}
]"""

        raw_result = self.llm.generate(prompt)
        
        final_data = []
        try:
            clean_raw = raw_result.strip()
            start_idx = clean_raw.find("[")
            end_idx = clean_raw.rfind("]") + 1
            if start_idx != -1 and end_idx != 0:
                clean_raw = clean_raw[start_idx:end_idx]
                
            llm_output = json.loads(clean_raw)
            
            # 3. 라마가 준 분류 태그 예외 보정 및 파이썬 원문 강제 결합
            for item in llm_output:
                sent_id = item.get("id")
                if sent_id is not None and sent_id < len(sentences):
                    raw_class = item.get("분류", "W").strip()
                    
                    # 라마가 속성 다 떼먹고 이름만 달랑 뱉었을 때 방어
                    if raw_class in character_names:
                        raw_class = f"{raw_class}_P"
                        
                    # 대소문자가 틀렸거나 포맷이 미세하게 깨진 경우 자동 교정
                    for real_name in character_names:
                        if raw_class.lower().startswith(real_name.lower()):
                            if "_" in raw_class:
                                suffix = raw_class.rsplit("_", 1)[1].upper()
                                if suffix not in ["P", "B", "K", "D"]:
                                    suffix = "P"
                            else:
                                suffix = "P"
                            raw_class = f"{real_name}_{suffix}"
                            break
                    else:
                        # 리스트에 없는 이상한 헛소리를 채워놨다면 안전하게 세계관("W")으로 세탁
                        if not raw_class.endswith(("_P", "_B", "_K", "_D")) and raw_class != "W":
                            raw_class = "W"

                    final_data.append({
                        "문장": sentences[sent_id],  # 형 원문 그대로 강제 주입
                        "분류": raw_class
                    })
            
        except Exception as e:
            print(f"[🚨 라마 분류 실패 로그]: {raw_result}")
            final_data = [{"문장": sent, "분류": "W"} for sent in sentences]

        return json.dumps(final_data, ensure_ascii=False)