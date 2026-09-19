(() => {
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };

  async function refreshConfigurationStatus() {
    try {
      const response = await fetch('/api/health');
      if (!response.ok) throw new Error('Health check unavailable');
      const health = await response.json();
      const models = health.models || {};
      const live = health.chat_mode === 'live';

      setText('target-model', models.target || 'Awaiting configuration');
      setText('auditor-model', models.auditor || 'Awaiting configuration');
      setText('judge-model', models.judge || 'Awaiting configuration');
      setText('understanding-model', models.understanding || 'Awaiting configuration');
      setText('api-key-status', live ? 'Securely configured · live access ready' : 'Awaiting secure local API key');

      const dot = document.querySelector('.connection-dot');
      if (dot) dot.classList.toggle('connected', live);
    } catch (_) {
      setText('api-key-status', 'Configuration status unavailable');
    }
  }

  function professionalizePlaceholders() {
    document.querySelectorAll('.evaluation-mini-grid b').forEach((el) => {
      if (el.textContent.trim() === 'Not run') el.textContent = 'Awaiting evaluation';
    });
    document.querySelectorAll('.score-card > strong').forEach((el) => {
      if (el.textContent.trim() === 'Not run') el.textContent = 'Awaiting evaluation';
    });
    if (document.getElementById('expert-count')?.textContent.trim() === 'Demo') {
      setText('expert-count', 'Workflow ready');
    }
    if (document.getElementById('grader-agreement')?.textContent.trim() === 'Demo') {
      setText('grader-agreement', 'Awaiting evidence');
    }
    if (document.getElementById('validation-status')?.textContent.trim() === 'Awaiting evidence') {
      setText('validation-status', 'Awaiting expert evidence');
    }
  }

  window.addEventListener('load', () => {
    refreshConfigurationStatus();
    setTimeout(professionalizePlaceholders, 250);
  });
})();
