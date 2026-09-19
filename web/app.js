const navItems=[...document.querySelectorAll('.nav-item')];
const views=[...document.querySelectorAll('.view')];
const toast=document.getElementById('toast');
let activeScenarioId=null;

const WORKSPACE_KEY='threadaware.workspace.id';
function makeWorkspaceId(){return window.crypto?.randomUUID?window.crypto.randomUUID():`ws-${Date.now()}-${Math.random().toString(36).slice(2)}`;}
function currentWorkspaceId(){let id=localStorage.getItem(WORKSPACE_KEY);if(!id){id=makeWorkspaceId();localStorage.setItem(WORKSPACE_KEY,id);}return id;}

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

function prepareAwarenessRail(){
  const rail=document.querySelector('.continuity-rail');if(!rail)return;
  const title=rail.querySelector('.rail-title b');if(title)title.textContent="What I’m noticing";
  const sync=rail.querySelector('.sync');if(sync)sync.style.display='none';
  const list=rail.querySelector('.mini-timeline');
  if(list&&!list.dataset.awarenessReady){list.dataset.awarenessReady='1';list.innerHTML='<div class="awareness-empty"><b>I’ll keep the thread with you.</b><span>As the conversation moves, I’ll quietly notice what changes and what stays important.</span></div>';}
}

function noticeTone(kind,importance){if(importance==='high'||kind==='sensitivity')return'orange';if(['return','possible-interpretations','open-question'].includes(kind))return'purple';if(['priority-change','goal-change','constraint'].includes(kind))return'blue';return'mint';}
function addAwarenessNote(title,text,tone='mint'){
  prepareAwarenessRail();
  const list=document.querySelector('.continuity-rail .mini-timeline');if(!list||!text)return;
  list.querySelector('.awareness-empty')?.remove();
  const item=document.createElement('div');item.className=`awareness-note ${tone}`;
  item.innerHTML=`<span class="awareness-dot"></span><div><small>${escapeHTML(title||'')}</small><strong>${escapeHTML(text)}</strong></div>`;
  list.appendChild(item);
  list.scrollTop=list.scrollHeight;
}

function renderState(state){if(!state)return;
  const hasContext=['active_goals','constraints','preferences','decisions','unresolved_questions','updates'].some(key=>(state[key]||[]).length);
  const goal=(state.active_goals||[])[0]||'No active goal yet';
  const questions=(state.unresolved_questions||[]).join(' · ')||'None yet';
  const table=document.getElementById('context-table');
  if(table){const rows=[
    ['blue','◎','Active goals',(state.active_goals||[]).join(' · ')||'None'],
    ['mint','⬡','Constraints',(state.constraints||[]).join(' · ')||'None'],
    ['purple','♧','Preferences',(state.preferences||[]).join(' · ')||'None'],
    ['blue','□','Decisions',(state.decisions||[]).join(' · ')||'None'],
    ['orange','◆','Unresolved questions',questions],
    ['mint','⊙','Sensitivity',hasContext?(state.sensitivity||'low'):'Not assessed']
  ];table.innerHTML=rows.map(([c,i,l,v])=>`<div><span class="state-icon ${c}">${i}</span><b>${escapeHTML(l)}</b><span>${escapeHTML(v)}</span></div>`).join('');}
  const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
  set('summary-topic',state.active_topic||'Waiting for conversation');
  set('summary-goal',goal);
  set('summary-preferences',[(state.preferences||[]).join(' · '),(state.constraints||[]).join(' · ')].filter(Boolean).join(' · ')||'None recorded yet');
  set('summary-status',hasContext?'● Tracking':'Ready');
}

function renderEvaluation(e){if(!e||e.available===false)return;
  const helpful=score100(e.helpfulness),appropriate=score100(e.appropriateness),balanced=score100(e.balanced_behavior),continuity=score100(e.continuity);
  const set=(id,val)=>{const el=document.getElementById(id);if(el)el.textContent=val;};
  set('helpfulness-score',`${helpful}/100`);set('appropriateness-score',`${appropriate}/100`);set('balanced-score',`${balanced}/100`);set('continuity-score',`${continuity}/100`);
  const labels=document.querySelectorAll('.score-card>strong');const grade=(score)=>score>=90?'High':score>=75?'Good':'Review';
  [helpful,appropriate,balanced,continuity].forEach((score,index)=>{if(labels[index])labels[index].textContent=grade(score);});
  document.querySelectorAll('.evaluation-mini-grid b').forEach((el,index)=>{el.textContent=grade([helpful,appropriate,balanced,continuity][index]);});
  set('harmful-rate',e.harmful_compliance?'100%':'0%');set('overrefusal-rate',e.overrefusal?'100%':'0%');
  document.querySelector('.behavior-panel .mint-bar')?.style.setProperty('width',e.harmful_compliance?'100%':'0%');
  document.querySelector('.behavior-panel .blue-bar')?.style.setProperty('width',e.overrefusal?'100%':'0%');
  const severity=document.getElementById('severity-level');if(severity)severity.textContent=e.severity_awareness>=.8?'Aware':'Review';
}

function appendMessage(role,content){const feed=document.getElementById('conversation-feed');if(!feed)return;document.getElementById('chat-empty')?.remove();const row=document.createElement('article');row.className=`chat-row ${role==='user'?'user-row':'assistant-row'}`;row.dataset.rawContent=String(content??'');
  const avatar=role==='user'?'<div class="message-avatar">U</div>':'<div class="assistant-avatar"><span></span><span></span></div>';
  row.innerHTML=`${avatar}<div class="message-card ${role==='assistant'?'assistant-card':''}"><div class="message-meta"><b>${role==='user'?'You':'ThreadAware'}</b><span>${timeNow()}</span></div><p>${escapeHTML(content).replace(/\n/g,'<br>')}</p></div>`;feed.appendChild(row);feed.scrollTo({top:feed.scrollHeight,behavior:'smooth'});}

function showThinking(){const feed=document.getElementById('conversation-feed');if(!feed)return;removeThinking();const row=document.createElement('article');row.id='threadaware-thinking';row.className='chat-row assistant-row thinking-row';row.innerHTML='<div class="assistant-avatar"><span></span><span></span></div><div class="message-card assistant-card thinking-card"><div class="message-meta"><b>ThreadAware</b><span>thinking</span></div><div class="thinking-line"><span>Thinking</span><i></i><i></i><i></i></div></div>';feed.appendChild(row);feed.scrollTo({top:feed.scrollHeight,behavior:'smooth'});}
function removeThinking(){document.getElementById('threadaware-thinking')?.remove();}
function collectMessages(){return [...document.querySelectorAll('#conversation-feed .chat-row:not(.thinking-row)')].map(row=>({role:row.classList.contains('user-row')?'user':'assistant',content:row.dataset.rawContent||row.querySelector('.rich-message')?.innerText||row.querySelector('.message-card p')?.innerText||''})).filter(m=>m.content);}

async function sendChat(){const input=document.getElementById('chat-input');const button=document.getElementById('send-button');const text=input?.value.trim();if(!text||!button)return;appendMessage('user',text);input.value='';button.disabled=true;button.textContent='…';showThinking();try{const result=await api.post('/api/chat',{messages:collectMessages(),workspace_id:currentWorkspaceId()});removeThinking();appendMessage('assistant',result.reply);if(result.understanding)applyUnderstanding(result.understanding);if(result.clarification_needed)showToast('ThreadAware found more than one possible reading and asked before assuming.');}catch(err){removeThinking();appendMessage('assistant',`I hit a connection problem just now: ${err.message}`);}finally{button.disabled=false;button.textContent='➤';}}

document.getElementById('send-button')?.addEventListener('click',sendChat);document.getElementById('chat-input')?.addEventListener('keydown',e=>{if(e.key==='Enter')sendChat();});
const actionPrompts={clarify:'Before answering, check whether there is more than one reasonable interpretation. Ask one concise clarification only if choosing between them would materially change the answer.',summarize:'Please summarize the conversation so far, including my current goal, constraints, changes, and any unresolved questions.',consistency:'Please check whether the conversation and your latest response remain consistent with what I have told you.',alternatives:'Please identify the materially plausible interpretations without inventing details.'};
document.querySelectorAll('[data-chat-action]').forEach(button=>button.addEventListener('click',()=>{const input=document.getElementById('chat-input');if(!input)return;if(!collectMessages().length){showToast('Start a conversation first.');input.focus();return;}input.value=actionPrompts[button.dataset.chatAction]||'';sendChat();}));

function conversationEvents(u){
  if(!u)return[];
  const notices=Array.isArray(u.noticing)?u.noticing.filter(e=>e&&e.note):[];
  if(notices.length)return notices;

  const shift=u.topic_shift;
  const interp=u.interpretation;
  const readings=interp?.interpretations||interp?.plausible_interpretations||[];
  const topic=u.active_topic||shift?.new_topic;
  const events=[];

  if(readings.length>1&&interp?.reason){events.push({kind:'possible-interpretations',title:'Possible interpretations',note:interp.reason,importance:'normal'});}
  if(shift?.shifted&&shift?.acknowledgement){events.push({kind:shift.relation==='returning'?'return':'topic-shift',title:shift.relation==='returning'?'Earlier thread returned':'Conversation changed',note:shift.acknowledgement,importance:'normal'});}
  if(!events.length&&topic){events.push({kind:'connection',title:'Context',note:`Active topic: ${topic}`,importance:'quiet'});}
  return events;
}

function renderConversationEvents(events){
  const timeline=document.getElementById('continuity-timeline');
  if(timeline&&events.length)timeline.querySelector('.empty-state')?.remove();

  for(const event of events){
    const tone=noticeTone(event.kind,event.importance);
    addAwarenessNote(event.title,event.note,tone);
    if(timeline){
      const dot=tone==='orange'?'orange':tone==='purple'?'purple':tone==='blue'?'blue':'mint';
      timeline.insertAdjacentHTML('beforeend',`<div><span class="timeline-dot ${dot}"></span><b>${escapeHTML(event.title||'Conversation update')} <small>${timeNow()}</small></b><p>${escapeHTML(event.note)}</p></div>`);
    }
  }
}

/* One source of truth: both the Continuity timeline and the right-side panel consume
   the exact same conversation-event objects. If one can display an event, so can the other. */
function applyUnderstanding(u){
  if(!u)return;
  prepareAwarenessRail();
  const topic=u.active_topic||u.topic_shift?.new_topic;
  if(topic){const topicEl=document.getElementById('summary-topic');if(topicEl)topicEl.textContent=topic;const status=document.getElementById('summary-status');if(status)status.textContent='● Tracking';}
  renderConversationEvents(conversationEvents(u));
}
window.applyUnderstanding=applyUnderstanding;
window.addAwarenessNote=addAwarenessNote;

async function runScenario(){const button=document.getElementById('run-scenario');if(!button)return;button.disabled=true;const old=button.textContent;button.textContent='Running…';try{const health=await api.get('/api/health');const scenarios=await api.get('/api/scenarios');const scenario=scenarios.find(s=>s.id===activeScenarioId)||scenarios[0];if(!scenario)throw new Error('No scenarios are configured.');activeScenarioId=scenario.id;const result=await api.post('/api/evaluations/run',{scenario_id:scenario.id,live:health.mode==='live',max_turns:scenario.expected_turns||10});renderEvaluation(result.evaluation);renderState(result.continuity);if(result.transcript){const feed=document.getElementById('conversation-feed');if(feed){feed.innerHTML='';result.transcript.forEach(t=>appendMessage(t.role,t.content));}}showToast(`${result.mode==='live'?'Live':'Demo'} evaluation completed.`);switchView('evaluations');}catch(err){showToast(`Evaluation failed: ${err.message}`);}finally{button.disabled=false;button.textContent=old;}}
document.getElementById('run-scenario')?.addEventListener('click',runScenario);

function renderScenarios(scenarios){const list=document.getElementById('scenario-list');if(!list||!Array.isArray(scenarios)||!scenarios.length)return;list.innerHTML=scenarios.map((s)=>{const category=String(s.category||'').toLowerCase();const [c,icon]=category.includes('health')?['pink','♥']:category.includes('wellbeing')?['mint','♣']:category.includes('safety')?['orange','♢']:['cyan','◇'];const sev=String(s.severity||'low').toLowerCase();return `<article data-scenario-id="${escapeHTML(s.id)}"><span class="scenario-icon ${c}">${icon}</span><div><b>${escapeHTML(s.title||s.id)}</b><p>${escapeHTML(s.objective||s.description||'Multi-turn conversational evaluation scenario.')}</p></div><span class="tag">Multi-turn</span><span class="tag">${escapeHTML(s.category||'General')}</span><span>${escapeHTML(s.expected_turns||'—')} turns</span><span class="severity ${sev}">● ${escapeHTML(s.severity||'Low')}</span><b>›</b></article>`}).join('');list.querySelectorAll('article').forEach(a=>a.addEventListener('click',()=>{activeScenarioId=a.dataset.scenarioId;list.querySelectorAll('article').forEach(x=>x.style.outline='');a.style.outline='2px solid #8dbcf7';showToast('Scenario selected.');}));}

function renderValidation(v){if(!v)return;const real=Boolean(v.has_real_expert_evidence||v.source==='expert-reviewed');const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};if(real){set('expert-count',String(v.expert_reviewed_scenarios??'—'));set('grader-agreement',v.grader_expert_agreement!=null?`${Math.round(v.grader_expert_agreement*100)}%`:'—');set('validation-status','Validated');}else{set('expert-count','Workflow ready');set('grader-agreement','Awaiting evidence');set('validation-status','Awaiting expert evidence');}}
function renderInsights(i){if(!i)return;const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};set('insight-runs',String(i.total_runs??i.total_conversations??0));if(i.average_turns!=null)set('avg-turns',`${Number(i.average_turns).toFixed(1)} turns`);if(i.consistency!=null)set('consistency',`${Math.round(i.consistency*100)}%`);if(i.risk_rate!=null)set('risk-rate',`${Math.round(i.risk_rate*100)}%`);const strengths=document.getElementById('strength-list');if(strengths&&Array.isArray(i.strengths)&&i.strengths.length)strengths.innerHTML=i.strengths.map(x=>`<li>${escapeHTML(typeof x==='string'?x:x.text||x.finding||'')}</li>`).join('');const improvements=document.getElementById('improvement-list');if(improvements&&Array.isArray(i.improvements)&&i.improvements.length)improvements.innerHTML=i.improvements.map(x=>`<li>${escapeHTML(typeof x==='string'?x:x.text||x.finding||'')}</li>`).join('');}

async function hydrate(){prepareAwarenessRail();try{const [health,state,evaluation,scenarios,validation,insights]=await Promise.all([api.get('/api/health'),api.get('/api/state'),api.get('/api/evaluations/latest'),api.get('/api/scenarios'),api.get('/api/validation'),api.get('/api/insights')]);renderState(state);renderEvaluation(evaluation);renderScenarios(scenarios);renderValidation(validation);renderInsights(insights);const badge=document.getElementById('mode-badge');if(badge){badge.textContent=health.chat_mode==='live'?'LIVE':'DEMO · LOCAL';badge.classList.toggle('live',health.chat_mode==='live');}}catch(err){console.error(err);const badge=document.getElementById('mode-badge');if(badge)badge.textContent='OFFLINE';showToast('ThreadAware API is offline.');}}

hydrate();