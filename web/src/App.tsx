import { Navigate, Route, Routes } from "react-router-dom";
import { ApprovalsPage } from "./approvals/ApprovalsPage";
import { RequireAuth } from "./auth/RequireAuth";
import { InvitePage, LoginPage, SetupPage } from "./auth/pages";
import { NewProjectPage } from "./projects/NewProjectPage";
import { ProductionPage } from "./production/ProductionPage";
import { ProjectPage } from "./projects/ProjectPage";
import { VideoPage } from "./projects/VideoPage";
import { ImportReelPage } from "./scripts/ImportReelPage";
import { ScriptFlowPage } from "./scripts/ScriptFlowPage";
import { ScriptsRoute } from "./videos/ScriptsRoute";
import { VideosPage } from "./videos/VideosPage";
import { MediaPage } from "./media/MediaPage";
import { ClipPage } from "./clip/ClipPage";
import { ItemPage } from "./library/ItemPage";
import { LibraryPage } from "./library/LibraryPage";
import { BrandPage, ToBrand } from "./brand/BrandPage";
import { BrandHome, GoToBrand, Shell } from "./shell/Shell";
import { ToastProvider } from "./toast";
import { TeamPage } from "./team/TeamPage";
import { LooksPage } from "./looks/LooksPage";
import { UsageBrandPage } from "./usage/UsageBrandPage";
import { UsagePage } from "./usage/UsagePage";
import { ReelReviewPage } from "./scripts/ReelReviewPage";

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
          <Route path="b/:brandId/scripts" element={<ScriptsRoute />} />
          <Route path="b/:brandId/scripts/import" element={<ImportReelPage />} />
          <Route path="b/:brandId/scripts/new" element={<Navigate to=".." relative="path" replace />} />
          <Route path="b/:brandId/scripts/:scriptId" element={<ScriptFlowPage />} />
          <Route path="b/:brandId/scripts/:scriptId/reel" element={<ReelReviewPage />} />
          <Route path="b/:brandId/projects" element={<Navigate to="../videos" relative="path" replace />} />
          <Route path="b/:brandId/projects/new" element={<NewProjectPage />} />
          <Route path="b/:brandId/projects/:projectId" element={<ProjectPage />} />
          <Route path="b/:brandId/videos" element={<VideosPage />} />
          <Route path="b/:brandId/videos/:projectId" element={<VideoPage />} />
          <Route path="b/:brandId/brand" element={<BrandPage />} />
          <Route path="b/:brandId/kit" element={<ToBrand />} />
          <Route path="b/:brandId/screens" element={<ToBrand tab="screens" />} />
          <Route path="b/:brandId/library" element={<Navigate to="characters" replace />} />
          <Route path="b/:brandId/library/:kindSlug" element={<LibraryPage />} />
          <Route path="b/:brandId/library/:kindSlug/:itemId" element={<ItemPage />} />
          <Route path="b/:brandId/clip" element={<ClipPage />} />
          <Route path="b/:brandId/media" element={<MediaPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="looks" element={<LooksPage />} />
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
