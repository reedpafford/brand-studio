import { Navigate, Route, Routes } from "react-router-dom";
import { ApprovalsPage } from "./approvals/ApprovalsPage";
import { RequireAuth } from "./auth/RequireAuth";
import { InvitePage, LoginPage, SetupPage } from "./auth/pages";
import { NewProjectPage } from "./projects/NewProjectPage";
import { ProductionPage } from "./production/ProductionPage";
import { ProjectPage } from "./projects/ProjectPage";
import { ProjectsPage } from "./projects/ProjectsPage";
import { NewScriptPage } from "./scripts/NewScriptPage";
import { ScriptFlowPage } from "./scripts/ScriptFlowPage";
import { ScriptsPage } from "./scripts/ScriptsPage";
import { ClipPage } from "./clip/ClipPage";
import { ItemPage } from "./library/ItemPage";
import { LibraryPage } from "./library/LibraryPage";
import { BrandPage, ToBrand } from "./brand/BrandPage";
import { BrandHome, GoToBrand, Shell } from "./shell/Shell";
import { ToastProvider } from "./toast";
import { TeamPage } from "./team/TeamPage";
import { UsageBrandPage } from "./usage/UsageBrandPage";
import { UsagePage } from "./usage/UsagePage";

export function App() {
  return (
    <ToastProvider>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<GoToBrand />} />
          <Route path="b/:brandId" element={<BrandHome />} />
          <Route path="b/:brandId/scripts" element={<ScriptsPage />} />
          <Route path="b/:brandId/scripts/new" element={<NewScriptPage />} />
          <Route path="b/:brandId/scripts/:scriptId" element={<ScriptFlowPage />} />
          <Route path="b/:brandId/projects" element={<ProjectsPage />} />
          <Route path="b/:brandId/projects/new" element={<NewProjectPage />} />
          <Route path="b/:brandId/projects/:projectId" element={<ProjectPage />} />
          <Route path="b/:brandId/brand" element={<BrandPage />} />
          <Route path="b/:brandId/kit" element={<ToBrand />} />
          <Route path="b/:brandId/screens" element={<ToBrand tab="screens" />} />
          <Route path="b/:brandId/library" element={<Navigate to="characters" replace />} />
          <Route path="b/:brandId/library/:kindSlug" element={<LibraryPage />} />
          <Route path="b/:brandId/library/:kindSlug/:itemId" element={<ItemPage />} />
          <Route path="b/:brandId/clip" element={<ClipPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="production" element={<ProductionPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="usage/brands/:brandId" element={<UsageBrandPage />} />
        </Route>
      </Route>
    </Routes>
    </ToastProvider>
  );
}
