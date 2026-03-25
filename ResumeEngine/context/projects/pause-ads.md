---
name: Pause Ads & SAM (Static Ads Manager)
description: Client-side pause ad system with rolling ad calls and advanced reporting
type: project
company: NBCUniversal
dates: 2022-2023
status: Shipped
---

# Pause Ads & SAM — Static Ads Manager Architecture

## Project Summary

Client-side system architecture enabling unlimited, configurable pause ads on Peacock with advanced reporting. Replaced FreeWheel response size limitations (10 static images per session) with rolling ad call system and flexible configuration, enabling future sponsorship and static ad expansion.

## Background & Challenge

Peacock's Pause Ads feature supported only 10 static images per session due to FreeWheel response size limits. Product wanted unlimited configurable ads with variable screen time and support for live events. Reporting was weak—no visibility into actual time-on-screen or impression count.

## Key Contribution

**Architecture Design & Delivery**: Designed client-side system, rolling ad call mechanism, and reporting framework. Partnered with Solutions Architect and Ad Ops expert for implementation.

## Key Actions

- Architected FreeWheel-integrated rolling ad call system: initial batch + trigger-based follow-ups
- Used client-side caching to optimize image delivery and minimize latency
- Designed quartile-based reporting tied to pause events and ad slots (e.g., "Break 5, Slot 2, Quartile 3")
- Deferred full "end tag" tracking due to complexity across services but outlined enhancement plan
- Partnered with Solutions Architect (2 levels below Principal) and Ad Ops domain expert
- Created data flows, MVP roadmap, and technical wiki to drive understanding and buy-in

## Key Results

- Architecture minimized FreeWheel call volume while vastly improving ad flexibility
- **SAM was adopted as key delivery mechanism** and greenlit by senior leadership
- Reporting framework enabled richer metrics for monetization analysis
- Unified solution enabled scalability across pause ads, sponsorships, and future static ad products

## Technology Stack

- FreeWheel API integration
- Rolling ad call mechanism (initial batch + trigger-based)
- Client-side caching for image optimization
- Quartile-based reporting system
- Pause event and ad slot tracking

## Resume Bullet Language

- Architected client-side pause ad system supporting unlimited configurable ads with rolling FreeWheel ad calls
- Designed quartile-based reporting framework enabling visibility into ad time-on-screen and impression metrics
- Engineered solution that minimized vendor call volume while enabling scalability across pause ads, sponsorships, and future static ad products

---

## Related Projects

- [[projects/brightline-frame-ads]] — Related ad insertion infrastructure
- [[projects/key-plays-sponsorships]] — Related monetization architecture

## Context Notes

- **Vendor**: FreeWheel (ad serving platform)
- **Scale**: Scaled from 10 ads per session to unlimited configurable ads
- **Status**: Shipped and in active use on Peacock
