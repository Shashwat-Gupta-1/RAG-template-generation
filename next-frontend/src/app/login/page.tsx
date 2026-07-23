"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const [isRegistering, setIsRegistering] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const endpoint = isRegistering ? "/auth/register" : "/auth/login";
      const payload = isRegistering 
        ? { name, email, password } 
        : { email, password };

      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "An error occurred");
      }

      // If registration was successful, log them in automatically
      if (isRegistering) {
        const loginRes = await fetch("http://localhost:8000/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        
        if (!loginRes.ok) throw new Error("Registration succeeded, but login failed.");
        const loginData = await loginRes.json();
        login(loginData.access_token);
      } else {
        login(data.access_token);
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl overflow-hidden transition-all">
        <div className="p-8">
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              {isRegistering ? "Create an Account" : "Welcome Back"}
            </h1>
            <p className="text-zinc-400 mt-2 text-sm">
              {isRegistering ? "Sign up to start generating posters" : "Please sign in to your account"}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {isRegistering && (
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Full Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-3 bg-zinc-800/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                  placeholder="Enter your name"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 bg-zinc-800/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                placeholder="name@company.com"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 bg-zinc-800/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                placeholder="Enter your password"
                required
              />
            </div>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-900 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="animate-spin -ml-1 mr-2 h-5 w-5" />
                  {isRegistering ? "Creating account..." : "Signing in..."}
                </>
              ) : (
                isRegistering ? "Sign Up" : "Sign In"
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegistering(!isRegistering);
                setError("");
              }}
              className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {isRegistering 
                ? "Already have an account? Sign In" 
                : "Don't have an account? Register"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
