import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { NeedsYouPage } from "./approvals/NeedsYouPage";
import { RequireAuth } from "./auth/RequireAuth";
import { InvitePage, LoginPage, SetupPage } from "./auth/pages";
import { NewProjectPage } from "./projects/NewProjectPage";
import { ProductionPage } from "./production/ProductionPage";
import { VideoRoute } from "./videos/VideoChat";
import { HomePage } from "./home/HomePage";
import { ImportReelPage } from "./scripts/ImportReelPage";
import { ScriptFlowPage } from "./scripts/ScriptFlowPage";
import { NewScriptPage } from "./scripts/NewScriptButton";
import { ScriptsRoute } from "./videos/ScriptsRoute";
import { LibraryList, MoreList } from "./shell/PhoneLists";
import { MyRequestsPage } from "./approvals/MyRequestsPage";
import { FolderPage } from "./videos/FolderPage";
import { MediaPage } from "./media/MediaPage";
import { MediaItemPage } from "./media/MediaItemPage";
import { FreestylePage, ToNewVideo } from "./freestyle/FreestylePage";
import { ItemPage } from "./library/ItemPage";
import { LibraryPage } from "./library/LibraryPage";
import { BrandKit, ToBrand } from "./brand/BrandKit";
import { GoToBrand, Shell } from "./shell/Shell";
import { ToastProvider } from "./toast";
import { TeamPage } from "./team/TeamPage";
import { SettingsPage } from "./settings/SettingsPage";
import { NewBrandPage } from "./shell/NewBrand";
import { UsageBrandPage } from "./usage/UsageBrandPage";
import { MinePage } from "./usage/MinePage";
import { UsagePage } from "./usage/UsagePage";
import { ReelReviewPage } from "./scripts/ReelReviewPage";
import { BrandSetup } from "./studio/BrandSetup";
import { Library } from "./studio/Library";
import { NewVideo } from "./studio/NewVideo";
import { Settings } from "./studio/Settings";
import { Spend } from "./studio/Spend";
import { StudioShell } from "./studio/StudioShell";
import { Video } from "./studio/Video";
import { Videos } from "./studio/Videos";

export function App() {
  return (
    <ToastProvider>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route element={<RequireAuth />}>
        {/* The new look (the redesign): where "/" opens for the owner. The current screens are still beside it. */}
        <Route path="s" element={<StudioShell />}>
          <Route index element={<GoToBrand studio />} />
          <Route path="b/:brandId" element={<NewVideo />} />
          <Route path="b/:brandId/videos" element={<Videos />} />
          <Route path="b/:brandId/videos/:projectId" element={<Video />} />
          <Route path="b/:brandId/library" element={<Library />} />
          <Route path="b/:brandId/spend" element={<Spend />} />
          <Route path="b/:brandId/setup" element={<BrandSetup />} />
          <Route path="brands/new" element={<BrandSetup />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route element={<Shell />}>
          <Route index element={<GoToBrand />} />
          <Route path="b/:brandId" element={<HomePage />} />
          <Route path="b/:brandId/scripts" element={<ScriptsRoute />} />
          <Route path="b/:brandId/scripts/import" element={<ImportReelPage />} />
          <Route path="b/:brandId/scripts/new" element={<NewScriptPage />} />
          <Route path="b/:brandId/scripts/:scriptId" element={<ScriptFlowPage />} />
          <Route path="b/:brandId/scripts/:scriptId/reel" element={<ReelReviewPage />} />
          <Route path="b/:brandId/projects" element={<Navigate to="../videos" relative="path" replace />} />
          <Route path="b/:brandId/projects/new" element={<NewProjectPage />} />
          <Route path="b/:brandId/projects/:projectId" element={<ToVideo />} />
          <Route path="b/:brandId/videos" element={<FolderPage />} />
          <Route path="b/:brandId/videos/new" element={<HomePage />} />
          <Route path="b/:brandId/videos/:projectId" element={<VideoRoute />} />
          <Route path="b/:brandId/brand" element={<BrandKit />} />
          <Route path="b/:brandId/kit" element={<ToBrand />} />
          <Route path="b/:brandId/screens" element={<ToBrand />} />
          <Route path="b/:brandId/library" element={<Navigate to="characters" replace />} />
          <Route path="b/:brandId/library/:kindSlug" element={<LibraryPage />} />
          <Route path="b/:brandId/library/:kindSlug/:itemId" element={<ItemPage />} />
          <Route path="b/:brandId/clip" element={<Navigate to="../videos/new" relative="path" replace />} />
          <Route path="b/:brandId/media" element={<MediaPage />} />
          <Route path="b/:brandId/more/library" element={<LibraryList />} />
          <Route path="more" element={<MoreList />} />
          <Route path="requests" element={<MyRequestsPage />} />
          <Route path="b/:brandId/media/:key" element={<MediaItemPage />} />
          <Route path="brands/new" element={<NewBrandPage />} />
          <Route path="freestyle" element={<ToNewVideo />} />
          <Route path="freestyle/:freestyleId" element={<FreestylePage />} />
          <Route path="b/:brandId/freestyle/:freestyleId" element={<FreestylePage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="looks" element={<Navigate to="/settings?tab=looks" replace />} />
          <Route path="languages" element={<Navigate to="/settings?tab=languages" replace />} />
          {/* Needs you keeps the old address, so links to one request (/approvals?job=ID) still land on it. */}
          <Route path="approvals" element={<NeedsYouPage />} />
          <Route path="production" element={<ProductionPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="usage/mine" element={<MinePage />} />
          <Route path="usage/brands/:brandId" element={<UsageBrandPage />} />
        </Route>
      </Route>
    </Routes>
    </ToastProvider>
  );
}

/** The old step-by-step video page's address opens the video page (v6 S3); its ?step= opens the matching tab. */
function ToVideo() {
  const { brandId, projectId } = useParams();
  const { search } = useLocation();
  return <Navigate to={`/b/${brandId}/videos/${projectId}${search}`} replace />;
}
