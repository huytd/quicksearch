from fastapi import FastAPI, Query, HTTPException
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
import json
import re

app = FastAPI(title="QuickSearch API", description="A simple search API powered by DuckDuckGo")


async def search_duckduckgo(query: str, max_results: int = 10) -> List[dict]:
    """
    Search DuckDuckGo and parse the HTML results.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        List of search results with title, URL, and description
    """
    search_url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(search_url, headers=headers)
        cookies = response.cookies

        form_data = {
            "q": query,
            "kl": ""
        }

        response = await client.post(search_url, headers=headers, data=form_data, cookies=cookies)

        soup = BeautifulSoup(response.text, "html.parser")

        results = []

        for result in soup.select(".result"):
            title_elem = result.select_one(".result__a")
            url_elem = result.select_one(".result__a")
            snippet_elem = result.select_one(".result__snippet")

            if title_elem and url_elem:
                results.append({
                    "title": title_elem.get_text(strip=True),
                    "url": url_elem.get("href"),
                    "description": snippet_elem.get_text(strip=True) if snippet_elem else ""
                })

            if len(results) >= max_results:
                break

        return results


async def read_url(url: str) -> dict:
    """
    Fetch a URL and extract its main text content.

    Args:
        url: The URL to fetch

    Returns:
        Dictionary containing URL, title, and main text content
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)

            soup = BeautifulSoup(response.text, "html.parser")

            title_elem = soup.find("title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()

            main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post|main")) or soup.body

            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            text = re.sub(r"\n+", "\n", text)

            return {
                "url": str(response.url),
                "title": title,
                "content": text,
                "status_code": response.status_code
            }
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing content: {str(e)}")


@app.get("/search")
async def search(
    q: str = Query(..., description="Search query", min_length=1),
    limit: Optional[int] = Query(10, description="Maximum number of results to return", ge=1, le=50)
):
    """
    Search DuckDuckGo and return results as JSON.
    """
    try:
        results = await search_duckduckgo(q, max_results=limit)
        return {
            "query": q,
            "results_count": len(results),
            "results": results
        }
    except Exception as e:
        return {
            "query": q,
            "error": str(e),
            "results": []
        }


@app.get("/read")
async def read(
    url: str = Query(..., description="URL to fetch and extract text from", min_length=1)
):
    """
    Fetch a URL and return its main text content.
    """
    return await read_url(url)


@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "QuickSearch API",
        "version": "0.1.0",
        "endpoints": {
            "/search": {
                "method": "GET",
                "description": "Search DuckDuckGo",
                "parameters": {
                    "q": "Search query (required)",
                    "limit": "Maximum results (optional, default: 10, max: 50)"
                }
            },
            "/read": {
                "method": "GET",
                "description": "Fetch and extract text content from a URL",
                "parameters": {
                    "url": "URL to fetch (required)"
                }
            }
        }
    }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()