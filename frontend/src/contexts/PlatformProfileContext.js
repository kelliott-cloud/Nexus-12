import { createContext, useContext, useState, useEffect } from "react";
import { api } from "@/lib/api";

const PlatformProfileContext = createContext({
  profile: null,
  loading: true,
  isFeatureOn: () => true,
  isFeatureAvailable: () => true,
  isModelAvailable: () => true,
  productLine: "full",
  brandName: "Nexus Cloud",
});

export function PlatformProfileProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/platform/profile")
      .then(res => setProfile(res.data))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, []);

  const features = profile?.features || {};
  const isFeatureOn = (key) => features[key] === "on";
  const isFeatureAvailable = (key) => features[key] !== "off";
  const isModelAvailable = (key) => {
    const hidden = profile?.ai_models?.hidden || [];
    return !hidden.includes(key);
  };

  const productLine = profile?.billing?.product_line || "full";
  const brandName = profile?.branding?.platform_name || "Nexus Cloud";

  return (
    <PlatformProfileContext.Provider value={{
      profile, loading, isFeatureOn, isFeatureAvailable, isModelAvailable, productLine, brandName
    }}>
      {children}
    </PlatformProfileContext.Provider>
  );
}

export function usePlatformProfile() {
  return useContext(PlatformProfileContext);
}
