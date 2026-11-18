from typing import List, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.documents import Document

class RouteDecision(BaseModel):
    route: Literal["kb", "direct"] = Field(description="kb for IT/support questions; direct for greetings/simple chat")

class EvidenceGrade(BaseModel):
    grade: Literal["good", "weak"] = Field(description="Whether evidence is sufficient to answer")
class AgentState(TypedDict):
    question:str # Original user question
    current_query:str     # Query used for retrieval or web search
    kb_docs:list[Document] #kb docs stored 
    web_results:str #web result stored by tavily done
    kb_grade:str
    web_grade:str 
    answer:str #final answer
    source_used:str 
    retry_count:int 
    trace: List[str]   # Execution steps for debugging and tracking
    citations: List[dict]  # Source references and citation metadata
