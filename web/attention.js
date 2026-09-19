(() => {
  const escape = (value) => String(value ?? '').replace(/[&<>\"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[ch]));

  const inline = (value) => escape(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>');

  function richText(value) {
    const lines = String(value ?? '').replace(/\r/g, '').split('\n');
    const out = [];
    let list = null;
    let paragraph = [];

    const flushParagraph = () => {
      if (!paragraph.length) return;
      out.push(`<p>${inline(paragraph.join(' '))}</p>`);
      paragraph = [];
    };
    const closeList = () => {
      if (!list) return;
      out.push(`</${list}>`);
      list = null;
    };

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) {
        flushParagraph();
        closeList();
        continue;
      }
      const heading = line.match(/^#{1,3}\s+(.+)$/);
      const bullet = line.match(/^[-*•]\s+(.+)$/);
      const ordered = line.match(/^\d+[.)]\s+(.+)$/);
      const quote = line.match(/^>\s?(.+)$/);

      if (heading) {
        flushParagraph(); closeList();
        out.push(`<h3>${inline(heading[1])}</h3>`);
      } else if (bullet) {
        flushParagraph();
        if (list !== 'ul') { closeList(); list = 'ul'; out.push('<ul>'); }
        out.push(`<li>${inline(bullet[1])}</li>`);
      } else if (ordered) {
        flushParagraph();
        if (list !== 'ol') { closeList(); list = 'ol'; out.push('<ol>'); }
        out.push(`<li>${inline(ordered[1])}</li>`);
      } else if (quote) {
        flushParagraph(); closeList();
        out.push(`<blockquote>${inline(quote[1])}</blockquote>`);
      } else {
        closeList();
        paragraph.push(line);
      }
    }
    flushParagraph(); closeList();
    return out.join('');
  }

  const heading = document.querySelector('.chat-heading h1');
  if (heading) {
    const hour = new Date().getHours();
    heading.textContent = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  }

  const empty = document.getElementById('chat-empty');
  if (empty && !empty.querySelector('.hero-starters')) {
    empty.insertAdjacentHTML('beforeend', `
      <div class="hero-starters" aria-label="Conversation starters">
        <button class="hero-prompt" data-prompt="I want to work through something that has changed over time. Help me keep track of what matters as we talk."><b>Follow an evolving situation</b><span>See how ThreadAware carries goals, changes, and constraints forward.</span></button>
        <button class="hero-prompt" data-prompt="There may be more than one reasonable way to interpret what I mean. If it matters, ask me before assuming."><b>Test clarification</b><span>Explore how the system handles uncertainty without jumping to conclusions.</span></button>
        <button class="hero-prompt" data-prompt="I want to return to something we discussed earlier and update it with new information."><b>Return to an earlier topic</b><span>Watch memory update when later details change what came before.</span></button>
      </div>`);
  }

  document.querySelectorAll('.hero-prompt').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById('chat-input');
      const send = document.getElementById('send-button');
      if (!input || !send) return;
      input.value = button.dataset.prompt || '';
      input.focus();
      send.click();
    });
  });

  window.appendMessage = function(role, content) {
    const feed = document.getElementById('conversation-feed');
    if (!feed) return;
    document.getElementById('chat-empty')?.remove();
    const row = document.createElement('article');
    row.className = `chat-row ${role === 'user' ? 'user-row' : 'assistant-row'}`;
    const avatar = role === 'user'
      ? '<div class="message-avatar">U</div>'
      : '<div class="assistant-avatar"><span></span><span></span></div>';
    const body = role === 'assistant'
      ? `<div class="rich-message">${richText(content)}</div>`
      : `<div class="rich-message"><p>${inline(content).replace(/\n/g, '<br>')}</p></div>`;
    const now = new Intl.DateTimeFormat([], {hour:'numeric', minute:'2-digit'}).format(new Date());
    row.dataset.rawContent = String(content ?? '');
    row.innerHTML = `${avatar}<div class="message-card ${role === 'assistant' ? 'assistant-card' : ''}"><div class="message-meta"><b>${role === 'user' ? 'You' : 'ThreadAware'}</b><span>${now}</span></div>${body}</div>`;
    feed.appendChild(row);
    feed.scrollTo({top: feed.scrollHeight, behavior:'smooth'});
  };

  window.collectMessages = function() {
    return [...document.querySelectorAll('#conversation-feed .chat-row')]
      .map((row) => ({
        role: row.classList.contains('user-row') ? 'user' : 'assistant',
        content: row.dataset.rawContent || row.querySelector('.rich-message')?.innerText || ''
      }))
      .filter((message) => message.content);
  };
})();
