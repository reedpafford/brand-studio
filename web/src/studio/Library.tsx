import { useParams } from "react-router-dom";
import { CastTab } from "./LibraryCast";
import { FootageTab } from "./LibraryFootage";
import { useTab } from "./libraryParts";
import { ProductTab } from "./LibraryProduct";
import { VoicesTab } from "./LibraryVoices";
import "./studio.css"; // in this order, whichever page the app loads first: the frame's, a video's, then these
import "./video.css"; // the empty box, the rows of ways and the small parts of a dialog are a video's own
import "./library.css";

const TABS = { product: ProductTab, cast: CastTab, footage: FootageTab, voices: VoicesTab };

/** /s/b/:brandId/library: what the brand keeps for every video, in the new look (the redesign, stage 5). Product, Cast,
 *  Footage and Voices, each reading and sending exactly what the current site's Library does, through its hooks.
 *  Nothing is sent without a press. Places, screens and the brand kit stay on the current site. */
export function Library() {
  const brandId = Number(useParams().brandId);
  const [tab] = useTab();
  const Tab = TABS[tab];
  return <Tab key={brandId} brandId={brandId} />;
}
