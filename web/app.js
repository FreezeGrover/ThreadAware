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
