import { ChevronLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { ReelPicker } from "./ReelImport";

/** Import a reel: a link or a video file. The script is made at once and opens on its Script screen while the reel is prepared. */
export function ImportReelPage() {
  const brandId = Number(useParams().brandId);
  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-8">
      <Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense">
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        Scripts
      </Link>
      <h1 className="type-page">Import a reel</h1>
      <ReelPicker brandId={brandId} />
    </main>
  );
}
