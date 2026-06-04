import { useMemo, useState } from "react";

export function useCitationSelection(summary) {
  const citations = useMemo(() => extractCitations(summary), [summary]);
  const claims = useMemo(() => extractClaims(summary), [summary]);
  const [selectedCitationId, setSelectedCitationId] = useState("");
  const [selectedClaimId, setSelectedClaimId] = useState("");

  const selectedCitation = citations.find((citation) => citation.citation_id === selectedCitationId) || citations[0] || null;
  const selectedClaim = claims.find((claim) => claim.claim_id === selectedClaimId)
    || claims.find((claim) => claim.citations?.some((citation) => citation.citation_id === selectedCitation?.citation_id))
    || null;

  const selectCitation = (citationId, claimId = "") => {
    setSelectedCitationId(citationId || "");
    if (claimId) setSelectedClaimId(claimId);
  };

  const selectClaim = (claimId) => {
    setSelectedClaimId(claimId || "");
    const claim = claims.find((item) => item.claim_id === claimId);
    const firstCitation = claim?.citations?.[0];
    if (firstCitation) setSelectedCitationId(firstCitation.citation_id);
  };

  return {
    citations,
    claims,
    selectedCitation,
    selectedCitationId,
    selectedClaim,
    selectedClaimId,
    selectCitation,
    selectClaim,
  };
}

export function extractClaims(summary) {
  return summary?.sections?.flatMap((section) => section.claims || []) || [];
}

export function extractCitations(summary) {
  return extractClaims(summary).flatMap((claim) =>
    (claim.citations || []).map((citation, index) => ({
      ...citation,
      claim_id: claim.claim_id,
      claim_text: claim.claim_text,
      claim_status: claim.support_status,
      citation_label: citation.citation_id ? `C${String(index + 1).padStart(2, "0")}` : "Citation",
    })),
  );
}
