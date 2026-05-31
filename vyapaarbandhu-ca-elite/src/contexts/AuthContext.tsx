import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface CAProfile {
  ca_id:            number;
  name:             string;
  email:            string;
  plan:             string;
  white_label_name: string | null;
}

interface AuthContextType {
  isAuthenticated: boolean;
  caName:          string;
  caProfile:       CAProfile | null;
  token:           string | null;
  login:           (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup:          (name: string, email: string, password: string, phone?: string) => Promise<{ success: boolean; error?: string }>;
  logout:          () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

const BASE_URL    = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TOKEN_KEY   = 'vb_token';
const PROFILE_KEY = 'vb_profile';

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY)
  );
  const [caProfile, setCaProfile] = useState<CAProfile | null>(() => {
    const stored = localStorage.getItem(PROFILE_KEY);
    return stored ? JSON.parse(stored) : null;
  });

  const isAuthenticated = !!token && !!caProfile;
  const caName = caProfile?.white_label_name || caProfile?.name || 'CA Portal';

  // Verify token still valid on page load
  useEffect(() => {
    if (token && !caProfile) {
      fetch(`${BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(r => { if (!r.ok) { logout(); return null; } return r.json(); })
        .then(data => {
          if (!data) return;
          const profile: CAProfile = {
            ca_id:            data.ca_id,
            name:             data.name,
            email:            data.email,
            plan:             data.plan,
            white_label_name: data.white_label_name,
          };
          setCaProfile(profile);
          localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
        })
        .catch(() => logout());
    }
  }, []);

  const _saveSession = (t: string, profile: CAProfile) => {
    setToken(t);
    setCaProfile(profile);
    localStorage.setItem(TOKEN_KEY,   t);
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  };

  const login = async (email: string, password: string) => {
    try {
      const res  = await fetch(`${BASE_URL}/auth/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) return { success: false, error: data.detail || 'Login failed' };
      _saveSession(data.access_token, {
        ca_id: data.ca_id, name: data.name, email: data.email,
        plan: data.plan, white_label_name: data.white_label_name,
      });
      return { success: true };
    } catch {
      return { success: false, error: 'Network error. Check your connection.' };
    }
  };

  const signup = async (name: string, email: string, password: string, phone?: string) => {
    try {
      const res  = await fetch(`${BASE_URL}/auth/signup`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ name, email, password, phone }),
      });
      const data = await res.json();
      if (!res.ok) return { success: false, error: data.detail || 'Signup failed' };
      _saveSession(data.access_token, {
        ca_id: data.ca_id, name: data.name, email: data.email,
        plan: data.plan, white_label_name: data.white_label_name,
      });
      return { success: true };
    } catch {
      return { success: false, error: 'Network error. Check your connection.' };
    }
  };

  const logout = () => {
    setToken(null);
    setCaProfile(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, caName, caProfile, token, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};