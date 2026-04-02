import { useState, useEffect, useRef } from "react";
import { handleError, handleSilent } from "@/lib/errorHandler";
import { Bell, X, Check, CheckCheck, Trash2, Bot, Users, FileUp, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/App";
import { toast } from "sonner";

const NOTIFICATION_ICONS = {
  ai_response: Bot,
  task_completed: Check,
  member_joined: Users,
  file_uploaded: FileUp,
  invitation: Mail,
  budget_alert: Bell,
};

const NOTIFICATION_COLORS = {
  ai_response: "text-amber-400",
  task_completed: "text-emerald-400",
  member_joined: "text-blue-400",
  file_uploaded: "text-purple-400",
  invitation: "text-pink-400",
  budget_alert: "text-red-400",
};

export default function NotificationBell({ onNavigate }) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const dropdownRef = useRef(null);
  const audioRef = useRef(null);
  const lastCountRef = useRef(0);

  useEffect(() => {
    fetchNotifications();
    // Poll for new notifications (30s when visible, pause when hidden)
    let interval;
    const startPolling = () => {
      interval = setInterval(fetchNotifications, 30000);
    };
    const handleVisibility = () => {
      clearInterval(interval);
      if (!document.hidden) {
        fetchNotifications();
        startPolling();
      }
    };
    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  useEffect(() => {
    // Play sound when new notifications arrive
    if (unreadCount > lastCountRef.current && soundEnabled && audioRef.current) {
      audioRef.current.play().catch(() => {});
    }
    lastCountRef.current = unreadCount;
  }, [unreadCount, soundEnabled]);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchNotifications = async () => {
    try {
      const res = await api.get("/notifications?limit=20");
      setNotifications(res.data.notifications || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (err) { handleSilent(err, "NotificationBell:op1"); }
  };

  const markAsRead = async (notificationId) => {
    try {
      await api.put(`/notifications/${notificationId}/read`);
      setNotifications(notifications.map(n => 
        n.notification_id === notificationId ? { ...n, read: true } : n
      ));
      setUnreadCount(Math.max(0, unreadCount - 1));
    } catch (err) { handleSilent(err, "NotificationBell:op2"); }
  };

  const markAllAsRead = async () => {
    try {
      await api.put("/notifications/read-all");
      setNotifications(notifications.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
      toast.success("All notifications marked as read");
    } catch (err) { handleSilent(err, "NotificationBell:op3"); }
  };

  const deleteNotification = async (notificationId) => {
    try {
      await api.delete(`/notifications/${notificationId}`);
      const wasUnread = notifications.find(n => n.notification_id === notificationId && !n.read);
      setNotifications(notifications.filter(n => n.notification_id !== notificationId));
      if (wasUnread) setUnreadCount(Math.max(0, unreadCount - 1));
    } catch (err) { handleSilent(err, "NotificationBell:op4"); }
  };

  const handleNotificationClick = (notification) => {
    if (!notification.read) {
      markAsRead(notification.notification_id);
    }
    if (notification.link && onNavigate) {
      onNavigate(notification.link);
    }
    setIsOpen(false);
  };

  const formatTime = (isoString) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Hidden audio element for notification sound */}
      <audio ref={audioRef} preload="auto">
        <source src="data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleQAHO5DT7LqADAQ0markup7tz8k0QA6/e3dj/8AAAAxEW48PDz+7Ozs7O3t9fT09PT19fX29/b29vb3+Pj4+fn6+vv8/f7+/v7+/v7+/v7+/v7+/v7+/v7+" type="audio/wav"/>
      </audio>
      
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="relative text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 p-2"
        data-testid="notification-bell"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </Button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-100">Notifications</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
                >
                  <CheckCheck className="w-3 h-3" />
                  Mark all read
                </button>
              )}
            </div>
          </div>

          {/* Notification List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-8 text-center">
                <Bell className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                <p className="text-sm text-zinc-500">No notifications yet</p>
              </div>
            ) : (
              notifications.map((notification) => {
                const Icon = NOTIFICATION_ICONS[notification.type] || Bell;
                const iconColor = NOTIFICATION_COLORS[notification.type] || "text-zinc-400";
                
                return (
                  <div
                    key={notification.notification_id}
                    className={`flex items-start gap-3 px-4 py-3 border-b border-zinc-800/50 cursor-pointer transition-colors ${
                      notification.read ? "bg-zinc-900" : "bg-zinc-800/50"
                    } hover:bg-zinc-800`}
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className={`mt-0.5 ${iconColor}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm ${notification.read ? "text-zinc-400" : "text-zinc-100"}`}>
                        {notification.title}
                      </p>
                      <p className="text-xs text-zinc-500 truncate mt-0.5">
                        {notification.message}
                      </p>
                      <p className="text-[10px] text-zinc-600 mt-1">
                        {formatTime(notification.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {!notification.read && (
                        <div className="w-2 h-2 bg-blue-500 rounded-full" />
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteNotification(notification.notification_id);
                        }}
                        className="p-1 text-zinc-600 hover:text-zinc-400 rounded"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-2 border-t border-zinc-800 flex items-center justify-between">
              <button
                onClick={() => setSoundEnabled(!soundEnabled)}
                className={`text-xs ${soundEnabled ? "text-zinc-400" : "text-zinc-600"} hover:text-zinc-200`}
              >
                Sound {soundEnabled ? "on" : "off"}
              </button>
              <button
                onClick={() => {
                  setIsOpen(false);
                  onNavigate?.("/settings?tab=notifications");
                }}
                className="text-xs text-zinc-400 hover:text-zinc-200"
              >
                Settings
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
