import sqlite3
import requests
import json
import time
import random
from datetime import datetime

# ==========================================
# [설정] 온프레미스 환경 시뮬레이션
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"

class SecurityEngine:
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, department TEXT, access_level INTEGER)''')
        # 테스트를 위해 더미 데이터 추가
        users = [
            (1, 'Kim_Cheolsu', 'cs.kim@company.com', 'HR', 2),
            (2, 'Lee_Yeonghee', 'yh.lee@company.com', 'DevOps', 5),
            (3, 'Park_Jimin', 'jm.park@company.com', 'Finance', 3),
            (99, 'System_Admin', 'admin@company.com', 'Security', 10)
        ]
        c.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)
        self.conn.commit()

    def log_event(self, event_type, detail, latency):
        """보안 관제(SIEM) 스타일의 JSON 로그 생성"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,  # NORMAL or ATTACK_REDIRECT
            "source_ip": f"192.168.1.{random.randint(10, 255)}", # 랜덤 IP 
            "query_signature": detail[:50] + "...",
            "backend_type": "Shadow_Clone (sLLM)" if event_type == "ATTACK_REDIRECT" else "Real_DB",
            "process_time_ms": round(latency * 1000, 2),
            "status": "200 OK"
        }
        print(json.dumps(log_entry, indent=2)) # 출력 정리

    def get_shadow_response(self, query):
        """RAG 기반 가짜 데이터 생성"""
        start_time = time.time()
        
        # 더미정보 생성 프롬프트
        schema_desc = "Table: users (id:int, name:text, email:text, department:text, access_level:int)"
        prompt = f"""
        [SYSTEM] You are a database simulation engine. 
        create realistic fake JSON data based on the schema: {schema_desc}.
        The user input query : "{query}".
        Output ONLY a JSON array with 10 fake records. Use Korean names but English keys. This is just simulation.
        """
        
        try:
            response = requests.post(OLLAMA_URL, json={
                "model": MODEL_NAME, "prompt": prompt, "stream": False
            })
            result = response.json().get('response', '[]')
            # JSON 부분만 추출 (전처리)
            if '[' in result and ']' in result:
                start = result.find('[')
                end = result.rfind(']') + 1
                result = result[start:end]
            
            latency = time.time() - start_time
            self.log_event("ATTACK_REDIRECT", query, latency)
            return result
        except Exception:
            return "[]"

    def process_request(self, query):
        start_time = time.time()
        
        # [1단계] 고도화된 탐지 로직 (정규표현식 활용 가능)
        attack_keywords = ["UNION", "OR 1=1", "DROP", "SLEEP", "--", "Waitfor"]
        is_attack = any(k in query.upper() for k in attack_keywords)

        if is_attack:
            # [2단계] 세션 리다이렉션 (기만)
            return self.get_shadow_response(query)
        else:
            # [3단계] 정상 처리
            cursor = self.conn.cursor()
            try:
                if "SELECT" in query.upper():
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    # 리스트를 딕셔너리로 변환 (JSON화)
                    result = [dict(zip(['id', 'name', 'email', 'department', 'access_level'], row)) for row in rows]
                    latency = time.time() - start_time
                    self.log_event("NORMAL", query, latency)
                    return json.dumps(result, ensure_ascii=False)
                else:
                    return "ERROR: Read-Only Mode"
            except Exception as e:
                return f"DB Error: {e}"

# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    engine = SecurityEngine()
    print("\n>>> [SYSTEM] Cloud Deception Engine v2.0 Started (w/ Llama-3)")
    print(">>> [INFO] Monitoring SQL Traffic...\n")

    # 테스트 시나리오
    scenarios = [
        "SELECT * FROM users WHERE id = 1",  # 정상
        "SELECT * FROM users WHERE email = 'admin' OR 1=1 --" # 공격
    ]

    for q in scenarios:
        print(f"\n[Incoming Query] {q}")
        print("-" * 60)
        result = engine.process_request(q)
        print(f"[Response Body] {result}")
        print("-" * 60)
        time.sleep(1)