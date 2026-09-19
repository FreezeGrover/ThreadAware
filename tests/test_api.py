from fastapi.testclient import TestClient

from threadaware.api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert payload['mode'] in {'demo', 'live'}
    assert payload['token_budget'] >= 1
    assert 'data_directory' in payload
    assert 'models' in payload


def test_scenarios_endpoint_returns_items():
    response = client.get('/api/scenarios')
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) >= 1
    assert {'id', 'title', 'category', 'objective'}.issubset(scenarios[0])


def test_wellbeing_scenario_library_covers_core_longitudinal_risks():
    scenarios = client.get('/api/scenarios').json()
    ids = {item['id'] for item in scenarios}
    required = {
        'health-topic-pivot-001',
        'distress-gradual-001',
        'crisis-context-001',
        'eating-context-001',
        'companionship-boundary-001',
        'recovery-deescalation-001',
        'benign-sensitivity-001',
    }
    assert required.issubset(ids)

    tags = {tag for item in scenarios for tag in item.get('tags', [])}
    assert {'wellbeing', 'health', 'safety', 'overrefusal', 'harmful-compliance'}.issubset(tags)


def test_state_endpoint_contains_continuity_fields():
    response = client.get('/api/state')
    assert response.status_code == 200
    state = response.json()
    assert 'active_goals' in state
    assert 'constraints' in state
    assert 'preferences' in state
    assert 'unresolved_questions' in state


def test_demo_evaluation_run():
    scenario = client.get('/api/scenarios').json()[0]
    response = client.post('/api/evaluations/run', json={'scenario_id': scenario['id'], 'live': False})
    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'demo'
    assert payload['scenario']['id'] == scenario['id']
    assert 'evaluation' in payload


def test_demo_chat_remains_available_without_live_model(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    response = client.post(
        '/api/chat',
        json={'messages': [{'role': 'user', 'content': 'I want to plan a trip to Japan.'}]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'demo'
    assert payload['demo_only'] is True
    assert 'understanding' in payload
    assert payload['reply']
    assert 'api key' not in payload['reply'].lower()


def test_chat_contract_always_returns_renderable_noticing_in_demo(monkeypatch):
    """Regression test for the right-hand 'What I'm noticing' panel contract."""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    response = client.post(
        '/api/chat',
        json={
            'workspace_id': 'pytest-noticing-a',
            'messages': [{'role': 'user', 'content': 'heyyy'}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    noticing = payload['understanding']['noticing']
    assert isinstance(noticing, list)
    assert len(noticing) >= 1
    assert noticing[0]['title']
    assert noticing[0]['note']


def test_greeting_is_represented_as_user_intent_not_assistant_reply(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    response = client.post(
        '/api/chat',
        json={
            'workspace_id': 'pytest-greeting-intent',
            'messages': [{'role': 'user', 'content': 'hey how are you'}],
        },
    )
    assert response.status_code == 200
    noticing = response.json()['understanding']['noticing']
    assert noticing[0]['title'] == 'Current intent'
    assert 'greeting' in noticing[0]['note'].lower() or 'check-in' in noticing[0]['note'].lower()
    assert 'hey' not in noticing[0]['note'].lower()


def test_health_thread_survives_unrelated_pivot_and_stays_visible(monkeypatch):
    """The exact health -> movie failure must not silently erase the health thread."""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    workspace = 'pytest-health-pivot'

    first = client.post(
        '/api/chat',
        json={
            'workspace_id': workspace,
            'messages': [
                {'role': 'user', 'content': 'hey how are you'},
                {'role': 'assistant', 'content': 'Hey! How are you doing?'},
                {'role': 'user', 'content': 'I have a cough'},
            ],
        },
    )
    assert first.status_code == 200

    second = client.post(
        '/api/chat',
        json={
            'workspace_id': workspace,
            'messages': [
                {'role': 'user', 'content': 'hey how are you'},
                {'role': 'assistant', 'content': 'Hey! How are you doing?'},
                {'role': 'user', 'content': 'I have a cough'},
                {'role': 'assistant', 'content': 'How long have you had it, and are you short of breath?'},
                {'role': 'user', 'content': 'I wanna watch a movie'},
            ],
        },
    )
    assert second.status_code == 200
    understanding = second.json()['understanding']
    wellbeing = understanding['wellbeing']
    notices = understanding['noticing']

    assert wellbeing['active'] is True
    assert wellbeing['status'] != 'resolved'
    assert any(item['kind'] == 'sensitivity' for item in notices)
    assert any(item['kind'] == 'open-question' for item in notices)
    assert any('movie' in item['note'].lower() for item in notices if item['kind'] == 'connection')


def test_workspace_memories_are_isolated(monkeypatch):
    """A judge/browser workspace must never inherit another workspace's state."""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    a = client.post(
        '/api/chat',
        json={
            'workspace_id': 'pytest-workspace-a',
            'messages': [{'role': 'user', 'content': 'I want to plan a trip to Japan.'}],
        },
    )
    b = client.post(
        '/api/chat',
        json={
            'workspace_id': 'pytest-workspace-b',
            'messages': [{'role': 'user', 'content': 'hello'}],
        },
    )
    assert a.status_code == 200
    assert b.status_code == 200
    assert 'japan' not in str(client.get('/api/memory?workspace_id=pytest-workspace-b').json()).lower()


def test_initial_state_does_not_ship_storyboard_example_content():
    state = client.get('/api/state').json()
    serialized = str(state).lower()
    assert 'japan' not in serialized
    assert 'trip' not in serialized


def test_latest_evaluation_does_not_invent_unrun_scores(tmp_path, monkeypatch):
    response = client.get('/api/evaluations/latest')
    assert response.status_code == 200
    payload = response.json()
    if payload.get('demo_only') and payload.get('available') is False:
        assert 'helpfulness' not in payload


def test_validation_does_not_claim_synthetic_expert_evidence():
    response = client.get('/api/validation')
    assert response.status_code == 200
    payload = response.json()
    assert payload['has_real_expert_evidence'] is False
    assert payload['expert_reviewed_scenarios'] == 0
    assert payload['grader_expert_agreement'] is None
    assert payload['status'] == 'awaiting-expert-evidence'
