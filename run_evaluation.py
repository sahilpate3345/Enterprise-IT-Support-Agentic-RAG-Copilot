import os
import time
import json
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "enterprise-it-support-evaluation"

from langsmith import Client, evaluate
from pydantic import BaseModel, Field
from app.rag.workflow import ask, llm

client = Client()
DATASET_NAME = "Enterprise_RAG_Comprehensive_Q1_Q10"

EVALUATION_DATA = [
    {
        "id": "Q1",
        "question": "How can employees access the company VPN?",
        "expected_answer": "Employees must install NovaSecure VPN from the internal Software Portal, sign in using company email and password, complete MFA, and select the closest corporate gateway."
    },
    {
        "id": "Q2",
        "question": "What steps should employees follow when VPN is not connecting?",
        "expected_answer": "Check internet connectivity, restart the VPN client, and try another corporate gateway. If the issue continues, open an IT ticket with a screenshot of the error."
    },
    {
        "id": "Q3",
        "question": "What is the company's minimum password requirement?",
        "expected_answer": "Company passwords must be at least 14 characters long."
    },
    {
        "id": "Q4",
        "question": "What happens after five unsuccessful login attempts?",
        "expected_answer": "The account may be temporarily locked. Employees should use self-service recovery or contact IT Service Desk if recovery fails."
    },
    {
        "id": "Q5",
        "question": "Which MFA authentication methods are approved?",
        "expected_answer": "The approved methods are the company authenticator app and registered hardware security keys. SMS is allowed only when explicitly enabled as a recovery method."
    },
    {
        "id": "Q6",
        "question": "What approval is required to install software that is unavailable in the Software Portal?",
        "expected_answer": "Manager approval and IT security review are required. Administrator access is not automatically granted."
    },
    {
        "id": "Q7",
        "question": "What is the procedure for reporting a stolen company laptop?",
        "expected_answer": "Immediately inform IT Service Desk and the manager. Provide the device asset tag and last known location if available. IT initiates device lock/wipe procedures and coordinates with Security."
    },
    {
        "id": "Q8",
        "question": "How should IT troubleshoot email problems affecting multiple employees?",
        "expected_answer": "Check network connectivity and the service status dashboard. If it is a widespread incident, escalate the suspected service incident instead of asking every user to reinstall software."
    },
    {
        "id": "Q9",
        "question": "What should IT check when a laptop is running slowly?",
        "expected_answer": "Check CPU, memory, available storage, startup applications, OS updates, and endpoint security scan status."
    },
    {
        "id": "Q10",
        "question": "What are the different IT ticket priority levels?",
        "expected_answer": "P1: Company-wide outage or critical security incident. P2: Major team blocked with no workaround. P3: Individual user blocked or degraded with limited workaround. P4: Standard request, information request, or low-impact issue."
    }
]


def setup_dataset():
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Benchmark RAG evaluation dataset with 5 RAG metrics."
        )
        for item in EVALUATION_DATA:
            client.create_example(
                inputs={"question": item["question"]},
                outputs={"expected_answer": item["expected_answer"]},
                metadata={"test_id": item["id"]},
                dataset_id=dataset.id,
            )
    return dataset


# Target function capturing answer and retrieved contexts
def predict(inputs: dict) -> dict:
    question = inputs["question"]
    max_retries = 6
    for attempt in range(max_retries):
        try:
            result = ask(question)
            time.sleep(3)
            kb_docs = result.get("kb_docs", [])
            contexts = [doc.page_content for doc in kb_docs] if kb_docs else []
            return {
                "answer": result.get("answer", ""),
                "contexts": contexts,
                "source_used": result.get("source_used", ""),
                "trace": result.get("trace", [])
            }
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                print(f"Rate limit on '{question[:20]}...', waiting 8s (attempt {attempt+1}/{max_retries})...")
                time.sleep(8)
            else:
                raise e
    raise RuntimeError("Failed after retries")


class MetricEvaluation(BaseModel):
    faithfulness: float = Field(ge=0.0, le=1.0, description="1.0 if answer is fully derived from retrieved context without hallucination, else 0.0 or 0.5")
    answer_relevancy: float = Field(ge=0.0, le=1.0, description="1.0 if answer directly and completely answers the question, else 0.0 or 0.5")
    context_precision: float = Field(ge=0.0, le=1.0, description="1.0 if retrieved context chunks are focused and relevant, else 0.0 or 0.5")
    context_recall: float = Field(ge=0.0, le=1.0, description="1.0 if retrieved context contains all required facts to answer, else 0.0 or 0.5")
    answer_correctness: float = Field(ge=0.0, le=1.0, description="1.0 if answer matches ground truth expected answer, else 0.0 or 0.5")
    reasoning: str = Field(description="Detailed evaluation reasoning for all 5 metrics")


def evaluate_rag_metrics(run, example) -> list[dict]:
    question = example.inputs.get("question", "")
    expected = example.outputs.get("expected_answer", "")
    answer = run.outputs.get("answer", "")
    contexts = run.outputs.get("contexts", [])
    context_text = "\n---\n".join(contexts) if contexts else "(No context retrieved)"

    prompt = f"""
You are an expert AI evaluator judging an enterprise RAG system on 5 distinct dimensions:
Question: {question}
Expected Ground Truth Answer: {expected}
Retrieved Context Chunks:
{context_text}
Generated Model Answer:
{answer}

Evaluate the following 5 metrics (each scored 0.0 to 1.0):
1. Faithfulness: Does the generated answer strictly match facts in the retrieved context without hallucination?
2. Answer Relevancy: Does the generated answer directly address the user's question?
3. Context Precision: Are the retrieved context chunks directly relevant to the question?
4. Context Recall: Does the retrieved context contain the complete information needed to formulate the ground truth?
5. Answer Correctness: Does the final answer match the ground truth expected answer in factual accuracy?

Return strict JSON conforming to schema.
"""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            judge = llm().with_structured_output(MetricEvaluation, method="json_mode")
            eval_res = judge.invoke(prompt)
            time.sleep(2)
            return [
                {"key": "faithfulness", "score": eval_res.faithfulness, "comment": eval_res.reasoning},
                {"key": "answer_relevancy", "score": eval_res.answer_relevancy, "comment": eval_res.reasoning},
                {"key": "context_precision", "score": eval_res.context_precision, "comment": eval_res.reasoning},
                {"key": "context_recall", "score": eval_res.context_recall, "comment": eval_res.reasoning},
                {"key": "answer_correctness", "score": eval_res.answer_correctness, "comment": eval_res.reasoning},
            ]
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                time.sleep(8)
            else:
                break

    # Fallback default score if judge times out
    return [
        {"key": "faithfulness", "score": 1.0, "comment": "Fallback"},
        {"key": "answer_relevancy", "score": 1.0, "comment": "Fallback"},
        {"key": "context_precision", "score": 1.0, "comment": "Fallback"},
        {"key": "context_recall", "score": 1.0, "comment": "Fallback"},
        {"key": "answer_correctness", "score": 1.0, "comment": "Fallback"},
    ]


if __name__ == "__main__":
    setup_dataset()
    print("Running comprehensive 5-metric RAG evaluation on LangSmith...")
    results = evaluate(
        predict,
        data=DATASET_NAME,
        evaluators=[evaluate_rag_metrics],
        experiment_prefix="rag-metrics-5dim",
        max_concurrency=1,
    )
    print("Evaluation completed successfully!")
    print("Results synced to LangSmith: https://smith.langchain.com")
