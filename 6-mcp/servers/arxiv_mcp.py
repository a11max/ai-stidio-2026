"""
arXiv MCP Server

MCP-сервер для поиска и получения информации о научных статьях на arXiv.

Запуск:
    python arxiv_mcp.py
"""

import os

import requests
import feedparser
from fastmcp import FastMCP

# Сетевые настройки сервера (совместимо с текущим FastMCP API)
ARXIV_HOST = os.getenv("ARXIV_HOST", "158.160.175.155")
ARXIV_PORT = int(os.getenv("ARXIV_PORT", "8000"))

# Создаём MCP сервер
mcp = FastMCP("ArxivResearch", host=ARXIV_HOST, port=ARXIV_PORT)

# Базовый URL для arXiv API
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# Маппинг полей для поиска
FIELD_MAP = {
    "all": "all",
    "title": "ti",
    "abstract": "abs",
    "author": "au"
}


@mcp.tool()
def search_arxiv(query: str, field: str = "all", max_results: int = 3) -> str:
    """
    Поиск научных статей на arXiv по ключевым словам.
    Возвращает топ-N наиболее релевантных статей.
    
    Args:
        query: Поисковый запрос на английском языке. Ключевые слова через пробел.
        field: Поле для поиска: all (все поля), title (заголовок), abstract (аннотация), author (автор)
        max_results: Максимальное количество результатов (по умолчанию 3)
    """
    # Формируем поисковый запрос
    field_prefix = FIELD_MAP.get(field, "all")
    
    # Заменяем пробелы на +
    query_formatted = query.replace(" ", "+")
    search_query = f"{field_prefix}:{query_formatted}"
    
    # Формируем параметры запроса
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    try:
        response = requests.get(ARXIV_API_URL, params=params, timeout=15)
        feed = feedparser.parse(response.content)
        
        if not feed.entries:
            return "Статьи по данному запросу не найдены."
        
        results = []
        for i, entry in enumerate(feed.entries, 1):
            arxiv_id = entry.id.split('/abs/')[-1]
            authors = ', '.join(a.name for a in entry.authors[:3])
            if len(entry.authors) > 3:
                authors += " и др."
            
            # Укорачиваем аннотацию
            summary = entry.summary.replace('\n', ' ')[:300]
            
            results.append(
                f"{i}. **{entry.title}**\n"
                f"   - arXiv ID: {arxiv_id}\n"
                f"   - Авторы: {authors}\n"
                f"   - Аннотация: {summary}...\n"
            )
        
        total = feed.feed.opensearch_totalresults
        return f"Найдено статей: {total}. Топ-{max_results}:\n\n" + "\n".join(results)
    
    except Exception as e:
        return f"Ошибка при запросе к arXiv: {str(e)}"


@mcp.tool()
def get_paper_details(arxiv_id: str) -> str:
    """
    Получить полную информацию о статье по её arXiv ID,
    включая полную аннотацию, авторов, категории и ссылки.
    
    Args:
        arxiv_id: Идентификатор статьи на arXiv (например, 2304.12345 или 1706.03762)
    """
    # Очищаем ID от возможных префиксов
    arxiv_id = arxiv_id.replace("arXiv:", "").strip()
    
    params = {
        "id_list": arxiv_id,
        "max_results": 1
    }
    
    try:
        response = requests.get(ARXIV_API_URL, params=params, timeout=15)
        feed = feedparser.parse(response.content)
        
        if not feed.entries:
            return f"Статья с ID {arxiv_id} не найдена."
        
        entry = feed.entries[0]
        authors = ', '.join(a.name for a in entry.authors)
        categories = ', '.join(t['term'] for t in entry.tags)
        
        # Получаем ссылки
        pdf_link = ""
        abs_link = ""
        for link in entry.links:
            if link.get('title') == 'pdf':
                pdf_link = link.href
            if link.rel == 'alternate':
                abs_link = link.href
        
        result = (
            f"**{entry.title}**\n\n"
            f"**arXiv ID:** {arxiv_id}\n"
            f"**Авторы:** {authors}\n"
            f"**Опубликовано:** {entry.published}\n"
            f"**Категории:** {categories}\n"
            f"**Ссылка на статью:** {abs_link}\n"
            f"**Ссылка на PDF:** {pdf_link}\n\n"
            f"**Аннотация:**\n{entry.summary}"
        )
        
        return result
    
    except Exception as e:
        return f"Ошибка при запросе к arXiv: {str(e)}"


@mcp.tool()
def search_by_author(author_name: str, max_results: int = 5) -> str:
    """
    Поиск статей конкретного автора на arXiv.
    
    Args:
        author_name: Имя автора (например, "Hinton" или "Yann LeCun")
        max_results: Максимальное количество результатов (по умолчанию 5)
    """
    return search_arxiv(author_name, field="author", max_results=max_results)


@mcp.tool()
def search_recent(topic: str, max_results: int = 5) -> str:
    """
    Поиск недавних статей по теме, отсортированных по дате публикации.
    
    Args:
        topic: Тема для поиска (на английском языке)
        max_results: Максимальное количество результатов (по умолчанию 5)
    """
    query_formatted = topic.replace(" ", "+")
    search_query = f"all:{query_formatted}"
    
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    
    try:
        response = requests.get(ARXIV_API_URL, params=params, timeout=15)
        feed = feedparser.parse(response.content)
        
        if not feed.entries:
            return f"Статьи по теме '{topic}' не найдены."
        
        results = []
        for i, entry in enumerate(feed.entries, 1):
            arxiv_id = entry.id.split('/abs/')[-1]
            authors = ', '.join(a.name for a in entry.authors[:2])
            if len(entry.authors) > 2:
                authors += " и др."
            
            # Дата публикации
            published = entry.published[:10] if entry.published else "N/A"
            
            summary = entry.summary.replace('\n', ' ')[:200]
            
            results.append(
                f"{i}. [{published}] **{entry.title}**\n"
                f"   - ID: {arxiv_id} | Авторы: {authors}\n"
                f"   - {summary}...\n"
            )
        
        return f"Недавние статьи по теме '{topic}':\n\n" + "\n".join(results)
    
    except Exception as e:
        return f"Ошибка при запросе к arXiv: {str(e)}"


if __name__ == "__main__":
    print("📚 Запуск arXiv MCP Server...")
    print(f"📡 Сервер доступен по адресу: http://{ARXIV_HOST}:{ARXIV_PORT}/sse")
    print("⚠️  Для остановки нажмите Ctrl+C")
    print("")
    print("Доступные инструменты:")
    print("  • search_arxiv(query, field, max_results) — поиск статей")
    print("  • get_paper_details(arxiv_id) — детали статьи")
    print("  • search_by_author(author_name) — статьи автора")
    print("  • search_recent(topic) — недавние статьи")
    
    # SSE транспорт для совместимости с Responses API
    mcp.run(transport="sse")

