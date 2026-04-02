import { useState, useEffect, useCallback } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X, Bot, User, GitBranch, Merge, LogIn, LogOut, Globe } from "lucide-react";
import { api } from "@/App";

const AI_MODELS = [
  { key: "claude", label: "Claude" },
  { key: "chatgpt", label: "ChatGPT" },
  { key: "deepseek", label: "DeepSeek" },
  { key: "grok", label: "Grok" },
  { key: "gemini", label: "Gemini" },
  { key: "perplexity", label: "Perplexity" },
  { key: "mistral", label: "Mistral" },
  { key: "cohere", label: "Cohere" },
  { key: "groq", label: "Groq" },
];

const OPERATORS = ["==", "!=", ">", ">=", "<", "<=", "contains", "not_contains", "exists", "not_exists"];

export default function NodeConfigPanel({ node, dbNode, onUpdate, onClose }) {
  const [label, setLabel] = useState(dbNode?.label || "");
  const [model, setModel] = useState(dbNode?.ai_model || "chatgpt");
  const [systemPrompt, setSystemPrompt] = useState(dbNode?.system_prompt || "");
  const [userPrompt, setUserPrompt] = useState(dbNode?.user_prompt_template || "");
  const [temperature, setTemperature] = useState(dbNode?.temperature ?? 0.7);
  const [maxTokens, setMaxTokens] = useState(dbNode?.max_tokens ?? 4096);
  const [timeout, setTimeout_] = useState(dbNode?.timeout_seconds ?? 120);
  const [retryCount, setRetryCount] = useState(dbNode?.retry_count ?? 1);
  const [condField, setCondField] = useState(dbNode?.condition_logic?.field || "");
  const [condOp, setCondOp] = useState(dbNode?.condition_logic?.operator || "==");
  const [condValue, setCondValue] = useState(dbNode?.condition_logic?.value || "");
  const [dirty, setDirty] = useState(false);
  const [variables, setVariables] = useState([]);
  const [showVarPicker, setShowVarPicker] = useState(false);
  const [varTarget, setVarTarget] = useState(null); // which field to insert into

  useEffect(() => {
    setLabel(dbNode?.label || "");
    setModel(dbNode?.ai_model || "chatgpt");
    setSystemPrompt(dbNode?.system_prompt || "");
    setUserPrompt(dbNode?.user_prompt_template || "");
    setTemperature(dbNode?.temperature ?? 0.7);
    setMaxTokens(dbNode?.max_tokens ?? 4096);
    setTimeout_(dbNode?.timeout_seconds ?? 120);
    setRetryCount(dbNode?.retry_count ?? 1);
    setCondField(dbNode?.condition_logic?.field || "");
    setCondOp(dbNode?.condition_logic?.operator || "==");
    setCondValue(dbNode?.condition_logic?.value || "");
    setDirty(false);
  }, [dbNode]);

  // Load available variables for autocomplete
  const loadVariables = useCallback(async () => {
    if (!dbNode?.workflow_id) return;
    try {
      const res = await api.get(`/workflows/${dbNode.workflow_id}/variables`);
      setVariables(res.data.variables || []);
    } catch (err) { handleSilent(err, "NodeConfigPanel:op1"); }
  }, [dbNode?.workflow_id]);

  useEffect(() => { loadVariables(); }, [loadVariables]);

  const insertVariable = (field, varRef) => {
    const ref = `{{${varRef.source}.${varRef.field}}}`;
    if (field === "system_prompt") setSystemPrompt(prev => prev + ref);
    else if (field === "user_prompt") setUserPrompt(prev => prev + ref);
    else if (field === "cond_value") setCondValue(prev => prev + ref);
    setShowVarPicker(false);
    setDirty(true);
  };

  const handleSave = () => {
    const updates = { label };
    const nodeType = dbNode?.type;

    if (nodeType === "ai_agent") {
      updates.ai_model = model;
      updates.system_prompt = systemPrompt;
      updates.user_prompt_template = userPrompt;
      updates.temperature = parseFloat(temperature);
      updates.max_tokens = parseInt(maxTokens);
      updates.timeout_seconds = parseInt(timeout);
      updates.retry_count = parseInt(retryCount);
    } else if (nodeType === "condition") {
      updates.condition_logic = { field: condField, operator: condOp, value: condValue };
    }

    onUpdate(updates);
    setDirty(false);
  };

  const nodeType = dbNode?.type;
  const markDirty = () => setDirty(true);

  return (
    <div className="w-80 border-l border-zinc-800/60 bg-zinc-900/80 overflow-y-auto" data-testid="node-config-panel">
      <div className="flex items-center justify-between p-3 border-b border-zinc-800/60">
        <h3 className="text-sm font-medium text-zinc-200">Configure Node</h3>
        <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 space-y-4">
        {/* Label */}
        <div>
          <label className="text-xs font-medium text-zinc-400 mb-1 block">Label</label>
          <Input value={label} onChange={(e) => { setLabel(e.target.value); markDirty(); }}
            className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" data-testid="node-label-input" />
        </div>

        {/* AI Agent Config */}
        {nodeType === "ai_agent" && (
          <>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">AI Model</label>
              <select value={model} onChange={(e) => { setModel(e.target.value); markDirty(); }}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="node-model-select">
                {AI_MODELS.map((m) => (
                  <option key={m.key} value={m.key}>{m.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">System Prompt</label>
              <textarea value={systemPrompt} onChange={(e) => { setSystemPrompt(e.target.value); markDirty(); }}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[80px] resize-y"
                placeholder="You are a helpful assistant..." data-testid="node-system-prompt" />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 flex items-center justify-between">
                <span>User Prompt Template <span className="text-zinc-600 font-normal">{"(use {{variable}})"}</span></span>
                <button onClick={() => { setVarTarget("user_prompt"); setShowVarPicker(!showVarPicker); }} className="text-[10px] text-emerald-400 hover:text-emerald-300 px-1.5 py-0.5 rounded bg-emerald-500/10" data-testid="var-picker-btn">{"{{"} Insert Variable</button>
              </label>
              {showVarPicker && varTarget === "user_prompt" && variables.length > 0 && (
                <div className="mb-2 bg-zinc-800 border border-zinc-700 rounded-md max-h-32 overflow-y-auto" data-testid="var-picker-dropdown">
                  {variables.map((v, i) => (
                    <button key={i} onClick={() => insertVariable("user_prompt", v)} className="w-full text-left px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 flex items-center justify-between">
                      <span className="font-mono text-emerald-400">{`{{${v.source}.${v.field}}}`}</span>
                      <span className="text-zinc-500 ml-2 truncate">{v.description}</span>
                    </button>
                  ))}
                </div>
              )}
              <textarea value={userPrompt} onChange={(e) => { setUserPrompt(e.target.value); markDirty(); }}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[80px] resize-y"
                placeholder="Analyze: {{input.text}}" data-testid="node-user-prompt" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1 block">Temperature</label>
                <Input type="number" min="0" max="2" step="0.1" value={temperature}
                  onChange={(e) => { setTemperature(e.target.value); markDirty(); }}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" data-testid="node-temperature" />
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1 block">Max Tokens</label>
                <Input type="number" min="100" max="128000" step="100" value={maxTokens}
                  onChange={(e) => { setMaxTokens(e.target.value); markDirty(); }}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" data-testid="node-max-tokens" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1 block">Timeout (s)</label>
                <Input type="number" min="10" max="600" value={timeout}
                  onChange={(e) => { setTimeout_(e.target.value); markDirty(); }}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1 block">Retries</label>
                <Input type="number" min="0" max="5" value={retryCount}
                  onChange={(e) => { setRetryCount(e.target.value); markDirty(); }}
                  className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" />
              </div>
            </div>
          </>
        )}

        {/* Condition Config */}
        {nodeType === "condition" && (
          <>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Field</label>
              <Input value={condField} onChange={(e) => { setCondField(e.target.value); markDirty(); }}
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" placeholder="e.g., risk_level" data-testid="cond-field" />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Operator</label>
              <select value={condOp} onChange={(e) => { setCondOp(e.target.value); markDirty(); }}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="cond-operator">
                {OPERATORS.map((op) => <option key={op} value={op}>{op}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Value</label>
              <Input value={condValue} onChange={(e) => { setCondValue(e.target.value); markDirty(); }}
                className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" placeholder="e.g., high" data-testid="cond-value" />
            </div>
          </>
        )}

        {/* Human Review config (#12) */}
        {nodeType === "human_review" && (
          <>
            <div className="bg-amber-900/20 border border-amber-800/30 rounded-md p-3">
              <p className="text-xs text-amber-300">This node pauses the workflow for human review.</p>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Checkpoint Type</label>
              <select value={dbNode?.checkpoint_type || "approve_reject"} onChange={(e) => { onUpdate({ checkpoint_type: e.target.value }); }} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="hr-checkpoint-type">
                <option value="approve_reject">Approve / Reject</option>
                <option value="review_edit">Review &amp; Edit</option>
                <option value="select_option">Select Option</option>
                <option value="provide_input">Provide Input</option>
                <option value="confirm_proceed">Confirm &amp; Proceed</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Timeout (minutes, 0=no limit)</label>
              <Input type="number" min="0" value={dbNode?.timeout_minutes || 0} onChange={(e) => { onUpdate({ timeout_minutes: parseInt(e.target.value) || 0 }); }} className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm" />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Review Instructions</label>
              <textarea value={dbNode?.system_prompt || ""} onChange={(e) => { setSystemPrompt(e.target.value); markDirty(); }} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[60px] resize-y" placeholder="What should the reviewer check?" />
            </div>
          </>
        )}

        {/* Merge config (#13) */}
        {nodeType === "merge" && (
          <>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Merge Strategy</label>
              <select value={dbNode?.merge_strategy || "concatenate"} onChange={(e) => { onUpdate({ merge_strategy: e.target.value }); }} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="merge-strategy-select">
                <option value="concatenate">Wait for All (Concatenate)</option>
                <option value="pick_best">First Response Wins</option>
                <option value="summarize">Summarize All</option>
              </select>
            </div>
            <div className="bg-zinc-800/50 border border-zinc-700/30 rounded-md p-3">
              <p className="text-xs text-zinc-400">This node waits for all incoming branches to complete, then combines their outputs using the selected strategy.</p>
            </div>
          </>
        )}

        {/* Input node schema (#16) */}
        {nodeType === "input" && (
          <div className="space-y-3">
            <div className="bg-blue-900/20 border border-blue-800/30 rounded-md p-3">
              <p className="text-xs text-blue-300">This node receives input data. Define fields below to create a structured run form.</p>
            </div>
            <p className="text-[10px] text-zinc-500">Input fields can be referenced in downstream nodes using <code className="bg-zinc-800 px-1 rounded">{"{{input.fieldname}}"}</code></p>
          </div>
        )}

        {/* Trigger node config (#14) */}
        {nodeType === "trigger" && (
          <div className="space-y-3">
            <div className="bg-emerald-900/20 border border-emerald-800/30 rounded-md p-3">
              <p className="text-xs text-emerald-300">This node defines how the workflow is triggered — webhook, cron schedule, or event.</p>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Trigger Type</label>
              <select value={dbNode?.trigger_config?.type || "webhook"} onChange={(e) => { onUpdate({ trigger_config: { ...dbNode?.trigger_config, type: e.target.value } }); }} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="trigger-type-select">
                <option value="webhook">Webhook (POST URL)</option>
                <option value="cron">Schedule (Cron)</option>
                <option value="event">Event (message, task, file)</option>
                <option value="manual">Manual Only</option>
              </select>
            </div>
            {dbNode?.trigger_config?.type === "cron" && (
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1 block">Cron Expression</label>
                <Input value={dbNode?.trigger_config?.cron_expr || "0 9 * * *"} onChange={(e) => { onUpdate({ trigger_config: { ...dbNode?.trigger_config, cron_expr: e.target.value } }); }} className="bg-zinc-800 border-zinc-700 text-zinc-200 text-sm font-mono" placeholder="0 9 * * *" />
                <p className="text-[10px] text-zinc-600 mt-1">Daily at 9am: 0 9 * * * | Hourly: 0 * * * * | Every 30min: */30 * * * *</p>
              </div>
            )}
            {dbNode?.trigger_config?.type === "event" && (
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1 block">Event Name</label>
                <select value={dbNode?.trigger_config?.event_name || "message.created"} onChange={(e) => { onUpdate({ trigger_config: { ...dbNode?.trigger_config, event_name: e.target.value } }); }} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200">
                  <option value="message.created">New Message</option>
                  <option value="task.created">New Task</option>
                  <option value="task.completed">Task Completed</option>
                  <option value="artifact.created">New Artifact</option>
                  <option value="member.joined">Member Joined</option>
                </select>
              </div>
            )}
            <p className="text-[10px] text-zinc-500">Trigger data is available as <code className="bg-zinc-800 px-1 rounded">{"{{trigger.payload}}"}</code></p>
          </div>
        )}

        {/* Output info */}
        {nodeType === "output" && (
          <div className="bg-zinc-800/50 border border-zinc-700/30 rounded-md p-3">
            <p className="text-xs text-zinc-400">This node collects the final output from upstream nodes.</p>
          </div>
        )}

        {/* Variable reference help for AI Agent */}
        {nodeType === "ai_agent" && (
          <div className="bg-zinc-800/50 border border-zinc-700/30 rounded-md p-2.5">
            <p className="text-[10px] text-zinc-500">Use <code className="bg-zinc-700 px-1 rounded">{"{{input.text}}"}</code> or <code className="bg-zinc-700 px-1 rounded">{"{{node_label.response}}"}</code> to reference data from upstream nodes.</p>
          </div>
        )}

        {/* Save button */}
        {dirty && (
          <Button onClick={handleSave} className="w-full bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-sm" data-testid="save-node-config-btn">
            Save Changes
          </Button>
        )}
      </div>
    </div>
  );
}
