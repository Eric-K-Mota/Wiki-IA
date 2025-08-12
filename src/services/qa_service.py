# src/services/qa_service.py
import re
import os
from typing import List, Dict
from dotenv import load_dotenv
import google.generativeai as genai

# Carrega as variáveis de ambiente (o GOOGLE_API_KEY do ficheiro .env)
load_dotenv()

class QAService:
    """
    Serviço de QA que utiliza a API do Gemini para gerar respostas inteligentes e formatadas.
    """

    def __init__(self):
        """Inicializa o serviço e configura o modelo Gemini."""
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("A chave de API do Google (GOOGLE_API_KEY) não foi encontrada.")
            
            genai.configure(api_key=api_key)
            # Usamos o gemini-1.5-flash, um modelo rápido e poderoso ideal para chat
            self.model = genai.GenerativeModel('gemini-1.5-flash')

        except Exception as e:

            self.model = None

  # Dentro de src/services/qa_service.py

    def generate_answer(self, question: str, context_chunks: List[Dict]) -> Dict:
        """
        Gera uma resposta sintetizada e formatada usando o modelo Gemini.
        """
        if not self.model:
            return {'answer': "O serviço de IA não está configurado corretamente.", 'confidence': 0.0, 'sources': []}

        if not context_chunks:
            return {'answer': 'Não encontrei informações na base de conhecimento para esta pergunta.', 'confidence': 0.0, 'sources': []}

        contexto_completo = "\n\n---\n\n".join([chunk['content'] for chunk in context_chunks])


        prompt = f"""
        Você é um assistente de suporte interno especialista, chamado Manus AI. Sua tarefa é responder à pergunta do usuário de forma clara e profissional.

        **REGRAS CRÍTICAS:**
        1.  Use **exclusivamente** a informação fornecida no 'CONTEXTO' abaixo.
        2.  **Seja completo e detalhado.** Inclua todos os passos, listas de campos, exemplos de código ou observações importantes que encontrar no contexto. Não resuma em excesso.
        3.  **Não invente informações** nem use conhecimento externo. Se a resposta não estiver no contexto, responda: "Com base na documentação disponível, não encontrei uma resposta direta para a sua pergunta.".
        4.  Use **formatação Markdown** (títulos com `##`, listas com `*` ou `1.`, e negrito com `**`) para tornar a resposta fácil de ler.
        5.  Se o contexto mencionar múltiplos tópicos (ex: vários bancos), foque a tua resposta no tópico específico da pergunta do usuário.
        6.  **NOVO -> Se encontrar blocos de código, especialmente SQL, mostre eles e formate-os usando blocos de código Markdown com a linguagem especificada (ex: ```sql ... ```).**
        7.  **NOVO -> Se o contexto mencionar uma imagem (ex: Arquivo:nome.jpg), NÃO a descreva. Em vez disso, insira um placeholder ÚNICO no formato: <WIKI_IMAGE>nome_da_imagem.ext</WIKI_IMAGE>.**

        ---
        **CONTEXTO EXTRAÍDO DA WIKI INTERNA:**
        {contexto_completo}
        ---

        **PERGUNTA DO USUÁRIO:**
        {question}

        **SUA RESPOSTA COMPLETA E FORMATADA:**
        """

        try:

            response = self.model.generate_content(prompt)
            answer = response.text
        except Exception as e:

            answer = "Ocorreu um erro ao comunicar com o serviço de IA. Por favor, tente novamente."

        sources = self._extract_sources(context_chunks)
        confidence = self._calculate_confidence(context_chunks)

        return {
            'answer': answer,
            'confidence': round(confidence, 2),
            'sources': sources,
        }
        

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
        return sources[:5]

    def _calculate_confidence(self, context_chunks: List[Dict]) -> float:

        if not context_chunks: return 0.0
        scores = [chunk.get('similarity_score', 0.0) for chunk in context_chunks]
        return sum(scores) / len(scores) if scores else 0.0