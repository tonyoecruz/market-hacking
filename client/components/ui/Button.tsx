import * as React from "react"
import { Slot } from "@radix-ui/react-slot" // Wait, I didn't install radix slot, I'll stick to standard button
import { cva, type VariantProps } from "class-variance-authority" // Didn't install cva yet. I'll use simple Props.
import { cn } from "@/lib/utils"
import { motion, HTMLMotionProps } from "framer-motion"

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: "primary" | "secondary" | "outline" | "ghost" | "danger"
    size?: "sm" | "md" | "lg"
    isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = "primary", size = "md", isLoading, children, ...props }, ref) => {

        // Base styles
        const baseStyles = "relative inline-flex items-center justify-center rounded-xl font-bold transition-all duration-300 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"

        // Variants
        const variants = {
            primary: "bg-primary text-black hover:bg-white hover:shadow-[0_0_20px_rgba(255,255,255,0.4)] hover:scale-[1.02]",
            secondary: "bg-secondary text-white hover:bg-white hover:text-secondary hover:shadow-[0_0_20px_var(--secondary-glow)]",
            outline: "border-2 border-primary text-primary hover:bg-primary hover:text-black hover:shadow-[0_0_15px_var(--primary-glow)]",
            ghost: "text-gray-400 hover:text-white hover:bg-white/5",
            danger: "bg-danger text-white hover:bg-red-600 hover:shadow-[0_0_20px_rgba(255,0,85,0.4)]"
        }

        // Sizes
        const sizes = {
            sm: "h-8 px-3 text-xs",
            md: "h-11 px-6 text-sm",
            lg: "h-14 px-8 text-base"
        }

        return (
            <motion.button
                whileTap={{ scale: 0.95 }}
                className={cn(baseStyles, variants[variant], sizes[size], className)}
                ref={ref}
                disabled={isLoading || props.disabled}
                {...props}
            >
                {isLoading ? (
                    <span className="mr-2 animate-spin w-4 h-4 border-2 border-current border-t-transparent rounded-full" />
                ) : null}
                {children}
            </motion.button>
        )
    }
)
Button.displayName = "Button"
