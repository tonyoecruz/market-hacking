"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import api from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Lock, User, Terminal } from "lucide-react";
import { motion } from "framer-motion";

const schema = z.object({
  username: z.string().min(3, "Username required"),
  password: z.string().min(3, "Password required"),
  email: z.string().email().optional().or(z.literal("")),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isRegister, setIsRegister] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setLoading(true);
    setError("");
    try {
      if (isRegister) {
        // Register Flow
        await api.post("/auth/register", data);
        alert("Account created! You can now login.");
        setIsRegister(false);
        reset();
      } else {
        // Login Flow
        const res = await api.post("/auth/login", data);
        const { token, user } = res.data;
        localStorage.setItem("scope3_token", token);
        localStorage.setItem("scope3_user", JSON.stringify(user));
        router.push("/dashboard");
      }
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Operation failed. Check connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Dynamic Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 50, repeat: Infinity, ease: "linear" }}
          className="absolute -top-[20%] -left-[10%] w-[600px] h-[600px] bg-primary/20 rounded-full blur-[120px]"
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
          className="absolute -bottom-[20%] -right-[10%] w-[500px] h-[500px] bg-secondary/15 rounded-full blur-[100px]"
        />
      </div>

      <GlassCard className="w-full max-w-md relative z-10 border-t border-primary/20">
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-primary/30"
          >
            <Terminal className="w-8 h-8 text-primary" />
          </motion.div>
          <h1 className="text-3xl font-bold text-white tracking-widest uppercase title-font">
            SCOPE<span className="text-primary">3</span>
          </h1>
          <p className="text-xs text-gray-500 font-mono mt-2 tracking-[0.2em] uppercase">
            Terminal Access V15.0
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="relative">
            <div className="absolute left-3 top-9 text-gray-500">
              <User size={18} />
            </div>
            <Input
              label="Codename / User"
              {...register("username")}
              className="pl-10"
              error={errors.username?.message}
              autoComplete="off"
            />
          </div>

          {isRegister && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="relative"
            >
              <div className="absolute left-3 top-9 text-gray-500">
                <User size={18} />
              </div>
              <Input
                label="Email (Optional)"
                {...register("email")}
                className="pl-10"
                error={errors.email?.message}
              />
            </motion.div>
          )}

          <div className="relative">
            <div className="absolute left-3 top-9 text-gray-500">
              <Lock size={18} />
            </div>
            <Input
              label="Secure Key"
              type="password"
              {...register("password")}
              className="pl-10"
              error={errors.password?.message}
            />
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="text-danger text-xs text-center bg-danger/10 py-2 rounded-lg border border-danger/20"
            >
              ⚠️ {error}
            </motion.div>
          )}

          <Button
            type="submit"
            className="w-full"
            isLoading={loading}
            size="lg"
          >
            {isRegister ? "CREATE IDENTITY" : "INITIATE SESSION"}
          </Button>

          <div className="text-center mt-4">
            <button
              type="button"
              onClick={() => { setIsRegister(!isRegister); setError(""); }}
              className="text-xs text-gray-500 hover:text-primary cursor-pointer transition-colors uppercase tracking-widest"
            >
              {isRegister ? "Already have access? Login" : "Request Access Credentials / Register"}
            </button>
          </div>
        </form>
      </GlassCard>
    </div>
  );
}
