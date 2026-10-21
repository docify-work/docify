import { useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router";
import { loginUrl, setUnauthorizedHandler } from "@/api/client";
import { qk } from "@/api/endpoints";
import { RequireAdmin, RequireAuth, RequireMember } from "@/components/Guards";
import { AppShell } from "@/components/layout/AppShell";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { WorkspaceLayout } from "@/components/layout/WorkspaceLayout";
import { SleepingBanner } from "@/components/SleepingBanner";
import { useThemeSync } from "@/lib/theme";

// Route-level code splitting: every page is its own chunk (chat/markdown stay out of the entry bundle).
const Landing = lazy(() => import("@/pages/landing/LandingPage"));
const Login = lazy(() => import("@/pages/auth/Login"));
const Signup = lazy(() => import("@/pages/auth/Signup"));
const VerifyEmail = lazy(() => import("@/pages/auth/VerifyEmail"));
const ForgotPassword = lazy(() => import("@/pages/auth/ForgotPassword"));
const ResetPassword = lazy(() => import("@/pages/auth/ResetPassword"));
const Invite = lazy(() => import("@/pages/auth/Invite"));
const Privacy = lazy(() => import("@/pages/Privacy"));
const NotFound = lazy(() => import("@/pages/NotFound"));
const Home = lazy(() => import("@/pages/Home"));
const CreateWorkspace = lazy(() => import("@/pages/CreateWorkspace"));
const Account = lazy(() => import("@/pages/Account"));
const Dashboard = lazy(() => import("@/pages/workspace/Dashboard"));
const Repos = lazy(() => import("@/pages/workspace/Repos"));
const RepoDetail = lazy(() => import("@/pages/workspace/RepoDetail"));
const DocPage = lazy(() => import("@/pages/workspace/DocPage"));
const Changelog = lazy(() => import("@/pages/workspace/Changelog"));
const Search = lazy(() => import("@/pages/workspace/Search"));
const Chat = lazy(() => import("@/pages/workspace/Chat"));
const Jobs = lazy(() => import("@/pages/workspace/Jobs"));
const Review = lazy(() => import("@/pages/workspace/Review"));
const Settings = lazy(() => import("@/pages/workspace/Settings"));
const Members = lazy(() => import("@/pages/workspace/Members"));
const DemoRedirect = lazy(() => import("@/pages/DemoRedirect"));
const UiGallery = import.meta.env.DEV ? lazy(() => import("@/pages/dev/UiGallery")) : null;

/** Routes 401s from the API client through the router (and forgets the cached user). */
function UnauthorizedRedirector() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  useEffect(
    () =>
      setUnauthorizedHandler((next) => {
        qc.setQueryData(qk.me, null);
        navigate(loginUrl(next), { replace: true });
      }),
    [navigate, qc],
  );
  return null;
}

export default function App() {
  const location = useLocation();
  useThemeSync(location.pathname);
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:rounded-md focus:bg-surface focus:px-3 focus:py-1.5 focus:shadow-md"
      >
        Skip to content
      </a>
      {/* The landing page works without the backend, so it never shows the banner. */}
      {location.pathname !== "/" && <SleepingBanner />}
      <UnauthorizedRedirector />
      <Routes>
        {/* The landing page is full-bleed with its own nav/footer. */}
        <Route
          index
          element={
            <Suspense fallback={<div className="min-h-dvh bg-[#fbfbfd]" />}>
              <Landing />
            </Suspense>
          }
        />
        <Route element={<PublicLayout />}>
          <Route path="login" element={<Login />} />
          <Route path="signup" element={<Signup />} />
          <Route path="verify-email" element={<VerifyEmail />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="invite/:token" element={<Invite />} />
          <Route path="privacy" element={<Privacy />} />
          <Route path="demo" element={<DemoRedirect />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        <Route element={<AppShell />}>
          <Route path="app" element={<RequireAuth><Home /></RequireAuth>} />
          <Route path="new" element={<RequireAuth><CreateWorkspace /></RequireAuth>} />
          <Route path="account" element={<RequireAuth><Account /></RequireAuth>} />
          <Route path="w/:ws" element={<WorkspaceLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="repos" element={<Repos />} />
            <Route path="repos/:repoId" element={<RepoDetail />} />
            <Route path="docs/:docId" element={<DocPage />} />
            <Route path="changelog/:repoId" element={<Changelog />} />
            <Route path="search" element={<Search />} />
            <Route path="chat" element={<Chat />} />
            <Route path="jobs" element={<RequireMember><Jobs /></RequireMember>} />
            <Route path="members" element={<RequireMember><Members /></RequireMember>} />
            <Route path="review" element={<RequireAdmin><Review /></RequireAdmin>} />
            <Route path="settings" element={<RequireAdmin><Settings /></RequireAdmin>} />
            <Route path="*" element={<NotFound inline />} />
          </Route>
          {UiGallery && <Route path="dev/ui" element={<UiGallery />} />}
        </Route>
      </Routes>
    </div>
  );
}
