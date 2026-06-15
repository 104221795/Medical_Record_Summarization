const SECTION_TITLES = [
  "Patient Snapshot",
  "Diagnosis Evidence",
  "Medication Evidence",
  "Timeline Evidence",
  "Diagnostics Evidence",
  "Assessment Evidence",
  "Plan Evidence",
  "Unknown / Missing Evidence",
  "Active Problems",
  "Recent Clinical Course",
  "Medications",
  "Labs and Imaging Highlights",
  "Needs Clinician Review",
  "DIAGNOSIS_FACTS",
  "MEDICATIONS_FACTS",
  "TIMELINE_FACTS",
  "ASSESSMENT_FACTS",
  "PLAN_FACTS",
  "DIAGNOSTICS_FACTS",
];

const sectionPattern = new RegExp(`\\[\\s*(${SECTION_TITLES.map(escapeRegExp).join("|")})\\s*\\]`, "gi");

export function normalizeClinicalText(text = "") {
  const raw = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!raw) return "";
  const withSections = raw.replace(sectionPattern, (_match, title) => `\n[${canonicalTitle(title)}]\n`);
  const lines = [];
  withSections.split("\n").forEach((line) => {
    const clean = line.replace(/[ \t]+/g, " ").trim();
    if (!clean) return;
    if (isSectionLine(clean)) {
      lines.push(clean);
      return;
    }
    const bulletParts = clean.split(/\s+-\s+/).map((part) => part.trim()).filter(Boolean);
    if (bulletParts.length > 1) {
      bulletParts.forEach((part) => lines.push(`- ${part.replace(/^[-*•]\s*/, "")}`));
    } else if (/^[-*•]\s+/.test(clean)) {
      lines.push(`- ${clean.replace(/^[-*•]\s+/, "")}`);
    } else {
      lines.push(clean);
    }
  });
  return lines.join("\n").trim();
}

export function formatClinicalDisplayLines(text = "") {
  return normalizeClinicalText(text).split("\n").filter(Boolean).map((line) => {
    if (isSectionLine(line)) {
      return { type: "section", text: line.replace(/^\[|\]$/g, "") };
    }
    if (line.startsWith("- ")) {
      return { type: "bullet", text: line.slice(2).trim() };
    }
    return { type: "text", text: line };
  });
}

function isSectionLine(line = "") {
  return SECTION_TITLES.some((title) => line.toLowerCase() === `[${title.toLowerCase()}]`);
}

function canonicalTitle(value = "") {
  const found = SECTION_TITLES.find((title) => title.toLowerCase() === String(value).trim().toLowerCase());
  return found || String(value).trim();
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
