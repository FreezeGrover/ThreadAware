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
      const tabbar = section.querySelector('.tabbar');
      tabbar?.insertAdjacentElement('afterend', box);
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
      const scenariosNav = document.querySelector('.nav-item[data-view="scenarios"]');
      scenariosNav?.click();
      setTimeout(() => scenarioSearch?.focus(), 80);
    });
  }

  document.querySelectorAll('.outline-button').forEach((button) => {
    button.addEventListener('click', () => {
      const label = button.textContent.trim();
      const toast = document.getElementById('toast');
      if (!toast) return;
      toast.textContent = label.includes('Report') ? 'A validation report becomes available when evidence has been collected.' : 'Export becomes available when stored evidence exists.';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2600);
    });
  });

  /* ThreadAware awareness stream: keep the entire visible history for this conversation. */
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const toneFor = (kind, importance) => {
    if (importance === 'high' || kind === 'sensitivity') return 'orange';
    if (['return','possible-interpretations','open-question'].includes(kind)) return 'purple';
    if (['priority-change','goal-change','constraint'].includes(kind)) return 'blue';
    return 'mint';
  };

  window.addAwarenessNote = function(title, text, tone='mint', meta='') {
    window.prepareAwarenessRail?.();
    const list = document.querySelector('.continuity-rail .mini-timeline');
    if (!list) return;
    list.querySelector('.awareness-empty')?.remove();
    const item = document.createElement('div');
    item.className = `awareness-note ${tone}`;
    const stamp = new Intl.DateTimeFormat([], {hour:'numeric', minute:'2-digit'}).format(new Date());
    item.innerHTML = `<span class="awareness-dot"></span><div><small>${esc(title)}</small><strong>${esc(text)}</strong><em>${esc(meta || stamp)}</em></div>`;
    list.appendChild(item);
    item.scrollIntoView({behavior:'smooth',block:'nearest'});
  };

  window.applyUnderstanding = function(u) {
    if (!u) return;
    window.prepareAwarenessRail?.();
    const topic = u.active_topic || u.topic_shift?.new_topic;
    if (topic) {
      const topicEl = document.getElementById('summary-topic');
      if (topicEl) topicEl.textContent = topic;
      const status = document.getElementById('summary-status');
      if (status) status.textContent = '● Tracking';
    }

    const events = Array.isArray(u.noticing) ? u.noticing : [];
    if (events.length) {
      events.forEach(event => {
        if (!event?.title || !event?.note) return;
        window.addAwarenessNote(event.title, event.note, toneFor(event.kind, event.importance));
      });
    } else {
      const shift = u.topic_shift;
      if (shift?.shifted) {
        const from = shift.previous_topic || 'the earlier thread';
        const to = shift.new_topic || topic || 'a new direction';
        if (shift.relation === 'returning') window.addAwarenessNote('Interesting — we came back to this', `We’re returning to ${to}. I kept the earlier thread with us.`, 'purple');
        else window.addAwarenessNote('Hmm, we changed direction', `We moved from ${from} to ${to}. I’m keeping both threads in view.`, 'orange');
      }
    }

    const timeline = document.getElementById('continuity-timeline');
    if (timeline && events.length) {
      timeline.querySelector('.empty-state')?.remove();
      events.forEach(event => {
        if (!event?.title || !event?.note) return;
        timeline.insertAdjacentHTML('beforeend', `<div><span class="timeline-dot ${toneFor(event.kind,event.importance)}"></span><b>${esc(event.title)} <small>${new Intl.DateTimeFormat([], {hour:'numeric', minute:'2-digit'}).format(new Date())}</small></b><p>${esc(event.note)}</p></div>`);
      });
    }
  };
})();
