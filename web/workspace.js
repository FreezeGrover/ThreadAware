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

  function resetVisibleConversationState() {
    const feed = document.getElementById('conversation-feed');
    if (feed) {
      feed.innerHTML = '<div id="chat-empty" class="chat-empty"><b>Start a conversation</b><span>ThreadAware will follow what changes, what stays important, and what may need clarification.</span></div>';
    }

    const awareness = document.querySelector('.continuity-rail .mini-timeline');
    if (awareness) {
      awareness.dataset.awarenessReady = '1';
      awareness.innerHTML = '<div class="awareness-empty"><b>I’ll keep the thread with you.</b><span>As the conversation moves, I’ll quietly notice what changes and what stays important.</span></div>';
    }

    const timeline = document.getElementById('continuity-timeline');
    if (timeline) {
      timeline.innerHTML = '<div class="empty-state"><b>No conversation yet</b><p>Conversation changes and returning threads will appear here as you chat.</p></div>';
    }

    const set = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    };
    set('live-current-intent', 'Waiting for the conversation');
    set('live-priority-thread', 'Nothing urgent is being carried forward');
    set('live-open-question', 'None right now');
    set('live-sensitivity', 'No elevated signal yet');
    set('summary-topic', 'Waiting for conversation');
    set('summary-goal', 'No active goal yet');
    set('summary-preferences', 'None recorded yet');
    set('summary-status', 'Ready');

    const input = document.getElementById('chat-input');
    if (input) input.value = '';
    document.getElementById('threadaware-thinking')?.remove();
  }

  function clearCurrentBrowserConversation(oldId) {
    localStorage.removeItem(`${TRANSCRIPT_PREFIX}${oldId}`);
    sessionStorage.removeItem(`${TRANSCRIPT_PREFIX}${oldId}`);
  }

  function showResetError(message) {
    const toast = document.getElementById('toast');
    if (toast) {
      toast.textContent = message;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 3500);
      return;
    }
    window.alert(message);
  }

  function installFreshStart() {
    const rail = document.querySelector('.continuity-rail');
    const title = rail?.querySelector('.rail-title');
    if (!title || title.querySelector('.memory-clear-button')) return;

    const button = document.createElement('button');
    button.className = 'memory-clear-button';
    button.textContent = 'Fresh start';
    button.title = 'Completely clear this conversation and begin with no carried-over memory';

    button.addEventListener('click', async () => {
      const ok = window.confirm('Start fresh? This permanently clears this conversation, its saved transcript, and its ThreadAware memory for this browser workspace.');
      if (!ok) return;

      const oldId = workspaceId;
      button.disabled = true;
      const oldText = button.textContent;
      button.textContent = 'Clearing…';

      try {
        const response = await fetch('/api/memory/clear', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({workspace_id: oldId})
        });
        if (!response.ok) throw new Error('The server could not confirm that conversation memory was cleared.');

        clearCurrentBrowserConversation(oldId);
        resetVisibleConversationState();

        // Rotate only after the old workspace has been confirmed cleared. Normal page
        // refreshes keep the same ID, so memory remains persistent until Fresh start.
        workspaceId = newId();
        localStorage.setItem(WORKSPACE_KEY, workspaceId);
        window.location.reload();
      } catch (error) {
        button.disabled = false;
        button.textContent = oldText;
        showResetError(`Fresh start was not completed: ${error.message}`);
      }
    });

    title.appendChild(button);
  }

  /* Persist chat across ordinary refreshes. Fresh start is the explicit hard-reset
     boundary. Noticing is rendered exclusively by app.js so there is no competing
     renderer, duplicate event stream, timestamp layer, or fetch race. */
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
