import re
import uuid
from typing import List
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from thefuzz import fuzz

class EmbeddingService:
    """Serviço responsável por gerar embeddings e gerenciar o banco vetorial com ChromaDB"""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Inicializa o modelo de embeddings e o cliente do ChromaDB.
        """

        self.model = SentenceTransformer(model_name)

        self.chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name="wiki_knowledge_base",
            metadata={"description": "Base de conhecimento da Wiki interna"}
        )

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Divide o texto em chunks com coerência, baseando-se em parágrafos e frases.
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = current_chunk[-overlap:] if overlap > 0 else ""
            
            # Divide parágrafos muito longos em sentenças para não exceder o chunk_size
            if len(paragraph) > chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = current_chunk[-overlap:] if overlap > 0 else ""
                    current_chunk += sentence + " "
            else:
                current_chunk += paragraph + "\n\n"
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Gera embeddings vetoriais para uma lista de textos.
        """
        return self.model.encode(texts).tolist()

    def add_document_to_vectordb(self, document_id: int, title: str, chunks: List[str]) -> List[str]:
        """
        Armazena os embeddings e metadados dos chunks de um documento na base vetorial.
        O texto de cada chunk é ENRIQUECIDO com o título do documento para melhorar a busca.
        """
        if not chunks:
            return []

        enriched_chunks = [f"Título da Página: {title}\n\nConteúdo: {chunk}" for chunk in chunks]
        embeddings = self.generate_embeddings(enriched_chunks)
        
        embedding_ids = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            embedding_id = str(uuid.uuid4())
            embedding_ids.append(embedding_id)
            metadatas.append({
                'document_id': document_id,
                'title': title,
                'chunk_index': i,
                'chunk_length': len(chunk)
            })

        self.collection.add(
            embeddings=embeddings,
            documents=enriched_chunks,
            metadatas=metadatas,
            ids=embedding_ids
        )
        return embedding_ids

    def _extract_keywords(self, query: str) -> List[str]:
        """Extrai palavras-chave de uma query, ignorando palavras muito curtas."""
        return [word for word in re.findall(r'\b\w+\b', query.lower()) if len(word) > 3]

    def search_similar_chunks(self, query: str, n_results: int = 5, keyword: str = None) -> List[dict]:
        """
        Busca Híbrida Completa: Usa keyword para busca direta com priorização de título,
        ou uma combinação de semântica + keyword para busca normal.
        """
        
        if keyword:
            # --- Bloco para buscas com keyword (Ex: "Rejeição 528") ---

            try:
                all_docs = self.collection.get(include=['documents', 'metadatas'])
                candidate_chunks = []
                for i in range(len(all_docs['documents'])):
                    doc_content = all_docs['documents'][i]
                    if keyword.lower() in doc_content.lower():
                        candidate_chunks.append({ 'content': doc_content, 'metadata': all_docs['metadatas'][i] })
                
                if not candidate_chunks: return []

                for chunk in candidate_chunks:
                    title_lower = chunk['metadata']['title'].lower()
                    fuzzy_score = fuzz.partial_ratio(query.lower(), title_lower)
                    title_bonus = 1000 if keyword in title_lower else 0
                    chunk['rank_score'] = fuzzy_score + title_bonus

                candidate_chunks.sort(key=lambda x: x['rank_score'], reverse=True)
                best_document_id = candidate_chunks[0]['metadata']['document_id']
                
                full_document_chunks = []
                for i in range(len(all_docs['documents'])):
                    if all_docs['metadatas'][i]['document_id'] == best_document_id:
                        full_document_chunks.append({
                            'content': all_docs['documents'][i],
                            'metadata': all_docs['metadatas'][i],
                            'similarity_score': 1.0
                        })
                full_document_chunks.sort(key=lambda x: x['metadata']['chunk_index'])
                return full_document_chunks
            except Exception as e:
                print(f"Erro durante a busca com fallback: {e}")
                return []

        else:
            # --- Bloco para buscas SEMÂNTICAS (Ex: "homologar boleto sicredi") ---
            print("Executando busca semântica HÍBRIDA com reordenação por keywords.")
            query_embedding = self.model.encode([query]).tolist()[0]
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=100,
                include=['documents', 'metadatas', 'distances']
            )
            
            if not results or not results.get('documents') or not results['documents'][0]:
                return []

            query_keywords = self._extract_keywords(query)
            
            candidates = []
            for i in range(len(results['documents'][0])):
                content_lower = results['documents'][0][i].lower()
                score = 1 / (1 + results['distances'][0][i])
                keyword_bonus = sum(1 for keyword in query_keywords if keyword in content_lower)
                if query_keywords and all(keyword in content_lower for keyword in query_keywords):
                    score += 10
                candidates.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'final_score': score + keyword_bonus
                })
            
            candidates.sort(key=lambda x: x['final_score'], reverse=True)

            formatted = []
            for candidate in candidates[:n_results]:
                formatted.append({
                    'content': candidate['content'],
                    'metadata': candidate['metadata'],
                    'similarity_score': round(candidate.get('final_score', 0), 2)
                })
            return formatted

    def clear_vectordb(self):
        """
        Remove todos os dados armazenados no ChromaDB.
        """
        try:
            self.chroma_client.delete_collection("wiki_knowledge_base")
            self.collection = self.chroma_client.get_or_create_collection(
                name="wiki_knowledge_base",
                metadata={"description": "Base de conhecimento da Wiki interna"}
            )
            print("Banco de dados vetorial limpo com sucesso.")
        except Exception as e:
            print(f"Erro ao limpar banco de dados vetorial: {e}")