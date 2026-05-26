from database import NarrativeDB
from llm import OllamaLLM

class Validator:
    def __init__(self):
        self.db = NarrativeDB()
        self.llm = OllamaLLM()

    def validate(self, character_name: str, scene: str) -> dict:
        results = {"status": "pass", "reason": "", "failed_at": None}

        # W 검증 (예외 없음)
        w_docs = self.db.search(self.db.world, scene)
        if w_docs:
            prompt = f"""다음 장면이 세계관 설정과 논리적으로 모순되는지 판단해줘.
세계관 설정: {w_docs}
장면: {scene}
모순이 있으면 '비정합', 없으면 '정합' 으로만 답해줘."""
            result = self.llm.generate(prompt)
            if "비정합" in result:
                results["status"] = "fail"
                results["reason"] = result
                results["failed_at"] = "W"
                return results

        if character_name not in self.db.characters:
            return results

        # K 검증 + 제1원칙
        k_docs = self.db.search(self.db.characters[character_name]["k"], scene)
        if k_docs:
            prompt = f"""다음 장면이 캐릭터의 기존 지식과 논리적으로 모순되는지 판단해줘.
지식: {k_docs}
장면: {scene}
모순이 있으면 '비정합', 없으면 '정합' 으로만 답해줘."""
            result = self.llm.generate(prompt)
            if "비정합" in result:
                # 제1원칙: 세계관에 부합하면 예외
                prompt = f"""다음 장면이 세계관 설정에 부합하는지 판단해줘.
세계관 설정: {w_docs}
장면: {scene}
부합하면 '예외', 아니면 '비예외' 로만 답해줘."""
                exception = self.llm.generate(prompt)
                if "예외" in exception:
                    pass  # K 업데이트 (나중에 구현)
                else:
                    results["status"] = "fail"
                    results["reason"] = result
                    results["failed_at"] = "K"
                    return results

        # P, B 검증 + 제2원칙
        for attr in ["p", "b"]:
            docs = self.db.search(self.db.characters[character_name][attr], scene)
            if docs:
                prompt = f"""다음 장면이 캐릭터 설정과 논리적으로 모순되는지 판단해줘.
캐릭터 설정: {docs}
장면: {scene}
모순이 있으면 '비정합', 없으면 '정합' 으로만 답해줘."""
                result = self.llm.generate(prompt)
                if "비정합" in result:
                    # 제2원칙: 욕망에 부합하면 예외
                    d_docs = self.db.search(self.db.characters[character_name]["d"], scene)
                    prompt = f"""다음 장면이 캐릭터의 욕망이나 목적 달성을 위한 합리적 선택인지 판단해줘.
욕망/목적: {d_docs}
장면: {scene}
합리적이면 '예외', 아니면 '비예외' 로만 답해줘."""
                    exception = self.llm.generate(prompt)
                    if "예외" in exception:
                        pass  # P, B 업데이트 (나중에 구현)
                    else:
                        results["status"] = "fail"
                        results["reason"] = result
                        results["failed_at"] = attr.upper()
                        return results

        return results
    def classify(self, scene: str, character_names: list) -> dict:
        characters = ", ".join(character_names)
        prompt = f"""다음 장면의 각 문장을 아래 기준에 따라 분류해줘.

    분류 기준:
    - W (세계관 설정): 특정 캐릭터와 무관하게 이 세계의 규칙, 지리, 역사, 사실로 취급되는 정보
    예) "이 세계에서 마법은 감정이 강할수록 강해진다", "왕국의 수도는 북쪽에 있다"

    - P (성격): 캐릭터의 성격, 기질, 행동 방식을 나타내는 문장
    예) "홍길동은 망설임 없이 적에게 뛰어들었다" → 홍길동의 P

    - B (신념): 캐릭터가 옳다고 믿는 가치관, 신념을 나타내는 문장
    예) "홍길동은 약자를 반드시 도와야 한다고 생각했다" → 홍길동의 B

    - K (지식): 캐릭터가 알고 있거나 모르는 정보, 사실을 나타내는 문장
    예) "홍길동은 변사또가 탐관오리임을 알고 있었다" → 홍길동의 K

    - D (욕망): 캐릭터의 목표, 욕망, 원하는 것을 나타내는 문장
    예) "홍길동은 반드시 복수를 이루고자 했다" → 홍길동의 D

    등장 캐릭터: {characters}

    장면:
    {scene}

    각 문장마다 아래 JSON 형식으로만 답해줘. 다른 말은 하지 마.
    [
    {{"문장": "문장 내용", "분류": "W 또는 캐릭터이름_P/B/K/D"}},
    ...
    ]
    예시:
    [
    {{"문장": "이 세계에서 마법은 감정이 강할수록 강해진다", "분류": "W"}},
    {{"문장": "홍길동은 망설임 없이 뛰어들었다", "분류": "홍길동_P"}}
    ]"""
        result = self.llm.generate(prompt)
        return result