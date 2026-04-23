import { MarketingNav } from "@/components/marketing/marketing-nav";
import { Hero } from "@/components/marketing/hero";
import { StackSection } from "@/components/marketing/stack-section";
import { CapabilitiesCarousel } from "@/components/marketing/capabilities-carousel";
import { LatestReleases } from "@/components/marketing/latest-releases";
import { UpcomingFeatures } from "@/components/marketing/upcoming-features";
import { Pricing } from "@/components/marketing/pricing";
import { Faq } from "@/components/marketing/faq";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export default function HomePage() {
  return (
    <>
      <MarketingNav />
      <main>
        <Hero />
        <StackSection />
        <CapabilitiesCarousel />
        <section id="sorties" className="scroll-mt-20">
          <LatestReleases />
        </section>
        <UpcomingFeatures />
        <Pricing />
        <section id="faq" className="scroll-mt-20">
          <Faq />
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
