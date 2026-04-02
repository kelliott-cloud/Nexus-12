import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { handleSilent } from "@/lib/errorHandler";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Star, ThumbsUp, Flag, Trash2, Loader2, MessageSquare, Edit2, Send
} from "lucide-react";
import { FeatureHelp, FEATURE_HELP } from "@/components/FeatureHelp";

function StarRating({ rating, onRate, interactive = false, size = "w-4 h-4" }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <Star
          key={i}
          className={`${size} ${i <= rating ? "fill-amber-400 text-amber-400" : "text-zinc-600"} ${interactive ? "cursor-pointer hover:text-amber-300" : ""}`}
          onClick={() => interactive && onRate(i)}
        />
      ))}
    </div>
  );
}

export default function ReviewsPanel({ workspaceId }) {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [breakdown, setBreakdown] = useState({});
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("recent");

  // Review form
  const [showForm, setShowForm] = useState(false);
  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState(null);
  const [editRating, setEditRating] = useState(0);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await api.get("/marketplace");
      const list = res.data.templates || res.data || [];
      setTemplates(list);
    } catch (err) { handleSilent(err, "Reviews:templates"); }
    setLoading(false);
  }, []);

  const fetchReviews = useCallback(async (templateId) => {
    try {
      const res = await api.get(`/marketplace/${templateId}/reviews?sort=${sort}`);
      setReviews(res.data.reviews || []);
      setBreakdown(res.data.rating_breakdown || {});
    } catch (err) { handleSilent(err, "Reviews:list"); }
  }, [sort]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);
  useEffect(() => { if (selectedTemplate) fetchReviews(selectedTemplate.marketplace_id); }, [selectedTemplate, fetchReviews]);

  const submitReview = async () => {
    if (!rating || !selectedTemplate) return toast.error("Please select a rating");
    setSubmitting(true);
    try {
      await api.post(`/marketplace/${selectedTemplate.marketplace_id}/reviews`, { rating, title, content });
      toast.success("Review submitted");
      setShowForm(false); setRating(0); setTitle(""); setContent("");
      fetchReviews(selectedTemplate.marketplace_id);
      fetchTemplates();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed to submit review"); }
    setSubmitting(false);
  };

  const updateReview = async (reviewId) => {
    try {
      await api.put(`/marketplace/${selectedTemplate.marketplace_id}/reviews/${reviewId}`, { rating: editRating, title: editTitle, content: editContent });
      toast.success("Review updated");
      setEditingId(null);
      fetchReviews(selectedTemplate.marketplace_id);
    } catch (err) { toast.error("Update failed"); }
  };

  const deleteReview = async (reviewId) => {
    try {
      await api.delete(`/marketplace/${selectedTemplate.marketplace_id}/reviews/${reviewId}`);
      toast.success("Review deleted");
      fetchReviews(selectedTemplate.marketplace_id);
      fetchTemplates();
    } catch (err) { toast.error(err?.response?.data?.detail || "Delete failed"); }
  };

  const flagReview = async (reviewId) => {
    try {
      await api.post(`/marketplace/${selectedTemplate.marketplace_id}/reviews/${reviewId}/flag`, { reason: "inappropriate" });
      toast.success("Review flagged for moderation");
    } catch (err) { toast.error("Flag failed"); }
  };

  const markHelpful = async (reviewId) => {
    try {
      await api.post(`/marketplace/${selectedTemplate.marketplace_id}/reviews/${reviewId}/helpful`);
      toast.success("Marked as helpful");
      fetchReviews(selectedTemplate.marketplace_id);
    } catch (err) { handleSilent(err, "Reviews:helpful"); }
  };

  const totalReviews = Object.values(breakdown).reduce((a, b) => a + b, 0);
  const avgRating = totalReviews > 0 ? Object.entries(breakdown).reduce((sum, [r, c]) => sum + parseInt(r) * c, 0) / totalReviews : 0;

  if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" data-testid="reviews-panel">
      <div className="max-w-5xl mx-auto space-y-6">
        <FeatureHelp featureId="reviews" {...FEATURE_HELP["reviews"]} />
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Marketplace Reviews & Ratings</h2>
          <p className="text-sm text-zinc-500 mt-1">Read and write reviews for marketplace agents and templates</p>
        </div>

        {!selectedTemplate ? (
          <div className="space-y-3">
            {templates.length === 0 ? (
              <Card className="bg-zinc-900 border-zinc-800"><CardContent className="py-12 text-center text-zinc-500">No marketplace templates available yet.</CardContent></Card>
            ) : templates.map(tpl => (
              <Card key={tpl.marketplace_id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 cursor-pointer transition-colors" onClick={() => setSelectedTemplate(tpl)} data-testid={`review-template-${tpl.marketplace_id}`}>
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-amber-600/15 flex items-center justify-center">
                      <Star className="w-5 h-5 text-amber-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-200">{tpl.name}</div>
                      <div className="text-xs text-zinc-500">{tpl.description?.slice(0, 80) || "No description"}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {tpl.avg_rating > 0 && (
                      <div className="flex items-center gap-1">
                        <StarRating rating={Math.round(tpl.avg_rating)} size="w-3 h-3" />
                        <span className="text-xs text-zinc-400">{tpl.avg_rating?.toFixed(1)} ({tpl.rating_count || 0})</span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Button variant="ghost" size="sm" onClick={() => { setSelectedTemplate(null); setReviews([]); }} data-testid="reviews-back-btn">Back to Templates</Button>
              <Button size="sm" onClick={() => setShowForm(!showForm)} className="bg-amber-600 hover:bg-amber-700" data-testid="reviews-write-btn">
                <Edit2 className="w-3.5 h-3.5 mr-1" /> Write Review
              </Button>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
              <CardContent className="py-4">
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-zinc-100">{avgRating.toFixed(1)}</div>
                    <StarRating rating={Math.round(avgRating)} size="w-4 h-4" />
                    <div className="text-xs text-zinc-500 mt-1">{totalReviews} review{totalReviews !== 1 ? "s" : ""}</div>
                  </div>
                  <div className="flex-1 space-y-1">
                    {[5, 4, 3, 2, 1].map(star => {
                      const count = breakdown[String(star)] || 0;
                      const pct = totalReviews > 0 ? (count / totalReviews) * 100 : 0;
                      return (
                        <div key={star} className="flex items-center gap-2 text-xs">
                          <span className="text-zinc-400 w-3">{star}</span>
                          <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                          <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-zinc-500 w-6 text-right">{count}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>

            {showForm && (
              <Card className="bg-zinc-900 border-zinc-800" data-testid="review-form">
                <CardContent className="py-4 space-y-3">
                  <div>
                    <label className="text-xs text-zinc-400 mb-1 block">Your Rating</label>
                    <StarRating rating={rating} onRate={setRating} interactive size="w-6 h-6" />
                  </div>
                  <Input placeholder="Review title (optional)" value={title} onChange={e => setTitle(e.target.value)} className="bg-zinc-800 border-zinc-700" data-testid="review-title-input" />
                  <Textarea placeholder="Share your experience..." value={content} onChange={e => setContent(e.target.value)} rows={3} className="bg-zinc-800 border-zinc-700" data-testid="review-content-input" />
                  <Button onClick={submitReview} disabled={submitting || !rating} className="bg-amber-600 hover:bg-amber-700" data-testid="review-submit-btn">
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
                    Submit Review
                  </Button>
                </CardContent>
              </Card>
            )}

            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-400">{reviews.length} review{reviews.length !== 1 ? "s" : ""}</span>
              <Select value={sort} onValueChange={v => setSort(v)}>
                <SelectTrigger className="w-36 h-8 bg-zinc-800 border-zinc-700 text-xs" data-testid="reviews-sort">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recent">Most Recent</SelectItem>
                  <SelectItem value="rating">Highest Rated</SelectItem>
                  <SelectItem value="helpful">Most Helpful</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {reviews.map(review => (
              <Card key={review.review_id} className="bg-zinc-900/50 border-zinc-800" data-testid={`review-${review.review_id}`}>
                <CardContent className="py-4 space-y-2">
                  {editingId === review.review_id ? (
                    <div className="space-y-2">
                      <StarRating rating={editRating} onRate={setEditRating} interactive size="w-5 h-5" />
                      <Input value={editTitle} onChange={e => setEditTitle(e.target.value)} className="bg-zinc-800 border-zinc-700 h-8" />
                      <Textarea value={editContent} onChange={e => setEditContent(e.target.value)} rows={2} className="bg-zinc-800 border-zinc-700" />
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => updateReview(review.review_id)} className="bg-emerald-600 h-7 text-xs">Save</Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditingId(null)} className="h-7 text-xs">Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <StarRating rating={review.rating} size="w-3.5 h-3.5" />
                          {review.title && <span className="text-sm font-medium text-zinc-200">{review.title}</span>}
                        </div>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="sm" onClick={() => markHelpful(review.review_id)} className="text-zinc-500 hover:text-zinc-300 h-7 text-xs" data-testid={`review-helpful-${review.review_id}`}>
                            <ThumbsUp className="w-3 h-3 mr-1" /> {review.helpful_count || 0}
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => { setEditingId(review.review_id); setEditRating(review.rating); setEditTitle(review.title); setEditContent(review.content); }} className="text-zinc-500 hover:text-zinc-300 h-7"><Edit2 className="w-3 h-3" /></Button>
                          <Button variant="ghost" size="sm" onClick={() => flagReview(review.review_id)} className="text-zinc-500 hover:text-amber-400 h-7"><Flag className="w-3 h-3" /></Button>
                          <Button variant="ghost" size="sm" onClick={() => deleteReview(review.review_id)} className="text-zinc-500 hover:text-red-400 h-7"><Trash2 className="w-3 h-3" /></Button>
                        </div>
                      </div>
                      {review.content && <p className="text-sm text-zinc-400">{review.content}</p>}
                      <div className="text-xs text-zinc-600">by {review.user_name} &middot; {new Date(review.created_at).toLocaleDateString()}</div>
                    </>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
