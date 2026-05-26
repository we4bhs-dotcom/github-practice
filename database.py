import chromadb
from embedder import SentenceTransformerEmbedder
import hashlib  # 파일 최상단에 추가

class NarrativeDB:
    def __init__(self, storage_path="./narrative_db"):
        print("[NarrativeDB] ChromaDB 클라이언트 초기화 시작...")
        
        # 인메모리 Client 대신 로컬 디스크 저장 방식을 쓰면 락 걸리는 현상이 줄어듭니다.
        self.client = chromadb.PersistentClient(path=storage_path)
        
        print("[NarrativeDB] 컬렉션 로드 중...")
        self.world = self.client.get_or_create_collection("world")
        self.embedder = SentenceTransformerEmbedder()
        
        # 🚨 아까 누락되었던 딕셔너리 초기화 (이게 없으면 main.py에서 에러 터짐)
        self.characters = {} 
        print("[NarrativeDB] 초기화 완료!")

    def add(self, collection, text, doc_id):
        vector = self.embedder.embed(text)
        collection.add(
            documents=[text],
            embeddings=[vector],
            ids=[doc_id]
        )

    def search(self, collection, query, top_k=3):
        vector = self.embedder.embed(query)
        results = collection.query(
            query_embeddings=[vector],
            n_results=top_k
        )
        # 결과가 비어있을 때를 대비한 방어 코드
        if results and results.get("documents") and results["documents"]:
            return results["documents"][0]
        return []

    def add_character(self, name):
        # 이제 안전하게 딕셔너리에 추가됩니다.
        if name in self.characters:
            return
            
        # 💡 한글 이름 억까 방지: 이름을 고유한 영문/숫자 해시값으로 변환하여 컬렉션 생성
        safe_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:12]
        self.characters[name] = {
            "p": self.client.get_or_create_collection(f"char_{name}_p"),
            "b": self.client.get_or_create_collection(f"char_{name}_b"),
            "k": self.client.get_or_create_collection(f"char_{name}_k"),
            "d": self.client.get_or_create_collection(f"char_{name}_d"),
        }