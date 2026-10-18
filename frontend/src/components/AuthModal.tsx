"use client";

import React, { useState } from "react";
import {
  X,
  Lock,
  Mail,
  User as UserIcon,
  ShieldCheck,
  AlertCircle,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { User } from "../types";
import { signupUser, loginUser } from "../lib/api";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: User) => void;
  initialTab?: "login" | "signup";
}

export function AuthModal({
  isOpen,
  onClose,
  onAuthSuccess,
  initialTab = "login",
}: AuthModalProps) {
  const [tab, setTab] = useState<"login" | "signup">(initialTab);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setErrorMessage("Please enter a valid email address.");
      return;
    }

    if (tab === "signup") {
      if (!name.trim()) {
        setErrorMessage("Please enter your display name.");
        return;
      }
      if (!password || password.length < 6) {
        setErrorMessage("Password must be at least 6 characters long.");
        return;
      }
    }

    setIsLoading(true);
    try {
      if (tab === "signup") {
        const res = await signupUser(name.trim(), cleanEmail, password);
        onAuthSuccess(res.user);
        onClose();
      } else {
        const res = await loginUser(cleanEmail, password.trim() || undefined);
        onAuthSuccess(res.user);
        onClose();
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "Authentication failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-50 via-white to-blue-50/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#1678ef]/10 flex items-center justify-center text-[#1678ef] shadow-xs">
              <Lock className="w-5 h-5 text-[#1678ef]" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#102f58]">
                {tab === "login" ? "Sign In to GraphOS" : "Create GraphOS Account"}
              </h3>
              <p className="text-xs text-[#71849e]">
                {tab === "login"
                  ? "Enter your stored email to access your persistent investigations and graphs"
                  : "Dedicated tenant graph storage with Argon2 encryption"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-600 transition cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Toggle */}
        <div className="flex border-b border-slate-100 px-6 bg-slate-50/50">
          <button
            type="button"
            onClick={() => {
              setTab("login");
              setErrorMessage(null);
            }}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition cursor-pointer ${
              tab === "login"
                ? "border-[#1678ef] text-[#1678ef]"
                : "border-transparent text-[#71849e] hover:text-[#102f58]"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setTab("signup");
              setErrorMessage(null);
            }}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition cursor-pointer ${
              tab === "signup"
                ? "border-[#1678ef] text-[#1678ef]"
                : "border-transparent text-[#71849e] hover:text-[#102f58]"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMessage && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex flex-col gap-1.5 animate-in fade-in">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                <span className="flex-1">{errorMessage}</span>
              </div>
              {tab === "login" && errorMessage.toLowerCase().includes("no account found") && (
                <button
                  type="button"
                  onClick={() => {
                    setTab("signup");
                    setErrorMessage(null);
                  }}
                  className="text-left text-[11px] font-semibold text-[#1678ef] hover:underline pl-6 cursor-pointer"
                >
                  Need an account? Click here to register with this email →
                </button>
              )}
            </div>
          )}

          {tab === "signup" && (
            <div>
              <label className="block text-xs font-semibold text-[#102f58] mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#71849e]">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Sarah Connor"
                  className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-xs text-[#102f58] placeholder-[#71849e]/60 focus:outline-none focus:border-[#1678ef] focus:ring-1 focus:ring-[#1678ef] bg-white transition"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-[#102f58] mb-1.5">
              {tab === "login" ? "Registered Email Address" : "Email Address"}
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#71849e]">
                <Mail className="w-4 h-4" />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={tab === "login" ? "Enter your stored email (e.g. jheelpashine2006@gmail.com)" : "analyst@enterprise.com"}
                className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-xs text-[#102f58] placeholder-[#71849e]/60 focus:outline-none focus:border-[#1678ef] focus:ring-1 focus:ring-[#1678ef] bg-white transition"
              />
            </div>
            {tab === "login" && (
              <p className="text-[10px] text-[#71849e] mt-1">
                We will look up your stored email in the database to sign you in.
              </p>
            )}
          </div>

          {tab === "signup" && (
            <div>
              <label className="block text-xs font-semibold text-[#102f58] mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#71849e]">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-xs text-[#102f58] placeholder-[#71849e]/60 focus:outline-none focus:border-[#1678ef] focus:ring-1 focus:ring-[#1678ef] bg-white transition"
                />
              </div>
              <p className="text-[10px] text-[#71849e] mt-1">
                Passwords are encrypted via Argon2id before storage in FalkorDB.
              </p>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-[#1678ef] to-[#0ea5e9] hover:brightness-110 shadow-md shadow-blue-500/20 transition transform hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer mt-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Checking Database...</span>
              </>
            ) : tab === "signup" ? (
              <>
                <span>Create Account</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            ) : (
              <>
                <span>Sign In with Stored Email</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>

          {/* Security Guarantee Pill */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-center gap-1.5 text-[10px] text-[#71849e]">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>FalkorDB graphos_auth · Isolated tenant sessions</span>
          </div>
        </form>
      </div>
    </div>
  );
}
