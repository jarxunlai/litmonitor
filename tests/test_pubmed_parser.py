import httpx

from litmonitor.services.pubmed import parse_pubmed_xml
from litmonitor.services import pubmed


def test_parse_pubmed_xml_handles_missing_abstract_and_multiple_authors():
    xml = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>123</PMID>
          <Article>
            <Journal>
              <Title>Nature Medicine</Title>
              <JournalIssue><PubDate><Year>2026</Year><Month>Apr</Month><Day>01</Day></PubDate></JournalIssue>
            </Journal>
            <ArticleTitle>Test title</ArticleTitle>
            <AuthorList>
              <Author><LastName>Lai</LastName><ForeName>Jade</ForeName></Author>
              <Author><CollectiveName>Consortium</CollectiveName></Author>
            </AuthorList>
            <ELocationID EIdType="doi">10.1/example</ELocationID>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>
    """

    papers = parse_pubmed_xml(xml)

    assert len(papers) == 1
    assert papers[0].pmid == "123"
    assert papers[0].abstract is None
    assert papers[0].authors == "Jade Lai; Consortium"
    assert papers[0].doi == "10.1/example"
    assert papers[0].publication_date.isoformat() == "2026-04-01"


def test_get_with_retries_recovers_from_transient_transport_error(monkeypatch):
    calls = []

    class Client:
        def get(self, url, params):
            calls.append((url, params))
            if len(calls) == 1:
                raise httpx.ConnectError("reset")
            return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))

    monkeypatch.setattr(pubmed.time, "sleep", lambda seconds: None)

    response = pubmed._get_with_retries(Client(), "https://example.test", {"q": "x"}, attempts=2)

    assert response.json() == {"ok": True}
    assert len(calls) == 2
