const navItems = [...document.querySelectorAll('.nav-item')];
const views = [...document.querySelectorAll('.view')];
const title = document.getElementById('view-title');

const labels = {
  chat: 'Conversation',
  continuity: 'Continuity',
  scenarios: 'Scenarios',
  evaluations: 'Evaluations',
  validation: 'Validation',
  insights: 'Insights',
};

navItems.forEach((item) => {
  item.addEventListener('click', () => {
    const target = item.dataset.view;
    navItems.forEach((nav) => nav.classList.toggle('active', nav === item));
    views.forEach((view) => view.classList.toggle('active', view.id === `${target}-view`));
    title.textContent = labels[target] || 'ThreadAware';
  });
});

const api = {
  async get(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },
  async post(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(detail.detail || 'Request failed');
    }
    return response.json();
  },
};

function setSystemStatus(health) {
  const card = document.querySelector('.sidebar-card');
  if (!card) return;
  const strong = card.querySelector('strong');
  const small = card.querySelector('small');
  strong.textContent = health.mode === 'live' ? 'Live' : 'Demo ready';
  small.textContent = health.mode === 'live' ? 'OpenAI connected' : 'System status';
}

function setStateGroup(label, values, asTags = false) {
  const groups = [...document.querySelectorAll('.continuity-panel .state-group')];
  const group = groups.find((node) => node.querySelector('label')?.textContent.trim() === label);
  if (!group) return;

  [...group.children].forEach((child) => {
    if (child.tagName !== 'LABEL') child.remove();
  });

  if (!values?.length) {
    const empty = document.createElement('div');
    empty.className = 'state-item muted';
    empty.textContent = 'None currently';
    group.appendChild(empty);
    return;
  }

  if (asTags) {
    const row = document.createElement('div');
    row.className = 'tag-row';
    values.forEach((value) => {
      const tag = document.createElement('span');
      tag.textContent = value;
      row.appendChild(tag);
    });
    group.appendChild(row);
    return;
  }

  values.forEach((value) => {
    const item = document.createElement('div');
    item.className = 'state-item';
    item.textContent = value;
    group.appendChild(item);
  });
}

function setMetric(label, value) {
  const cards = [...document.querySelectorAll('.metric-card')];
  const card = cards.find((node) => node.querySelector('small')?.textContent.trim() === label);
  if (card) card.querySelector('strong').textContent = value;
}

function setSplitMetric(label, value) {
  const rows = [...document.querySelectorAll('.split-metric > div')];
  const row = rows.find((node) => node.querySelector('span')?.textContent.trim() === label);
  if (row) row.querySelector('strong').textContent = value;
}

function percent(value, digits = 0) {
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

async function hydrate() {
  try {
    const [health, state, evaluation, validation] = await Promise.all([
      api.get('/api/health'),
      api.get('/api/state'),
      api.get('/api/evaluations/latest'),
      api.get('/api/validation'),
    ]);

    setSystemStatus(health);
    setStateGroup('Active goals', state.active_goals);
    setStateGroup('Constraints', state.constraints);
    setStateGroup('Preferences', state.preferences, true);
    setStateGroup('Open questions', state.unresolved_questions);

    setMetric('Helpfulness', percent(evaluation.helpfulness));
    setMetric('Appropriateness', percent(evaluation.appropriateness));
    setMetric('Context adaptation', percent(evaluation.context_adaptation));
    setMetric('Continuity', percent(evaluation.continuity));
    setSplitMetric('Harmful compliance', percent(evaluation.harmful_compliance_rate, 1));
    setSplitMetric('Overrefusal', percent(evaluation.overrefusal_rate, 1));

    setMetric('Grader ↔ expert agreement', percent(validation.grader_expert_agreement));
    setMetric('Expert-reviewed scenarios', String(validation.expert_reviewed_scenarios));
    setMetric('Repeated-run consistency', percent(validation.repeated_run_consistency));

    const adaptationStrong = document.querySelector('.continuity-panel .metric-row strong');
    const adaptationBar = document.querySelector('.continuity-panel .progress span');
    if (adaptationStrong) adaptationStrong.textContent = percent(evaluation.context_adaptation);
    if (adaptationBar) adaptationBar.style.width = percent(evaluation.context_adaptation);
  } catch (error) {
    console.error('ThreadAware hydration failed:', error);
    const card = document.querySelector('.sidebar-card strong');
    if (card) card.textContent = 'API offline';
  }
}

async function sendChat() {
  const input = document.querySelector('.composer input');
  const button = document.querySelector('.composer button');
  const messagesContainer = document.querySelector('.messages');
  const text = input?.value.trim();
  if (!text || !button || !messagesContainer) return;

  const userBubble = document.createElement('div');
  userBubble.className = 'message user';
  userBubble.textContent = text;
  messagesContainer.appendChild(userBubble);
  input.value = '';
  button.disabled = true;
  button.textContent = 'Thinking…';

  const history = [...messagesContainer.querySelectorAll('.message')].map((node) => ({
    role: node.classList.contains('user') ? 'user' : 'assistant',
    content: node.textContent,
  }));

  try {
    const result = await api.post('/api/chat', { messages: history });
    const assistantBubble = document.createElement('div');
    assistantBubble.className = 'message assistant emphasized';
    assistantBubble.textContent = result.reply;
    messagesContainer.appendChild(assistantBubble);
  } catch (error) {
    const assistantBubble = document.createElement('div');
    assistantBubble.className = 'message assistant';
    assistantBubble.textContent = `Live model is not configured yet. ${error.message}`;
    messagesContainer.appendChild(assistantBubble);
  } finally {
    button.disabled = false;
    button.textContent = 'Send';
  }
}

const sendButton = document.querySelector('.composer button');
const composerInput = document.querySelector('.composer input');
if (sendButton) sendButton.addEventListener('click', sendChat);
if (composerInput) {
  composerInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') sendChat();
  });
}

hydrate();
