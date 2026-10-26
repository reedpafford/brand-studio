import { useSearchParams } from "react-router-dom";
import { ScriptsPage } from "../scripts/ScriptsPage";
import { VideosPage } from "./VideosPage";

/** The brand's home: its scripts, or (`?view=videos`) its videos. */
export function ScriptsRoute() {
  const [params] = useSearchParams();
  return params.get("view") === "videos" ? <VideosPage /> : <ScriptsPage />;
}
