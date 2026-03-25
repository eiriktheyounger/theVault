---
name: Key Plays
description: AI/ML-powered near real-time sports highlights feature for Peacock
type: project
company: NBCUniversal
dates: 2022-2025
status: Shipped
awards: Technology & Engineering Emmy Award (2023)
---

# Key Plays — AI/ML Sports Highlights at Scale

## Project Summary

Near real-time sports highlights feature enabling viewers to watch key plays just after they happen on live broadcasts. Powered by AI/ML for automated play selection with rich metadata. Recognized with Technology & Engineering Emmy Award for innovation in broadcast-scale AI implementation.

## Role & Contribution

**Head Architect for AI/ML Solution**: Led technical architecture for automated highlight selection during live events with near real-time delivery and rich metadata. Architecture evolved from MVP to critical platform service.

## Key Accomplishments

### Accomplishment 1: Key Plays Sponsorships Architecture

**Situation**: Sponsorships were manually configured, lacked auditability, and couldn't scale across sports as more properties (NFL, EPL, etc.) were added.

**Task**: Architect scalable, auditable sponsorship solution for Key Plays.

**Action**:
- Identified that technical debt and manual processing were limiting monetization
- Advocated for reusable, multi-use architecture: CMS > BFF > Client > Player
- Designed sponsorship insertion system using static assets with logic for ad vs. no-ad subscribers
- Collaborated with Ad Ops to define preconfiguration standards compatible with targeting systems
- Secured SVP buy-in and mapped integration timeline to SAM (Static Ads Manager)
- Prioritized long-term sustainability and modularity over patchwork fixes

**Result**:
- MVP launched for English Premier League in 2022
- Became stable cornerstone of Peacock's sports coverage
- Architecture proved robust and became standard for nearly all Peacock sports
- By departure, Key Plays outages were classified as high-severity incidents escalated to CTO
- Enabled future automation, ad targeting, and data-driven sponsorship revenue scaling

---

## Key Results

- **Emmy Award**: Technology & Engineering Emmy (2023) for innovation in AI/ML highlight selection
- Feature became critical infrastructure for Peacock sports
- Launched across multiple sports properties (EPL, NFL, and more)
- Scaled from MVP to platform-critical service with CTO-level escalation for outages
- Rich metadata enabled both viewer engagement and monetization

## Scale & Impact

- Millions of Peacock sports viewers use Key Plays daily
- Near real-time delivery of highlights within minutes of play completion
- Cross-sports platform standardization
- AI/ML-based play selection driving engagement metrics
- Sponsorship monetization enabling revenue growth

## Technology Stack

- AI/ML models for automated play selection
- Real-time metadata extraction and enrichment
- CMS > BFF > Client > Player architecture
- Sponsorship insertion and targeting integration
- FreeWheel and ad tech integration
- Multi-platform deployment

## Awards & Recognition

- **Technology & Engineering Emmy Award** (2023)
- Peer-reviewed recognition by working technologists
- Industry validation of broadcast-scale AI implementation

## Resume Bullet Language

- Head architect for Key Plays AI/ML solution, recognized with Technology & Engineering Emmy Award for automated near real-time highlight selection during live events
- Architected scalable sponsorship insertion system for Key Plays enabling cross-sports platform standardization
- Designed and shipped key plays feature becoming critical infrastructure for Peacock sports with CTO-level incident escalation
- Collaborated across product, ad ops, and engineering to balance AI innovation with monetization strategy

---

## Related Projects

- [[projects/live-actions]] — Complementary interactive feature
- [[projects/olympic-daily-recap]] — Related AI/ML sports content work
- [[projects/pause-ads]] — Related ad insertion infrastructure

## Context Notes

- **Era**: AI/ML in broadcast (2022-2025)
- **Recognition**: Technology & Engineering Emmy (most prestigious Emmy for technical achievement)
- **Impact**: Scaled from MVP to platform-critical service
- **Status**: Shipped and in active use across Peacock sports
