export const overlayTemplates = [
  {
    id: "weekly_template",
    label: "Weekly Template",
  },
  {
    id: "five_ema",
    label: "5 EMA",
  },
] as const;

export type OverlayTemplateId = (typeof overlayTemplates)[number]["id"];

const STORAGE_KEY = "sb-trading-system-active-overlay-templates";
const defaultActiveTemplates: OverlayTemplateId[] = ["weekly_template"];

export function loadActiveOverlayTemplates(): OverlayTemplateId[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultActiveTemplates;
    const saved = JSON.parse(raw);
    if (!Array.isArray(saved)) return defaultActiveTemplates;

    const knownIds = new Set<OverlayTemplateId>(
      overlayTemplates.map((template) => template.id),
    );
    return saved.filter(
      (id): id is OverlayTemplateId =>
        typeof id === "string" && knownIds.has(id as OverlayTemplateId),
    );
  } catch {
    return defaultActiveTemplates;
  }
}

export function saveActiveOverlayTemplates(templateIds: OverlayTemplateId[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(templateIds));
}
