import { cn } from "@/lib/utils";
import { motion, HTMLMotionProps } from "framer-motion";
import React from "react";

interface GlassCardProps extends HTMLMotionProps<"div"> {
    children: React.ReactNode;
    className?: string;
    noPadding?: boolean;
}

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
    ({ children, className, noPadding = false, ...props }, ref) => {
        return (
            <motion.div
                ref={ref}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className={cn(
                    "glass-card overflow-hidden",
                    noPadding ? "p-0" : "p-6",
                    className
                )}
                {...props}
            >
                {children}
            </motion.div>
        );
    }
);
GlassCard.displayName = "GlassCard";
