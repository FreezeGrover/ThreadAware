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


def test_validation_does_not_claim_synthetic_expert_evidence():
    response = client.get('/api/validation')
    assert response.status_code == 200
    payload = response.json()
    assert payload['has_real_expert_evidence'] is False
    assert payload['expert_reviewed_scenarios'] == 0
    assert payload['grader_expert_agreement'] is None
    assert payload['status'] == 'awaiting-expert-evidence'
