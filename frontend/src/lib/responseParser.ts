/**
 * GraphOS Standardized Investigation Response Parser
 * Parses agent answers into the 6 canonical sections:
 * 1. Investigation Summary
 * 2. Evidence & Connected Entities
 * 3. Reasoning / Investigation Steps
 * 4. Risk Assessment
 * 5. Recommended Actions
 * 6. Sources & Execution Details
 */

export interface StructuredInvestigationSections {
  summary: string;
  evidence: string;
  reasoning: string;
  risk: string;
  recommendations: string;
  sources: string;
  isStructured: boolean;
  unparsedContent: string;
}

export function parseInvestigationResponse(text: string): StructuredInvestigationSections {
  const result: StructuredInvestigationSections = {
    summary: "",
    evidence: "",
    reasoning: "",
    risk: "",
    recommendations: "",
    sources: "",
    isStructured: false,
    unparsedContent: text || "",
  };

  if (!text || typeof text !== "string") {
    return result;
  }

  // Section 1: Investigation Summary / Executive Summary
  const summaryMatch = text.match(
    /(?:###?\s*(?:1\.?\s*)?(?:Investigation Summary|Executive Summary)[^\n]*\n)([\s\S]*?)(?=(?:###?\s*(?:2\.?\s*)?(?:Evidence|Connected Entities|Supporting Graph Evidence Chain)|###?\s*(?:3\.?\s*)?Reasoning|$))/i
  );

  // Section 2: Evidence & Connected Entities / Supporting Graph Evidence Chain
  const evidenceMatch = text.match(
    /(?:###?\s*(?:2\.?\s*)?(?:Evidence & Connected Entities|Evidence|Connected Entities|Supporting Graph Evidence Chain|Verified Evidence)[^\n]*\n)([\s\S]*?)(?=(?:###?\s*(?:3\.?\s*)?(?:Reasoning|Investigation Steps)|###?\s*(?:4\.?\s*)?Risk Assessment|$))/i
  );

  // Section 3: Reasoning / Investigation Steps
  const reasoningMatch = text.match(
    /(?:###?\s*(?:3\.?\s*)?(?:Reasoning \/? Investigation Steps|Reasoning|Investigation Steps)[^\n]*\n)([\s\S]*?)(?=(?:###?\s*(?:4\.?\s*)?Risk Assessment|###?\s*(?:5\.?\s*)?Recommended Actions?|$))/i
  );

  // Section 4: Risk Assessment / Blast Radius
  const riskMatch = text.match(
    /(?:###?\s*(?:4\.?\s*)?(?:Risk Assessment|Blast Radius|Verified Blast Radius)[^\n]*\n)([\s\S]*?)(?=(?:###?\s*(?:5\.?\s*)?Recommended Actions?|###?\s*(?:6\.?\s*)?Sources|$))/i
  );

  // Section 5: Recommended Actions / Actionable Remediation
  const recMatch = text.match(
    /(?:###?\s*(?:5\.?\s*)?(?:Recommended Actions?|Remediation|Actionable Remediation|Immediate Actions?|Next Steps?)[^\n]*\n)([\s\S]*?)(?=(?:###?\s*(?:6\.?\s*)?(?:Sources|Execution Details)|$))/i
  );

  // Section 6: Sources & Execution Details
  const sourcesMatch = text.match(
    /(?:###?\s*(?:6\.?\s*)?(?:Sources & Execution Details|Sources|Execution Details)[^\n]*\n)([\s\S]*?)$/i
  );

  if (summaryMatch || evidenceMatch || reasoningMatch || riskMatch || recMatch || sourcesMatch) {
    result.isStructured = true;
    result.summary = summaryMatch ? summaryMatch[1].trim() : "";
    result.evidence = evidenceMatch ? evidenceMatch[1].trim() : "";
    result.reasoning = reasoningMatch ? reasoningMatch[1].trim() : "";
    result.risk = riskMatch ? riskMatch[1].trim() : "";
    result.recommendations = recMatch ? recMatch[1].trim() : "";
    result.sources = sourcesMatch ? sourcesMatch[1].trim() : "";
  }

  return result;
}
