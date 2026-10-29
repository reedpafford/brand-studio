import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// A full run renders the whole app in many workers at once; a first screen can take over the
// default 1 s to appear there, though it's quick alone. Waits stay waits: this only gives them room.
configure({ asyncUtilTimeout: 5_000 });
