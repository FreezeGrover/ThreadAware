(() => {
  const explainers = {
    continuity: {
      Overview: ['◇','Continuity overview','A live summary of the current topic, user goal, constraints, preferences, decisions, unresolved questions, and sensitivity.'],
      Timeline: ['↝','Conversation timeline','See when goals, topics, constraints, clarification needs, and important updates changed across the conversation.'],
      'Context State': ['◎','Current context state','Inspect the conversation state ThreadAware is carrying forward into the next response.'],
      Decisions: ['□','Decisions','Review decisions already made so later responses do not silently contradict them.'],
      'Open Questions': ['◆','Open questions','See unresolved questions that may still matter before the conversation can move forward safely and coherently.']
    },
    evaluations: {
      Overview: ['▥','Evaluation overview','Summarizes how the model performed across helpfulness, appropriateness, balance, continuity, and severity awareness.'],
      Criteria: ['✓','Evaluation criteria','Shows the dimensions ThreadAware uses to judge long-conversation behavior rather than isolated single answers.'],
      Results: ['◎','Run results','Displays evidence from completed evaluation runs. Empty states remain clearly marked until real runs exist.'],
      'Model Comparison': ['⇄','Model comparison','Compares stored evaluation runs across target models using the same scenario and dimensions.'],
      Export: ['⇩','Export evidence','Prepares reproducible evaluation evidence and run data for analysis outside the interface.']
    },
    scenarios: {
      Library: ['⌘','Scenario library','Browse realistic multi-turn situations designed to test changing needs, wellbeing, safety, continuity, and returning topics.'],
      'Create New': ['＋','Create a scenario','Define a new evolving conversation with an objective, expected turns, category, and severity.'],
      Templates: ['▤','Scenario templates','Use reusable structures for common evaluation patterns without hard-coding one specific conversation.'],
      'My Scenarios': ['◇','Saved scenarios','Review scenarios created for this local research workspace.']
    },
    validation: {
      'Expert Review': ['♙','Expert review','Records where human subject-matter review is planned or available. Demo placeholders are never presented as real validation evidence.'],
      'Grader Agreement': ['◎','Grader agreement','Compares automated judgments with expert judgments once real reviewed samples are available.'],
      Methodology: ['▥','Methodology','Explains constructs, scoring, scenario design, evidence boundaries, and how the evaluation avoids confusing demo output with validated findings.'],
      Reproducibility: ['↻','Reproducibility','Tracks repeated runs, model configuration, stored evidence, and the information needed to reproduce results.']
    }
  };

  function ensureExplainer(view, tabName) {
    const section = document.getElementById(`${view}-view`);
    if (!section || !explainers[view]?.[tabName]) return;
    let box = section.querySelector('.tab-explainer');
    if (!box) {
      box = document.createElement('div');
      box.className = 'tab-explainer';
      section.querySelector('.tabbar')?.insertAdjacentElement('afterend', box);
    }
    const [icon,title,copy] = explainers[view][tabName];
    box.innerHTML = `<span class="tab-explainer-icon">${icon}</span><div><b>${title}</b><p>${copy}</p></div>`;
  }

  document.querySelectorAll('.view .tabbar').forEach((bar) => {
    const view = bar.closest('.view')?.id?.replace('-view','');
    const tabs = [...bar.querySelectorAll('.tab')];
    const active = tabs.find(t => t.classList.contains('active')) || tabs[0];
    if (view && active) ensureExplainer(view, active.textContent.trim());
    tabs.forEach((tab) => tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      if (view) ensureExplainer(view, tab.textContent.trim());
    }));
  });

  const filterButtons = [...document.querySelectorAll('#scenarios-view .filter-pills button')];
  const scenarioSearch = document.querySelector('#scenarios-view .search-field input');
  function filterScenarios() {
    const active = filterButtons.find(b => b.classList.contains('active'))?.textContent.trim().toLowerCase() || 'all';
    const query = scenarioSearch?.value.trim().toLowerCase() || '';
    document.querySelectorAll('#scenario-list article').forEach((card) => {
      const text = card.innerText.toLowerCase();
      const categoryMatch = active === 'all' || text.includes(active.replace('changing needs','changing').replace('returning topics','returning'));
      card.style.display = categoryMatch && (!query || text.includes(query)) ? '' : 'none';
    });
  }
  filterButtons.forEach((button) => button.addEventListener('click', () => {
    filterButtons.forEach(b => b.classList.remove('active'));
    button.classList.add('active');
    filterScenarios();
  }));
  scenarioSearch?.addEventListener('input', filterScenarios);

  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.title = 'Increase or reduce interface contrast';
    themeToggle.addEventListener('click', () => document.body.classList.toggle('focus-contrast'));
  }

  const searchButton = document.querySelector('.top-actions .icon-button[aria-label="Search"]');
  if (searchButton) {
    searchButton.title = 'Focus scenario search';
    searchButton.addEventListener('click', () => {
      document.querySelector('.nav-item[data-view="scenarios"]')?.click();
      setTimeout(() => scenarioSearch?.focus(), 80);
    });
  }

  document.querySelectorAll('.outline-button').forEach((button) => {
    button.addEventListener('click', () => {
      const toast = document.getElementById('toast');
      if (!toast) return;
      toast.textContent = button.textContent.trim().includes('Report')
        ? 'A validation report becomes available when evidence has been collected.'
        : 'Export becomes available when stored evidence exists.';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2600);
    });
  });

  /* One quiet awareness stream. app.js is the only renderer; this file only styles it. */
  const style = document.createElement('style');
  style.id = 'threadaware-noticing-polish';
  style.textContent = `
    .continuity-rail{padding:18px 18px 16px!important;overflow:hidden!important}
    .continuity-rail:after{display:none!important}
    .continuity-rail .rail-title{display:flex!important;align-items:center!important;gap:10px!important;min-height:34px!important;margin:0!important}
    .continuity-rail .rail-title b{font-size:14px!important;line-height:1.15!important;letter-spacing:-.015em!important;white-space:nowrap!important;color:#10213d!important}
    .continuity-rail .rail-title .sync{display:none!important}
    .continuity-rail .rail-icon{flex:0 0 auto!important}
    .continuity-rail .memory-clear-button{margin-left:auto!important;flex:0 0 auto!important;padding:7px 11px!important;font-size:10px!important;border-radius:999px!important}
    .continuity-rail .mini-timeline[data-awareness-ready="1"]{display:flex!important;flex-direction:column!important;gap:0!important;margin-top:12px!important;max-height:430px!important;overflow:auto!important;padding:0!important}
    .continuity-rail .awareness-empty{border:0!important;background:transparent!important;box-shadow:none!important;padding:13px 4px 8px!important;display:block!important}
    .continuity-rail .awareness-empty b{display:none!important}
    .continuity-rail .awareness-empty span{font-size:12px!important;line-height:1.6!important;color:#8290a5!important}
    .continuity-rail .awareness-note{display:grid!important;grid-template-columns:8px minmax(0,1fr)!important;gap:10px!important;padding:14px 4px!important;border:0!important;border-bottom:1px solid #edf1f5!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;animation:awarenessIn .2s ease-out!important}
    .continuity-rail .awareness-note:last-child{border-bottom:0!important}
    .continuity-rail .awareness-note .awareness-dot{width:6px!important;height:6px!important;margin-top:7px!important;box-shadow:none!important;opacity:.8!important}
    .continuity-rail .awareness-note small{display:none!important}
    .continuity-rail .awareness-note strong{font-size:13px!important;line-height:1.58!important;font-weight:560!important;letter-spacing:-.005em!important;color:#273750!important}
    .continuity-rail .awareness-note em{display:none!important}
  `;
  document.head.appendChild(style);
})();
