const navItems = [...document.querySelectorAll('.nav-item')];
const views = [...document.querySelectorAll('.view')];
const title = document.getElementById('view-title');

const labels = { chat:'Conversation', continuity:'Continuity', scenarios:'Scenarios', evaluations:'Evaluations', validation:'Validation', insights:'Insights' };

navItems.forEach((item)=>item.addEventListener('click',()=>{
  const target=item.dataset.view;
  navItems.forEach((nav)=>nav.classList.toggle('active',nav===item));
  views.forEach((view)=>view.classList.toggle('active',view.id===`${target}-view`));
  title.textContent=labels[target]||'ThreadAware';
}));

const api={
  async get(path){const r=await fetch(path);if(!r.ok)throw new Error(await r.text());return r.json();},
  async post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok){const d=await r.json().catch(()=>({detail:'Request failed'}));throw new Error(d.detail||'Request failed');}return r.json();}
};

function percent(v,d=0){return `${(Number(v)*100).toFixed(d)}%`;}
function setSystemStatus(h){const c=document.querySelector('.sidebar-card');if(!c)return;c.querySelector('strong').textContent=h.mode==='live'?'Live':'Demo ready';c.querySelector('small').textContent=h.mode==='live'?'OpenAI connected':'System status';}
function setStateGroup(label,values,asTags=false){const groups=[...document.querySelectorAll('.continuity-panel .state-group')];const g=groups.find((n)=>n.querySelector('label')?.textContent.trim()===label);if(!g)return;[...g.children].forEach((c)=>{if(c.tagName!=='LABEL')c.remove();});if(!values?.length){const e=document.createElement('div');e.className='state-item muted';e.textContent='None currently';g.appendChild(e);return;}if(asTags){const row=document.createElement('div');row.className='tag-row';values.forEach((v)=>{const s=document.createElement('span');s.textContent=v;row.appendChild(s);});g.appendChild(row);return;}values.forEach((v)=>{const x=document.createElement('div');x.className='state-item';x.textContent=v;g.appendChild(x);});}
function setMetric(label,value){const cards=[...document.querySelectorAll('.metric-card')];const c=cards.find((n)=>n.querySelector('small')?.textContent.trim()===label);if(c)c.querySelector('strong').textContent=value;}
function setSplitMetric(label,value){const rows=[...document.querySelectorAll('.split-metric > div')];const r=rows.find((n)=>n.querySelector('span')?.textContent.trim()===label);if(r)r.querySelector('strong').textContent=value;}
function applyEvaluation(e,state){setMetric('Helpfulness',percent(e.helpfulness));setMetric('Appropriateness',percent(e.appropriateness));setMetric('Context adaptation',percent(e.context_adaptation));setMetric('Continuity',percent(e.continuity));setSplitMetric('Harmful compliance',e.harmful_compliance?'100%':'0%');setSplitMetric('Overrefusal',e.overrefusal?'100%':'0%');if(state){setStateGroup('Active goals',state.active_goals);setStateGroup('Constraints',state.constraints);setStateGroup('Preferences',state.preferences,true);setStateGroup('Open questions',state.unresolved_questions);}const s=document.querySelector('.continuity-panel .metric-row strong');const b=document.querySelector('.continuity-panel .progress span');if(s)s.textContent=percent(e.context_adaptation);if(b)b.style.width=percent(e.context_adaptation);}

async function hydrate(){try{const [h,s,e,v]=await Promise.all([api.get('/api/health'),api.get('/api/state'),api.get('/api/evaluations/latest'),api.get('/api/validation')]);setSystemStatus(h);setStateGroup('Active goals',s.active_goals);setStateGroup('Constraints',s.constraints);setStateGroup('Preferences',s.preferences,true);setStateGroup('Open questions',s.unresolved_questions);applyEvaluation(e,s);setMetric('Grader ↔ expert agreement',percent(v.grader_expert_agreement));setMetric('Expert-reviewed scenarios',String(v.expert_reviewed_scenarios));setMetric('Repeated-run consistency',percent(v.repeated_run_consistency));}catch(err){console.error(err);const c=document.querySelector('.sidebar-card strong');if(c)c.textContent='API offline';}}

async function sendChat(){const input=document.querySelector('.composer input');const button=document.querySelector('.composer button');const box=document.querySelector('.messages');const text=input?.value.trim();if(!text||!button||!box)return;const ub=document.createElement('div');ub.className='message user';ub.textContent=text;box.appendChild(ub);input.value='';button.disabled=true;button.textContent='Thinking…';const history=[...box.querySelectorAll('.message')].map((n)=>({role:n.classList.contains('user')?'user':'assistant',content:n.textContent}));try{const r=await api.post('/api/chat',{messages:history});const ab=document.createElement('div');ab.className='message assistant emphasized';ab.textContent=r.reply;box.appendChild(ab);}catch(err){const ab=document.createElement('div');ab.className='message assistant';ab.textContent=`Live model is not configured yet. ${err.message}`;box.appendChild(ab);}finally{button.disabled=false;button.textContent='Send';}}

async function runEvaluation(){const button=[...document.querySelectorAll('.primary-button')].find((b)=>b.textContent.trim()==='New evaluation');if(!button)return;button.disabled=true;button.textContent='Running…';try{const health=await api.get('/api/health');const scenarios=await api.get('/api/scenarios');const scenario=scenarios[0];const result=await api.post('/api/evaluations/run',{scenario_id:scenario.id,live:health.mode==='live',max_turns:10});applyEvaluation(result.evaluation,result.continuity);const box=document.querySelector('.messages');if(box&&result.transcript){box.innerHTML='';result.transcript.forEach((turn)=>{const div=document.createElement('div');div.className=`message ${turn.role==='user'?'user':'assistant'}`;div.textContent=turn.content;box.appendChild(div);});}document.querySelector('[data-view="evaluations"]')?.click();}catch(err){alert(`Evaluation failed: ${err.message}`);}finally{button.disabled=false;button.textContent='New evaluation';}}

const sendButton=document.querySelector('.composer button');const composerInput=document.querySelector('.composer input');if(sendButton)sendButton.addEventListener('click',sendChat);if(composerInput)composerInput.addEventListener('keydown',(e)=>{if(e.key==='Enter')sendChat();});const runButton=[...document.querySelectorAll('.primary-button')].find((b)=>b.textContent.trim()==='New evaluation');if(runButton)runButton.addEventListener('click',runEvaluation);

hydrate();
