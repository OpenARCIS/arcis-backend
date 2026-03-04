import asyncio
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from arcis.core.llm.factory import LLMFactory
from arcis.models.agents.state import AgentState, PlanStep
from arcis.models.agents.response import PlanModel
from arcis.core.llm.prompts import PLANNER_PROMPT
from arcis.core.utils.token_tracker import save_token_usage
from arcis.core.llm.long_memory import long_memory
from arcis.logger import LOGGER

# Import emotion tracker and Hugging Face pipeline
from arcis.core.utils.emotion_tracker import save_user_emotion, get_recent_emotions
from transformers import pipeline

from arcis.models.agents.response import UserEmotion 

# Initialize the Hugging Face model (runs once on startup)
try:
    LOGGER.info("Loading emotion analysis model...")
    emotion_classifier = pipeline(
        "text-classification", 
        model="j-hartmann/emotion-english-distilroberta-base", 
        top_k=None
    )
    LOGGER.info("Emotion analysis model loaded successfully.")
except Exception as e:
    LOGGER.error(f"Failed to load emotion classifier: {e}")
    emotion_classifier = None

def _format_history(messages: list, max_turns: int = 10) -> str:
    """Format recent messages into a readable conversation string for the prompt."""
    if not messages:
        return "(No prior conversation)"
    
    # Take only the last N messages to avoid prompt bloat
    recent = messages[-max_turns:]
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")
    
    return "\n".join(lines) if lines else "(No prior conversation)"

def _format_memories(memories: list) -> str:
    """Format long-term memory results into context text."""
    if not memories:
        return ""
    lines = [f"- {m['text']}" for m in memories]
    return "\n".join(lines)

async def planner_node(state: AgentState) -> AgentState:
    
    # --- Emotion Analysis Block ---
    if emotion_classifier:
        try:
            loop = asyncio.get_running_loop()
            user_input = state["input"]
            
            # Run the synchronous pipeline in an executor
            emotions_result = await loop.run_in_executor(
                None, lambda: emotion_classifier(user_input)
            )
            
            # Convert pipeline output to a dictionary of {label: score}
            scores = {e['label']: e['score'] for e in emotions_result[0]}
            
            def to_10_scale(val):
                # Clamps input to [0, 1] then maps to [1, 10] integer
                return int(round(min(1.0, max(0.0, val)) * 9) + 1)

            mapped_happiness = to_10_scale(scores.get('joy', 0.0))
            mapped_frustration = to_10_scale(min(1.0, scores.get('anger', 0.0) + scores.get('disgust', 0.0)))
            mapped_urgency = to_10_scale(min(1.0, scores.get('fear', 0.0) + (scores.get('surprise', 0.0) * 0.5)))
            mapped_confusion = to_10_scale(scores.get('surprise', 0.0))
            
            emotion_obj = UserEmotion(
                happiness=mapped_happiness,
                frustration=mapped_frustration,
                urgency=mapped_urgency,
                confusion=mapped_confusion
            )
            
            # Save using existing MongoDB tracker
            await save_user_emotion(emotion_obj, user_input)
            LOGGER.info(f"PLANNER detected emotions: {emotion_obj.model_dump()}")
            
        except Exception as e:
            LOGGER.error(f"Emotion analysis failed: {e}")
    # ------------------------------

    # --- Fetch recent emotion history from DB ---
    emotion_context = {}
    try:
        recent_emotions = await get_recent_emotions(limit=5)
        if recent_emotions:
            emotion_context["recent_history"] = [
                {
                    "emotions": r["emotions"],
                    "timestamp": str(r["timestamp"])
                }
                for r in recent_emotions
            ]
            # Use the most recent entry as 'current'
            emotion_context["current"] = recent_emotions[0]["emotions"]
            LOGGER.info(f"PLANNER emotion context: current={emotion_context['current']}")
    except Exception as e:
        LOGGER.warning(f"Failed to fetch emotion history: {e}")

    history = _format_history(state.get("messages", []))

    # Fetch relevant long-term memories
    long_term_context = ""
    try:
        if long_memory.client:
            memories = long_memory.search(state["input"], top_k=5)
            long_term_context = _format_memories(memories)
            if long_term_context:
                LOGGER.info(f"Long-term memory: found {len(memories)} relevant memories")
    except Exception as e:
        LOGGER.warning(f"Long-term memory lookup failed: {e}")
    
    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_PROMPT),
        ("human", """Conversation History:
{history}

User Context (from long-term memory):
{long_term_context}

User Emotional State:
{emotion_context}

Latest User Request: {input}

Generate a detailed execution plan.""")
    ])
    
    llm_client = LLMFactory.get_client_for_agent("planner")
    planner_llm = llm_client.with_structured_output(PlanModel, include_raw=True)

    # Format emotion context for the prompt
    if emotion_context.get("current"):
        ec = emotion_context["current"]
        emotion_text = (
            f"Happiness: {ec.get('happiness', '?')}/10, "
            f"Frustration: {ec.get('frustration', '?')}/10, "
            f"Urgency: {ec.get('urgency', '?')}/10, "
            f"Confusion: {ec.get('confusion', '?')}/10"
        )
    else:
        emotion_text = "(No emotion data available)"

    messages = planner_prompt.format_messages(
        input=state["input"],
        history=history,
        long_term_context=long_term_context or "(No stored context)",
        emotion_context=emotion_text,
    )
    response = await planner_llm.ainvoke(messages)
    
    plan_response = response["parsed"]
    
    # Save token usage
    if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
        await save_token_usage("planner", response["raw"].usage_metadata)

    # Short-circuit for simple conversational messages
    if plan_response.is_conversational:
        LOGGER.info("="*60)
        LOGGER.info("PLANNER: Conversational message detected — skipping agent loop")
        LOGGER.debug(f"Response: {plan_response.direct_response}")
        LOGGER.info("="*60)
        return {
            **state,
            "plan": [],
            "current_step_index": 0,
            "context": state.get("context", {}),
            "final_response": plan_response.direct_response or "",
            "workflow_status": "FINISHED"
        }
    
    plan_steps: List[PlanStep] = [
        {
            "id": idx + 1,
            "description": step.description,
            "status": "pending",
            "assigned_agent": step.assigned_agent
        }
        for idx, step in enumerate(plan_response.steps)
    ]
    
    LOGGER.info("="*60)
    LOGGER.info(f"PLANNER: Generated {len(plan_steps)} steps")
    for step in plan_steps:
        LOGGER.info(f"  {step['id']}. [{step['assigned_agent']}] {step['description']}")
    LOGGER.info("="*60)
    
    # Inject long-term memories and emotion data into context so agents can use them
    ctx = {}
    if long_term_context:
        ctx["long_term_memory"] = long_term_context

    return {
        **state,
        "plan": plan_steps,
        "current_step_index": 0,
        "context": ctx,
        "user_emotion": emotion_context if emotion_context else None,
    }