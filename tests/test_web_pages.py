from starlette.requests import Request

from litmonitor.web.routes import index, search_page


def make_request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


def test_home_page_template_response_uses_current_starlette_signature():
    response = index(make_request("/"))

    assert response.template.name == "base.html"


def test_search_page_template_response_uses_current_starlette_signature():
    response = search_page(make_request("/search"))

    assert response.template.name == "search.html"


def test_base_template_contains_task_navigation_and_icons():
    html = response_text(index(make_request("/")))

    assert "Literature tasks" in html
    assert 'class="icon' in html
    assert "Search literature" in html
    assert "Run weekly profiles" in html


def test_search_template_contains_pubmed_style_search_panel():
    html = response_text(search_page(make_request("/search")))

    assert "Search PubMed" in html
    assert "Find biomedical papers" in html
    assert "search-panel" in html
    assert "Article results" in html


def response_text(response) -> str:
    return response.body.decode()
