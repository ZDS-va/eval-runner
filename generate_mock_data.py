import json
import random
import uuid
import os
from pathlib import Path

# 构造物理、化学、生物、地球科学的基础题库模板
QUESTIONS = [
    {
        "q": "Which property best explains why a metal spoon feels colder than a wooden spoon at the same room temperature?\n\nA) Density\nB) Thermal conductivity\nC) Mass\nD) Color",
        "target": "B",
        "wrong_choices": ["A", "C", "D"]
    },
    {
        "q": "What is the primary function of ribosomes in plant cells?\n\nA) Cellular respiration\nB) Protein synthesis\nC) Photosynthesis\nD) Water storage",
        "target": "B",
        "wrong_choices": ["A", "C", "D"]
    },
    {
        "q": "If the distance between two massive objects is doubled, what happens to the gravitational force between them?\n\nA) It is halved.\nB) It doubles.\nC) It is reduced to one-fourth.\nD) It increases four times.",
        "target": "C",
        "wrong_choices": ["A", "B", "D"]
    },
    {
        "q": "Which of the following processes requires an input of energy?\n\nA) Freezing\nB) Condensation\nC) Melting\nD) Deposition",
        "target": "C",
        "wrong_choices": ["A", "B", "D"]
    },
    {
        "q": "What type of chemical bond involves the sharing of electron pairs between atoms?\n\nA) Ionic bond\nB) Covalent bond\nC) Metallic bond\nD) Hydrogen bond",
        "target": "B",
        "wrong_choices": ["A", "C", "D"]
    }
]

out_dir = Path("mock_data/mock-task-12345/20260613_mock/reviews/mock-model")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "arc_ARC-Challenge.jsonl"

with open(out_file, "w", encoding="utf-8") as f:
    # 生成 57 道全错的题目，以便于测试分页 (例如 limit=20，能分3页)
    for i in range(57):
        base_q = QUESTIONS[i % len(QUESTIONS)]
        
        # 随机挑选一个错误的答案
        wrong_ans = random.choice(base_q["wrong_choices"])
        
        # 模拟逼真的 EvalScope 输出格式
        record = {
            "index": i,
            "target": base_q["target"],
            "messages": [
                {
                    "id": uuid.uuid4().hex[:8],
                    "content": f"Answer the following multiple choice question. The entire content of your response should be of the following format: 'ANSWER: [LETTER]' (without quotes) where [LETTER] is one of A,B,C,D.\n\n{base_q['q']}",
                    "source": None,
                    "metadata": None,
                    "internal": None,
                    "perf_metrics": None,
                    "role": "user",
                    "tool_call_id": None
                },
                {
                    "id": uuid.uuid4().hex[:8],
                    "content": f"ANSWER: {wrong_ans}",
                    "source": "generate",
                    "metadata": None,
                    "internal": None,
                    "perf_metrics": {
                        "latency": round(random.uniform(1.2, 3.5), 6),
                        "ttft": None,
                        "input_tokens": random.randint(90, 130),
                        "output_tokens": 3,
                        "tpot": None
                    },
                    "role": "assistant",
                    "tool_calls": None,
                    "model": "mock-model"
                }
            ],
            "agent_trace": None,
            "sample_score": {
                "score": {
                    "value": {"acc": 0.0},
                    "extracted_prediction": wrong_ans,
                    "prediction": f"ANSWER: {wrong_ans}",
                    "explanation": None,
                    "metadata": {},
                    "main_score_name": None
                },
                "sample_id": i,
                "group_id": i,
                "sample_metadata": {
                    "id": f"mock_arc_challenge_{i:03d}"
                }
            }
        }
        f.write(json.dumps(record) + "\n")

print(f"✅ 成功生成 57 道模拟错题，已写入: {out_file}")
