import { Fragment, useState, type ReactNode } from "react";
import { Search } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Dialog } from "./Dialog";

export type Hit = { group: string; label: string; to: string; lead: ReactNode; note?: string; /** something to do on the way (leaving the new look) */ onPick?: () => void };

/** Search or jump (⌘K, the rail's button, the phone's Search tab): the places to go and the brand's videos, narrowed
 *  as you type. ↑↓ move, Enter opens the marked one, Esc closes. */
export function Jump({ hits, onClose }: { hits: Hit[]; onClose: () => void }) {
  const [text, setText] = useState("");
  const [at, setAt] = useState(0);
  const navigate = useNavigate();
  const shown = hits.filter((h) => h.label.toLowerCase().includes(text.trim().toLowerCase()));
  const pick = (h: Hit) => {
    h.onPick?.();
    onClose();
  };
  return (
    <Dialog
      title="Search or jump"
      onClose={onClose}
      onConfirm={() => {
        const h = shown[at];
        if (!h) return;
        pick(h);
        navigate(h.to);
      }}
    >
      <label>
        <Search size={16} strokeWidth={1.75} aria-hidden />
        <input
          data-autofocus
          aria-label="Search or jump"
          placeholder="Search videos, or type where you want to go"
          autoComplete="off"
          value={text}
          onChange={(e) => (setText(e.target.value), setAt(0))}
          onKeyDown={(e) => {
            if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
            e.preventDefault();
            setAt(Math.max(0, Math.min(shown.length - 1, at + (e.key === "ArrowDown" ? 1 : -1))));
          }}
        />
      </label>
      <nav aria-label="Results">
        {shown.map((h, n) => (
          <Fragment key={`${h.group} ${h.to}`}>
            {h.group !== shown[n - 1]?.group && <h6>{h.group}</h6>}
            <Link to={h.to} aria-current={n === at ? "true" : undefined} ref={n === at ? (a) => a?.scrollIntoView?.({ block: "nearest" }) : undefined} onMouseEnter={() => setAt(n)} onClick={() => pick(h)}>
              {h.lead}
              <span className="clip">{h.label}</span>
              {h.note && <small>{h.note}</small>}
            </Link>
          </Fragment>
        ))}
        {shown.length === 0 && <p className="none">Nothing matches.</p>}
      </nav>
    </Dialog>
  );
}
