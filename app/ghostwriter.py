"""Ghostwriter GraphQL API client."""
import base64
import requests

_GRAPHQL_PATH = "/v1/graphql"

_RECENT_PROJECTS_QUERY = """
query RecentProjects($limit: Int!) {
  project(order_by: {startDate: desc}, limit: $limit) {
    id
    codename
    complete
    startDate
    endDate
    client { name shortName }
    reports(order_by: {last_update: desc}, limit: 1) {
      id
      title
      complete
    }
  }
}
"""

_PROJECT_REPORTS_QUERY = """
query ProjectReports($projectId: bigint!) {
  project(where: {id: {_eq: $projectId}}) {
    reports(order_by: {last_update: desc}) {
      id
      title
      complete
      last_update
    }
  }
}
"""

_GENERATE_REPORT_MUTATION = """
mutation GenerateReport($id: Int!) {
  generateReport(id: $id) {
    reportData
  }
}
"""

_DOWNLOAD_EVIDENCE_QUERY = """
query DownloadEvidence($evidenceId: Int!) {
  downloadEvidence(evidenceId: $evidenceId) {
    fileBase64
  }
}
"""


class GhostwriterError(Exception):
    pass


class GhostwriterClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        verify_ssl: bool = True,
        cf_client_id: str = "",
        cf_client_secret: str = "",
    ):
        self._base_url = base_url.rstrip("/")
        self._url = self._base_url + _GRAPHQL_PATH
        self._verify_ssl = verify_ssl
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if cf_client_id and cf_client_secret:
            self._headers["CF-Access-Client-Id"] = cf_client_id
            self._headers["CF-Access-Client-Secret"] = cf_client_secret

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            resp = requests.post(
                self._url, json=payload, headers=self._headers, timeout=30,
                verify=self._verify_ssl,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise GhostwriterError(f"Request failed: {exc}") from exc

        body = resp.json()
        if "errors" in body:
            msgs = "; ".join(e.get("message", "unknown") for e in body["errors"])
            raise GhostwriterError(f"GraphQL error: {msgs}")
        return body.get("data", {})

    def get_recent_projects(self, limit: int = 4) -> list[dict]:
        data = self._gql(_RECENT_PROJECTS_QUERY, {"limit": limit})
        return data.get("project", [])

    def get_project_reports(self, project_id: int) -> list[dict]:
        data = self._gql(_PROJECT_REPORTS_QUERY, {"projectId": project_id})
        rows = data.get("project", [])
        return rows[0]["reports"] if rows else []

    def generate_report(self, report_id: int) -> str:
        """Return the raw base64-encoded reportData string."""
        data = self._gql(_GENERATE_REPORT_MUTATION, {"id": report_id})
        return data["generateReport"]["reportData"]

    def fetch_evidence(self, evidence_id: int, path: str) -> bytes:
        """Fetch a binary evidence file via the downloadEvidence GraphQL mutation."""
        data = self._gql(_DOWNLOAD_EVIDENCE_QUERY, {"evidenceId": evidence_id})
        encoded = data.get("downloadEvidence", {}).get("fileBase64")
        if not encoded:
            raise GhostwriterError(f"No fileBase64 returned for evidence {path}")
        return base64.b64decode(encoded)
