"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="client-token"]').content;
const words = {
  en:{apiDocs:"API documentation",eyebrow:"IMAGE REVIEW WORKSPACE",title:"From images to a checked reading table.",subtitle:"Import water meter images, review each reading, and export a clear CSV record.",export:"Export CSV",images:"Your images",choose:"Choose water meter images",formats:"JPEG, PNG or WEBP · up to 20 MB each",importHint:"Importing stays on this computer. Start recognition to send selected images to the API.",demo:"Try the offline demo",demoHint:"Illustrations and saved example values. No API key or recognition calls.",connection:"Recognition API",keyLabel:"Your API key",connect:"Connect and check quota",disconnected:"Not connected",connected:"Connected · key held in memory only",getKey:"Create an API key",quotaHint:"Default free accounts receive 20 recognitions per day, shared with the website. Resets daily; unused calls do not roll over. Actual quota follows your account.",table:"Reading table",pause:"Pause",run:"Start / resume recognition",demoBanner:"DEMO rows use illustrative images and saved values. They are never sent for live recognition.",image:"Image",aiReading:"AI reading",confirmed:"Confirmed reading",status:"Status",review:"Review an image",selectRow:"Select a row to compare the image and reading.",aiOriginal:"Original AI reading",reviewed:"I have checked this reading",note:"Notes",save:"Save review",csvHint:"CSV keeps the reading text. In Excel, import reading columns as Text to preserve leading zeros.",footer:"Local review client · Images are submitted only when you start recognition.",emptyTitle:"Build your reading table",emptyBody:"Add your images or load the offline demo, then select a row to review it.",ready:"Ready",accepted:"Reading available",unreadable:"Needs review",failed:"Failed",submission_unknown:"Check submission",submitting:"Submitting",queued:"Queued",running:"Processing",waiting_ai:"Waiting for service",count:"images",saved:"Review saved",imported:"Images imported. Select a row to review it.",demoLoaded:"Offline demo loaded. These are illustrative results, not fresh recognition.",paused:"Pause requested. Existing submitted tasks are kept for resume.",started:"Recognition started. You can pause and resume without submitting existing tasks again.",working:"Processing",needsKey:"Enter an API key first.",noRows:"Add an image first.",downloaded:"CSV downloaded. Unreadable and unreviewed rows are included.",unlimited:"Account quota is unlimited",dailyLimit:"Daily limit",used:"Used today",freeAccountHint:"Daily allowance is shared with the website and resets each day. Unused calls do not roll over.",paidHint:"Paid and cooperation quotas follow your account and are shared with the website.",daily:"Daily remaining",monthly:"Monthly remaining",fixed:"Fixed remaining"},
  "zh-cn":{apiDocs:"API 文档",eyebrow:"水表图片核对工作台",title:"从水表图片，到核对完成的读数表。",subtitle:"导入图片，逐张核对读数，将结果整理为可导出的 CSV 表格。",export:"导出 CSV",images:"导入水表图片",choose:"选择单张或多张水表图片",formats:"JPEG、PNG、WEBP · 每张不超过 20 MB",importHint:"导入时图片保存在本机。点击开始识别后，才会提交到识别 API。",demo:"体验离线演示",demoHint:"使用示意图和预设读数，无需 API Key，不产生识别调用。",connection:"识别接口",keyLabel:"你的 API Key",connect:"连接并查询额度",disconnected:"尚未连接",connected:"已连接 · 密钥仅保留在内存中",getKey:"创建 API Key",quotaHint:"免费账号默认每天20次，与官网共用额度；每天重置，未用完不累积。实际额度以账号为准。",table:"读数表",pause:"暂停",run:"开始／继续识别",demoBanner:"演示行使用示意图和预设结果，不会提交真实识别。",image:"图片",aiReading:"AI 读数",confirmed:"人工确认值",status:"状态",review:"核对图片",selectRow:"选择表格中的一行，对照原图核对读数。",aiOriginal:"AI 原始读数",reviewed:"我已核对这个读数",note:"备注",save:"保存核对",csvHint:"CSV 保留原始读数文本。在 Excel 中导入时，请将读数列设为“文本”以保留前导零。",footer:"本机核对工具 · 点击开始识别后才提交图片。",emptyTitle:"建立你的水表读数表",emptyBody:"导入自己的图片，或加载离线演示，再选择一行开始核对。",ready:"待识别",accepted:"已有读数",unreadable:"待人工复核",failed:"处理失败",submission_unknown:"需核查提交",submitting:"提交中",queued:"排队中",running:"识别中",waiting_ai:"等待识别服务",count:"张图片",saved:"核对结果已保存",imported:"图片已导入，可选择一行核对。",demoLoaded:"已加载离线演示，图像和读数为示例，不是本次真实识别。",paused:"正在暂停，已提交任务会保留，可继续查询。",started:"已开始识别，暂停后继续不会重复提交已有任务。",working:"正在处理",needsKey:"请先输入 API Key。",noRows:"请先导入图片。",downloaded:"CSV 已导出，未读出和未确认的行也已保留。",unlimited:"账号额度不限量",dailyLimit:"每日上限",used:"今日已用",freeAccountHint:"每日额度与官网共用，每天重置，未用完不累积；实际次数以上方显示为准。",paidHint:"付费及合作额度按账号实际规则执行，与官网共用。",daily:"今日剩余",monthly:"月度剩余",fixed:"固定额度剩余"}
};
let lang = navigator.language.toLowerCase().startsWith("zh") ? "zh-cn" : "en";
let state = {rows:[],active:false,key_configured:false}, selected = null, dirty = false;
const t = key => words[lang][key] || words.en[key] || key;
function notice(message,error=false){$("notice").textContent=message;$("notice").hidden=!message;$("notice").classList.toggle("error",error);}
async function api(path,body,headers={}){
  const response=await fetch(path,{method:body===undefined?"GET":"POST",headers:{"X-Client-Token":token,...(body!==undefined&&!(body instanceof File)?{"Content-Type":"application/json"}:{}),...headers},body:body===undefined?undefined:body instanceof File?body:JSON.stringify(body)});
  const value=await response.json();if(!response.ok)throw new Error(value.error||`HTTP ${response.status}`);return value;
}
function translate(){document.documentElement.lang=lang;$("language").value=lang;document.querySelectorAll("[data-t]").forEach(e=>e.textContent=t(e.dataset.t));render();}
function cell(text,css){const el=document.createElement("td");el.textContent=text;if(css)el.className=css;return el;}
function render(){
  if(state.message)notice(state.message,true);
  $("count").textContent=`${state.rows.length} ${t("count")}${state.active?" · "+t("working"):""}`;
  $("export").disabled=!state.rows.length;$("empty").hidden=!!state.rows.length;$("pause").disabled=!state.active;
  $("run").disabled=state.active||!state.key_configured||!state.rows.some(r=>!r.demo&&!["accepted","unreadable","failed","submission_unknown"].includes(r.status));
  $("connect").disabled=state.active;$("demo-banner").hidden=!state.rows.some(r=>r.demo);
  $("connection-state").textContent=t(state.key_configured?"connected":"disconnected");
  const q=state.quota;
  $("quota").textContent=!q?"":q.is_unlimited?t("unlimited"):q.account_type==="free"?`${t("dailyLimit")}: ${q.daily_limit??"—"} · ${t("used")}: ${q.used??"—"} · ${t("daily")}: ${q.remaining??"—"}`:q.quota_summary_text||`${t("monthly")}: ${q.monthly_remaining??0} · ${t("fixed")}: ${q.fixed_remaining??0}`;
  document.querySelector('[data-t="quotaHint"]').textContent=t(q?(q.account_type==="free"?"freeAccountHint":"paidHint"):"quotaHint");
  $("rows").replaceChildren();
  for(const row of state.rows){
    const tr=document.createElement("tr");tr.dataset.id=row.id;tr.className=row.id===selected?"selected":"";tr.tabIndex=0;tr.setAttribute("aria-label",row.filename);
    const name=cell("");const strong=document.createElement("span");strong.className="row-name";strong.textContent=row.filename;name.append(strong);
    if(row.demo){const tag=document.createElement("span");tag.className="row-kind";tag.textContent="DEMO";name.append(tag);}
    tr.append(name,cell(row.ai_reading||"—","reading"),cell(row.reviewed?row.confirmed_reading:"—","reading"));
    const status=cell("");const badge=document.createElement("span");badge.className="badge "+row.status;badge.textContent=t(row.status);status.append(badge);tr.append(status);
    const choose=()=>{if(dirty&&!window.confirm(lang==="zh-cn"?"放弃尚未保存的修改？":"Discard unsaved changes?"))return;selected=row.id;dirty=false;render();};
    tr.onclick=choose;tr.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose();}};$("rows").append(tr);
  }
  const row=state.rows.find(r=>r.id===selected);$("review-empty").hidden=!!row;$("review-form").hidden=!row;
  if(row&&!dirty){$("filename").textContent=row.filename;$("preview").src="/images/"+encodeURIComponent(row.id);$("preview").alt=row.filename;$("original").value=row.ai_reading;$("confirmed").value=row.confirmed_reading||row.ai_reading;$("reviewed").checked=row.reviewed;$("note").value=row.note;$("row-error").textContent=row.error;}
}
async function refresh(){state=await api("/local/state");if(!selected&&state.rows.length)selected=state.rows[0].id;render();}
async function action(work){try{await work();}catch(error){notice(error.message,true);}}
$("language").onchange=()=>{lang=$("language").value;translate();};
$("demo").onclick=()=>action(async()=>{await api("/local/demo",{});await refresh();notice(t("demoLoaded"));});
$("files").onchange=()=>action(async()=>{const files=[...$("files").files];let count=0;for(const file of files){if(file.size>20*1024*1024)throw new Error(file.name+": 20 MB maximum");await api("/local/import",file,{"Content-Type":"application/octet-stream","X-Filename":encodeURIComponent(file.name)});count++;}$("files").value="";await refresh();notice(`${count} · ${t("imported")}`);});
$("connect").onclick=()=>action(async()=>{const key=$("key").value.trim();if(!key)throw new Error(t("needsKey"));await api("/local/configure",{key});$("key").value="";await refresh();notice(t("connected"));});
$("run").onclick=()=>action(async()=>{await api("/local/run",{});await refresh();notice(t("started"));});
$("pause").onclick=()=>action(async()=>{await api("/local/pause",{});await refresh();notice(t("paused"));});
for(const id of ["confirmed","reviewed","note"])$(id).oninput=()=>{dirty=true;};
$("save").onclick=()=>action(async()=>{await api("/local/review",{id:selected,reading:$("confirmed").value,reviewed:$("reviewed").checked,note:$("note").value});dirty=false;await refresh();notice(t("saved"));});
$("export").onclick=()=>action(async()=>{const r=await fetch("/local/export",{headers:{"X-Client-Token":token}});if(!r.ok)throw new Error(`HTTP ${r.status}`);const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="watermeter-readings.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);notice(t("downloaded"));});
window.addEventListener("beforeunload",event=>{if(dirty){event.preventDefault();event.returnValue="";}});
translate();refresh().catch(error=>notice(error.message,true));setInterval(()=>refresh().catch(()=>{}),1500);
