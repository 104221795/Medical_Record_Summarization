import { useMemo, useState } from "react";

export function useCitationSelection(summary) {
  const citations = useMemo(() => extractCitations(summary), [summary]);
  const claims = useMemo(() => extractClaims(summary), [summary]);
  const citationsById = useMemo(() => Object.fromEntries(citations.map((citation) => [citation.citation_id, citation])), [citations]);
  const evidenceByCitationId = citationsById;
  const claimsByCitationId = useMemo(() => {
    const lookup = {};
    citations.forEach((citation) => {
      const claim = claims.find((item) => item.claim_id === citation.claim_id);
      if (claim) lookup[citation.citation_id] = claim;
    });
    return lookup;
  }, [citations, claims]);
  const [selectedCitationId, setSelectedCitationId] = useState("");
  const [hoveredCitationId, setHoveredCitationId] = useState("");
  const [selectedClaimId, setSelectedClaimId] = useState("");

  const activeCitationId = hoveredCitationId || selectedCitationId;
  const selectedCitation = citations.find((citation) => citation.citation_id === selectedCitationId) || citations[0] || null;
  const activeCitation = citations.find((citation) => citation.citation_id === activeCitationId) || selectedCitation;
  const activeClaimId = (activeCitation?.citation_id && claimsByCitationId[activeCitation.citation_id]?.claim_id) || selectedClaimId;
  const selectedClaim = claims.find((claim) => claim.claim_id === activeClaimId)
    || null;

  const selectCitation = (citationId, claimId = "") => {
    setSelectedCitationId(citationId || "");
    const linkedClaimId = claimId || claimsByCitationId[citationId]?.claim_id || "";
    if (linkedClaimId) setSelectedClaimId(linkedClaimId);
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
    citationsById,
    evidenceByCitationId,
    claimsByCitationId,
    activeCitation,
    activeCitationId,
    activeClaimId,
    selectedCitation,
    selectedCitationId,
    hoveredCitationId,
    setHoveredCitationId,
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
  let globalIndex = 0;
  return extractClaims(summary).flatMap((claim) =>
    (claim.citations || []).map((citation, index) => ({
      ...citation,
      claim_id: claim.claim_id,
      claim_text: claim.claim_text,
      claim_type: claim.claim_type,
      claim_status: claim.support_status,
      citation_label: citation.citation_id ? `C${++globalIndex}` : `C${index + 1}`,
    })),
  );
}
