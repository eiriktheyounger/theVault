---
name: BrightLine Frame Ads Integration
description: Frame ad (squeeze-back) format integration for live sports monetization
type: project
company: NBCUniversal
dates: 2022-2023
status: Shipped
---

# BrightLine Frame Ads — Squeeze-Back Format Integration

## Project Summary

End-to-end architecture and integration of BrightLine's "frame ad" (squeeze-back) format for Peacock live sports. Navigated complex vendor negotiations, internal resistance, and cross-team alignment to deliver standards-compliant, frame-accurate ad delivery across all BrightLine formats (VOD and Live).

## Background & Challenge

NBCU aimed to support BrightLine's "frame ad" (squeeze-back) format during live sports events. BrightLine initially wanted deep control over the Peacock player through its SDK—a direct violation of platform standards. Internal teams were divided on trigger method (SCTE-35 vs. ID3), and resisted the complexity of the proposed architecture.

## Key Contribution

**End-to-End Architect**: Designed solution, navigated vendor/internal negotiations, secured stakeholder alignment, and oversaw engineering delivery.

## Key Actions

- Rejected BrightLine's SDK control request and negotiated vendor alignment at executive levels
- Advocated for SCTE-35-based event triggers instead of client-preferred ID3 tags
- Faced cross-team resistance due to complexity of 3-way communication model (SDK ↔ Player ↔ Client)
- Created tailored architecture wikis, low-level diagrams, and led VP/SVP review meetings to resolve stakeholder friction
- Walked alternative proposals through roadmap failures and got final alignment
- Oversaw engineering intake and delivery of final integration

## Key Results

- Successfully launched frame ads using proposed architecture
- **Now used across all BrightLine formats** (VOD and Live)
- Internal teams declared the solution "rock solid" in retrospectives
- BrightLine adopted the SDK usage model as canonical
- Generated **millions of ad impressions**, unlocking dynamic formats Peacock could monetize at scale
- Still cited by internal teams as the gold-standard implementation

## Technical Details

- SCTE-35-based event triggers (not ID3)
- Modular 3-way communication model (SDK ↔ Player ↔ Client)
- Standards-compliant implementation
- Frame-accurate ad delivery for live sports
- Vendor SDK constraints respected platform boundaries

## Resume Bullet Language

- Architected BrightLine frame ads integration for Peacock, negotiating vendor alignment and securing stakeholder buy-in for standards-compliant implementation
- Designed frame-accurate SCTE-35-based trigger mechanism enabling squeeze-back ad format across all BrightLine VOD and live sports
- Navigated complex cross-team dynamics to deliver solution cited as gold-standard implementation by internal teams
- Generated millions of ad impressions through innovative squeeze-back format support, unlocking new monetization opportunities

---

## Related Projects

- [[projects/pause-ads]] — Related ad insertion infrastructure
- [[projects/key-plays-sponsorships]] — Related monetization architecture

## Context Notes

- **Vendor**: BrightLine (squeeze-back format provider)
- **Challenge**: Balancing vendor needs, platform standards, team alignment
- **Status**: Shipped and in active use across all BrightLine formats
