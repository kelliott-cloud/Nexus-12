import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  DollarSign, Clock, Calendar, FileText, Key, Brain, Activity,
  Palette, Store, Loader2, Download, Plus, Trash2, Play, BarChart3,
  CheckCircle2, TrendingUp, Zap, Shield, Users
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

const TABS = [
  { key: "usage", label: "Usage Billing", icon: DollarSign },
  { key: "scheduled", label: "Scheduled Jobs", icon: Calendar },
  { key: "learning", label: "Agent Learning", icon: Brain },
  { key: "feed", label: "Activity Feed", icon: Activity },
  { key: "api", label: "Developer API", icon: Key },
  { key: "branding", label: "White-Label", icon: Palette },
  { key: "agents-market", label: "Agent Market", icon: Store },
  { key: "compliance", label: "Compliance", icon: Shield },
];

export default function StrategicFeaturesPanel({ workspaceId }) {
  const [tab, setTab] = useState("usage");
  return (
    <div className="flex-1 overflow-y-auto" data-testid="strategic-panel">
      <div className="border-b border-zinc-800 px-6 pt-4">
        <h2 className="text-lg font-semibold text-zinc-100 mb-3">Platform Features</h2>
        <div className="flex gap-0.5 overflow-x-auto pb-0">
          {TABS.map(t => {
            const Icon = t.icon;
            return <button key={t.key} onClick={() => setTab(t.key)} className={`flex items-center gap-1 px-2.5 py-2 text-[10px] font-medium border-b-2 transition-colors whitespace-nowrap ${tab === t.key ? "border-cyan-500 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}><Icon className="w-3 h-3" />{t.label}</button>;
          })}
        </div>
      </div>
      <div className="p-6 max-w-6xl mx-auto">
        <FeatureHelp featureId="strategic" {...FEATURE_HELP["strategic"]} />
        {tab === "usage" && <UsageTab workspaceId={workspaceId} />}
        {tab === "scheduled" && <ScheduledTab workspaceId={workspaceId} />}
        {tab === "learning" && <LearningTab workspaceId={workspaceId} />}
        {tab === "feed" && <FeedTab workspaceId={workspaceId} />}
        {tab === "api" && <APITab />}
        {tab === "branding" && <BrandingTab />}
        {tab === "agents-market" && <AgentMarketTab workspaceId={workspaceId} />}
        {tab === "compliance" && <ComplianceTab />}
      </div>
    </div>
  );
}

function UsageTab({ workspaceId }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get(`/billing/usage/${workspaceId}`).then(r => setData(r.data)).catch(() => {}); }, [workspaceId]);
  if (!data) return <Loader2 className="w-5 h-5 animate-spin text-zinc-500 mx-auto mt-8" />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[{l:"Total Cost",v:`$${data.total_cost_usd}`,c:"text-emerald-400"},{l:"Total Tokens",v:data.total_tokens?.toLocaleString(),c:"text-cyan-400"},{l:"Models Used",v:Object.keys(data.by_model||{}).length,c:"text-zinc-200"}].map(({l,v,c})=>(
          <Card key={l} className="bg-zinc-900 border-zinc-800"><CardContent className="py-4 text-center"><div className={`text-2xl font-bold ${c}`}>{v}</div><div className="text-xs text-zinc-500 mt-1">{l}</div></CardContent></Card>
        ))}
      </div>
      {Object.entries(data.by_model||{}).map(([model,stats])=>(
        <div key={model} className="flex items-center justify-between py-2 border-b border-zinc-800/30 text-sm">
          <div className="flex items-center gap-2"><Badge variant="outline" className="text-xs border-zinc-700">{model}</Badge><span className="text-zinc-400">{stats.calls} calls</span></div>
          <div className="flex gap-4 text-xs"><span className="text-zinc-500">{stats.tokens?.toLocaleString()} tok</span><span className="text-emerald-400">${stats.cost_usd}</span></div>
        </div>
      ))}
      <Button size="sm" onClick={()=>window.open(`/api/billing/usage/invoice/${workspaceId}?month=${new Date().toISOString().slice(0,7)}`)} variant="outline" className="border-zinc-700"><Download className="w-3 h-3 mr-1"/>Invoice</Button>
    </div>
  );
}

function ScheduledTab({ workspaceId }) {
  const [jobs,setJobs]=useState([]); const [name,setName]=useState(""); const [schedule,setSchedule]=useState("0 9 * * 1");
  useEffect(()=>{api.get(`/workspaces/${workspaceId}/scheduled-jobs`).then(r=>setJobs(r.data.jobs||[])).catch(()=>{});},[workspaceId]);
  const create=async()=>{if(!name)return;try{await api.post(`/workspaces/${workspaceId}/scheduled-jobs`,{name,schedule,schedule_human:"Custom",type:"a2a_pipeline"});toast.success("Created");setName("");api.get(`/workspaces/${workspaceId}/scheduled-jobs`).then(r=>setJobs(r.data.jobs||[]));}catch(err){toast.error("Failed");}};
  const runNow=async(id)=>{try{const r=await api.post(`/scheduled-jobs/${id}/run-now`);toast.success(`Triggered: ${r.data.run_id||"ok"}`);}catch(err){toast.error("Failed");}};
  return (
    <div className="space-y-4">
      <div className="flex gap-2"><Input value={name} onChange={e=>setName(e.target.value)} placeholder="Job name" className="bg-zinc-800 border-zinc-700 flex-1"/><Input value={schedule} onChange={e=>setSchedule(e.target.value)} placeholder="Cron (0 9 * * 1)" className="bg-zinc-800 border-zinc-700 w-40"/><Button onClick={create} className="bg-cyan-600"><Plus className="w-3 h-3 mr-1"/>Create</Button></div>
      {jobs.map(j=>(
        <Card key={j.job_id} className="bg-zinc-900/50 border-zinc-800"><CardContent className="py-3 flex items-center justify-between">
          <div><div className="text-sm text-zinc-200">{j.name}</div><div className="text-xs text-zinc-500">{j.schedule} · {j.run_count} runs · {j.enabled?"Active":"Paused"}</div></div>
          <div className="flex gap-1"><Button size="sm" variant="ghost" onClick={()=>runNow(j.job_id)} className="h-7 text-xs"><Play className="w-3 h-3 mr-1"/>Run Now</Button><Button size="sm" variant="ghost" onClick={async()=>{await api.delete(`/scheduled-jobs/${j.job_id}`);api.get(`/workspaces/${workspaceId}/scheduled-jobs`).then(r=>setJobs(r.data.jobs||[]));}} className="h-7 text-red-400"><Trash2 className="w-3 h-3"/></Button></div>
        </CardContent></Card>
      ))}
    </div>
  );
}

function LearningTab({ workspaceId }) {
  const [agents,setAgents]=useState([]); const [sel,setSel]=useState(""); const [data,setData]=useState(null);
  useEffect(()=>{api.get(`/workspaces/${workspaceId}/agents`).then(r=>{const a=r.data?.agents||r.data||[];setAgents(a);if(a.length&&!sel)setSel(a[0].agent_id);}).catch(()=>{});},[workspaceId]);
  useEffect(()=>{if(sel)api.get(`/workspaces/${workspaceId}/agents/${sel}/learning`).then(r=>setData(r.data)).catch(()=>{});},[sel,workspaceId]);
  return (
    <div className="space-y-4">
      <Select value={sel} onValueChange={setSel}><SelectTrigger className="w-48 bg-zinc-800 border-zinc-700"><SelectValue placeholder="Select agent"/></SelectTrigger><SelectContent>{agents.map(a=><SelectItem key={a.agent_id} value={a.agent_id}>{a.name}</SelectItem>)}</SelectContent></Select>
      {data&&(<>
        <div className="grid grid-cols-4 gap-3">{[{l:"Knowledge Chunks",v:data.knowledge.total_chunks,c:"text-cyan-400"},{l:"High Quality",v:`${data.knowledge.quality_rate}%`,c:"text-emerald-400"},{l:"From Conversations",v:data.knowledge.from_conversations,c:"text-purple-400"},{l:"Training Sessions",v:data.training_sessions,c:"text-amber-400"}].map(({l,v,c})=>(
          <Card key={l} className="bg-zinc-900 border-zinc-800"><CardContent className="py-3 text-center"><div className={`text-xl font-bold ${c}`}>{v}</div><div className="text-[10px] text-zinc-500 mt-0.5">{l}</div></CardContent></Card>
        ))}</div>
        {data.topics?.length>0&&<Card className="bg-zinc-900 border-zinc-800"><CardHeader><CardTitle className="text-sm text-zinc-100">Topic Distribution</CardTitle></CardHeader><CardContent className="space-y-1">{data.topics.map(t=>(<div key={t.topic} className="flex justify-between text-xs py-0.5"><span className="text-zinc-300">{t.topic}</span><span className="text-zinc-500">{t.count}</span></div>))}</CardContent></Card>}
      </>)}
    </div>
  );
}

function FeedTab({ workspaceId }) {
  const [activities,setActivities]=useState([]);
  useEffect(()=>{api.get(`/workspaces/${workspaceId}/activity-feed?limit=30`).then(r=>setActivities(r.data.activities||[])).catch(()=>{});},[workspaceId]);
  const typeIcon={ai_message:<Zap className="w-3 h-3 text-cyan-400"/>,pipeline_run:<Activity className="w-3 h-3 text-purple-400"/>,operator_session:<Brain className="w-3 h-3 text-amber-400"/>};
  return (
    <div className="space-y-2">
      <Button size="sm" variant="ghost" onClick={()=>api.get(`/workspaces/${workspaceId}/activity-feed?limit=30`).then(r=>setActivities(r.data.activities||[]))} className="h-7 text-xs text-zinc-400 mb-2"><Activity className="w-3 h-3 mr-1"/>Refresh</Button>
      {activities.map((a,i)=>(
        <div key={i} className="flex items-start gap-2 py-2 border-b border-zinc-800/30">
          <div className="mt-0.5">{typeIcon[a.type]||<Zap className="w-3 h-3 text-zinc-500"/>}</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 text-xs"><Badge variant="outline" className="text-[8px] border-zinc-700">{a.type?.replace("_"," ")}</Badge>{a.agent&&<span className="text-cyan-400">{a.agent}</span>}{a.model&&<span className="text-zinc-500">{a.model}</span>}{a.status&&<Badge className={`text-[8px] ${a.status==="completed"?"bg-emerald-500/20 text-emerald-400":"bg-zinc-700 text-zinc-400"}`}>{a.status}</Badge>}</div>
            {a.preview&&<p className="text-xs text-zinc-400 mt-0.5 line-clamp-1">{a.preview}</p>}
            {a.goal&&<p className="text-xs text-zinc-400 mt-0.5 line-clamp-1">{a.goal}</p>}
          </div>
          <div className="text-[9px] text-zinc-600 whitespace-nowrap">{a.cost_usd>0&&<span className="text-emerald-400 mr-2">${a.cost_usd.toFixed(4)}</span>}{a.timestamp&&new Date(a.timestamp).toLocaleTimeString()}</div>
        </div>
      ))}
      {activities.length===0&&<p className="text-xs text-zinc-500 text-center py-8">No activity yet</p>}
    </div>
  );
}

function APITab() {
  const [keys,setKeys]=useState([]); const [label,setLabel]=useState(""); const [newKey,setNewKey]=useState(null);
  useEffect(()=>{api.get("/developer/api-keys").then(r=>setKeys(r.data.keys||[])).catch(()=>{});},[]);
  const create=async()=>{try{const r=await api.post("/developer/api-keys",{label:label||"API Key"});setNewKey(r.data);setLabel("");api.get("/developer/api-keys").then(r=>setKeys(r.data.keys||[]));}catch(err){toast.error("Failed");}};
  return (
    <div className="space-y-4">
      <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-4 space-y-3">
        <div className="flex gap-2"><Input value={label} onChange={e=>setLabel(e.target.value)} placeholder="Key label" className="bg-zinc-800 border-zinc-700 flex-1"/><Button onClick={create} className="bg-cyan-600"><Key className="w-3 h-3 mr-1"/>Generate</Button></div>
        {newKey&&<div className="p-3 bg-cyan-900/10 border border-cyan-800/30 rounded"><p className="text-xs text-cyan-400 mb-1">Copy now (shown once):</p><code className="text-xs text-zinc-200 break-all">{newKey.key}</code></div>}
      </CardContent></Card>
      {keys.map(k=>(
        <div key={k.key_id} className="flex items-center justify-between py-2 border-b border-zinc-800/30 text-xs">
          <div className="flex items-center gap-2"><Key className="w-3 h-3 text-zinc-500"/><span className="text-zinc-300">{k.label}</span><Badge className={`text-[8px] ${k.revoked?"bg-red-500/20 text-red-400":"bg-emerald-500/20 text-emerald-400"}`}>{k.revoked?"revoked":"active"}</Badge></div>
          {!k.revoked&&<Button size="sm" variant="ghost" onClick={async()=>{await api.delete(`/developer/api-keys/${k.key_id}`);api.get("/developer/api-keys").then(r=>setKeys(r.data.keys||[]));}} className="h-6 text-red-400"><Trash2 className="w-3 h-3"/></Button>}
        </div>
      ))}
    </div>
  );
}

function BrandingTab() {
  const [brand,setBrand]=useState({app_name:"Nexus Cloud",primary_color:"#06b6d4",logo_url:"",custom_domain:""});
  const save=async()=>{try{await api.put("/orgs/default/branding",brand);toast.success("Branding saved");}catch(err){toast.error("Failed");}};
  return (
    <div className="space-y-4">
      <Card className="bg-zinc-900 border-zinc-800"><CardHeader><CardTitle className="text-sm text-zinc-100">Organization Branding</CardTitle></CardHeader><CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-xs text-zinc-500 mb-1 block">App Name</label><Input value={brand.app_name} onChange={e=>setBrand({...brand,app_name:e.target.value})} className="bg-zinc-800 border-zinc-700"/></div>
          <div><label className="text-xs text-zinc-500 mb-1 block">Primary Color</label><Input value={brand.primary_color} onChange={e=>setBrand({...brand,primary_color:e.target.value})} className="bg-zinc-800 border-zinc-700"/></div>
          <div><label className="text-xs text-zinc-500 mb-1 block">Logo URL</label><Input value={brand.logo_url} onChange={e=>setBrand({...brand,logo_url:e.target.value})} placeholder="https://..." className="bg-zinc-800 border-zinc-700"/></div>
          <div><label className="text-xs text-zinc-500 mb-1 block">Custom Domain</label><Input value={brand.custom_domain} onChange={e=>setBrand({...brand,custom_domain:e.target.value})} placeholder="app.yourdomain.com" className="bg-zinc-800 border-zinc-700"/></div>
        </div>
        <Button onClick={save} className="bg-cyan-600 w-full"><Palette className="w-3 h-3 mr-1"/>Save Branding</Button>
      </CardContent></Card>
    </div>
  );
}

function AgentMarketTab({ workspaceId }) {
  const [agents,setAgents]=useState([]);
  useEffect(()=>{api.get("/marketplace/strategic-agents").then(r=>setAgents(r.data.agents||[])).catch(()=>{});},[]);
  const install=async(id)=>{try{await api.post(`/marketplace/agents/${id}/install`,{workspace_id:workspaceId});toast.success("Agent installed!");}catch(err){toast.error("Install failed");}};
  return (
    <div className="space-y-4">
      {agents.length===0?<p className="text-xs text-zinc-500 text-center py-8">No agents listed yet. Publish a trained agent to the marketplace.</p>:
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{agents.map(a=>(
        <Card key={a.listing_id} className="bg-zinc-900 border-zinc-800"><CardContent className="py-4 space-y-2">
          <div className="flex justify-between"><h3 className="text-sm font-medium text-zinc-100">{a.name}</h3>{a.price_usd>0?<span className="text-emerald-400 text-sm font-bold">${a.price_usd}</span>:<Badge className="bg-emerald-500/20 text-emerald-400 text-[9px]">Free</Badge>}</div>
          <p className="text-xs text-zinc-400 line-clamp-2">{a.description}</p>
          <div className="flex items-center gap-2 text-[10px] text-zinc-500"><span>{a.knowledge_chunks} knowledge chunks</span><span>{a.install_count} installs</span>{a.base_model&&<Badge variant="outline" className="text-[8px] border-zinc-700">{a.base_model}</Badge>}</div>
          <Button size="sm" onClick={()=>install(a.listing_id)} className="bg-cyan-600 w-full text-xs"><Store className="w-3 h-3 mr-1"/>Install to Workspace</Button>
        </CardContent></Card>
      ))}</div>}
    </div>
  );
}

function ComplianceTab() {
  const [report,setReport]=useState(null);
  useEffect(()=>{api.get("/admin/compliance-report").then(r=>setReport(r.data)).catch(()=>{});},[]);
  if(!report)return <Loader2 className="w-5 h-5 animate-spin text-zinc-500 mx-auto mt-8"/>;
  return (
    <div className="space-y-4">
      <Badge className="bg-emerald-500/20 text-emerald-400">{report.report_type}</Badge>
      {[{title:"Access Control",data:report.access_control},{title:"Data Protection",data:report.data_protection},{title:"Audit Logging",data:report.audit_logging},{title:"AI Governance",data:report.ai_governance}].map(({title,data})=>(
        <Card key={title} className="bg-zinc-900 border-zinc-800"><CardHeader><CardTitle className="text-sm text-zinc-100">{title}</CardTitle></CardHeader><CardContent className="space-y-1">
          {Object.entries(data||{}).map(([k,v])=>(<div key={k} className="flex justify-between text-xs py-0.5 border-b border-zinc-800/20"><span className="text-zinc-500">{k.replace(/_/g," ")}</span><span className="text-zinc-300">{String(v)}</span></div>))}
        </CardContent></Card>
      ))}
      <div className="flex gap-2">
        <Button size="sm" onClick={()=>window.open("/api/admin/audit-export?format=csv&days=30")} variant="outline" className="border-zinc-700"><Download className="w-3 h-3 mr-1"/>Export CSV (30d)</Button>
        <Button size="sm" onClick={()=>window.open("/api/admin/audit-export?format=json&days=90")} variant="outline" className="border-zinc-700"><Download className="w-3 h-3 mr-1"/>Export JSON (90d)</Button>
      </div>
    </div>
  );
}
