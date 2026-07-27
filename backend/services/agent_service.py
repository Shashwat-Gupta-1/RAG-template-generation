from typing import Any, Dict, Optional
from backend.phase2.create_agent import SessionAgent, _COMPILED_GRAPH

async def run_agent_chat(conversation_id: str, message: Optional[str] = None) -> Dict[str, Any]:
    agent = SessionAgent()
    res = await agent.chat(conversation_id, message)
    
    # If the response is a dictionary (our refactored response style), return it directly
    if isinstance(res, dict):
        return res
        
    # Fallback to reading the state directly from checkpointer
    config = {"configurable": {"thread_id": str(conversation_id)}}
    state = await _COMPILED_GRAPH.aget_state(config)
    assumptions = state.values.get("assumptions") or {}
    clarification_question = state.values.get("clarification_question")
    ready = bool(state.values.get("generated_prompt"))
    
    return {
        "reply": res,
        "assumptions": assumptions,
        "clarification_question": clarification_question,
        "ready": ready
    }

async def run_agent_rebuild(conversation_id: str, assumptions: Dict[str, Any], user_edits: str = "") -> Dict[str, Any]:
    agent = SessionAgent()
    prompt = await agent.rebuild_prompt(conversation_id, assumptions, user_edits)
    return {"generated_prompt": prompt}

async def run_agent_refine(conversation_id: str, refinement_request: str, previous_prompt: Optional[str] = None) -> Dict[str, Any]:
    agent = SessionAgent()
    prompt = await agent.refine_prompt(conversation_id, refinement_request, previous_prompt)
    return {"generated_prompt": prompt}


async def run_agent_generate_image(conversation_id: str) -> Dict[str, Any]:
    agent = SessionAgent()
    res = await agent.generate_image(conversation_id)
    if isinstance(res, dict):
        return {
            "image_path": res.get("path"),
            "method": res.get("method", "generate")
        }
    return {"image_path": res, "method": "generate"}
