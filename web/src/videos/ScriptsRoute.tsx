import { Navigate, useSearchParams } from "react-router-dom";
import { ScriptsPage } from "../scripts/ScriptsPage";

/** The brand's scripts. Videos had been a view here (`?view=videos`); it is its own section now, and old links land there. */
export function ScriptsRoute() {
  const [params] = useSearchParams();
  if (params.get("view") !== "videos") return <ScriptsPage />;
  const rest = new URLSearchParams(params); // a copy: the router's own params must not change during render
  rest.delete("view");
  const q = rest.toString();
  return <Navigate to={`../videos${q ? `?${q}` : ""}`} relative="path" replace />;
}
