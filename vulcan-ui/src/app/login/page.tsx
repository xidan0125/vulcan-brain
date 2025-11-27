'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Zap } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [bootText, setBootText] = useState<string[]>([]);
  const { login } = useAuth();

  // Boot sequence animation
  useEffect(() => {
    const lines = [
      "VULCAN BRAIN v3.0",
      "Initializing secure connection...",
      "Authentication module ready."
    ];
    let i = 0;
    const interval = setInterval(() => {
      if (i < lines.length) {
        setBootText(prev => [...prev, lines[i]]);
        i++;
      } else {
        clearInterval(interval);
      }
    }, 300);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
      {/* Subtle grid background */}
      <div className="fixed inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />

      {/* Login card */}
      <div className="relative z-10 w-full max-w-sm">
        <div className="bg-zinc-900/60 backdrop-blur-sm border border-white/10 rounded-md p-8">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-orange-500 to-red-600 rounded-md mb-4 shadow-lg shadow-orange-500/20">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-lg font-medium text-zinc-200 tracking-wide">VULCAN BRAIN</h1>
            <p className="text-[10px] text-zinc-600 font-mono tracking-widest mt-1">SECURE ACCESS PORTAL</p>
          </div>

          {/* Boot sequence */}
          <div className="mb-6 bg-zinc-950/50 border border-white/5 rounded px-3 py-2 font-mono text-[11px]">
            {bootText.map((line, i) => (
              <div key={i} className={`${i === 0 ? 'text-orange-400' : 'text-zinc-600'}`}>
                {i > 0 && <span className="text-zinc-700 mr-1">&gt;</span>}
                {line}
              </div>
            ))}
            {bootText.length === 3 && (
              <div className="text-emerald-500 mt-1">
                <span className="text-zinc-700 mr-1">&gt;</span>
                Ready for authentication.
              </div>
            )}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] font-mono text-zinc-500 tracking-wider mb-1.5">
                USERNAME
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2.5 bg-zinc-950/50 border border-white/10 rounded-md focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20 text-zinc-200 placeholder-zinc-700 transition-colors font-mono text-sm"
                placeholder="admin"
                required
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono text-zinc-500 tracking-wider mb-1.5">
                PASSWORD
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 bg-zinc-950/50 border border-white/10 rounded-md focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20 text-zinc-200 placeholder-zinc-700 transition-colors font-mono text-sm"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <div className="p-2.5 bg-rose-950/30 border border-rose-500/30 rounded-md text-rose-400 text-xs font-mono">
                ERROR: {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white text-sm font-medium rounded-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-orange-500/20"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border border-white/30 border-t-white rounded-sm animate-spin" />
                  <span className="font-mono text-xs tracking-wider">AUTHENTICATING...</span>
                </>
              ) : (
                <span className="font-mono text-xs tracking-wider">AUTHENTICATE</span>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-[9px] text-zinc-700 font-mono tracking-wider">
              AUTHORIZED PERSONNEL ONLY
            </p>
          </div>
        </div>

        {/* Subtle glow */}
        <div className="absolute -inset-1 bg-gradient-to-r from-orange-500/5 to-red-500/5 rounded-md blur-xl -z-10" />
      </div>
    </div>
  );
}
