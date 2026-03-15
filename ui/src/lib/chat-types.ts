// Chat API Types
export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatRequest {
  message: string;
  conversation_history?: ChatMessage[];
  search_limit?: number;
}

export interface DocumentReference {
  file_path: string;
  file_name: string;
  relevance_score: number;
  excerpt?: string;
}

export interface ChatResponse {
  answer: string;
  references: DocumentReference[];
  obsidian_links: string[];
  confidence: string;
  took_ms: number;
  documents_retrieved: number;
}
