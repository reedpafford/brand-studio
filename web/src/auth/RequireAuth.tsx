import { Navigate, Outlet } from "react-router-dom";
import { useMe } from "./useMe";

export function RequireAuth() {
  const { data: me, isPending, isError } = useMe();
  if (isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (isError) return <p className="p-6 text-danger">Can't reach the server. Try again in a moment.</p>;
  return me ? <Outlet /> : <Navigate to="/login" replace />;
}
