from app.services.tags import clean_tags


class TestCleanTags:
    def test_strips_whitespace(self) -> None:
        assert clean_tags(["  python  ", " fastapi "]) == ["python", "fastapi"]

    def test_removes_empty_strings(self) -> None:
        assert clean_tags(["python", "", "  ", "fastapi"]) == ["python", "fastapi"]

    def test_deduplicates(self) -> None:
        assert clean_tags(["python", "fastapi", "python", "FastAPI"]) == [
            "python",
            "fastapi",
            "FastAPI",
        ]

    def test_preserves_first_seen_order(self) -> None:
        assert clean_tags(["c", "b", "a", "b", "c"]) == ["c", "b", "a"]

    def test_empty_input(self) -> None:
        assert clean_tags([]) == []

    def test_all_blank_input(self) -> None:
        assert clean_tags(["", "  ", "   "]) == []
