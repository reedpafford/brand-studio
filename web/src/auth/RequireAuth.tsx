import { Navigate, Outlet } from "react-router-dom";
import { Banner, Button } from "../components";
import { useMe } from "./useMe";

export function RequireAuth() {
  const { data: me, isPending, isError, isFetching, refetch } = useMe();
  if (isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (isError)
    return (
      <div className="mx-auto max-w-content p-4 sm:p-8">
        <Banner
          title="Can't reach the server."
          action={
            <Button variant="secondary" busy={isFetching} onClick={() => refetch()}>
              Try again
            </Button>
          }
        >
          Nothing was lost. It usually clears in a moment.
        </Banner>
      </div>
    );
  return me ? <Outlet /> : <Navigate to="/login" replace />;
}
