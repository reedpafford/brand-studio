import { Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { InvitePage, LoginPage, SetupPage } from "./auth/pages";
import { KitPage } from "./brand/KitPage";
import { ScreensPage } from "./brand/ScreensPage";
import { BrandHome, GoToBrand, Shell } from "./shell/Shell";
import { TeamPage } from "./team/TeamPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<GoToBrand />} />
          <Route path="b/:brandId" element={<BrandHome />} />
          <Route path="b/:brandId/kit" element={<KitPage />} />
          <Route path="b/:brandId/screens" element={<ScreensPage />} />
          <Route path="team" element={<TeamPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
