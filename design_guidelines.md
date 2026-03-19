{
  "design_system_name": "KBS Bridge Manager — Dark Enterprise Ops",
  "brand_attributes": [
    "trustworthy",
    "compliance-first",
    "operator-efficient",
    "real-time operational clarity",
    "serious enterprise SaaS"
  ],
  "inspiration_sources": {
    "visual_references": [
      {
        "source": "Dribbble search",
        "url": "https://dribbble.com/search/hotel-management-system-dashboard",
        "notes": "Dark enterprise dashboards with dense tables + KPI cards; use restrained accents + strong hierarchy."
      },
      {
        "source": "shadcn blocks",
        "url": "https://www.shadcn.io/blocks/crud-activity-feed-01",
        "notes": "Good pattern for audit feed / activity stream with filters and dense spacing."
      },
      {
        "source": "shadcn blocks",
        "url": "https://www.shadcn.io/blocks/profile-activity-timeline",
        "notes": "Timeline layout inspiration for submission attempts + audit trail."
      },
      {
        "source": "shadcn/ui docs",
        "url": "https://ui.shadcn.com/docs",
        "notes": "Component primitives, theming tokens, accessibility conventions."
      }
    ]
  },
  "visual_personality": {
    "style": [
      "Swiss-style grid discipline",
      "dark enterprise minimalism",
      "subtle glass (only for topbar / overlays)",
      "bento metrics"
    ],
    "look_and_feel": {
      "background": "Deep near-black with slight blue/graphite tint (not pure black) to reduce eye fatigue.",
      "surfaces": "Layered graphite cards with crisp 1px borders; avoid heavy gradients.",
      "accents": "Single teal-cyan operational accent for active/primary; amber for warnings; red for failure; green for success."
    },
    "density_mode": "Default: comfortable. Provide a 'Compact' table density toggle later (v2). For v1, tables should be slightly dense with clear row separation."
  },
  "typography": {
    "font_pairing": {
      "display": {
        "name": "Space Grotesk",
        "usage": "Page titles, KPI numbers, section headers",
        "google_fonts_import": "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap"
      },
      "body": {
        "name": "IBM Plex Sans",
        "usage": "Body, tables, form labels, helper text (excellent TR glyph coverage)",
        "google_fonts_import": "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap"
      },
      "mono": {
        "name": "IBM Plex Mono",
        "usage": "SOAP XML viewer, IDs, hashes, request/response payloads",
        "google_fonts_import": "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap"
      }
    },
    "scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg font-medium text-muted-foreground",
      "section_title": "text-lg font-semibold",
      "card_kpi": "text-3xl font-semibold tabular-nums",
      "table": "text-sm leading-5",
      "small": "text-xs text-muted-foreground"
    },
    "numbers": {
      "kpi": "Use tabular-nums for alignment: class 'tabular-nums'.",
      "time": "Use locale-aware formatting; TR default."
    }
  },
  "color_system": {
    "mode": "dark",
    "semantic_tokens_hsl": {
      "background": "220 18% 6%",
      "foreground": "210 40% 98%",
      "card": "220 18% 9%",
      "card-foreground": "210 40% 98%",
      "popover": "220 18% 9%",
      "popover-foreground": "210 40% 98%",
      "muted": "220 14% 14%",
      "muted-foreground": "215 18% 70%",
      "border": "220 14% 18%",
      "input": "220 14% 18%",
      "ring": "188 86% 45%",
      "primary": "188 86% 45%",
      "primary-foreground": "220 18% 8%",
      "secondary": "220 14% 14%",
      "secondary-foreground": "210 40% 98%",
      "accent": "220 14% 14%",
      "accent-foreground": "210 40% 98%",
      "destructive": "0 72% 52%",
      "destructive-foreground": "210 40% 98%",
      "success": "142 70% 45%",
      "warning": "38 92% 50%",
      "info": "199 89% 48%"
    },
    "status_badges": {
      "queued": {"bg": "bg-slate-500/15", "text": "text-slate-200", "border": "border-slate-500/30"},
      "sending": {"bg": "bg-cyan-500/15", "text": "text-cyan-200", "border": "border-cyan-500/30"},
      "acked": {"bg": "bg-emerald-500/15", "text": "text-emerald-200", "border": "border-emerald-500/30"},
      "retrying": {"bg": "bg-amber-500/15", "text": "text-amber-200", "border": "border-amber-500/30"},
      "failed": {"bg": "bg-rose-500/15", "text": "text-rose-200", "border": "border-rose-500/30"},
      "quarantined": {"bg": "bg-fuchsia-500/10", "text": "text-fuchsia-200", "border": "border-fuchsia-500/25", "note": "Use sparingly; not a gradient. Purely for high attention."}
    },
    "charts": {
      "success": "hsl(142 70% 45%)",
      "fail": "hsl(0 72% 52%)",
      "retry": "hsl(38 92% 50%)",
      "queue": "hsl(188 86% 45%)",
      "muted_line": "hsl(220 14% 28%)"
    },
    "gradient_policy": {
      "allowed": "Only as a subtle decorative header/backdrop, max 15–20% viewport. Keep light-to-dark within teal/graphite family.",
      "sample_safe_gradient": "radial-gradient(1200px circle at 15% 10%, rgba(20,184,166,0.14), transparent 55%), radial-gradient(900px circle at 85% 0%, rgba(56,189,248,0.10), transparent 55%)",
      "explicit_prohibitions": [
        "No purple/pink gradients",
        "No gradients on text-heavy areas",
        "No gradients on small UI elements (<100px)"
      ]
    }
  },
  "design_tokens_css": {
    "where_to_apply": "/app/frontend/src/index.css (replace :root/.dark token block to match below, keep tailwind layers intact)",
    "css": ":root {\n  --radius: 0.75rem;\n}\n.dark {\n  --background: 220 18% 6%;\n  --foreground: 210 40% 98%;\n  --card: 220 18% 9%;\n  --card-foreground: 210 40% 98%;\n  --popover: 220 18% 9%;\n  --popover-foreground: 210 40% 98%;\n  --primary: 188 86% 45%;\n  --primary-foreground: 220 18% 8%;\n  --secondary: 220 14% 14%;\n  --secondary-foreground: 210 40% 98%;\n  --muted: 220 14% 14%;\n  --muted-foreground: 215 18% 70%;\n  --accent: 220 14% 14%;\n  --accent-foreground: 210 40% 98%;\n  --destructive: 0 72% 52%;\n  --destructive-foreground: 210 40% 98%;\n  --border: 220 14% 18%;\n  --input: 220 14% 18%;\n  --ring: 188 86% 45%;\n  --chart-1: 188 86% 45%;\n  --chart-2: 142 70% 45%;\n  --chart-3: 38 92% 50%;\n  --chart-4: 0 72% 52%;\n  --chart-5: 215 18% 70%;\n}\n"
  },
  "layout_and_grid": {
    "app_shell": {
      "pattern": "Sidebar + topbar + content",
      "desktop_grid": "min-h-screen grid grid-cols-[280px_1fr]",
      "sidebar": "sticky top-0 h-svh border-r bg-card/30 backdrop-blur supports-[backdrop-filter]:bg-card/20",
      "content": "px-4 sm:px-6 lg:px-8 py-6",
      "max_width": "Use max-w-[1400px] only for forms/detail pages; tables can be full width for scanning."
    },
    "page_header": {
      "layout": "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
      "title_block": "space-y-1",
      "actions_block": "flex flex-wrap items-center gap-2"
    },
    "bento_metrics": {
      "grid": "grid gap-4 sm:grid-cols-2 xl:grid-cols-4",
      "card": "rounded-xl border bg-card/60 backdrop-blur"
    },
    "responsive": {
      "mobile_priority": "Mobile is secondary but must not break: sidebar collapses into Sheet; tables become horizontally scrollable via ScrollArea.",
      "table_overflow": "Wrap tables with <ScrollArea className=\"w-full\"> or overflow-x-auto container."
    }
  },
  "component_path": {
    "shadcn_primary": [
      "/app/frontend/src/components/ui/button.jsx",
      "/app/frontend/src/components/ui/badge.jsx",
      "/app/frontend/src/components/ui/card.jsx",
      "/app/frontend/src/components/ui/table.jsx",
      "/app/frontend/src/components/ui/tabs.jsx",
      "/app/frontend/src/components/ui/select.jsx",
      "/app/frontend/src/components/ui/input.jsx",
      "/app/frontend/src/components/ui/textarea.jsx",
      "/app/frontend/src/components/ui/dialog.jsx",
      "/app/frontend/src/components/ui/alert.jsx",
      "/app/frontend/src/components/ui/alert-dialog.jsx",
      "/app/frontend/src/components/ui/switch.jsx",
      "/app/frontend/src/components/ui/tooltip.jsx",
      "/app/frontend/src/components/ui/scroll-area.jsx",
      "/app/frontend/src/components/ui/separator.jsx",
      "/app/frontend/src/components/ui/skeleton.jsx",
      "/app/frontend/src/components/ui/sonner.jsx",
      "/app/frontend/src/components/ui/sheet.jsx",
      "/app/frontend/src/components/ui/breadcrumb.jsx",
      "/app/frontend/src/components/ui/dropdown-menu.jsx",
      "/app/frontend/src/components/ui/command.jsx",
      "/app/frontend/src/components/ui/calendar.jsx"
    ],
    "compose_new_components_in_src_components": [
      "DashboardShell.jsx (sidebar + topbar + content)",
      "StatusBadge.jsx (maps statuses to Badge variants)",
      "AgentHeartbeatPill.jsx (animated dot + last seen)",
      "SubmissionAttemptsTimeline.jsx (vertical timeline)",
      "XmlViewerCard.jsx (mono viewer with copy/download)",
      "KpiCard.jsx (metric + sparkline placeholder)",
      "FiltersBar.jsx (search + status select + date range)",
      "LanguageToggle.jsx (TR/EN)"
    ]
  },
  "component_specs": {
    "buttons": {
      "shape": "Professional / Corporate: radius 10–12px for primary; secondary is outline; ghost for table row actions",
      "variants": {
        "primary": "Button (default) with primary token; add subtle inner highlight via bg-primary/90 hover:bg-primary focus-visible:ring-primary",
        "secondary": "variant=secondary for safe actions (Requeue, Retry) when not destructive",
        "destructive": "variant=destructive for Delete/Quarantine actions",
        "ghost": "variant=ghost for icon-only buttons in tables"
      },
      "motion": {
        "hover": "hover:brightness-[1.05]",
        "press": "active:scale-[0.98] (only on buttons)",
        "focus": "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      },
      "data_testid_rule": "All buttons must have data-testid: e.g., data-testid=\"submissions-retry-selected-button\"."
    },
    "inputs_and_forms": {
      "field_layout": "Use 2-column grid on desktop for check-in, 1-column on mobile: grid gap-4 md:grid-cols-2",
      "label": "Always present; helper text in text-xs text-muted-foreground.",
      "tc_vs_passport_toggle": "Use Tabs (TC Kimlik / Yabancı Pasaport). Each tab shows contextual fields.",
      "validation": "Inline error below field in text-xs text-rose-300; also toast on submit failure.",
      "critical": "For TR characters: ensure fonts and input allow İ, ı, Ş, ş, Ğ, ğ, Ö, ö, Ü, ü."
    },
    "tables": {
      "pattern": "Dense enterprise table with sticky header, row hover, quick actions, and status chips.",
      "container": "rounded-xl border bg-card/40",
      "header": "sticky top-0 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60",
      "row": "hover:bg-muted/40",
      "cell": "py-3",
      "empty_state": "Use Skeleton while loading, and a calm empty state card with a suggested next action.",
      "performance": "Paginate at 25/50/100; keep search debounced (300ms)."
    },
    "badges": {
      "status": "Use Badge with custom classes per status (see status_badges mapping). Do not rely on color alone; include text label.",
      "agent_online": "emerald badge + pulsing dot",
      "agent_offline": "slate badge + hollow dot",
      "kbs_mode": "info badge for Normal, warning for Delayed/Timeout, destructive for Unavailable"
    },
    "timeline": {
      "use_case": "Submission Detail: attempts timeline + audit events",
      "structure": "Vertical list with left rail, icon per event type, timestamp, status pill.",
      "motion": "Animate items in with framer-motion (fade up, 12px). Respect prefers-reduced-motion."
    },
    "xml_viewer": {
      "container": "Card > CardHeader (actions) + CardContent with ScrollArea",
      "code": "pre font-mono text-xs leading-5 text-foreground/90",
      "highlight": "Optional: install prismjs for xml highlighting (see libraries). Provide a copy-to-clipboard button."
    },
    "toasts": {
      "library": "sonner",
      "usage": "Success: 'Gönderim kuyruğa alındı' / 'Submission queued'. Error includes correlation id and action CTA."
    }
  },
  "page_level_layouts": {
    "login": {
      "layout": "Split screen (desktop): left brand panel, right login card. Mobile: single centered card.",
      "left_panel": "Muted decorative background with small safe gradient overlay + hotel/ops imagery.",
      "right_panel": "Card with title, subtitle, email/password, tenant/hotel code optional.",
      "test_ids": [
        "login-email-input",
        "login-password-input",
        "login-submit-button",
        "language-toggle-button"
      ]
    },
    "dashboard_overview": {
      "top": "Page header + date range filter + refresh indicator",
      "kpis": [
        "Total queued",
        "Sent last 24h",
        "Ack success rate",
        "Failed",
        "Quarantined",
        "Agents online"
      ],
      "charts": "Use Recharts for: success/fail stacked bar over time + queue size line.",
      "agent_strip": "Horizontal list of agents with heartbeat pills."
    },
    "checkin": {
      "layout": "Form in Card with sections: Guest Identity, Stay Info, Submit panel.",
      "sections": [
        "Identity (Tabs: TC / Passport)",
        "Contact (optional)",
        "Stay metadata (room, arrival, departure)",
        "Consent + submit"
      ],
      "submit_panel": "Right side summary (desktop): hotel, agent route, KBS mode, last sync time."
    },
    "submissions_list": {
      "filters": "Search (name, doc no, submission id), Status Select, Date range (Calendar), Hotel Select (multi-tenant), Agent Select.",
      "bulk": "Bulk actions row appears when selection >0: Retry, Requeue, Quarantine, Export.",
      "table_columns": [
        "Status",
        "Guest",
        "Document",
        "Hotel",
        "Agent",
        "Created",
        "Last attempt",
        "Attempts",
        "Actions"
      ]
    },
    "submission_detail": {
      "layout": "Two-column on desktop: left timeline + audit, right payload panels.",
      "right_panels": [
        "Request SOAP XML",
        "Response SOAP XML",
        "Headers/metadata",
        "Retry controls"
      ],
      "actions": "Retry now, Requeue, Mark corrected, Download XML"
    },
    "agent_monitor": {
      "layout": "Grid of agent cards + detail drawer",
      "agent_card": "Name, hotel, online/offline badge, queue size, last heartbeat, CPU/mem placeholders.",
      "controls": "Simulate offline (demo only), restart agent (future), copy agent key"
    },
    "kbs_control_panel": {
      "layout": "Card with radio group or segmented control for mode + sliders for delay/timeout",
      "modes": [
        "Normal",
        "Unavailable",
        "Timeout",
        "Delayed ACK",
        "Invalid Response"
      ]
    },
    "audit_trail": {
      "layout": "Filters bar + table + expandable row detail dialog",
      "filters": "Date range, actor, hotel, entity type, event type, correlation id"
    },
    "hotels_management": {
      "layout": "Table + right-side drawer for create/edit",
      "fields": "Name, City, KBS credentials status, Bridge agent count, Created"
    },
    "settings": {
      "layout": "Stacked cards: Language, Polling interval, Table density (future), Theme lock (dark)."
    }
  },
  "motion_and_microinteractions": {
    "principles": [
      "Motion communicates state changes (queued → sending → acked)",
      "Keep subtle; never distract operators",
      "Prefer opacity/translate; avoid large scale transforms on layout containers"
    ],
    "recommended_library": {
      "name": "framer-motion",
      "install": "npm i framer-motion",
      "usage_notes": "Use for: table row expansion, timeline entrance, agent heartbeat subtle pulse. Wrap with prefers-reduced-motion checks."
    },
    "patterns": {
      "agent_heartbeat": "Online dot: animate opacity 1→0.35 every 1.4s; Offline: static ring.",
      "refresh_indicator": "When polling, show small spinner next to 'Son güncelleme / Last updated'.",
      "status_change": "When a submission status changes, flash the row background for 400ms: bg-primary/10 then fade to transparent (only row, not the whole table)."
    }
  },
  "data_visualization": {
    "library": {
      "name": "recharts",
      "install": "npm i recharts",
      "charts": [
        "StackedBarChart: acked vs failed vs retrying (by hour/day)",
        "LineChart: queue size over time",
        "Donut: success rate"
      ]
    },
    "chart_container": {
      "card": "Use Card. Place chart in CardContent with h-[220px]",
      "axes": "Muted ticks: text-muted-foreground",
      "grid": "Stroke: border color 220 14% 18%",
      "tooltip": "Use shadcn Tooltip/Popover styling; no default recharts tooltip."
    }
  },
  "accessibility": {
    "focus": "Visible focus ring always; do not remove outlines.",
    "contrast": "All text on dark surfaces must be >= WCAG AA; use muted-foreground only for secondary info.",
    "color_plus_text": "Statuses must include label text; not color-only.",
    "reduced_motion": "Respect prefers-reduced-motion: disable heartbeat pulse and timeline entrance animations.",
    "keyboard": "All menus/dialogs must be keyboard operable (shadcn defaults)."
  },
  "internationalization": {
    "default_language": "tr",
    "toggle": "Topbar language switcher (TR/EN) using DropdownMenu or ToggleGroup.",
    "date_time": "TR locale formatting by default; ensure EN uses en-US or en-GB consistently.",
    "test_ids": {
      "language_toggle": "language-toggle",
      "language_menu_tr": "language-option-tr",
      "language_menu_en": "language-option-en"
    }
  },
  "testing_attributes": {
    "rule": "All interactive and key informational elements MUST include data-testid.",
    "examples": [
      "data-testid=\"dashboard-refresh-button\"",
      "data-testid=\"submissions-status-filter-select\"",
      "data-testid=\"submissions-search-input\"",
      "data-testid=\"agent-card-<agentId>\"",
      "data-testid=\"submission-detail-xml-copy-button\"",
      "data-testid=\"audit-log-row-<eventId>\"",
      "data-testid=\"hotel-create-button\""
    ],
    "naming": "Use kebab-case describing role, not appearance."
  },
  "image_urls": {
    "login_left_panel": [
      {
        "url": "https://images.unsplash.com/photo-1571096892464-eee432a6f965?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzV8MHwxfHNlYXJjaHwxfHxob3RlbCUyMGtleSUyMGNhcmR8ZW58MHx8fGJsYWNrX2FuZF93aGl0ZXwxNzczOTYzMDg0fDA&ixlib=rb-4.1.0&q=85",
        "description": "Monochrome hotel key card; use as subtle background with overlay for login split panel.",
        "category": "auth"
      }
    ],
    "empty_states_or_illustrative": [
      {
        "url": "https://images.unsplash.com/photo-1581309558346-f325181f9df6?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2OTV8MHwxfHNlYXJjaHwxfHxob3RlbCUyMHJlY2VwdGlvbiUyMGRlc2t8ZW58MHx8fGJsYWNrfDE3NzM5NjMwODF8MA&ixlib=rb-4.1.0&q=85",
        "description": "Minimal reception desk phone; can be used in empty states or settings banner (keep subtle).",
        "category": "ops"
      }
    ]
  },
  "instructions_to_main_agent": {
    "global_setup": [
      "Remove/avoid any centered .App layouts from App.css; do not apply text-align:center.",
      "Set app to dark by default: add 'dark' class on <html> or top-level container and keep a future toggle optional.",
      "Replace shadcn tokens in /app/frontend/src/index.css with the provided dark enterprise token set.",
      "Add Google Fonts imports (Space Grotesk, IBM Plex Sans, IBM Plex Mono) in index.html or CSS import and set Tailwind font-family utilities via config or global body styles.",
      "Prefer shadcn/ui components in /src/components/ui/*.jsx for all interactive elements (Select, Dropdown, Dialog, Sheet, Calendar, Table, Tabs, Sonner)."
    ],
    "navigation": [
      "Implement a SidebarNav with grouped sections: Overview, Operations (Check-in, Submissions), Monitoring (Agents, KBS Control), Compliance (Audit Trail), Admin (Hotels, Settings).",
      "Topbar contains: breadcrumb, global search (Command), language switcher, user menu."
    ],
    "status_language": [
      "Statuses must be translated (TR/EN) and consistent across badges, filters, and detail pages.",
      "All status colors must match the mapping in status_badges; ensure text labels are present."
    ],
    "tables_and_lists": [
      "Submissions table: implement sticky header, row hover, inline action menu, and bulk action bar.",
      "Use ScrollArea or overflow-x-auto for wide tables; keep first column (Status) visually sticky if possible."
    ],
    "submission_detail": [
      "Provide timeline left; XML viewer right in two cards (request/response) with copy/download buttons.",
      "Use monospace font for payloads; ensure long lines wrap/scroll."
    ],
    "real_time_feel": [
      "Add a 'Last updated' chip and subtle spinner when polling.",
      "Agent cards should show heartbeat dot + lastSeen; animate only when online."
    ],
    "data_testids": [
      "Add data-testid to every interactive control and key info labels (counts, status, last updated).",
      "Use stable IDs (submissionId, agentId, hotelId) in data-testid for rows/cards."
    ]
  },

  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
