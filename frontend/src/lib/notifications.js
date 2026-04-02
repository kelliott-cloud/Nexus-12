// Push notification utilities
// Registers service worker and requests push permission

export async function requestNotificationPermission() {
  if (!("Notification" in window)) {
    console.warn("Notifications not supported");
    return false;
  }

  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;

  const permission = await Notification.requestPermission();
  return permission === "granted";
}

let _swRegistered = false;
export async function registerServiceWorker() {
  if (_swRegistered) return null;
  if (!("serviceWorker" in navigator)) return null;
  try {
    _swRegistered = true;
    const registration = await navigator.serviceWorker.register("/sw.js");
    return registration;
  } catch (err) {
    _swRegistered = false;
    return null;
  }
}

export function showLocalNotification(title, body, options = {}) {
  if (Notification.permission !== "granted") return;

  // Don't show if tab is focused
  if (document.hasFocus()) return;

  const notification = new Notification(title, {
    body,
    icon: "/favicon.ico",
    badge: "/favicon.ico",
    tag: options.tag || "nexus",
    ...options,
  });

  notification.onclick = () => {
    window.focus();
    notification.close();
    if (options.url) {
      window.location.href = options.url;
    }
  };

  // Auto-close after 5 seconds
  setTimeout(() => notification.close(), 5000);
}
