import { Link, useSearchParams } from "react-router-dom";

/** Scripts · Videos under the brand page's title. Scripts is the default; Videos is `?view=videos`. */
export function ViewSwitch() {
  const [params] = useSearchParams();
  const videos = params.get("view") === "videos";
  const seg = (on: boolean) => `grid min-h-control flex-1 place-items-center px-4 font-medium sm:flex-none ${on ? "bg-accent-soft text-accent-text" : "text-muted hover:bg-surface-2"}`;
  return (
    <nav aria-label="View" className="flex w-full overflow-hidden rounded-md border border-border-strong sm:w-fit">
      <Link to="?" aria-current={videos ? undefined : "page"} className={seg(!videos)}>
        Scripts
      </Link>
      <Link to="?view=videos" aria-current={videos ? "page" : undefined} className={seg(videos)}>
        Videos
      </Link>
    </nav>
  );
}
