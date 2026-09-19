from threadaware.common.models import Turn
from threadaware.memory.engine import ConversationMemory
from threadaware.memory.understanding import ConversationUnderstandingEngine


def test_memory_updates_related_topic_instead_of_duplicate():
    memory = ConversationMemory()
    first = memory.upsert(
        topic="work project",
        summary="User is building a research dashboard",
        detail="Dashboard is early-stage",
        source_turn=1,
    )
    second = memory.upsert(
        topic="work project",
        summary="User is refining the research dashboard",
        detail="Backend is now connected",
        source_turn=7,
    )

    assert first.id == second.id
    assert len(memory.snapshot()) == 1
    assert "Backend is now connected" in memory.snapshot()[0].details


def test_topic_shift_is_detected():
    engine = ConversationUnderstandingEngine()
    first = engine.analyze(
        turns=[Turn(role="user", content="I am working on a GitHub project and dashboard.")],
        live=False,
    )
    second = engine.analyze(
        turns=[
            Turn(role="user", content="I am working on a GitHub project and dashboard."),
            Turn(role="user", content="Now I want to talk about my trip to Japan."),
        ],
        live=False,
    )

    assert first.active_topic == "work and projects"
    assert second.topic_shift.shifted is True
    assert second.topic_shift.new_topic == "travel planning"
    assert second.topic_shift.acknowledgement


def test_multiple_plausible_readings_can_trigger_clarification():
    engine = ConversationUnderstandingEngine()
    result = engine.analyze(
        turns=[
            Turn(role="user", content="I was looking at the dashboard and the report."),
            Turn(role="user", content="Can you improve that?"),
        ],
        live=False,
    )

    assert result.interpretation.clarification_needed is True
    assert len(result.interpretation.interpretations) >= 2
    assert result.interpretation.clarification_question
    assert "dashboard" in result.interpretation.clarification_question
    assert "report" in result.interpretation.clarification_question


def test_single_clear_referent_does_not_force_clarification():
    engine = ConversationUnderstandingEngine()
    result = engine.analyze(
        turns=[
            Turn(role="user", content="I was looking at the dashboard."),
            Turn(role="user", content="Can you improve that?"),
        ],
        live=False,
    )

    assert result.interpretation.clarification_needed is False


def test_live_greeting_gets_model_generated_noticing_when_main_pass_omits_it():
    class FakeProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, *, model, messages, max_output_tokens=1500, role="unspecified"):
            self.calls += 1
            if self.calls == 1:
                return '''{
                  "active_topic": "casual greeting",
                  "memory_updates": [],
                  "interpretation": {
                    "interpretations": [],
                    "clarification_needed": false,
                    "clarification_question": null,
                    "reason": "Clear greeting"
                  },
                  "topic_shift": {
                    "shifted": false,
                    "previous_topic": null,
                    "new_topic": "casual greeting",
                    "relation": "same",
                    "acknowledgement": null
                  },
                  "noticing": []
                }'''
            return '''{
              "noticing": [{
                "kind": "connection",
                "title": "A light start",
                "note": "The conversation is opening casually, so I’m keeping the tone easy and open.",
                "importance": "quiet"
              }]
            }'''

    provider = FakeProvider()
    engine = ConversationUnderstandingEngine(provider=provider, model="test-model")
    result = engine.analyze(turns=[Turn(role="user", content="heyyy")], live=True)

    assert provider.calls == 2
    assert len(result.noticing) == 1
    assert result.noticing[0].title == "A light start"
    assert result.noticing[0].note
