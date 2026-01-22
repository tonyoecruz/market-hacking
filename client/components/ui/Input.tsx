import * as React from "react"
import { cn } from "@/lib/utils"

export interface InputProps
    extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string
    error?: string
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
    ({ className, type, label, error, ...props }, ref) => {
        return (
            <div className="w-full">
                {label && (
                    <label className="block text-xs font-bold text-gray-400 mb-1.5 ml-1 uppercase tracking-wider">
                        {label}
                    </label>
                )}
                <input
                    type={type}
                    className={cn(
                        "flex h-11 w-full rounded-xl border border-white/10 bg-black/20 px-4 py-2 text-sm text-white placeholder:text-gray-600 focus:border-primary focus:bg-black/40 focus:outline-none focus:ring-1 focus:ring-primary transition-all duration-300",
                        error && "border-danger focus:border-danger focus:ring-danger",
                        className
                    )}
                    ref={ref}
                    {...props}
                />
                {error && (
                    <p className="mt-1 ml-1 text-xs text-danger font-medium">{error}</p>
                )}
            </div>
        )
    }
)
Input.displayName = "Input"

export { Input }
