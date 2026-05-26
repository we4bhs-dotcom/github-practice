import json
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

    def classify(self, scene: str, character_names: list) -> list:
        # [수정] Ollama가 출력한 JSON 스트링을 파이썬 객체(list/dict)로 안전하게 변환하여 리턴
        characters = ", ".join(character_names)
        prompt = f"""(기존 프롬프트 생략)... 각 문장마다 아래 JSON 형식으로만 답해줘. 다른 말은 하지 마.
        [ {{"문장": "내용", "분류": "W 또는 이름_P/B/K/D"}} ] \n장면:\n{scene}"""
        
        raw_result = self.llm.generate(prompt)
        try:
            # 마크다운 껍데기(```json ... ```)가 붙어 나올 경우를 대비한 가벼운 정제 필요할 수 있음
            return json.loads(raw_result)
        except json.JSONDecodeError:
            # 파싱 실패 시 원문이라도 추적할 수 있도록 예외 처리
            print("[Warning] JSON 파싱 실패. 원문 스트링을 리턴합니다.")
            return raw_result