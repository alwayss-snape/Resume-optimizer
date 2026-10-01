import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { type AppConfig, getConfig } from "./lib/api";
import { useApp } from "./lib/store";
import { useTheme } from "./lib/useTheme";
import { Landing } from "./pages/Landing";

export function App() {
  const { step, settings } = useApp();
  // undefined while loading, null if the server can't be reached
  const [config, setConfig] = useState<AppConfig | null | undefined>(undefined);
  useTheme(settings.theme);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-screen flex-col bg-bg text-ink">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-gold focus:px-4 focus:py-2 focus:text-on-gold">
          Skip to content
        </a>
        <Header config={config} />
        <main id="main" className="flex-1">
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25, ease: "easeOut" }}>
              {/* Steps after upload arrive in P5.3–P5.5. */}
              <Landing onStart={() => undefined} />
            </motion.div>
          </AnimatePresence>
        </main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-[1240px] flex-col justify-between gap-2 px-4 py-6 text-xs text-muted sm:flex-row md:px-8">
            <span>Every rewrite comes from your own resume.</span>
            <span>Tailor · Resume Studio</span>
          </div>
        </footer>
      </div>
    </MotionConfig>
  );
}
