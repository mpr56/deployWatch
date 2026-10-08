// A link to an editing screen. Visitors get the auth gate instead.

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../lib/auth";

export function EditLink({
  to,
  className,
  children,
}: {
  to: string;
  className?: string;
  children: ReactNode;
}) {
  const { canEdit, openGate } = useAuth();
  if (canEdit) {
    return (
      <Link to={to} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" className={className} onClick={openGate}>
      {children}
    </button>
  );
}
