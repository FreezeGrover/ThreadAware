const navItems=[...document.querySelectorAll('.nav-item')];
const views=[...document.querySelectorAll('.view')];
const toast=document.getElementById('toast');
let activeScenarioId=null;

const api={
  async get(path){const r=await fetch(path);if(!r.ok)throw new Error(await r.text());return r.json();},
  async post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok){const d=await r.json().catch(()=>({detail:'Request failed'}));throw new Error(d.detail||'Request failed');}return r.json();}
};

function showToast(message){if(!toast)return;toast.textContent=message;toast.classList.add('show');clearTimeout(showToast.timer);showToast.timer=setTimeout(()=>toast.classList.remove('show'),2600);}
function clamp01(v){return Math.max(0,Math.min(1,Number(v)||0));}
function score100(v){return Math.round(clamp01(v)*100);}
function timeNow(){return new Intl.DateTimeFormat([],{hour:'numeric',minute:'2-digit'}).format(new Date());}
function escapeHTML(value){return String(value??'').replace(/[&<>'"]/g,(ch)=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));}

navItems.forEach(item=>item.addEventListener('click',()=>switchView(item.dataset.view)));
document.querySelectorAll('[data-jump]').forEach(btn=>btn.addEventListener('click',()=>switchView(btn.dataset.jump)));
function switchView(name){navItems.forEach(n=>n.classList.toggle('active',n.dataset.view===name));views.forEach(v=>v.classList.toggle('active',v.id===`${name}-view`));window.scrollTo({top:0,behavior:'smooth'});}

function renderState(state){if(!state)return;
  const goal=(state.active_goals||[])[0]||'No active goal yet';
  const prefs=(state.preferences||[]).join(' · ')||'No explicit preferences yet';
  const questions=(state.unresolved_questions||[]).join(' · ')||'None at the moment';
  const rail=document.querySelector('.continuity-rail .mini-timeline');
  if(rail){rail.innerHTML=`
    <div class="mini-state mint-dot"><small>Current Topic</small><strong>${escapeHTML(state.active_topic||'Current conversation')}</strong></div>
    <div class="mini-state mint-dot"><small>User Goal</small><strong>${escapeHTML(goal)}</strong></div>
    <div class="mini-state purple-dot"><small>Key Preferences</small><strong>${escapeHTML(prefs)}</strong></div>
    <div class="mini-state mint-dot"><small>Decisions Made</small><strong>${escapeHTML((state.decisions||[]).join(' · ')||'None recorded yet')}</strong></div>
    <div class="mini-state orange-dot"><small>Open Questions</small><strong>${escapeHTML(questions)}</strong></div>`;}

  const table=document.getElementById('context-table');
  if(table){const rows=[
    ['blue','◎','Active goals',(state.active_goals||[]).join(' · ')||'None'],
    ['mint','⬡','Constraints',(state.constraints||[]).join(' · ')||'None'],
    ['purple','♧','Preferences',(state.preferences||[]).join(' · ')||'None'],
    ['blue','□','Decisions',(state.decisions||[]).join(' · ')||'None'],
    ['orange','◆','Unresolved questions',questions],
    ['mint','⊙','Sensitivity',state.sensitivity||'low']
  ];table.innerHTML=rows.map(([c,i,l,v])=>`<div><span class="state-icon ${c}">${i}</span><b>${escapeHTML(l)}</b><span>${escapeHTML(v)}</span></div>`).join('');}
}

function renderEvaluation(e){if(!e)return;
  const helpful=score100(e.helpfulness),appropriate=score100(e.appropriateness),balanced=score100(e.balanced_behavior),continuity=score100(e.continuity);
  const set=(id,val)=>{const el=document.getElementById(id);if(el)el.textContent=val;};
  set('helpfulness-score',`${helpful}/100`);set('appropriateness-score',`${appropriate}/100`);set('balanced-score',`${balanced}/100`);set('continuity-score',`${continuity}/100`);
  set('harmful-rate',e.harmful_compliance?'100%':'0%');set('overrefusal-rate',e.overrefusal?'100%':'0%');
  document.querySelector('.behavior-panel .mint-bar')?.style.setProperty('width',e.harmful_compliance?'100%':'0%');
  document.querySelector('.behavior-panel .blue-bar')?.style.setProperty('width',e.overrefusal?'100%':'0%');
  const severity=document.getElementById('severity-level');if(severity)severity.textContent=e.severity_awareness>=.8?'Aware':'Review';
}

function appendMessage(role,content){const feed=document.getElementById('conversation-feed');if(!feed)return;const row=document.createElement('article');row.className=`chat-row ${role==='user'?'user-row':'assistant-row'}`;
  const avatar=role==='user'?'<div class="message-avatar">S</div>':'<div class="assistant-avatar"><span></span><span></span></div>';
  row.innerHTML=`${avatar}<div class="message-card ${role==='assistant'?'assistant-card':''}"><div class="message-meta"><b>${role==='user'?'You':'ThreadAware'}</b><span>${timeNow()}</span></div><p>${escapeHTML(content).replace(/\n/g,'<br>')}</p></div>`;feed.appendChild(row);row.scrollIntoView({behavior:'smooth',block:'end'});}

function collectMessages(){return [...document.querySelectorAll('#conversation-feed .chat-row')].map(row=>({role:row.classList.contains('user-row')?'user':'assistant',content:row.querySelector('.message-card p')?.innerText||''})).filter(m=>m.content);}

async function sendChat(){const input=document.getElementById('chat-input');const button=document.getElementById('send-button');const text=input?.value.trim();if(!text||!button)return;appendMessage('user',text);input.value='';button.disabled=true;button.textContent='…';try{const result=await api.post('/api/chat',{messages:collectMessages()});appendMessage('assistant',result.reply);if(result.understanding)applyUnderstanding(result.understanding);if(result.clarification_needed)showToast('ThreadAware detected a material ambiguity and asked for clarification.');}catch(err){appendMessage('assistant',`Live mode is not ready yet. ${err.message}`);}finally{button.disabled=false;button.textContent='➤';}}

document.getElementById('send-button')?.addEventListener('click',sendChat);document.getElementById('chat-input')?.addEventListener('keydown',e=>{if(e.key==='Enter')sendChat();});

function applyUnderstanding(u){if(!u)return;const mem=u.memory||u.memory_state||[];const shift=u.topic_shift;const interp=u.interpretation;
  const timeline=document.getElementById('continuity-timeline');if(timeline&&(shift||interp)){const blocks=[];if(interp?.plausible_interpretations?.length>1)blocks.push(`<div><span class="timeline-dot purple"></span><b>Interpretation branch <small>${timeNow()}</small></b><p>${escapeHTML(interp.plausible_interpretations.length)} plausible readings recorded; hidden chain-of-thought is not exposed.</p></div>`);if(shift?.shifted)blocks.push(`<div><span class="timeline-dot orange"></span><b>Topic shift <small>${timeNow()}</small></b><p>${escapeHTML(shift.acknowledgement||'Conversation direction changed.')}</p></div>`);if(blocks.length)timeline.insertAdjacentHTML('beforeend',blocks.join(''));}
  if(mem.length){showToast(`Conversation understanding updated ${mem.length} memory item${mem.length===1?'':'s'}.`);}
}

async function runScenario(){const button=document.getElementById('run-scenario');if(!button)return;button.disabled=true;const old=button.textContent;button.textContent='Running…';try{const health=await api.get('/api/health');const scenarios=await api.get('/api/scenarios');const scenario=scenarios.find(s=>s.id===activeScenarioId)||scenarios[0];if(!scenario)throw new Error('No scenarios are configured.');activeScenarioId=scenario.id;const result=await api.post('/api/evaluations/run',{scenario_id:scenario.id,live:health.mode==='live',max_turns:scenario.expected_turns||10});renderEvaluation(result.evaluation);renderState(result.continuity);if(result.transcript){const feed=document.getElementById('conversation-feed');if(feed){feed.innerHTML='';result.transcript.forEach(t=>appendMessage(t.role,t.content));}}showToast(`${result.mode==='live'?'Live':'Demo'} evaluation completed.`);switchView('evaluations');}catch(err){showToast(`Evaluation failed: ${err.message}`);}finally{button.disabled=false;button.textContent=old;}}
document.getElementById('run-scenario')?.addEventListener('click',runScenario);

function renderScenarios(scenarios){const list=document.getElementById('scenario-list');if(!list||!Array.isArray(scenarios)||!scenarios.length)return;const iconFor={health:['pink','♥'],wellbeing:['mint','♣'],travel:['blue','✈'],work:['purple','▣']};list.innerHTML=scenarios.map((s,i)=>{const [c,icon]=iconFor[String(s.category||'').toLowerCase()]||['cyan','◇'];const sev=String(s.severity||'low').toLowerCase();return `<article data-scenario-id="${escapeHTML(s.id)}"><span class="scenario-icon ${c}">${icon}</span><div><b>${escapeHTML(s.title||s.id)}</b><p>${escapeHTML(s.objective||s.description||'Multi-turn conversational evaluation scenario.')}</p></div><span class="tag">Multi-turn</span><span class="tag">${escapeHTML(s.category||'General')}</span><span>${escapeHTML(s.expected_turns||'—')} turns</span><span class="severity ${sev}">● ${escapeHTML(s.severity||'Low')}</span><b>›</b></article>`}).join('');list.querySelectorAll('article').forEach(a=>a.addEventListener('click',()=>{activeScenarioId=a.dataset.scenarioId;list.querySelectorAll('article').forEach(x=>x.style.outline='');a.style.outline='2px solid #8dbcf7';showToast('Scenario selected.');}));}

function renderValidation(v){if(!v)return;const real=Boolean(v.has_real_expert_evidence||v.source==='expert-reviewed');const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};if(real){set('expert-count',String(v.expert_reviewed_scenarios??'—'));set('grader-agreement',v.grader_expert_agreement!=null?`${Math.round(v.grader_expert_agreement*100)}%`:'—');set('validation-status','Validated');}else{set('expert-count','Demo');set('grader-agreement','Demo');set('validation-status','Awaiting evidence');}}

function renderInsights(i){if(!i)return;const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};set('insight-runs',String(i.total_runs??i.total_conversations??0));if(i.average_turns!=null)set('avg-turns',`${Number(i.average_turns).toFixed(1)} turns`);if(i.consistency!=null)set('consistency',`${Math.round(i.consistency*100)}%`);if(i.risk_rate!=null)set('risk-rate',`${Math.round(i.risk_rate*100)}%`);
  const strengths=document.getElementById('strength-list');if(strengths&&Array.isArray(i.strengths)&&i.strengths.length)strengths.innerHTML=i.strengths.map(x=>`<li>${escapeHTML(typeof x==='string'?x:x.text||x.finding||'')}</li>`).join('');
  const improvements=document.getElementById('improvement-list');if(improvements&&Array.isArray(i.improvements)&&i.improvements.length)improvements.innerHTML=i.improvements.map(x=>`<li>${escapeHTML(typeof x==='string'?x:x.text||x.finding||'')}</li>`).join('');}

async function hydrate(){try{const [health,state,evaluation,scenarios,validation,insights]=await Promise.all([api.get('/api/health'),api.get('/api/state'),api.get('/api/evaluations/latest'),api.get('/api/scenarios'),api.get('/api/validation'),api.get('/api/insights')]);renderState(state);renderEvaluation(evaluation);renderScenarios(scenarios);renderValidation(validation);renderInsights(insights);if(health.mode==='demo')showToast('ThreadAware is running in demo mode until the server-side API key is configured.');}catch(err){console.error(err);showToast('ThreadAware API is offline.');}}

hydrate();
