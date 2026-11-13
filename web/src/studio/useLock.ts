import { useEffect, useRef } from "react";

/** One paid press, one request, however fast it is pressed again. The returned `lock(send)` runs `send` unless the
 *  last one it ran is still in flight; `send` is handed `done`, to call when its request settles (a mutation's
 *  `onSettled`). The mark is a ref, set before the request goes out, so two clicks that land before the page has
 *  drawn the first as in flight are still one request (as New video's Make it does). Presses that share one lock
 *  wait on each other. `busy`: the request as the page draws it; once that is seen to end the lock opens as well, so
 *  a request whose `done` never comes (another press on the same hook took its place) can't hold it shut. */
export function useLock(busy: boolean) {
  const flying = useRef(false);
  useEffect(() => {
    if (!busy) flying.current = false;
  }, [busy]);
  return (send: (done: () => void) => void) => {
    if (flying.current) return;
    flying.current = true;
    send(() => (flying.current = false));
  };
}
