import { Route, Routes } from "react-router-dom";

function Home() {
  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Brand Studio</h1>
      <p className="text-neutral-600">Sign-in comes next.</p>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
