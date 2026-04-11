"""Tests for team message bus."""

from agent.team import MessageBus


class TestMessageBus:
    """Tests for MessageBus."""

    def test_send_and_receive(self, tmp_path):
        """Send message then read inbox should return it."""
        bus = MessageBus(tmp_path)

        bus.send("alice", "bob", "Hello Bob!")

        messages = bus.read_inbox("bob")
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello Bob!"
        assert messages[0]["from"] == "alice"

    def test_inbox_drained_after_read(self, tmp_path):
        """Inbox should be empty after reading."""
        bus = MessageBus(tmp_path)

        bus.send("alice", "bob", "Hello")
        bus.read_inbox("bob")

        messages = bus.read_inbox("bob")
        assert len(messages) == 0

    def test_broadcast(self, tmp_path):
        """Broadcast should send to all teammates."""
        bus = MessageBus(tmp_path)

        result = bus.broadcast("lead", "Hello team", ["alice", "bob", "charlie"])

        assert "3 teammates" in result

        assert len(bus.read_inbox("alice")) == 1
        assert len(bus.read_inbox("bob")) == 1
        assert len(bus.read_inbox("charlie")) == 1

    def test_invalid_message_type(self, tmp_path):
        """Invalid message type should return error."""
        bus = MessageBus(tmp_path)

        result = bus.send("alice", "bob", "Hello", "invalid_type")
        assert "Error" in result
