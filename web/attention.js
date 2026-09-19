(() => {
  const heading = document.querySelector('.chat-heading h1');
  if (heading) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    heading.textContent = greeting;
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
})();
