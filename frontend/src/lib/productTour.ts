import type { Mode } from "./types";

export type TourSession = { mode: Mode; room: string };

export type TourStep = {
  id: string;
  path: string;
  title: string;
  body: string;
  icon: "clock" | "agents" | "quiz" | "chart" | "search" | "decisions" | "home";
  targets: string[];
  hints?: Record<string, string>;
};

export function tourSteps({ mode, room }: TourSession): TourStep[] {
  const demo = mode === "historical";
  return [
    {
      id: "welcome", path: "/", icon: "home", title: "Welcome to your dashboard",
      body: "Home brings together what you own, how it’s performing, and the reviews and trades that changed it. It’s where you can get a quick picture of your paper portfolio.",
      targets: ["dashboard"],
    },
    {
      id: "team", path: "/workspace", icon: "agents", title: "Meet your investment team",
      body: demo
        ? "In the simulation, scheduled reviews and rules such as a five-percentage-point drift from target can launch the Gemini 4 Argon lead. The team then decides whether to keep the mix or propose a rebalance."
        : "Live keeps market data up to date in the background. Choose Check portfolio now on Home to launch a Gemini 4 Argon review. The team can keep your current mix or propose a rebalance.",
      targets: ["agents-intro"],
    },
    demo ? {
      id: "playback", path: room, icon: "clock", title: "Replay a portfolio review",
      body: "Press Play to watch a recorded investigation. You can pause, scrub, or speed up the timeline to see what the agents did.",
      targets: ["replay", "timeline-intro"],
    } : {
      id: "playback", path: room, icon: "agents", title: "Watch your team work",
      body: "Your goals and risk limits guide the Lead Agent. It calls in specialists as needed. Evidence appears as they work through the investigation.",
      targets: ["run-intro", "agents-intro"],
    },
    {
      id: "models", path: room, icon: "agents", title: "See how the team investigates",
      body: "Gemini 4 Argon is the default Lead model. It combines evidence from specialists, typically using Gemini 3.8 Flash to examine prices, filings, and news. Use a card’s arrows to see what each agent checked.",
      targets: ["run-model", "agent-steps", "run-intro", "timeline-intro", "agents-intro"],
      hints: { "agents-intro": "Open an investigation from Agents to find the step arrows on each card." },
    },
    {
      id: "evidence", path: room, icon: "quiz", title: "How we rebalance your portfolio",
      body: "The CVXPY optimiser proposes how much to buy or sell to bring your portfolio closer to your plan. It weighs trading costs, a two-week return estimate, and risk measured with Ledoit–Wolf, while respecting your limits.",
      targets: ["evidence-open", "evidence", "evidence-example", "run-intro", "timeline-intro", "agents-intro"],
      hints: {
        "evidence-example": "Open a recorded calculation to see the portfolio engine’s work.",
        "run-intro": "Evidence will appear as the investigation progresses. You can continue while it runs.",
        "evidence-open": "This is the engine’s recorded output. Use Inspect evidence on any run to trace its sources and calculations.",
      },
    },
    {
      id: "verification", path: room, icon: "decisions", title: "See what gets checked",
      body: "Before a proposed change reaches you, the Python engine recalculates the numbers and checks your investment limits. Reviewers check the evidence and challenge the recommendation.",
      targets: ["assurance", "assurance-example", "run-intro", "timeline-intro", "agents-intro"],
      hints: {
        "assurance-example": "Open the recorded checks to see their results.",
        "run-intro": "Check results appear as the run reaches them. You can continue while it works.",
        "timeline-intro": "Recorded checks appear when they’re available for this investigation.",
      },
    },
    {
      id: "decisions", path: "/decisions", icon: "decisions", title: "You decide what changes",
      body: "By default, proposed paper trades wait for your approval. Review the holdings and checks, then approve or keep your current portfolio.",
      targets: ["proposal", "decisions-intro"],
    },
    {
      id: "benchmarks", path: "/benchmarks", icon: "chart", title: "Compare results and risk",
      body: "The evaluation uses a later window than the one used to tune the engine. Compare the simulation with buy and hold over the same dates and cost rules. Try Worst drop to see which strategy fell furthest.",
      targets: ["benchmark-metric", "benchmarks-intro"],
      hints: { "benchmarks-intro": "The comparison controls appear when benchmark results are available." },
    },
    {
      id: "holdings", path: "/", icon: "chart", title: "See what moves together",
      body: "Open Connections to see which holdings have moved in similar ways. A portfolio can hold several funds and still depend on many of the same market moves.",
      targets: ["connections"],
    },
    {
      id: "news", path: "/", icon: "search", title: "Read the news behind a move",
      body: "Open Latest news to see coverage pulled into the app. Select a story to read it. Once you have holdings, use My holdings to filter stories to those investments.",
      targets: ["news-story", "news-tab"],
      hints: { "news-story": "Try opening a story to see its source." },
    },
    demo ? {
      id: "finish", path: "/", icon: "home", title: "Explore the demo at your own pace",
      body: "Play around with the demo for as long as you like. When you’re ready to try it for yourself, open Profile, choose Change mode or retake questions, and select Use the app live.",
      targets: ["profile"],
    } : {
      id: "finish", path: "/", icon: "home", title: "Your portfolio, your pace",
      body: "Return to Home to see your holdings and run a fresh check when you’re ready. You can update your investment plan from Profile. All trades here are simulated.",
      targets: ["portfolio-check", "profile"],
    },
  ];
}

export type TourRect = { left: number; top: number; width: number; height: number };

export function placeTourCard(target: TourRect | null, viewport: { width: number; height: number }, card: { width: number; height: number }) {
  const margin = 16;
  const gap = 16;
  const clamp = (value: number, size: number, limit: number) => Math.max(margin, Math.min(value, limit - size - margin));
  const centered = { left: clamp((viewport.width - card.width) / 2, card.width, viewport.width),
    top: clamp((viewport.height - card.height) / 2, card.height, viewport.height), side: "none" };
  if (!target) return centered;
  const right = target.left + target.width;
  const bottom = target.top + target.height;
  const alignedTop = clamp(target.top + (target.height - card.height) / 2, card.height, viewport.height);
  const alignedLeft = clamp(target.left + (target.width - card.width) / 2, card.width, viewport.width);
  if (right + gap + card.width + margin <= viewport.width) return { left: right + gap, top: alignedTop, side: "right" };
  if (target.left - gap - card.width >= margin) return { left: target.left - gap - card.width, top: alignedTop, side: "left" };
  if (bottom + gap + card.height + margin <= viewport.height) return { left: alignedLeft, top: bottom + gap, side: "below" };
  if (target.top - gap - card.height >= margin) return { left: alignedLeft, top: target.top - gap - card.height, side: "above" };
  return { ...centered, top: target.top > viewport.height / 2 ? margin : viewport.height - card.height - margin };
}
