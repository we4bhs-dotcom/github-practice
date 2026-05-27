import json
import re  # 💡 정규식 임포트를 파일 최상단으로 이동
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

    # 💡 들여쓰기를 맞춰서 Validator 클래스의 정식 메서드로 안착시킴
    def classify(self, scene: str, character_names: list) -> str:  # ⭐️ 리턴 타입을 str로 변경 (main.py 연동용)
        characters = ", ".join(character_names)
        
        # 1. 파이썬이 정규식으로 문장을 완벽하게 분리 (원문 100% 보존)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', scene) if s.strip()]
        
        # 2. 라마에게 줄 프롬프트에 문장 번호를 매겨서 제공 (맥락 유지를 위해 통째로 줌)
        numbered_sentences = ""
        for idx, sent in enumerate(sentences):
            numbered_sentences += f"[{idx}] {sent}\n"
            
        prompt = f"""너는 소설 문장 분류기야. 제공된 '장면'의 전체 맥락과 대명사(그, 그의 등)가 어떤 캐릭터를 가리키는지 파악하여, 각 문장 번호에 맞는 분류 태그만 JSON 배열로 반환해.

분류 기준:
- W: 세계관 설정, 규칙, 지리, 역사, 혹은 캐릭터의 신체적 특징/흉터/외양/소품 설정
- 캐릭터이름_P: 캐릭터의 성격, 기질, 행동 방식
- 캐릭터이름_B: 캐릭터의 신념, 가치관
- 캐릭터이름_K: 캐릭터가 아는 지식, 정보
- 캐릭터이름_D: 캐릭터의 목표, 욕망

등장 캐릭터: {characters}

[중요] '그', '그의' 같은 대명사는 전체 맥락을 보고 등장 캐릭터 중 누구를 뜻하는지 파악해서 분류해라.

장면 (번호 규칙을 절대 훼손하지 마):
{numbered_sentences}

출력 형식 (오직 이 JSON 형식만 반환하고 다른 말은 절대 하지 마):
[
  {{"id": 0, "분류": "W 또는 캐릭터이름_P/B/K/D"}},
  ...
]"""

        raw_result = self.llm.generate(prompt)
        
        final_data = []
        try:
            # 안전한 JSON 추출
            clean_raw = raw_result.strip()
            start_idx = clean_raw.find("[")
            end_idx = clean_raw.rfind("]") + 1
            if start_idx != -1 and end_idx != 0:
                clean_raw = clean_raw[start_idx:end_idx]
                
            llm_output = json.loads(clean_raw)
            
            # 3. ⭐️ 핵심: 라마가 준 '분류'와 파이썬이 보존한 '원본 문장'을 강제로 결합
            for item in llm_output:
                sent_id = item.get("id")
                if sent_id is not None and sent_id < len(sentences):
                    final_data.append({
                        "문장": sentences[sent_id],  # 형 원문 그대로 주입
                        "분류": item.get("분류", "W")
                    })
            
        except Exception as e:
            print(f"[🚨 라마 분류 실패 로그]: {raw_result}")
            final_data = [{"문장": sent, "분류": "W"} for sent in sentences]

        # 4. ⭐️ main.py의 json.loads(raw)가 정상 작동하도록 JSON 문자열로 인코딩해서 리턴
        return json.dumps(final_data, ensure_ascii=False)