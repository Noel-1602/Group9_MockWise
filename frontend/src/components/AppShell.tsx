import React from "react";

interface AppShellProps {
  children: React.ReactNode;
  size?: "2xl" | "3xl" | "full" | "default";
  className?: string;
}

export function AppShell({
  children,
  size = "default",
  className = "",
}: AppShellProps) {
  const maxWidthClass =
    size === "2xl"
      ? "max-w-2xl"
      : size === "3xl"
      ? "max-w-3xl"
      : size === "full"
      ? "max-w-full"
      : "max-w-3xl";

  return (
    <div className={`mx-auto w-full ${maxWidthClass} ${className}`}>
      {children}
    </div>
  );
}

export default AppShell;
