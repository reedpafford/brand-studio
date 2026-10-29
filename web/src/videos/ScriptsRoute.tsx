import { Navigate, useSearchParams } from "react-router-dom";
import { ScriptsPage } from "../scripts/ScriptsPage";

/** The brand's scripts. Videos had been a view here (`?view=videos`); it is its own section now, and old links land there. */
export function ScriptsRoute() {
  const [params] = useSearchParams();
  if (params.get("view") !== "videos") return <ScriptsPage />;
  params.delete("view");
  const rest = params.toString();
  return <Navigate to={`../videos${rest ? `?${rest}` : ""}`} relative="path" replace />;
}
