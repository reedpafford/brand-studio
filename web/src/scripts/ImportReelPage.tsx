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
      <PageTop title="Import a reel">
        <Link to={scripts} className={buttonClass("ghost")}>
          Cancel
        </Link>
      </PageTop>
      <div className="sm:px-2">
        <ReelPicker brandId={brandId} brandName={brand?.name} />
      </div>
    </main>
  );
}
