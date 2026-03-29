"""
Autonomous Recommendation Engine (ReAct Agent)
------------------------------------------------
Uses a ReAct-style agent loop to gather context before generating
recommendations.  The agent can call tools (calendar, emotion history,
memory, web search) across multiple iterations — just like the existing
utility_agent — then a second structured-output call produces the final
recommendation cards.

Architecture:
  Phase 1 — Research:  LLM + bind_tools()  →  iterative tool calls
  Phase 2 — Synthesise: LLM + with_structured_output(RecommendationList)

Adding future data sources (Spotify, IMDB, …) is as simple as writing
a new @tool function and appending it to `recommendation_tools`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from arcis.core.llm.factory import LLMFactory
from arcis.core.utils.token_tracker import save_token_usage
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.logger import LOGGER
from arcis.models.recommendations import RecommendationList

# ---- Recommendation-specific tools ------------------------------------
from arcis.core.recommendations.tools import recommendation_tools

# The single-user identifier used for the current single-tenant deploy.
DEFAULT_USER_ID = "test_user"

# How many ReAct iterations the agent is allowed before we force a final answer.
MAX_ITERATIONS = 6

# System prompt for the research phase
RECOMMENDATION_AGENT_PROMPT = """\
You are ARCIS Recommendation Agent — an autonomous background agent that \
gathers context about the user's current state and generates personalised, \
actionable recommendations.

You are NOT chatting with the user.  You are running headlessly on a schedule.

AVAILABLE TOOLS:

Core context:
- get_upcoming_calendar:         Fetch upcoming calendar events, todos, and reminders
- get_emotion_history:           Fetch recent mood/emotion data
- memory_search:                 Search the user's long-term memory for preferences, \
habits, and personal facts
- brave_web_search:              Search the web for external context (weather, news, \
wellness tips, trending topics)

Spotify (music listening context & discovery):
- spotify_get_currently_playing: What the user is listening to right now
- spotify_get_recently_played:   Their recent listening history
- spotify_get_top_items:         Their all-time top tracks and artists
- spotify_get_recommendations:   Personalised track recommendations from Spotify
- spotify_get_genre_seeds:       Valid genre names for recommendations
- spotify_get_new_releases:      Fresh new album releases
- spotify_get_featured_playlists: Spotify editorial / mood playlists

TMDB (movies & TV discovery):
- tmdb_get_trending:             What's trending globally right now (day/week)
- tmdb_get_popular:              Currently popular movies or TV shows
- tmdb_get_top_rated:            All-time top-rated movies or TV shows
- tmdb_get_now_playing:          Movies currently in theatres
- tmdb_get_upcoming_movies:      Upcoming movie releases
- tmdb_get_airing_today:         TV episodes airing today
- tmdb_discover_movies:          Browse movies by genre, year, or rating
- tmdb_discover_tv:              Browse TV shows by genre, year, or rating
- tmdb_search:                   Search for a specific movie, show, or person
- tmdb_get_genres:               Get genre IDs needed for discover calls

WORKFLOW:
1. ALWAYS start by calling get_emotion_history and get_upcoming_calendar to \
understand the user's current situation.
2. Based on their mood and schedule, decide what additional context helps:
   - If they seem stressed or tired → check Spotify recent plays for mood context.
   - If they appear relaxed or have free time → check TMDB trending for \
entertainment ideas, or Spotify recommendations for music discovery.
   - Use memory_search to recall preferences (e.g. "user loves sci-fi films", \
"user prefers chill music when working").
   - Use brave_web_search for real-world context (weather, local events, news).
3. After gathering enough context (at minimum: emotion + calendar), stop calling \
tools and produce a thorough ANALYSIS summarising what you found and what \
kind of recommendations would be most helpful right now.

RULES:
- Do NOT ask the user any questions — you are running autonomously.
- Do NOT hallucinate data — only use what the tools return.
- Be empathetic and context-aware.  If the user is stressed, prioritise \
wellbeing.  If they have a busy day, prioritise focus/productivity. \
If they have free time, suggest entertainment (film, music, series).
- Use Spotify and TMDB data to make entertainment recommendations *specific* \
(e.g. "Based on your recent lo-fi listening and a free evening, here are \
calming films trending right now…").
- You may call multiple tools in a single iteration.
- Keep total tool calls efficient — do not call tools whose results you won't use.
"""



async def generate_recommendations() -> None:
    """
    Main entry point called by the scheduler.

    1. Run ReAct research loop — agent calls tools iteratively.
    2. Feed gathered context into structured-output call.
    3. Overwrite the `recommendations` collection for this user.
    """
    LOGGER.info("RECOMMENDATIONS: Starting recommendation generation (ReAct agent)")

    try:
        # Phase 1 — Research via ReAct loop
        research_context = await _run_research_agent()
        if not research_context:
            LOGGER.warning("RECOMMENDATIONS: Research phase returned no context — skipping")
            return

        # Phase 2 — Convert research into structured recommendations
        recommendation_list = await _synthesise_recommendations(research_context)
        if recommendation_list is None:
            return

        # Phase 3 — Store to MongoDB
        await _store_recommendations(recommendation_list, research_context)
        LOGGER.info(
            f"RECOMMENDATIONS: Generated and stored "
            f"{len(recommendation_list.recommendations)} recommendations"
        )

    except Exception as exc:
        LOGGER.error(
            f"RECOMMENDATIONS: Unhandled error during generation: {exc}", exc_info=True
        )


# ---------------------------------------------------------------------------
# Phase 1 — ReAct Research Agent
# ---------------------------------------------------------------------------

async def _run_research_agent() -> str | None:
    """
    Run a ReAct loop: LLM calls tools iteratively to gather context.
    Returns the LLM's final textual analysis, or None on failure.

    This mirrors the tool-loop pattern in utility_agent.py.
    """
    try:
        llm_client = LLMFactory.get_client_for_agent("utility_agent")
        tool_bound_llm = llm_client.bind_tools(recommendation_tools)

        # Build the initial message list
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        messages = [
            SystemMessage(content=RECOMMENDATION_AGENT_PROMPT),
            SystemMessage(content=f"Current Date and Time: {current_time}"),
            HumanMessage(
                content=(
                    "Gather context about the user's current state and upcoming schedule, "
                    "then produce an analysis of what recommendations would help them most "
                    "right now.  Start by checking their mood and calendar."
                )
            ),
        ]

        tool_map = {tool.name: tool for tool in recommendation_tools}
        final_text = ""

        for iteration in range(MAX_ITERATIONS):
            # On the last iteration, force a text-only final answer
            if iteration == MAX_ITERATIONS - 1:
                messages.append(
                    HumanMessage(
                        content=(
                            "You have reached the maximum number of tool iterations. "
                            "Do NOT call any more tools.  Synthesize a final analysis "
                            "from the information you have gathered so far."
                        )
                    )
                )
                LOGGER.warning(
                    f"RECOMMENDATIONS: Reached max iterations ({MAX_ITERATIONS}), "
                    "forcing final answer"
                )
                response = await llm_client.ainvoke(messages)  # no tools bound
                await _track_usage(response)
                final_text = response.content
                break

            # Normal iteration — LLM may call tools
            response = await tool_bound_llm.ainvoke(messages)
            await _track_usage(response)

            # No tool calls → agent is done researching
            if not response.tool_calls:
                final_text = response.content
                LOGGER.info(
                    f"RECOMMENDATIONS: Research complete after {iteration + 1} iteration(s)"
                )
                break

            # Execute tool calls
            LOGGER.debug(
                f"RECOMMENDATIONS: Iteration {iteration + 1}: "
                f"processing {len(response.tool_calls)} tool call(s)"
            )

            tool_messages = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                LOGGER.debug(f"RECOMMENDATIONS: Calling tool: {tool_name}({tool_args})")

                if tool_name in tool_map:
                    tool = tool_map[tool_name]
                    try:
                        if hasattr(tool, "ainvoke"):
                            result = await tool.ainvoke(tool_args)
                        else:
                            result = tool.invoke(tool_args)
                    except Exception as e:
                        result = f"Error executing {tool_name}: {e}"
                        LOGGER.warning(f"RECOMMENDATIONS: Tool error: {result}")
                else:
                    result = f"Unknown tool: {tool_name}"
                    LOGGER.warning(f"RECOMMENDATIONS: {result}")

                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )

            # Append assistant response + tool results to message history
            messages.append(response)
            messages.extend(tool_messages)

        if not final_text:
            LOGGER.warning("RECOMMENDATIONS: Research agent produced no output")
            return None

        LOGGER.debug(f"RECOMMENDATIONS: Research context length: {len(final_text)} chars")
        return final_text

    except Exception as exc:
        LOGGER.error(f"RECOMMENDATIONS: Research agent failed: {exc}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Phase 2 — Structured Output Synthesis
# ---------------------------------------------------------------------------

async def _synthesise_recommendations(research_context: str) -> RecommendationList | None:
    """
    Take the free-text research context and convert it into a strict
    RecommendationList using with_structured_output().

    Two-step design: letting the agent reason freely first, then
    constraining the output format, is more reliable than doing both
    in one call.
    """
    try:
        base_llm = LLMFactory.get_client_for_agent("utility_agent")
        structured_llm = base_llm.with_structured_output(RecommendationList)

        synthesis_prompt = (
            "You are a recommendation synthesiser.  Based on the research analysis below, "
            "generate 3 to 6 personalised, actionable recommendations for the user.\n\n"
            "Categories to use: wellbeing, productivity, focus, social, break.\n"
            "Priority: 1 (low) to 5 (urgent).\n"
            "Each recommendation needs: title (≤10 words), body (1-2 sentences "
            "explaining *why* this is relevant right now), category, priority, "
            "and a single emoji icon.\n\n"
            "Prioritise wellbeing if frustration/confusion is high.\n"
            "Prioritise focus/productivity if important events are imminent.\n"
            "Be specific — reference actual data from the analysis.\n\n"
            f"--- RESEARCH ANALYSIS ---\n{research_context}\n--- END ---"
        )

        LOGGER.debug("RECOMMENDATIONS: Calling structured-output LLM for synthesis")
        result: RecommendationList = await structured_llm.ainvoke(synthesis_prompt)

        # Token tracking for structured output (not all providers expose this)
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            await save_token_usage("recommendation_engine_synth", result.usage_metadata)

        return result

    except Exception as exc:
        LOGGER.error(f"RECOMMENDATIONS: Synthesis LLM call failed: {exc}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Phase 3 — Storage
# ---------------------------------------------------------------------------

async def _store_recommendations(
    recommendation_list: RecommendationList,
    research_context: str,
) -> None:
    """
    Replace all existing recommendations for this user with a fresh batch.
    Uses delete-then-insert which is fine for single-user.
    """
    collection = mongo.db[COLLECTIONS["recommendations"]]
    generated_at = datetime.now(timezone.utc)

    docs = [
        {
            "user_id": DEFAULT_USER_ID,
            "title": rec.title,
            "body": rec.body,
            "category": rec.category,
            "priority": rec.priority,
            "icon": rec.icon,
            "generated_at": generated_at,
            "_meta": {
                "research_context_length": len(research_context),
            },
        }
        for rec in recommendation_list.recommendations
    ]

    delete_result = await collection.delete_many({"user_id": DEFAULT_USER_ID})
    LOGGER.debug(f"RECOMMENDATIONS: Cleared {delete_result.deleted_count} old recommendations")

    if docs:
        await collection.insert_many(docs)
        LOGGER.debug(f"RECOMMENDATIONS: Inserted {len(docs)} new recommendations")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _track_usage(response) -> None:
    """Save token usage if the provider exposes it."""
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        await save_token_usage("recommendation_engine", response.usage_metadata)
    elif (
        hasattr(response, "response_metadata")
        and response.response_metadata.get("token_usage")
    ):
        await save_token_usage(
            "recommendation_engine", response.response_metadata["token_usage"]
        )
