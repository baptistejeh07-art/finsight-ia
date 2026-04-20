import Link from "next/link";
import { Sidebar } from "@/components/sidebar";
import { TopNav } from "@/components/top-nav";
import { EditModeProvider } from "@/components/edit-mode-provider";
import { UserPreferencesProvider } from "@/components/user-preferences-provider";
import { OnboardingTour } from "@/components/onboarding-tour";
import { ShortcutsRuntime } from "@/components/shortcuts-runtime";
import { I18nProvider } from "@/i18n/provider";

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <UserPreferencesProvider>
    <I18nProvider>
    <EditModeProvider>
      <Sidebar />
      <TopNav />
      <OnboardingTour />
      <ShortcutsRuntime />
      <div className="md:pl-56 min-h-screen flex flex-col">
        <div className="flex-1">{children}</div>

        {/* Bandeau réglementaire discret en bas de l'app */}
        <div className="border-t border-ink-200 bg-ink-50/50 py-3 px-6 text-center text-2xs text-ink-500">
          FinSight n&apos;est pas un conseil en investissement.{" "}
          <Link
            href="/disclaimer"
            className="underline hover:text-ink-700"
          >
            Lire l&apos;avertissement
          </Link>
          {" · "}
          <Link href="/mentions-legales" className="hover:text-ink-700">
            Mentions légales
          </Link>
          {" · "}
          <Link href="/privacy" className="hover:text-ink-700">
            Confidentialité
          </Link>
        </div>
      </div>
    </EditModeProvider>
    </I18nProvider>
    </UserPreferencesProvider>
  );
}
