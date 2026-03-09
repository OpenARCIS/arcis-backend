from arcis.core.llm.factory import LLMFactory
from arcis.core.workflow_manual.tools.web_search import web_search
from arcis.core.workflow_manual.tools.memory_search import memory_search
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER


async def prefetch_context(job: dict) -> dict:
    """
    Given a job document, gather relevant context using search tools.
    
    The job's title, description, and any prefetch_queries (from the scheduler
    agent parse) guide what to search for. If no explicit queries were provided,
    an LLM call determines what to look up.
    
    Returns a dict of gathered context keyed by source.
    """
    context = {}
    title = job.get("title", "")
    description = job.get("description", "")
    prefetch_queries = job.get("context", {}).get("prefetch_queries", [])

    # If the scheduler agent already provided specific queries, use them directly
    if prefetch_queries:
        search_queries = prefetch_queries
    else:
        # Ask LLM to generate search queries based on the job
        search_queries = await _generate_search_queries(title, description)

    # Web search
    web_results = []
    for query in search_queries[:3]:  # max 3 queries to avoid rate limits
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

    LOGGER.info(f"PREFETCH: Gathered context with {len(web_results)} web results, "
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
