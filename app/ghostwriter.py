"""Ghostwriter GraphQL API client."""
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


class GhostwriterError(Exception):
    pass


class GhostwriterClient:
    def __init__(self, base_url: str, token: str):
        self._url = base_url.rstrip("/") + _GRAPHQL_PATH
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            resp = requests.post(
                self._url, json=payload, headers=self._headers, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise GhostwriterError(f"Request failed: {exc}") from exc

        body = resp.json()
        if "errors" in body:
            msgs = "; ".join(e.get("message", "unknown") for e in body["errors"])
            raise GhostwriterError(f"GraphQL error: {msgs}")
        return body.get("data", {})

    def get_recent_projects(self, limit: int = 5) -> list[dict]:
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
