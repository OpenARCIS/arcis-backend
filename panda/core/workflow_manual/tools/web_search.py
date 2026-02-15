import json

from langchain.tools import tool
from ddgs import DDGS

@tool
def web_search(query: str, max_results: int = 5) -> str:
    '''
    Search the web for current information using DuckDuckGo.
    Returns results in a clear, structured format optimized for LLM parsing.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        JSON string containing search results with titles, snippets, and URLs
    '''
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
        
        if not raw_results:
            return json.dumps({
                "status": "no_results",
                "query": query,
                "results": []
            }, indent=2)
        
        # Clean and structure results
        results = [
            {
                "title": r["title"],
                "url": r["href"],
                "snippet": r["body"]
            }
            for r in raw_results
        ]
        
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