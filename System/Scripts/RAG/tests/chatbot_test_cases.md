# RAG Chatbot Test Cases
Created: 2026-04-02
Purpose: Validate entity graph integration, recency boost, and context file usage in /fast and /chat endpoints.

## Test Cases

### 1. Personal Identity Query
**Query:** "Who is Eric Manchester?"
**Expected behavior:**
- Entity detector finds "Eric Manchester" → loads Context_People/Eric_Manchester.md
- Should include both personal and professional data
- Follow-up: "Please provide me his contact information" — should have contact details from context file

**Validates:** Entity detection, context file loading, follow-up context retention

### 2. Technical Protocol Query
**Query:** "What is SCTE-35?"
**Expected behavior:**
- Glossary match OR entity detector finds "SCTE-35" → loads Context_Technology/SCTE35.md
- Should explain: protocol for ad insertion signaling in broadcast/streaming
- Follow-up: "What data can I put in the body of the SCTE-35 message?"
- May need additional context data — flag if insufficient

**Validates:** Glossary + context file layering, technical depth

### 3. Project Status Briefing
**Query:** "I am going to have a meeting about channel assembly. What is the project's current status and what are the current architecture and/or workflows? What deliverables does Eric have in the next week? When was the Jira Ticket submitted?"
**Expected behavior:**
- Entity detector finds "Channel Assembly" → loads Context_Technology/Channel_Assembly.md
- Recency boost surfaces recent meeting notes from HarmonicInternal/ViewLift/ChannelAssembly/
- Should pull architecture details from recent 03-24, 03-26 meeting notes
- Jira ticket data may or may not exist — should state if not found rather than hallucinate

**Validates:** Entity detection, recency boost, multi-part question handling, honesty about missing data

### 4. Meeting Prep — Person + Company
**Query:** "I have to meet with Manik from ViewLift. I need to be prepared with an overview of Manik and the current projects in process with ViewLift."
**Expected behavior:**
- Entity detector finds "Manik" → loads Context_People/Manik.md
- Entity detector finds "ViewLift" → loads Context_Companies/ViewLift.md
- Graph connections: Manik ↔ ViewLift ↔ Channel Assembly ↔ DirtVision
- Recency boost surfaces recent ViewLift project meetings
- Combined: person background + company context + active project status

**Validates:** Multi-entity detection, graph traversal, context combination, recency

### 5. Specific Data Lookup
**Query:** "What is Jessica's Zoom URL?"
**Expected behavior:**
- Entity detector finds "Jessica" → loads Context_People/Jessica.md
- Should return Zoom URL directly if present in context file
- If not present, should say so clearly

**Validates:** Entity detection, specific fact retrieval from context files

### 6. Job Search Timeline
**Query:** "When did I have my first interview with TCGPlayer? What is the current status of that process?"
**Expected behavior:**
- Should search for TCGPlayer in vault content
- May find in Daily notes, email threads, or job search notes
- Should provide chronological timeline if data exists
- Should state clearly if insufficient data

**Validates:** Temporal queries, job search data retrieval

### 7. Recency — Latest ViewLift Info (the original failing query)
**Query:** "What is the latest information on ViewLift?"
**Expected behavior:**
- Entity detector finds "ViewLift" → loads Context_Companies/ViewLift.md as preamble
- "latest" triggers recency boost — weights recent mtime chunks higher
- Should return March 2026 meeting data (channel assembly deployment, pricing, Akamai transition)
- Should NOT return November 2025 "Features and Requirements" doc as top result

**Validates:** Recency boost, entity context prepending, correct temporal ordering

### 8. Cross-Entity Relationship
**Query:** "What is the relationship between Akamai and ViewLift?"
**Expected behavior:**
- Entity detector finds "Akamai" + "ViewLift"
- Loads both context files
- Graph shows connections between the two
- Recent notes about Akamai transition, CDN costs, egress pricing

**Validates:** Multi-entity, relationship inference, graph connections

### 9. Glossary Direct Hit
**Query:** "What is SSAI?"
**Expected behavior:**
- Glossary match: Server-Side Ad Insertion
- Should hit glossary first (fast path) before vector search
- Context_Technology/SSAI.md should augment if glossary is thin

**Validates:** Glossary priority, context file augmentation

### 10. Temporal + Entity Combination
**Query:** "What happened with Bloomberg this week?"
**Expected behavior:**
- Entity detection: Bloomberg
- Recency boost: "this week" should heavily weight recent chunks
- Should pull from recent daily notes or meeting notes mentioning Bloomberg

**Validates:** Temporal language detection, entity + recency combination

## Scoring Criteria
For each test case, evaluate:
1. **Entity detected correctly?** (Y/N)
2. **Context file loaded?** (Y/N)
3. **Recency-appropriate results?** (Y/N — did recent data surface when expected?)
4. **Answer quality** (1-5: 1=wrong/hallucinated, 3=partial, 5=complete and accurate)
5. **Response time** (< 3s for /fast, < 10s for /chat)
