import pytest

from app.rendering.pipeline import (
    _build_evidence_index,
    _resolve_inline_evidence,
    _resolve_richtext_evidence,
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
        result = _resolve_inline_evidence("{{.login_page}}", self.idx)
        assert '<img src="evidence/1/shot.png"' in result
        assert "<figcaption>Login page screenshot</figcaption>" in result

    def test_plain_name_with_whitespace(self):
        result = _resolve_inline_evidence("{{. login_page }}", self.idx)
        assert '<img src="evidence/1/shot.png"' in result

    def test_ref_tag_replaced_with_caption_text(self):
        assert _resolve_inline_evidence("{{.ref login_page}}", self.idx) == "Login page screenshot"

    def test_caption_tag_replaced_with_caption_text(self):
        assert _resolve_inline_evidence("{{.caption login_page}}", self.idx) == "Login page screenshot"

    def test_caption_falls_back_to_friendly_name_when_none(self):
        # _EV2 has caption=None, so friendly_name is used
        assert _resolve_inline_evidence("{{.caption admin_panel}}", self.idx) == "admin_panel"

    def test_unknown_name_left_unchanged(self):
        text = "{{.no_such_evidence}}"
        assert _resolve_inline_evidence(text, self.idx) == text

    def test_no_braces_returns_unchanged(self):
        text = "plain text with no tags"
        assert _resolve_inline_evidence(text, self.idx) == text

    def test_empty_index_returns_unchanged(self):
        assert _resolve_inline_evidence("{{.login_page}}", {}) == "{{.login_page}}"

    def test_path_is_html_escaped(self):
        ev = {"id": 9, "path": 'evidence/9/fi"le.png', "friendly_name": "bad", "caption": "Bad"}
        result = _resolve_inline_evidence("{{.bad}}", {"bad": ev})
        assert "&quot;" in result
        assert 'src="evidence/9/fi"le.png"' not in result

    def test_caption_is_html_escaped(self):
        ev = {"id": 10, "path": "evidence/10/x.png", "friendly_name": "x", "caption": "<script>xss</script>"}
        result = _resolve_inline_evidence("{{.x}}", {"x": ev})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestResolveRichtextEvidence:
    @pytest.fixture(autouse=True)
    def by_id(self):
        self.by_id = {1: _EV1, 2: _EV2}

    def test_class_first_attribute_order(self):
        div = '<div class="richtext-evidence" data-evidence-id="1"></div>'
        result = _resolve_richtext_evidence(div, self.by_id)
        assert '<img src="evidence/1/shot.png"' in result
        assert "<figcaption>Login page screenshot</figcaption>" in result

    def test_id_first_attribute_order(self):
        div = '<div data-evidence-id="1" class="richtext-evidence"></div>'
        result = _resolve_richtext_evidence(div, self.by_id)
        assert '<img src="evidence/1/shot.png"' in result

    def test_unknown_id_left_unchanged(self):
        div = '<div class="richtext-evidence" data-evidence-id="99"></div>'
        assert _resolve_richtext_evidence(div, self.by_id) == div

    def test_no_richtext_evidence_string_returns_unchanged(self):
        text = "<p>hello world</p>"
        assert _resolve_richtext_evidence(text, self.by_id) == text

    def test_empty_by_id_returns_unchanged(self):
        div = '<div class="richtext-evidence" data-evidence-id="1"></div>'
        assert _resolve_richtext_evidence(div, {}) == div

    def test_caption_falls_back_to_friendly_name_when_none(self):
        # _EV2 has caption=None
        div = '<div class="richtext-evidence" data-evidence-id="2"></div>'
        result = _resolve_richtext_evidence(div, self.by_id)
        assert "<figcaption>admin_panel</figcaption>" in result

    def test_caption_is_html_escaped(self):
        ev = {"id": 5, "path": "evidence/5/x.png", "friendly_name": "x", "caption": "<script>xss</script>"}
        div = '<div class="richtext-evidence" data-evidence-id="5"></div>'
        result = _resolve_richtext_evidence(div, {5: ev})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_path_is_html_escaped(self):
        ev = {"id": 6, "path": 'evidence/6/fi"le.png', "friendly_name": "x", "caption": "X"}
        div = '<div class="richtext-evidence" data-evidence-id="6"></div>'
        result = _resolve_richtext_evidence(div, {6: ev})
        assert "&quot;" in result
        assert 'src="evidence/6/fi"le.png"' not in result
