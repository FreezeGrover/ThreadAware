(() => {
  const WORKSPACE_KEY = 'threadaware.workspace.id';
  const TRANSCRIPT_PREFIX = 'threadaware.transcript.';

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

  function readJSON(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || '') || fallback; }
    catch (_) { return fallback; }
  }

  function saveTranscript(messages) {
    if (Array.isArray(messages)) localStorage.setItem(transcriptKey(), JSON.stringify(messages));
  }

  function fallbackAppend(role, content) {
    const feed = document.getElementById('conversation-feed');
    if (!feed) return;
    document.getElementById('chat-empty')?.remove();
    const row = document.createElement('article');
    row.className = `chat-row ${role === 'user' ? 'user-row' : 'assistant-row'}`;
    row.dataset.rawContent = String(content ?? '');
    const avatar = role === 'user' ? '<div class="message-avatar">U</div>' : '<div class="assistant-avatar"><span></span><span></span></div>';
    const safe = String(content ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    row.innerHTML = `${avatar}<div class="message-card ${role === 'assistant' ? 'assistant-card' : ''}"><div class="message-meta"><b>${role === 'user' ? 'You' : 'ThreadAware'}</b></div><p>${safe.replace(/\n/g,'<br>')}</p></div>`;
    feed.appendChild(row);
  }

  function restoreTranscript() {
    const messages = readJSON(transcriptKey(), []);
    if (!messages.length || document.querySelector('#conversation-feed .chat-row')) return;
    for (const message of messages) {
      if (typeof window.appendMessage === 'function') window.appendMessage(message.role, message.content);
      else fallbackAppend(message.role, message.content);
    }
  }

  function installFreshStart() {
    const rail = document.querySelector('.continuity-rail');
    const title = rail?.querySelector('.rail-title');
    if (!title || title.querySelector('.memory-clear-button')) return;

    const button = document.createElement('button');
    button.className = 'memory-clear-button';
    button.textContent = 'Fresh start';
    button.title = 'Clear this browser workspace and begin a new conversation';

    button.addEventListener('click', async () => {
      const ok = window.confirm('Start fresh? This clears the conversation and memory for this browser workspace only.');
      if (!ok) return;
      const oldId = workspaceId;
      try {
        await fetch('/api/memory/clear', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({workspace_id: oldId})
        });
      } catch (_) {}
      localStorage.removeItem(`${TRANSCRIPT_PREFIX}${oldId}`);
      workspaceId = newId();
      localStorage.setItem(WORKSPACE_KEY, workspaceId);
      window.location.reload();
    });

    title.appendChild(button);
  }

  /* Persist chat only. Noticing is rendered exclusively by app.js so there is no
     competing renderer, duplicate event stream, timestamp layer, or fetch race. */
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    const method = String(init?.method || 'GET').toUpperCase();
    let requestInit = init;
    let outgoingMessages = null;

    if (url.includes('/api/chat') && method === 'POST' && init?.body) {
      try {
        const body = JSON.parse(init.body);
        body.workspace_id = workspaceId;
        outgoingMessages = Array.isArray(body.messages) ? body.messages : null;
        requestInit = {...init, body: JSON.stringify(body)};
      } catch (_) {}
    }

    const response = await nativeFetch(input, requestInit);

    if (url.includes('/api/chat') && method === 'POST' && outgoingMessages) {
      try {
        const data = await response.clone().json();
        if (data?.reply) saveTranscript([...outgoingMessages, {role:'assistant', content:data.reply}]);
      } catch (_) {}
    }
    return response;
  };

  setTimeout(() => {
    installFreshStart();
    restoreTranscript();
  }, 0);
})();
