import pytest

from app.rendering.pipeline import (
    _build_evidence_index,
    _resolve_inline_evidence,
    _resolve_richtext_evidence,
    make_vue_data,
)

_EV1 = {
    "id": 1,
    "path": "evidence/1/shot.png",
    "friendly_name": "login_page",
    "caption": "Login page screenshot",
}
_EV2 = {
    "id": 2,
    "path": "evidence/2/admin.png",
    "friendly_name": "admin_panel",
    "caption": None,
}
_REPORT = {"findings": [{"evidence": [_EV1, _EV2]}]}


class TestBuildEvidenceIndex:
    def test_indexes_by_name_and_id(self):
        by_name, by_id = _build_evidence_index(_REPORT)
        assert by_name["login_page"] is _EV1
        assert by_id[1] is _EV1
        assert by_name["admin_panel"] is _EV2
        assert by_id[2] is _EV2

    def test_empty_report_returns_empty_indexes(self):
        by_name, by_id = _build_evidence_index({})
        assert by_name == {}
        assert by_id == {}

    def test_evidence_without_friendly_name_indexed_by_id_only(self):
        ev = {"id": 3, "path": "evidence/3/x.png"}
        by_name, by_id = _build_evidence_index({"ev": ev})
        assert 3 in by_id
        assert by_name == {}


class TestResolveInlineEvidence:
    @pytest.fixture(autouse=True)
    def index(self):
        self.idx = {"login_page": _EV1, "admin_panel": _EV2}

    def test_plain_name_produces_figure(self):
        result, ids = _resolve_inline_evidence("{{.login_page}}", self.idx)
        assert '<img src="evidence/1/shot.png"' in result
        assert "<figcaption>Login page screenshot</figcaption>" in result
        assert ids == {1}

    def test_plain_name_with_whitespace(self):
        result, ids = _resolve_inline_evidence("{{. login_page }}", self.idx)
        assert '<img src="evidence/1/shot.png"' in result
        assert ids == {1}

    def test_ref_tag_replaced_with_caption_text(self):
        result, ids = _resolve_inline_evidence("{{.ref login_page}}", self.idx)
        assert result == "Login page screenshot"
        assert ids == set()

    def test_caption_tag_replaced_with_caption_text(self):
        result, ids = _resolve_inline_evidence("{{.caption login_page}}", self.idx)
        assert result == "Login page screenshot"
        assert ids == set()

    def test_caption_falls_back_to_friendly_name_when_none(self):
        # _EV2 has caption=None, so friendly_name is used
        result, ids = _resolve_inline_evidence("{{.caption admin_panel}}", self.idx)
        assert result == "admin_panel"
        assert ids == set()

    def test_unknown_name_left_unchanged(self):
        text = "{{.no_such_evidence}}"
        result, ids = _resolve_inline_evidence(text, self.idx)
        assert result == text
        assert ids == set()

    def test_no_braces_returns_unchanged(self):
        text = "plain text with no tags"
        result, ids = _resolve_inline_evidence(text, self.idx)
        assert result == text
        assert ids == set()

    def test_empty_index_returns_unchanged(self):
        result, ids = _resolve_inline_evidence("{{.login_page}}", {})
        assert result == "{{.login_page}}"
        assert ids == set()

    def test_path_is_html_escaped(self):
        ev = {"id": 9, "path": 'evidence/9/fi"le.png', "friendly_name": "bad", "caption": "Bad"}
        result, ids = _resolve_inline_evidence("{{.bad}}", {"bad": ev})
        assert "&quot;" in result
        assert 'src="evidence/9/fi"le.png"' not in result
        assert ids == {9}

    def test_caption_is_html_escaped(self):
        ev = {"id": 10, "path": "evidence/10/x.png", "friendly_name": "x", "caption": "<script>xss</script>"}
        result, ids = _resolve_inline_evidence("{{.x}}", {"x": ev})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert ids == {10}


class TestResolveRichtextEvidence:
    @pytest.fixture(autouse=True)
    def by_id(self):
        self.by_id = {1: _EV1, 2: _EV2}

    def test_class_first_attribute_order(self):
        div = '<div class="richtext-evidence" data-evidence-id="1"></div>'
        result, ids = _resolve_richtext_evidence(div, self.by_id)
        assert '<img src="evidence/1/shot.png"' in result
        assert "<figcaption>Login page screenshot</figcaption>" in result
        assert ids == {1}

    def test_id_first_attribute_order(self):
        div = '<div data-evidence-id="1" class="richtext-evidence"></div>'
        result, ids = _resolve_richtext_evidence(div, self.by_id)
        assert '<img src="evidence/1/shot.png"' in result
        assert ids == {1}

    def test_unknown_id_left_unchanged(self):
        div = '<div class="richtext-evidence" data-evidence-id="99"></div>'
        result, ids = _resolve_richtext_evidence(div, self.by_id)
        assert result == div
        assert ids == set()

    def test_no_richtext_evidence_string_returns_unchanged(self):
        text = "<p>hello world</p>"
        result, ids = _resolve_richtext_evidence(text, self.by_id)
        assert result == text
        assert ids == set()

    def test_empty_by_id_returns_unchanged(self):
        div = '<div class="richtext-evidence" data-evidence-id="1"></div>'
        result, ids = _resolve_richtext_evidence(div, {})
        assert result == div
        assert ids == set()

    def test_caption_falls_back_to_friendly_name_when_none(self):
        # _EV2 has caption=None
        div = '<div class="richtext-evidence" data-evidence-id="2"></div>'
        result, ids = _resolve_richtext_evidence(div, self.by_id)
        assert "<figcaption>admin_panel</figcaption>" in result
        assert ids == {2}

    def test_caption_is_html_escaped(self):
        ev = {"id": 5, "path": "evidence/5/x.png", "friendly_name": "x", "caption": "<script>xss</script>"}
        div = '<div class="richtext-evidence" data-evidence-id="5"></div>'
        result, ids = _resolve_richtext_evidence(div, {5: ev})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert ids == {5}

    def test_path_is_html_escaped(self):
        ev = {"id": 6, "path": 'evidence/6/fi"le.png', "friendly_name": "x", "caption": "X"}
        div = '<div class="richtext-evidence" data-evidence-id="6"></div>'
        result, ids = _resolve_richtext_evidence(div, {6: ev})
        assert "&quot;" in result
        assert 'src="evidence/6/fi"le.png"' not in result
        assert ids == {6}


class TestInlineEvidenceFilteredFromEvidenceList:
    def test_inline_evidence_removed_from_finding_evidence_list(self):
        div = '<div class="richtext-evidence" data-evidence-id="1"></div>'
        report = {
            "findings": [{
                "severity": "high",
                "description": div,
                "evidence": [_EV1, _EV2],
            }]
        }
        data = make_vue_data(report)
        finding = data["finding_groups"][0]["findings"][0]
        # EV1 was used inline — must be removed from the evidence list
        assert all(ev["id"] != 1 for ev in finding["evidence"])
        # EV2 was not used inline — must remain
        assert any(ev["id"] == 2 for ev in finding["evidence"])

    def test_non_inline_evidence_kept_in_evidence_list(self):
        report = {
            "findings": [{
                "severity": "low",
                "description": "<p>no inline evidence here</p>",
                "evidence": [_EV1],
            }]
        }
        data = make_vue_data(report)
        finding = data["finding_groups"][0]["findings"][0]
        assert len(finding["evidence"]) == 1

    def test_no_evidence_list_is_safe(self):
        div = '<div class="richtext-evidence" data-evidence-id="1"></div>'
        report = {
            "findings": [{
                "severity": "low",
                "description": div,
            }]
        }
        data = make_vue_data(report)
        finding = data["finding_groups"][0]["findings"][0]
        assert "evidence" not in finding or finding.get("evidence") is None
