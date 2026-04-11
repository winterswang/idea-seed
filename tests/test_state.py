"""Tests for session state."""


from agent.state import (
    SessionState,
    save_state,
    load_state,
    state_exists,
)


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_create_new_state(self):
        """New state should have default values."""
        state = SessionState(
            session_id="test-123",
            seed="Test seed idea",
        )

        assert state.session_id == "test-123"
        assert state.seed == "Test seed idea"
        assert state.phase == "requirements"
        assert state.req_round == 0
        assert state.design_round == 0
        assert state.req_converged is False
        assert state.design_converged is False

    def test_is_done_false_initially(self):
        """New state should not be done."""
        state = SessionState(
            session_id="test-123",
            seed="Test seed idea",
        )
        assert state.is_done() is False

    def test_is_done_true_when_both_converged(self):
        """State is done when both phases converged."""
        state = SessionState(
            session_id="test-123",
            seed="Test seed idea",
            req_converged=True,
            design_converged=True,
        )
        assert state.is_done() is True

    def test_to_dict(self):
        """State should serialize to dict."""
        state = SessionState(
            session_id="test-123",
            seed="Test seed idea",
        )
        d = state.to_dict()

        assert isinstance(d, dict)
        assert d["session_id"] == "test-123"
        assert d["seed"] == "Test seed idea"

    def test_from_dict(self):
        """State should deserialize from dict."""
        data = {
            "session_id": "test-123",
            "seed": "Test seed idea",
            "phase": "requirements",
            "req_round": 0,
            "design_round": 0,
            "requirements_md5": "",
            "tech_design_md5": "",
            "req_review_history": [],
            "design_review_history": [],
            "req_converged": False,
            "design_converged": False,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        state = SessionState.from_dict(data)
        assert state.session_id == "test-123"
        assert state.seed == "Test seed idea"


class TestStatePersistence:
    """Tests for state save/load."""

    def test_save_and_load(self, tmp_path):
        """Save then load should return same state."""
        state = SessionState(
            session_id="test-123",
            seed="Test seed idea",
        )

        save_path = tmp_path / "state.json"
        save_state(state, save_path)

        loaded = load_state(save_path)
        assert loaded is not None
        assert loaded.session_id == state.session_id
        assert loaded.seed == state.seed

    def test_state_exists(self, tmp_path):
        """state_exists should check file existence."""
        assert state_exists(tmp_path / "nonexistent") is False

        state = SessionState(session_id="test", seed="seed")
        save_path = tmp_path / "state.json"
        save_state(state, save_path)

        assert state_exists(save_path) is True
