---
name: NBCUniversal Principal End-to-End Architect
description: Role at NBCUniversal (2021-2025) leading interactive and AI/ML product development for Peacock
type: role
company: NBCUniversal
title: Principal End-to-End Architect
dates: 2021-2025
location: Remote
employment_type: Full-time
---

# NBCUniversal — Principal End-to-End Architect (2021–February 2025)

## Role Summary

Principal architect driving front-end and back-end product innovation for Peacock streaming platform. Led technical solutions teams in delivering complex interactive experiences and AI/ML-powered sports features. Architected overlay core service for live and VOD experiences, pioneering in-house solutions for user interactive experiences. Demonstrated market leadership in interactive personalization and AI-driven content at scale during record-breaking Paris 2024 Olympics coverage.

## Key Responsibilities

- Lead technical solutions teams in delivering compelling front and back end complex products
- Provided knowledge on technologies solutions to supporting alignment of applications and the product roadmap
- Created all solutions with capabilities to support large scale usership across multiple propositions
- Identified and developed an in-house solution for user interactive experiences
- Architected and collaborated across teams to create a overlay core service for live and VOD interactive experiences
- Led the development of Live Actions interactions for Olympics programming, ensuring time-synced overlays for viewers
- **Head Architect for Key Plays AI/ML solution** for automated selection of highlights during live events allowing users to view them just after the play happened with rich metadata
- Architected and implemented the GenAI driven Daily Olympic Recaps with the voice of Al Michaels
- Key Architect for products from the Ad Innovation organization solving complex projects that drove greater ad revenue
- Launched innovative ad tech and UI/UX solutions that helped increased ad revenue by over 200%
- Operated autonomously in setting technical priorities, aligning with business strategy while managing cross-team execution from ingest to playback systems
- Anticipated growing audience demand for interactive and AI-personalized sports experiences
- Designed and launched a greenfield interactive content platform enabling streamlined editorial workflows for live and VOD programming
- Guided product pivots using industry trend analysis and user testing insights, ensuring market fit for AI/ML-based recap products
- Partnered with ad operations, sales, and architecture teams to integrate monetization strategies into product roadmaps

## Key Accomplishments

### Accomplishment 1: Live Actions Ideation & Launch

**Situation**: After early user testing of a new interactive feature, the core product/design team received overwhelmingly negative feedback. The original idea was scrapped, and the team was frozen—stuck in analysis paralysis, stressed, and unsure how to proceed.

**Task**: Help the team rapidly recover by rebooting ideation and coalescing around a new product direction.

**Action**:
- Took a 4AM train to NYC—scheduled in-person whiteboard workshop for next morning
- Prepped the space, whiteboards, sticky notes, and facilitation plan—created safe room for ideation
- Led "no bad ideas" brainstorm—encouraged open submission, regardless of feasibility
- Facilitated rapid down-selection based on user impact, tech feasibility, business value
- Acted as technical guide to help shape selected concept into delivery-ready form
- Architected end-to-end system and coordinated implementation with engineering teams

**Result**:
- Team recovered and selected a new direction within a single morning session
- The resulting product—**Live Actions**—launched during Olympics (e.g., "keep watching soccer?")
- Feature became global standard across Peacock, Sky Showtime, and Showmax
- Also used for contextual ad overlays and promo interactions (e.g., "Add Oppenheimer to My Stuff")
- Patent filed under NDA for overlay trigger logic and reusable platform
- Event boosted team confidence and delivered a measurable innovation win under pressure

---

### Accomplishment 2: In-House Overlay Platform (NBCU Overlay Core Service)

**Situation**: NBCU was testing interactive overlays but vendor options were expensive and claimed IP. Needed a scalable in-house solution.

**Task**: Build a reusable internal overlay platform that unified UX logic, supported metadata triggers, and delivered real-time overlays—in time for the Olympics.

**Action**:
- Researched overlay vendors → rejected due to cost + IP risk
- Designed in-house backend service with unified overlay logic
- Standardized API spec for live + VOD parity
- Integrated metadata targeting and suppression logic
- Enabled studio-triggered overlays via broadcast ops → frame-accurate
- Collaborated with product, engineering, and broadcast teams

**Result**:
- Launched at Olympics for Gold Zone—allowed real-time content jumps
- Reused for ad overlays during promos + wrap-up shows
- Now a global NBCU service (Peacock, Sky, Showmax)
- Patent filed under NDA
- Saved dev effort via template reuse
- Still in active use and powering new innovation streams

---

### Accomplishment 3: Olympic Daily Rundown (GenAI Al Michaels Recaps)

**Situation**: NBCU aimed to deliver personalized Olympic highlights using GenAI and editorial curation, including an AI-generated Al Michaels voiceover.

**Task**: As sole architect for ingest and enrichment, design and operate the end-to-end acquisition pipeline for highlight clips and metadata.

**Action**:
- Led ingest and processing for both editorial and FFMPEG-based clip generation
- Integrated RAG-compatible metadata enrichment from internal and public sources
- Supported legal and compliance reviews, especially for AI-generated voice and Olympic footage
- Scoped and onboarded 3rd-party AI voice vendor for Al Michaels clone using licensed NBC Sports archival material
- Selected iOS/tvOS for playback platforms due to reach and stability
- Collaborated with VP lead architect (playlist generation) and acted as primary contact for marketing, Olympics, and security teams

**Result**:
- Architecture supported daily personalized playlists for millions of users
- NBCU processed over 5,000 hours of footage using AI
- Platform proved stable despite mid-Olympics voiceover challenges
- Work was politically high-visibility and showcased NBCU's AI capabilities globally
- Generated 7M+ personalized video variants

---

### Accomplishment 4: BrightLine Frame Ads Integration

**Situation**: NBCU aimed to support BrightLine's "frame ad" (squeeze-back) format. BrightLine initially wanted deep control over the Peacock player through its SDK—a direct violation of platform standards.

**Task**: Architect a solution that complies with internal standards, triggers frame-accurate live ads, and maintains modular communication.

**Action**:
- Rejected BrightLine's SDK control request and negotiated vendor alignment at executive levels
- Advocated for SCTE-35-based event triggers instead of client-preferred ID3 tags
- Faced cross-team resistance due to 3-way communication model complexity
- Created tailored architecture wikis, low-level diagrams, and led VP/SVP review meetings
- Walked alternative proposals through roadmap failures and got final alignment
- Oversaw engineering intake and delivery of final integration

**Result**:
- Successfully launched frame ads—now used across all BrightLine formats (VOD and Live)
- Internal teams declared the solution "rock solid" in retrospectives
- BrightLine adopted the SDK usage model as canonical
- Generated millions of ad impressions, unlocking dynamic formats Peacock could monetize at scale

---

### Accomplishment 5: Pause Ads & SAM (Static Ads Manager) Architecture

**Situation**: Peacock's Pause Ads feature supported only 10 static images per session due to FreeWheel response size limits. Product wanted unlimited configurable ads with variable screen time.

**Task**: Architect a client-side system to support rolling ad calls, flexible configurations, and advanced reporting.

**Action**:
- Architected FreeWheel-integrated rolling ad call system: initial batch + trigger-based follow-ups
- Used client-side caching to optimize image delivery and minimize latency
- Designed quartile-based reporting tied to pause events and ad slots
- Deferred full "end tag" tracking due to complexity but outlined enhancement plan
- Partnered with a Solutions Architect and Ad Ops domain expert
- Created data flows, MVP roadmap, and technical wiki

**Result**:
- Architecture minimized FreeWheel call volume while vastly improving ad flexibility
- SAM was adopted as key delivery mechanism and greenlit by senior leadership
- Reporting framework enabled richer metrics for monetization analysis
- Unified solution enabled scalability across pause ads, sponsorships, and future static ad products

---

### Accomplishment 6: Key Plays Sponsorships Architecture

**Situation**: Key Plays sponsorships were manually configured, lacked auditability, and couldn't scale as more sports were added.

**Task**: Architect a scalable, auditable sponsorship solution for Key Plays.

**Action**:
- Identified that technical debt and manual processing were limiting monetization
- Advocated for reusable, multi-use architecture: CMS > BFF > Client > Player
- Designed sponsorship insertion system using static assets and logic for ad vs. no-ad subscribers
- Collaborated with Ad Ops to define preconfiguration standards
- Secured SVP buy-in and mapped integration timeline to SAM
- Prioritized long-term sustainability and modularity

**Result**:
- MVP launched for English Premier League in 2022, became stable cornerstone
- Architecture proved robust and became standard for nearly all Peacock sports
- By departure, Key Plays outages were classified as high-severity incidents
- Enabled future automation, ad targeting, and data-driven sponsorship revenue scaling
- **Technology & Engineering Emmy Award** received for Key Plays design

---

### Accomplishment 7: Mentorship of Haannah Wallace (TPM Development)

**Situation**: Haannah joined NBCU with no experience in streaming or advertising.

**Task**: Mentor Haannah across ad tech, streaming, and architecture domains to help her become a lead TPM.

**Action**:
- Delivered foundational lessons on streaming media and ad workflows
- Acted as backup during escalations, giving her space to learn and lead
- Collaborated on complex projects like BrightLine, Frame Ads, SAM, and Pause Ads
- Provided strategic guidance, architecture context, and helped her navigate internal processes
- Ensured she could operate independently and credibly with senior stakeholders

**Result**:
- Haannah became the lead TPM for Ad Innovation globally
- Credited mentor for her success
- Successfully co-delivered several major ad innovation products
- Left behind a culture of mentorship and knowledge transfer

---

## Technologies & Infrastructure

- **Platforms**: Peacock, Sky Showtime, Showmax, iOS, tvOS
- **Video/Streaming**: OTT/VOD Architecture, Live streaming, HLS, DASH, CMAF, H.264, H.265, WebRTC, Low Latency Streaming, Adaptive Bitrate
- **Ad Tech**: SSAI, CSAI, Dynamic Ad Insertion, SCTE-35, SCTE-104, SMPTE, VAST, FreeWheel, BrightLine SDK
- **AI/ML**: GenAI, AI-driven content processing, AI voice generation, RAG metadata, personalized content
- **Cloud**: AWS, GCP, Azure, Cloud-based video processing
- **Development**: RESTful API Development, Microservices, API Development & Integration
- **Tools**: FFmpeg, DRM (Digital Rights Management), Multi-CDN Delivery
- **Other**: Interactive overlays, metadata management, workflow automation, compliance management

## Projects & Customers

- **Internal Products**: Peacock, Sky Showtime, Showmax (global NBCU platforms)
- **Major Events**: 2024 Olympics (multiple Emmy-winning features), English Premier League, NFL coverage
- **Vendors**: BrightLine, FreeWheel, AWS Media Services, AI voice vendors
- **Features Delivered**: Key Plays (Emmy Award winner), Live Actions (Emmy recognition), Olympic Daily Recaps (7M+ variants), Pause Ads, Frame Ads, Overlay Platform

## Awards & Recognition

- **Outstanding Interactive Experience Emmy Award** (2025) — Paris 2024 Olympics, sole Software Developer credit for Live Actions and Daily Recap workflows
- **Technology & Engineering Emmy Award** (2023) — Key Plays feature design and delivery

## Resume Bullet Language

- Architected and built Peacock Live Actions—the interactive viewing tool enabling fans to choose their own Olympic experience on their own terms—contributing to Emmy-winning Paris 2024 coverage (Outstanding Interactive Experience, 2025)
- Designed content workflows for AI-powered Olympic Daily Recap generating 7M+ personalized video variants with Al Michaels' synthesized narration, supporting 23.5 billion streamed minutes
- Head architect for Key Plays AI/ML sports highlights feature, recognized with Technology & Engineering Emmy Award for innovative near-real-time highlight selection and delivery
- Architected in-house overlay core service for live and VOD interactive experiences, enabling frame-accurate studio-controlled overlays across Peacock, Sky Showtime, and Showmax
- Increased Peacock ad revenue by over 200% through innovative ad tech and UI/UX solutions, including Frame Ads, Pause Ads, and dynamic sponsorship insertion
- Architected and launched greenfield interactive content platform enabling streamlined editorial workflows for live and VOD programming at scale
- Mentored emerging technical talent including developing Haannah Wallace into lead TPM for Ad Innovation globally

---

## Context Notes

- **Era**: Interactive personalization and AI/ML at scale (2021-2025)
- **Scale**: Served millions of Peacock viewers globally; 7M+ personalized variants; 23.5 billion streaming minutes
- **Impact**: Demonstrated market leadership in interactive sports streaming and AI-driven personalization
- **Industry Recognition**: Four Emmy Awards across career, including two at NBCU alone
- **Departure**: Organizational restructuring in February 2025
- **Leadership**: Autonomous technical decision-making; executive alignment; cross-team coordination
