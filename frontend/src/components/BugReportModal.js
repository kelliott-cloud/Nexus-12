import { useState } from "react";
import { LifeBuoy, Send, Loader2, CheckCircle, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { api } from "@/App";

const TICKET_TYPES = [
  { value: "bug", label: "Bug Report", description: "Something isn't working correctly" },
  { value: "enhancement", label: "Enhancement", description: "Suggest an improvement" },
  { value: "question", label: "Question", description: "Need help with something" },
  { value: "billing", label: "Billing", description: "Billing or subscription issue" },
  { value: "general_support", label: "General Support", description: "Other support request" },
];

export default function SupportRequestModal({ trigger, onSubmitted }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [ticketType, setTicketType] = useState("question");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [files, setFiles] = useState([]);

  const handleSubmit = async () => {
    if (!subject.trim() || !description.trim()) {
      toast.error("Please fill in subject and description");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post("/support/tickets", {
        subject, description, ticket_type: ticketType, priority,
      });
      // Upload attachments
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        await api.post(`/support/tickets/${res.data.ticket_id}/attachments`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      }
      setSubmitted(true);
      if (onSubmitted) onSubmitted();
      setTimeout(() => {
        setOpen(false);
        setSubmitted(false);
        setSubject(""); setDescription(""); setTicketType("question"); setPriority("medium"); setFiles([]);
      }, 2000);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-zinc-300 gap-2" data-testid="request-support-btn">
            <LifeBuoy className="w-4 h-4" />
            Request Support
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <LifeBuoy className="w-5 h-5 text-emerald-400" />
            Request Support
          </DialogTitle>
          <DialogDescription className="text-zinc-500">Submit a support ticket and our team will respond.</DialogDescription>
        </DialogHeader>

        {submitted ? (
          <div className="py-8 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-lg font-medium text-zinc-200">Ticket Submitted!</p>
            <p className="text-sm text-zinc-500 mt-1">We'll get back to you soon.</p>
          </div>
        ) : (
          <div className="space-y-4 mt-2">
            {/* Ticket Type */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Request Type</label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {TICKET_TYPES.map((t) => (
                  <button key={t.value} onClick={() => setTicketType(t.value)}
                    className={`text-left p-2.5 rounded-lg border text-xs transition-colors ${ticketType === t.value ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300" : "border-zinc-800 bg-zinc-800/30 text-zinc-400 hover:border-zinc-700"}`}
                    data-testid={`ticket-type-${t.value}`}>
                    <span className="font-medium block">{t.label}</span>
                    <span className="text-[10px] text-zinc-500 mt-0.5 block">{t.description}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Subject */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Subject</label>
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Brief summary of your request" className="bg-zinc-800 border-zinc-700 text-zinc-200" data-testid="ticket-subject" maxLength={300} />
            </div>

            {/* Description */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Description</label>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Provide as much detail as possible..." className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 min-h-[100px] resize-y focus:outline-none focus:ring-1 focus:ring-emerald-500/50" data-testid="ticket-description" />
            </div>

            {/* Priority */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 block">Priority</label>
              <select value={priority} onChange={(e) => setPriority(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200" data-testid="ticket-priority">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>

            {/* Attachments */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1 flex items-center gap-1 cursor-pointer">
                <Paperclip className="w-3 h-3" /> Attachments
                <input type="file" className="hidden" multiple onChange={(e) => setFiles(prev => [...prev, ...Array.from(e.target.files)])} />
                <span className="text-emerald-400 ml-1">+ Add file</span>
              </label>
              {files.length > 0 && (
                <div className="space-y-1 mt-1">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center justify-between px-2 py-1 rounded bg-zinc-800/60 text-xs text-zinc-400">
                      <span className="truncate">{f.name}</span>
                      <button onClick={() => setFiles(prev => prev.filter((_, idx) => idx !== i))} className="text-zinc-600 hover:text-red-400 ml-2">&times;</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <Button onClick={handleSubmit} disabled={submitting || !subject.trim() || !description.trim()} className="w-full bg-emerald-500 hover:bg-emerald-400 text-white font-medium" data-testid="submit-ticket-btn">
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Submitting...</> : <><Send className="w-4 h-4 mr-2" />Submit Ticket</>}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
