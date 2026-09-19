from fastapi.testclient import TestClient

from threadaware.api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert payload['mode'] in {'demo', 'live'}


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
