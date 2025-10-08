#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) Integration for AI Token Manager

This module provides intelligent documentation search, context-aware assistance,
and enhanced query capabilities using vector embeddings and semantic search.
"""

import os
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass
class Document:
    """Represents a document chunk for RAG"""
    content: str
    source: str
    metadata: Dict
    embedding: Optional[List[float]] = None

class SimpleRAG:
    """
    Lightweight RAG system for documentation and code assistance
    Uses TF-IDF and keyword matching for efficient retrieval without heavy dependencies
    """
    
    def __init__(self, docs_dir: str = "."):
        self.docs_dir = Path(docs_dir)
        self.documents: List[Document] = []
        self.index: Dict[str, List[int]] = {}  # keyword -> document indices
        
    def load_documents(self):
        """Load and index all documentation files"""
        doc_files = [
            'README.md',
            'DEPLOYMENT.md',
            'USAGE_GUIDE.md',
            'API_KEY_SETUP.md',
            'AUTO_REFRESH_DOCS.md',
            'QUICKSTART.md',
            'EXO_QUICKSTART.md'
        ]
        
        for doc_file in doc_files:
            file_path = self.docs_dir / doc_file
            if file_path.exists():
                self._index_document(file_path)
        
        # Also index code comments and docstrings from main file
        main_file = self.docs_dir / 'enhanced_multi_provider_manager.py'
        if main_file.exists():
            self._index_code_file(main_file)
        
        print(f"✅ Indexed {len(self.documents)} document chunks")
    
    def _index_document(self, file_path: Path):
        """Index a markdown documentation file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by headers for better chunking
            chunks = self._split_markdown(content)
            
            for chunk in chunks:
                if chunk.strip():
                    doc = Document(
                        content=chunk,
                        source=file_path.name,
                        metadata={'type': 'documentation', 'file': str(file_path)}
                    )
                    self.documents.append(doc)
                    self._add_to_index(doc, len(self.documents) - 1)
                    
        except Exception as e:
            print(f"Warning: Failed to index {file_path}: {e}")
    
    def _index_code_file(self, file_path: Path):
        """Index docstrings and comments from code file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract docstrings
            docstring_pattern = r'"""(.*?)"""'
            docstrings = re.findall(docstring_pattern, content, re.DOTALL)
            
            for docstring in docstrings:
                if len(docstring.strip()) > 50:  # Only meaningful docstrings
                    doc = Document(
                        content=docstring,
                        source='code_documentation',
                        metadata={'type': 'code', 'file': str(file_path)}
                    )
                    self.documents.append(doc)
                    self._add_to_index(doc, len(self.documents) - 1)
                    
        except Exception as e:
            print(f"Warning: Failed to index code file {file_path}: {e}")
    
    def _split_markdown(self, content: str, max_chunk_size: int = 1000) -> List[str]:
        """Split markdown content into chunks by headers"""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in content.split('\n'):
            # Start new chunk at headers
            if line.startswith('#') and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = len(line)
            else:
                current_chunk.append(line)
                current_size += len(line)
                
                # Split if chunk gets too large
                if current_size > max_chunk_size:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _add_to_index(self, doc: Document, doc_idx: int):
        """Add document keywords to inverted index"""
        keywords = self._extract_keywords(doc.content)
        
        for keyword in keywords:
            if keyword not in self.index:
                self.index[keyword] = []
            self.index[keyword].append(doc_idx)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Convert to lowercase and split
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                     'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
                     'that', 'these', 'those', 'it', 'its', 'if', 'then', 'than', 'so'}
        
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        """Search for relevant documents"""
        query_keywords = self._extract_keywords(query)
        
        # Score documents based on keyword matches
        scores: Dict[int, float] = {}
        
        for keyword in query_keywords:
            if keyword in self.index:
                for doc_idx in self.index[keyword]:
                    if doc_idx not in scores:
                        scores[doc_idx] = 0
                    scores[doc_idx] += 1
        
        # Boost exact phrase matches
        for doc_idx, doc in enumerate(self.documents):
            if query.lower() in doc.content.lower():
                if doc_idx not in scores:
                    scores[doc_idx] = 0
                scores[doc_idx] += 5
        
        # Sort by score and return top results
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = [(self.documents[idx], score) for idx, score in sorted_results]
        return results
    
    def get_context(self, query: str, max_tokens: int = 2000) -> str:
        """Get relevant context for a query"""
        results = self.search(query, top_k=5)
        
        if not results:
            return "No relevant documentation found."
        
        context_parts = []
        total_length = 0
        
        for doc, score in results:
            doc_text = f"[Source: {doc.source}]\n{doc.content}\n"
            doc_length = len(doc_text)
            
            if total_length + doc_length > max_tokens:
                break
            
            context_parts.append(doc_text)
            total_length += doc_length
        
        return "\n---\n".join(context_parts)
    
    def answer_question(self, question: str) -> str:
        """Provide an answer based on documentation"""
        context = self.get_context(question)
        
        if not context or context == "No relevant documentation found.":
            return self._fallback_answer(question)
        
        # Simple rule-based answering
        question_lower = question.lower()
        
        if 'how' in question_lower or 'setup' in question_lower or 'install' in question_lower:
            return self._extract_instructions(context)
        elif 'what' in question_lower or 'explain' in question_lower:
            return self._extract_explanation(context)
        elif 'error' in question_lower or 'fix' in question_lower or 'troubleshoot' in question_lower:
            return self._extract_troubleshooting(context)
        else:
            return self._format_context(context)
    
    def _extract_instructions(self, context: str) -> str:
        """Extract step-by-step instructions from context"""
        lines = context.split('\n')
        instructions = []
        
        for i, line in enumerate(lines):
            if re.match(r'^\d+\.|^[-*]\s|^###?\s', line.strip()):
                instructions.append(line.strip())
            elif line.strip().startswith('```'):
                # Include code blocks
                j = i + 1
                code_block = [line]
                while j < len(lines) and not lines[j].strip().startswith('```'):
                    code_block.append(lines[j])
                    j += 1
                if j < len(lines):
                    code_block.append(lines[j])
                instructions.append('\n'.join(code_block))
        
        if instructions:
            return '\n'.join(instructions)
        return context[:500]  # Fallback to first 500 chars
    
    def _extract_explanation(self, context: str) -> str:
        """Extract explanatory content"""
        # Look for paragraphs with explanatory content
        paragraphs = [p.strip() for p in context.split('\n\n') if len(p.strip()) > 50]
        return '\n\n'.join(paragraphs[:3])  # Top 3 paragraphs
    
    def _extract_troubleshooting(self, context: str) -> str:
        """Extract troubleshooting information"""
        lines = context.split('\n')
        troubleshooting = []
        
        in_troubleshooting = False
        for line in lines:
            if 'troubleshoot' in line.lower() or 'error' in line.lower() or 'fix' in line.lower():
                in_troubleshooting = True
            
            if in_troubleshooting:
                troubleshooting.append(line)
                if len(troubleshooting) > 20:  # Limit size
                    break
        
        if troubleshooting:
            return '\n'.join(troubleshooting)
        return self._format_context(context)
    
    def _format_context(self, context: str) -> str:
        """Format context for display"""
        return context[:1000] + ('...' if len(context) > 1000 else '')
    
    def _fallback_answer(self, question: str) -> str:
        """Provide fallback answer when no documentation found"""
        question_lower = question.lower()
        
        if 'api' in question_lower and 'key' in question_lower:
            return """To add API keys:
1. Use environment variables: export OPENROUTER_API_KEY="your_key"
2. Or add them via the Settings tab in the web interface
3. Keys are encrypted and stored securely"""
        
        elif 'install' in question_lower or 'setup' in question_lower:
            return """Quick setup:
1. Clone the repository
2. Create virtual environment: python3 -m venv venv
3. Activate it: source venv/bin/activate
4. Install dependencies: pip install -r requirements.txt
5. Run: streamlit run enhanced_multi_provider_manager.py"""
        
        elif 'deploy' in question_lower:
            return """Deployment options:
1. Local: ./start.sh
2. Docker: docker-compose up -d
3. Cloud: See DEPLOYMENT.md for platform-specific instructions"""
        
        else:
            return "Please check the documentation files (README.md, DEPLOYMENT.md) for more information."

class EnhancedRAGAssistant:
    """Enhanced RAG assistant with provider integration"""
    
    def __init__(self, rag: SimpleRAG, token_manager=None):
        self.rag = rag
        self.token_manager = token_manager
        self.conversation_history: List[Dict] = []
    
    def ask(self, question: str, use_ai: bool = False) -> str:
        """Ask a question and get an answer"""
        # First, try to answer from documentation
        doc_answer = self.rag.answer_question(question)
        
        if use_ai and self.token_manager:
            # Enhance with AI if available
            return self._get_ai_enhanced_answer(question, doc_answer)
        
        return doc_answer
    
    def _get_ai_enhanced_answer(self, question: str, doc_answer: str) -> str:
        """Get AI-enhanced answer using available providers"""
        try:
            # Build prompt with context
            prompt = f"""Based on this documentation:

{doc_answer}

Please answer this question: {question}

Provide a clear, concise answer focusing on practical steps."""

            messages = [{"role": "user", "content": prompt}]
            
            # Try to get response from token manager
            response, error = self.token_manager.send_chat_completion(messages)
            
            if error:
                return doc_answer  # Fallback to doc answer
            
            if response and 'choices' in response:
                ai_answer = response['choices'][0]['message']['content']
                return ai_answer
            
        except Exception as e:
            print(f"AI enhancement failed: {e}")
        
        return doc_answer
    
    def get_suggestions(self, context: str) -> List[str]:
        """Get helpful suggestions based on context"""
        suggestions = []
        context_lower = context.lower()
        
        if 'error' in context_lower:
            suggestions.extend([
                "Check the error logs for more details",
                "Verify your API keys are correctly set",
                "Review the troubleshooting section in DEPLOYMENT.md"
            ])
        
        if 'deploy' in context_lower:
            suggestions.extend([
                "Run health_check.py to verify system status",
                "Use validate_deployment.py before deploying",
                "Check DEPLOYMENT.md for platform-specific instructions"
            ])
        
        if 'api' in context_lower or 'key' in context_lower:
            suggestions.extend([
                "Use environment variables for API keys in production",
                "Never commit API keys to version control",
                "Keys are encrypted using Fernet encryption"
            ])
        
        return suggestions[:5]  # Limit to 5 suggestions

def main():
    """Demo the RAG system"""
    print("=" * 70)
    print("🤖 RAG Assistant for AI Token Manager")
    print("=" * 70)
    print()
    
    # Initialize RAG
    rag = SimpleRAG()
    print("📚 Loading documentation...")
    rag.load_documents()
    print()
    
    assistant = EnhancedRAGAssistant(rag)
    
    # Demo queries
    demo_queries = [
        "How do I install the application?",
        "How to add API keys?",
        "What deployment options are available?",
        "How to troubleshoot errors?"
    ]
    
    for query in demo_queries:
        print(f"❓ Question: {query}")
        print(f"💡 Answer:")
        answer = assistant.ask(query)
        print(answer)
        print()
        print("-" * 70)
        print()
    
    # Interactive mode
    print("\n🎯 Interactive Mode (type 'exit' to quit)")
    print("-" * 70)
    
    while True:
        try:
            query = input("\n❓ Your question: ").strip()
            if query.lower() in ['exit', 'quit', 'q']:
                break
            
            if not query:
                continue
            
            answer = assistant.ask(query)
            print(f"\n💡 Answer:\n{answer}")
            
            suggestions = assistant.get_suggestions(query)
            if suggestions:
                print(f"\n📌 Related suggestions:")
                for i, suggestion in enumerate(suggestions, 1):
                    print(f"   {i}. {suggestion}")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
