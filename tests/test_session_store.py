from src.agentic.session.store import DEFAULT_STATE, InMemorySessionStore


def test_new_session_returns_default_state():
    store = InMemorySessionStore()
    state = store.get("brand-new-session")
    assert state["fields"]["name"] is None
    assert state["history"] == []


def test_save_then_get_round_trips_history():
    store = InMemorySessionStore()
    state = store.get("session-1")
    state["history"].append({"role": "user", "text": "Hi, I'm Alex"})
    state["fields"]["name"] = "Alex"
    store.save("session-1", state)

    reloaded = store.get("session-1")
    assert reloaded["fields"]["name"] == "Alex"
    assert reloaded["history"][0]["text"] == "Hi, I'm Alex"


def test_sessions_are_isolated():
    store = InMemorySessionStore()
    state_a = store.get("user-a")
    state_a["fields"]["name"] = "Alex"
    store.save("user-a", state_a)

    state_b = store.get("user-b")
    assert state_b["fields"]["name"] is None
