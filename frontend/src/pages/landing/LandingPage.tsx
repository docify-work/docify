import "./landing.css";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { getDemo } from "@/api/endpoints";
import { Callout } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useAppConfig } from "@/lib/config";
import { oauthErrorMessage } from "@/lib/messages";
import { Architecture } from "./Architecture";
import { FinalCta, Footer, Stats } from "./Closing";
import { Features } from "./Features";
import { useSmoothScroll } from "./motion-utils";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { Marquee } from "./Marquee";
import { Nav } from "./Nav";
import { Product } from "./Product";

/** Marketing landing page: full-bleed, always dark, its own nav + footer (outside PublicLayout). */
export default function LandingPage() {
  usePageMeta([{ label: "Docs that keep up with your code" }]);
  useSmoothScroll();
  const { me } = useMe();
  const cfg = useAppConfig();
  const [params, setParams] = useSearchParams();
  const error = oauthErrorMessage(params.get("error"));
  const demo = useQuery({ queryKey: ["demo"], queryFn: getDemo, staleTime: 300_000, retry: false });
  const demoHref = demo.data?.available && demo.data.workspace_slug ? `/w/${demo.data.workspace_slug}` : null;
  const primaryHref = me ? "/app" : "/signup";
  const primaryLabel = me ? "Open your workspace" : "Connect your GitHub";

  return (
    <div className="landing min-h-dvh">
      <Nav signedIn={Boolean(me)} demoHref={demoHref} />
      {error && (
        <div className="fixed inset-x-0 top-20 z-40 mx-auto w-fit max-w-[92vw]">
          <Callout tone="danger" onDismiss={() => setParams({}, { replace: true })}>
            {error} <Link to="/login" className="underline">Try again</Link>
          </Callout>
        </div>
      )}
      <main id="main">
        <Hero primaryHref={primaryHref} primaryLabel={primaryLabel} demoHref={demoHref} />
        <Marquee />
        <HowItWorks />
        <Product />
        <Stats />
        <Features />
        <Architecture />
        <FinalCta primaryHref={primaryHref} primaryLabel={primaryLabel} demoHref={demoHref} />
      </main>
      <Footer version={`${cfg.env} · ${cfg.version}`} />
    </div>
  );
}
