import uuid

from arcis.core.llm.factory import LLMFactory
from arcis.core.workflow_manual.tools.web_search import web_search
from arcis.core.workflow_manual.tools.memory_search import memory_search
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER


async def prefetch_context(job: dict) -> dict:
    """
    Intelligently prepare context for a scheduled task by invoking the
    main planner graph (run_workflow).

    The graph uses PREFETCH_PLANNER_PROMPT to plan and execute preparatory
    work — research, file creation, email drafting, etc.

    Falls back to shallow web + memory search if the graph fails.
    """
    title = job.get("title", "")
    description = job.get("description", "")
    prefetch_queries = job.get("context", {}).get("prefetch_queries", [])

    # Build a rich prompt for the planner graph
    prompt = _build_prefetch_prompt(title, description, prefetch_queries)

    # Try the full planner graph first
    try:
        context = await _deep_prefetch(prompt)
        if context:
            LOGGER.info(f"PREFETCH: Deep prefetch completed for '{title}'")
            return context
    except Exception as e:
        LOGGER.warning(f"PREFETCH: Deep prefetch failed for '{title}', falling back to shallow: {e}")

    # Fallback: shallow web + memory search
    LOGGER.info(f"PREFETCH: Using shallow fallback for '{title}'")
    return await _shallow_prefetch(title, description, prefetch_queries)


def _build_prefetch_prompt(title: str, description: str, prefetch_queries: list[str]) -> str:
    """Build the user input prompt for the planner graph in prefetch mode."""
    parts = [
        f"[Scheduled Task Preparation]",
        f"Task: {title}",
    ]
    if description:
        parts.append(f"Details: {description}")
    if prefetch_queries:
        parts.append(f"Preparation instructions: {'; '.join(prefetch_queries)}")
    else:
        parts.append(
            f"Prepare everything the user will need when this task fires. "
            f"Research the topic, create files if appropriate, and gather relevant context."
        )
    return "\n".join(parts)


async def _deep_prefetch(prompt: str) -> dict | None:
    """
    Run the main planner graph to do intelligent task preparation.
    Returns the prefetch context dict, or None on failure.
    """
    from arcis.core.workflow_manual.manual_flow import run_workflow

    thread_id = f"prefetch_{uuid.uuid4().hex[:12]}"

    LOGGER.info(f"PREFETCH: Invoking planner graph (thread={thread_id})")
    LOGGER.debug(f"PREFETCH: Prompt: {prompt}")

    result = await run_workflow(
        user_input=prompt,
        thread_id=thread_id,
    )

    if not isinstance(result, dict):
        LOGGER.warning("PREFETCH: Graph returned non-dict result")
        return None

    # If the graph was interrupted (needs user input), treat as failure
    # since no user is present during prefetch
    if result.get("type") == "interrupt":
        LOGGER.warning(f"PREFETCH: Graph interrupted (no user present): {result.get('response')}")
        return None

    context = {}

    # Extract the final synthesized response
    final_response = result.get("final_response", "")
    if final_response:
        context["prefetch_response"] = final_response

    # Extract any accumulated context from the agents
    graph_context = result.get("context", {})
    if graph_context:
        context["prefetch_details"] = graph_context

    return context if context else None


async def _shallow_prefetch(title: str, description: str, prefetch_queries: list[str]) -> dict:
    """
    Lightweight fallback: web search + memory search.
    This is the original prefetch behavior.
    """
    context = {}

    # Determine search queries
    if prefetch_queries:
        search_queries = prefetch_queries
    else:
        search_queries = await _generate_search_queries(title, description)

    # Web search
    web_results = []
    for query in search_queries[:3]:
        try:
            result = await web_search.ainvoke({"query": query})
            if result:
                web_results.append({"query": query, "result": str(result)})
                LOGGER.debug(f"PREFETCH: Web search for '{query}' returned results")
        except Exception as e:
            LOGGER.warning(f"PREFETCH: Web search failed for '{query}': {e}")

    if web_results:
        context["web_search"] = web_results

    # Memory search
    try:
        memory_query = f"{title} {description}".strip()
        memory_result = await memory_search.ainvoke({"query": memory_query})
        if memory_result and memory_result != "No relevant memories found.":
            context["long_term_memory"] = str(memory_result)
            LOGGER.debug("PREFETCH: Found relevant long-term memories")
    except Exception as e:
        LOGGER.warning(f"PREFETCH: Memory search failed: {e}")

    LOGGER.info(f"PREFETCH: Shallow fallback gathered {len(web_results)} web results, "
                f"memory={'yes' if 'long_term_memory' in context else 'no'}")

    return context


async def _generate_search_queries(title: str, description: str) -> list[str]:
    """Use LLM to generate relevant search queries for context prefetching."""
    try:
        llm_client = LLMFactory.get_client_for_agent("utility_agent")

        prompt = (
            f"Generate 2-3 short search queries to gather context for this task:\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"Return ONLY the queries, one per line. No numbering, no explanation."
        )

        response = await llm_client.ainvoke(prompt)

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            await save_token_usage("scheduler_prefetch", response.usage_metadata)

        queries = [q.strip() for q in response.content.strip().split("\n") if q.strip()]
        return queries[:3]
    except Exception as e:
        LOGGER.warning(f"PREFETCH: Query generation failed, using title as fallback: {e}")
        return [title]
