import json
from langchain.tools import tool
from arcis.core.llm.long_memory import long_memory

@tool
def memory_search(query: str, category: str | None = None, top_k: int = 5) -> str:
    '''
    Search the user's long-term memory for past facts, preferences, or profile details.
    Results include text, category, and source.
    
    Args:
        query: The search query string to look for.
        category: Optional. Filter by category (e.g., 'user_profile', 'preference', 'key_detail', 'learned_fact').
        top_k: Maximum number of results to return (default: 5).
    
    Returns:
        JSON string containing the memories found.
    '''
    try:
        results = long_memory.search(query=query, top_k=top_k, category=category)
        
        if not results:
            return json.dumps({
                "status": "no_results",
                "query": query,
                "message": "No relevant memories found."
            }, indent=2)
            
        return json.dumps({
            "status": "success",
            "query": query,
            "count": len(results),
            "results": results
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
            "query": query
        }, indent=2)
