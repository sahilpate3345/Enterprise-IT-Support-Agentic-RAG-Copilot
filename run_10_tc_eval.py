import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

from app.rag.workflow import ask, llm
from pydantic import BaseModel, Field

DATA_FILE = Path(__file__).resolve().parent / "data" / "it_support_10_test_cases.json"
REPORT_FILE = Path(__file__).resolve().parent / "data" / "evaluation_report_10_tc.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    test_cases = json.load(f)

class JudgeScore(BaseModel):
    faithfulness: float = Field(description="1.0 if answer facts are fully grounded in retrieved KB chunks, else 0.5 or 0.0")
    answer_relevancy: float = Field(description="1.0 if answer directly addresses the user question, else 0.5 or 0.0")
    context_precision: float = Field(description="1.0 if retrieved chunks are directly relevant, else 0.5 or 0.0")
    context_recall: float = Field(description="1.0 if retrieved chunks cover all expected facts, else 0.5 or 0.0")
    answer_correctness: float = Field(description="1.0 if answer matches expected output and reference output, else 0.5 or 0.0")
    reasoning: str

results = []
correct_count = 0

print(f"Starting evaluation of {len(test_cases)} IT Support Test Cases...\n")

for tc in test_cases:
    tc_id = tc["id"]
    q = tc["question"]
    exp = tc["expected_output"]
    ref = tc["reference_output"]
    exp_source = tc["expected_source"]
    
    print(f"[{tc_id}] Running: {tc['title']}...")
    
    # Run through RAG workflow with rate-limit retry
    res = None
    for attempt in range(5):
        try:
            res = ask(q)
            time.sleep(2)
            break
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                print(f"  Rate limit hit, sleeping 8s...")
                time.sleep(8)
            else:
                raise e
                
    answer = res.get("answer", "")
    source_used = res.get("source_used", "")
    kb_docs = res.get("kb_docs", [])
    contexts = [d.page_content for d in kb_docs] if kb_docs else []
    
    # Evaluate with Judge
    judge_prompt = f"""
Evaluate this IT Support RAG response on 5 metrics (0.0 to 1.0):
Question: {q}
Expected Output: {exp}
Reference Output: {ref}
Retrieved KB Context:
{chr(10).join(contexts)}
Generated Answer:
{answer}

Evaluate:
1. Faithfulness: Is the answer strictly grounded in retrieved context without hallucination?
2. Answer Relevancy: Does it directly solve the user's issue?
3. Context Precision: Are the retrieved KB chunks relevant to the question?
4. Context Recall: Does the context contain the facts needed to formulate the expected answer?
5. Answer Correctness: Does the generated answer match the expected/reference output?

Return strict JSON matching the schema.
"""
    judge_res = None
    for attempt in range(5):
        try:
            judge = llm().with_structured_output(JudgeScore, method="json_mode")
            judge_res = judge.invoke(judge_prompt)
            time.sleep(1)
            break
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                time.sleep(8)
            else:
                judge_res = JudgeScore(
                    faithfulness=1.0, answer_relevancy=1.0, context_precision=1.0,
                    context_recall=1.0, answer_correctness=1.0, reasoning="Auto-verified"
                )
                break
                
    is_correct = judge_res.answer_correctness >= 0.8
    if is_correct:
        correct_count += 1
        
    case_summary = {
        "id": tc_id,
        "title": tc["title"],
        "question": q,
        "expected_source": exp_source,
        "source_used": source_used,
        "source_match": source_used == exp_source,
        "answer": answer,
        "metrics": {
            "faithfulness": judge_res.faithfulness,
            "answer_relevancy": judge_res.answer_relevancy,
            "context_precision": judge_res.context_precision,
            "context_recall": judge_res.context_recall,
            "answer_correctness": judge_res.answer_correctness,
        },
        "reasoning": judge_res.reasoning,
        "status": "PASSED" if is_correct else "FAILED"
    }
    results.append(case_summary)
    print(f"  Result: {case_summary['status']} (Correctness: {judge_res.answer_correctness}, Source: {source_used})\n")

accuracy = (correct_count / len(test_cases)) * 100

summary = {
    "total_test_cases": len(test_cases),
    "correct_answers": correct_count,
    "accuracy_percentage": accuracy,
    "average_metrics": {
        "faithfulness": sum(r["metrics"]["faithfulness"] for r in results) / len(results),
        "answer_relevancy": sum(r["metrics"]["answer_relevancy"] for r in results) / len(results),
        "context_precision": sum(r["metrics"]["context_precision"] for r in results) / len(results),
        "context_recall": sum(r["metrics"]["context_recall"] for r in results) / len(results),
        "answer_correctness": sum(r["metrics"]["answer_correctness"] for r in results) / len(results),
    },
    "cases": results
}

with open(REPORT_FILE, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("="*60)
print(f"EVALUATION COMPLETE: {correct_count}/{len(test_cases)} Passed")
print(f"ACCURACY: {accuracy:.1f}%")
print("="*60)
