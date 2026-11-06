import { Component, type ReactNode } from "react";
import { Button } from "../components";

/** One tab of the video's preview (S3): if it breaks on data it can't read, the page and the other tabs stay, and the tab
 *  says so with a way on (rule 22), never the whole page's error. */
export class PaneBoundary extends Component<{ tab: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error(`The ${this.props.tab} tab couldn't show this video`, error); // which tab, for whoever reads the console
  }

  componentDidUpdate(before: { tab: string }) {
    if (before.tab !== this.props.tab && this.state.failed) this.setState({ failed: false }); // another tab: try afresh
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
        <p className="text-lg font-semibold">This tab couldn’t show this video</p>
        <p className="max-w-[340px] text-sm text-muted">Nothing is lost: the other tabs and the chat still work. Try it again, or tell the director in the chat what you need.</p>
        <Button variant="secondary" onClick={() => this.setState({ failed: false })}>
          Try again
        </Button>
      </div>
    );
  }
}
