(() => {
  const WORKSPACE_KEY = 'threadaware.workspace.id';
  const TRANSCRIPT_PREFIX = 'threadaware.transcript.';
  const NOTICE_PREFIX = 'threadaware.notices.';

  function newId() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `ws-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  function getWorkspaceId() {
    let id = localStorage.getItem(WORKSPACE_KEY);
    if (!id) {
      id = newId();
      localStorage.setItem(WORKSPACE_KEY, id);
    }
    return id;
  }

  let workspaceId = getWorkspaceId();
  const transcriptKey = () => `${TRANSCRIPT_PREFIX}${workspaceId}`;
  const noticesKey = () => `${NOTICE_PREFIX}${workspaceId}`;

  function readJSON(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || '') || fallback; }
    catch (_) { return fallback; }
  }

  function saveTranscript(messages) {
    if (Array.isArray(messages)) localStorage.setItem(transcriptKey(), JSON.stringify(messages));
  }

  function saveNotices(events) {
    if (!Array.isArray(events) || !events.length) return;
    const existing = readJSON(noticesKey(), []);
    const seen = new Set(existing.map(x => `${x.kind || ''}|${x.title || ''}|${x.note || ''}`));
    for (const event of events) {
      const key = `${event?.kind || ''}|${event?.title || ''}|${event?.note || ''}`;
      if (event?.title && event?.note && !seen.has(key)) {
        existing.push(event);
        seen.add(key);
      }
    }
    localStorage.setItem(noticesKey(), JSON.stringify(existing));
  }

  function fallbackAppend(role, content) {
    const feed = document.getElementById('conversation-feed');
    if (!feed) return;
    document.getElementById('chat-empty')?.remove();
    const row = document.createElement('article');
    row.className = `chat-row ${role === 'user' ? 'user-row' : 'assistant-row'}`;
    row.dataset.rawContent = String(content ?? '');
    const avatar = role === 'user'
      ? '<div class="message-avatar">U</div>'
      : '<div class="assistant-avatar"><span></span><span></span></div>';
    const safe = String(content ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    row.innerHTML = `${avatar}<div class="message-card ${role === 'assistant' ? 'assistant-card' : ''}"><div class="message-meta"><b>${role === 'user' ? 'You' : 'ThreadAware'}</b></div><p>${safe.replace(/\n/g,'<br>')}</p></div>`;
    feed.appendChild(row);
  }

  function restoreWorkspace() {
    const messages = readJSON(transcriptKey(), []);
    if (messages.length && !document.querySelector('#conversation-feed .chat-row')) {
      for (const message of messages) {
        if (typeof window.appendMessage === 'function') window.appendMessage(message.role, message.content);
        else fallbackAppend(message.role, message.content);
      }
    }

    const notices = readJSON(noticesKey(), []);
    if (notices.length && typeof window.applyUnderstanding === 'function') {
      window.applyUnderstanding({noticing: notices});
    }
  }

  function installFreshStart() {
    const rail = document.querySelector('.continuity-rail');
    const title = rail?.querySelector('.rail-title');
    if (!title || title.querySelector('.memory-clear-button')) return;

    const button = document.createElement('button');
    button.className = 'memory-clear-button';
    button.textContent = 'Fresh start';
    button.title = 'Clear this browser workspace’s conversation and ThreadAware memory';
    Object.assign(button.style, {
      marginLeft: 'auto',
      border: '1px solid rgba(25,42,70,.15)',
      background: 'rgba(255,255,255,.82)',
      borderRadius: '999px',
      padding: '6px 10px',
      fontSize: '11px',
      fontWeight: '700',
      cursor: 'pointer'
    });

    button.addEventListener('click', async () => {
      const ok = window.confirm('Start fresh? This clears the conversation and ThreadAware memory for this browser workspace only.');
      if (!ok) return;
      const oldId = workspaceId;
      try {
        await fetch('/api/memory/clear', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({workspace_id: oldId})
        });
      } catch (_) {
        // Local browser state is still cleared even if the server cannot be reached.
      }
      localStorage.removeItem(`${TRANSCRIPT_PREFIX}${oldId}`);
      localStorage.removeItem(`${NOTICE_PREFIX}${oldId}`);
      workspaceId = newId();
      localStorage.setItem(WORKSPACE_KEY, workspaceId);
      window.location.reload();
    });

    title.appendChild(button);
  }

  /* Anonymous browser workspace isolation.
     No name is requested from the user. A browser-local random ID is safer and avoids
     collisions between judges. The same browser resumes its own thread; another browser
     receives a different workspace automatically. */
  const previousFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    const method = String(init?.method || 'GET').toUpperCase();
    let requestInit = init;
    let outgoingMessages = null;

    if ((url.includes('/api/chat') || url.includes('/api/understanding')) && method === 'POST' && init?.body) {
      try {
        const body = JSON.parse(init.body);
        body.workspace_id = workspaceId;
        outgoingMessages = Array.isArray(body.messages) ? body.messages : null;
        requestInit = {...init, body: JSON.stringify(body)};
      } catch (_) {}
    }

    const response = await previousFetch(input, requestInit);

    if (url.includes('/api/chat') && method === 'POST') {
      try {
        const copy = response.clone();
        const data = await copy.json();
        if (outgoingMessages && data?.reply) {
          saveTranscript([...outgoingMessages, {role: 'assistant', content: data.reply}]);
        }
        saveNotices(data?.understanding?.noticing || []);
      } catch (_) {}
    }

    return response;
  };

  setTimeout(() => {
    installFreshStart();
    restoreWorkspace();
  }, 0);
})();
