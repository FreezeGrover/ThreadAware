from threadaware.common.models import Turn
from threadaware.conversation.intelligence import ConversationalIntelligence


def test_casual_conversation_stays_casual():
    layer = ConversationalIntelligence()
    intent = layer.classify([Turn(role="user", content="Hey, how are you today?")])
    assert intent.mode == "casual"


def test_project_request_is_project_aware():
    layer = ConversationalIntelligence()
    intent = layer.classify([
        Turn(role="user", content="Can you update the ThreadAware dashboard and evaluation API?")
    ])
    assert intent.mode == "project"


def test_mixed_turn_preserves_human_and_project_context():
    layer = ConversationalIntelligence()
    intent = layer.classify([
        Turn(role="user", content="Hey, hope you're good. Can we refine the ThreadAware UI today?")
    ])
    assert intent.mode == "mixed"


def test_project_guidance_requests_warm_nonrobotic_voice():
    layer = ConversationalIntelligence()
    intent = layer.classify([
        Turn(role="user", content="Let's improve the project dashboard")
    ])
    guidance = layer.system_guidance(intent)
    assert "natural" in guidance.lower()
    assert "warm" in guidance.lower()
    assert "robotic" in guidance.lower()


def test_demo_reply_is_warm_and_useful_without_claiming_live_generation():
    layer = ConversationalIntelligence()
    turns = [Turn(role="user", content="I've been overwhelmed and stressed lately.")]
    reply = layer.demo_reply(turns)
    assert "sorry" in reply.lower()
    assert "one piece at a time" in reply.lower()
    assert "api key" not in reply.lower()
