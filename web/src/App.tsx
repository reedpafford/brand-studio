import { Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { InvitePage, LoginPage, SetupPage } from "./auth/pages";
import { useMe } from "./auth/useMe";

function Home() {
  const { data: me } = useMe();
  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Brand Studio</h1>
      <p className="text-muted">Signed in as {me?.name}.</p>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route element={<RequireAuth />}>
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}
