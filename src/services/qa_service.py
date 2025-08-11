# src/services/qa_service.py
import re
from typing import List, Dict

class QAService:
    """
    Serviço para geração de respostas que prioriza extrair a 'solução' do contexto.
    """

# Dentro de src/services/qa_service.py

    def generate_answer(self, question: str, context_chunks: List[Dict]) -> Dict:
        """
        Versão Final: Junta todos os chunks recebidos para remontar o documento antes de extrair a solução.
        """
        if not context_chunks:
            return { 'answer': 'Desculpe, não encontrei informações...', 'confidence': 0.0, 'sources': [] }

        # Passo 1: Junta o conteúdo de todos os chunks para ter o texto completo
        full_document_text = "\n".join([chunk['content'] for chunk in context_chunks])
        
        # Limpa o texto completo
        clean_content = re.sub(r'^(Título da Página:.*?\n\n)?(Conteúdo:\s)?', '', full_document_text, flags=re.DOTALL).strip()
        
        # Procura pela solução no texto completo
        solution_match = re.search(r'solucao\s*=\s*(.*?)(?=\n\s*\w+\s*=|$)', clean_content, re.IGNORECASE | re.DOTALL)
        
        answer = ""
        if solution_match:
            found_solution = solution_match.group(1).strip()
            if found_solution:
                answer = found_solution

        # Fallback se não encontrar a solução no texto completo
        if not answer:
            answer = clean_content if clean_content else f"Encontrei o documento '{context_chunks[0]['metadata']['title']}', mas não consegui extrair um resumo claro."

        sources = self._extract_sources(context_chunks)
        confidence = self._calculate_confidence(context_chunks)

        return { 'answer': answer, 'confidence': round(confidence, 2), 'sources': sources }
        
    def _calculate_confidence(self, context_chunks: List[Dict]) -> float:
        if not context_chunks:
            return 0.0
        return min(context_chunks[0].get('similarity_score', 0.0), 1.0)

    def _extract_sources(self, context_chunks: List[Dict]) -> List[Dict]:
        sources = []
        seen_ids = set()
        for chunk in context_chunks:
            if 'metadata' in chunk and chunk['metadata'] and 'document_id' in chunk['metadata']:
                doc_id = chunk['metadata']['document_id']
                if doc_id not in seen_ids:
                    sources.append({
                        'title': chunk['metadata'].get('title', 'Título não disponível'),
                        'document_id': doc_id,
                        'relevance': chunk.get('similarity_score', 0.0)
                    })
                    seen_ids.add(doc_id)
        
        sources.sort(key=lambda x: x['relevance'], reverse=True)
        return sources[:3]