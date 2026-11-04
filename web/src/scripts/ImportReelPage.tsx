import { Link, useParams } from "react-router-dom";
import { PageTop, buttonClass } from "../components";
import { useBrands } from "../shell/useBrands";
import { ReelPicker } from "./ReelImport";

/** Import a reel (v5 G_ImportReel): a link or a video file. The script is made at once and opens on its Script screen while the reel is prepared. */
export function ImportReelPage() {
  const brandId = Number(useParams().brandId);
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const scripts = `/b/${brandId}/scripts`;
  return (
    <main className="space-y-6 p-4 sm:p-6">
      <PageTop title="Import a reel" crumb={{ to: scripts, label: "Scripts" }}>
        <Link to={scripts} className={buttonClass("ghost")}>
          Cancel
        </Link>
      </PageTop>
      {/* v5 G_ImportReel: the page's own heading above the intro line, under the bar's "Scripts › Import a reel". */}
      <div className="space-y-2 sm:px-2">
        <h2 className="text-xl font-semibold">Import a reel</h2>
        <ReelPicker brandId={brandId} brandName={brand?.name} />
      </div>
    </main>
  );
}
