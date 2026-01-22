"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import api from "@/lib/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend } from "recharts";
import { Trash2, Plus, TrendingUp, DollarSign, Wallet } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// --- TYPES ---
interface Asset {
    ticker: string;
    quantity: number;
    avg_price: number;
    last_updated_at: string;
    // Calculated frontend fields
    current_price?: number;
    total_value?: number;
    profit?: number;
}

// --- MOCK DATA FOR CHARTS (Until we fetch real prices) ---
const COLORS = ['#00f3ff', '#bc13fe', '#00ff41', '#ff0055', '#ffd700'];

export default function Dashboard() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const [user, setUser] = useState<any>(null);

    // Auth Check
    useEffect(() => {
        const token = localStorage.getItem("scope3_token");
        if (!token) { router.push("/"); return; }
        const userData = localStorage.getItem("scope3_user");
        if (userData) setUser(JSON.parse(userData));
    }, [router]);

    // --- QUERIES ---
    const { data: assets = [], isLoading } = useQuery({
        queryKey: ['portfolio'],
        queryFn: async () => {
            const res = await api.get("/portfolio");
            // Basic simulation of "Current Price" = Avg Price * Random Variation (Just for demo visual)
            // In real app, we would fetch live prices here.
            return res.data.map((a: Asset) => ({
                ...a,
                current_price: a.avg_price, // Placeholder
                total_value: a.quantity * a.avg_price
            }));
        }
    });

    // --- MUTATIONS ---
    const deleteMutation = useMutation({
        mutationFn: async (ticker: string) => {
            await api.delete(`/portfolio/${ticker}`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['portfolio'] });
        }
    });

    // --- AGGREGATIONS ---
    const totalEquity = assets.reduce((acc: number, cur: Asset) => acc + (cur.total_value || 0), 0);

    // Group by Asset Class (Naïve implementation based on Ticker suffix for now)
    const allocationDaTa = assets.reduce((acc: any[], cur: Asset) => {
        const type = cur.ticker.endsWith("11") ? "FIIs/ETFs" : "AÇÕES";
        const existing = acc.find(x => x.name === type);
        if (existing) existing.value += cur.total_value;
        else acc.push({ name: type, value: cur.total_value });
        return acc;
    }, []);

    if (!user) return <div className="min-h-screen flex items-center justify-center text-primary animate-pulse">CONNECTING...</div>;

    return (
        <div className="min-h-screen p-4 md:p-8 pb-20">
            {/* HEADER */}
            <header className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white tracking-widest title-font">
                        SCOPE<span className="text-primary">3</span> <span className="text-sm text-gray-500 font-mono ml-2">V15.0</span>
                    </h1>
                    <p className="text-xs text-gray-500 font-mono mt-1">COMMANDER: {user.username.toUpperCase()}</p>
                </div>
                <div className="flex gap-4">
                    <Button variant="outline" size="sm" onClick={() => { localStorage.clear(); router.push('/') }}>
                        TERMINATE SESSION
                    </Button>
                </div>
            </header>

            {/* KPI GRID */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <GlassCard className="relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <Wallet size={64} />
                    </div>
                    <span className="text-xs text-gray-400 font-mono mb-1 block">TOTAL EQUITY</span>
                    <span className="text-4xl font-bold text-white neon-text">
                        {totalEquity.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </span>
                    <div className="flex items-center gap-2 mt-2">
                        <span className="text-xs text-success bg-success/10 px-2 py-0.5 rounded flex items-center gap-1">
                            <TrendingUp size={12} /> +0.00%
                        </span>
                        <span className="text-xs text-gray-500">24H VARIATION</span>
                    </div>
                </GlassCard>

                <GlassCard className="flex flex-col justify-center">
                    <span className="text-xs text-gray-400 font-mono mb-2">ALLOCATION</span>
                    <div className="h-24 w-full relative">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={allocationDaTa.length > 0 ? allocationDaTa : [{ name: 'Empty', value: 1 }]}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={35}
                                    outerRadius={50}
                                    paddingAngle={5}
                                    dataKey="value"
                                    stroke="none"
                                >
                                    {allocationDaTa.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                    {allocationDaTa.length === 0 && <Cell fill="#333" />}
                                </Pie>
                                <RechartsTooltip
                                    contentStyle={{ backgroundColor: '#050510', borderColor: '#333', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                        {/* Center Text */}
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <span className="text-xs font-bold text-gray-500">{assets.length} ASSETS</span>
                        </div>
                    </div>
                </GlassCard>

                <GlassCard className="flex flex-col justify-center items-center gap-4 border-dashed border-2 border-white/5 bg-transparent hover:bg-white/5 cursor-pointer transition-colors group">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                        <Plus className="text-primary" />
                    </div>
                    <span className="text-sm font-bold text-primary">ADD NEW ASSET</span>
                </GlassCard>
            </div>

            {/* ASSETS TABLE */}
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <span className="w-1 h-6 bg-secondary rounded-full"></span>
                PORTFOLIO COMPOSITION
            </h2>

            <GlassCard className="overflow-x-auto" noPadding>
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-white/10 bg-white/5">
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Ticker</th>
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-right">Qty</th>
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-right">Avg Price</th>
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-right">Total Value</th>
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <AnimatePresence>
                            {assets.map((asset: Asset) => (
                                <motion.tr
                                    key={asset.ticker}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: 20 }}
                                    className="border-b border-white/5 hover:bg-white/5 transition-colors group"
                                >
                                    <td className="p-4">
                                        <span className="font-bold text-white">{asset.ticker}</span>
                                    </td>
                                    <td className="p-4 text-right text-gray-300">{asset.quantity}</td>
                                    <td className="p-4 text-right text-gray-300">
                                        {asset.avg_price.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </td>
                                    <td className="p-4 text-right font-bold text-primary neon-text">
                                        {asset.total_value?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </td>
                                    <td className="p-4 text-right">
                                        <button
                                            onClick={() => {
                                                if (confirm(`Delete ${asset.ticker}?`)) deleteMutation.mutate(asset.ticker)
                                            }}
                                            className="text-gray-600 hover:text-danger p-2 transition-colors"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </td>
                                </motion.tr>
                            ))}
                        </AnimatePresence>

                        {assets.length === 0 && !isLoading && (
                            <tr>
                                <td colSpan={5} className="p-8 text-center text-gray-500">
                                    NO ASSETS DETECTED. CLICK "ADD NEW ASSET" TO START.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </GlassCard>
        </div>
    );
}
