import re
import uuid
import os
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
        
        Args:
            model_name: Nome do modelo de embeddings (multilíngue).
        """
        print(f"Carregando modelo de embeddings: {model_name}")
        self.model = SentenceTransformer(model_name)

        # Inicializa o cliente persistente do ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )

        # Cria ou obtém a coleção onde os embeddings serão armazenados
        self.collection = self.chroma_client.get_or_create_collection(
            name="wiki_knowledge_base",
            metadata={"description": "Base de conhecimento da Wiki interna"}
        )

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Divide o texto em chunks com coerência, baseando-se em parágrafos e frases.
        
        Args:
            text: Texto completo a ser fragmentado.
            chunk_size: Tamanho aproximado por chunk (em caracteres).
            overlap: Quantidade de sobreposição entre chunks (em caracteres).
        
        Returns:
            Lista de chunks de texto.
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            if len(paragraph) > chunk_size:
                # Parágrafo muito longo: dividir por sentenças
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > chunk_size:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                            # Adiciona sobreposição
                            current_chunk = current_chunk[-overlap:] if overlap > 0 else ""
                    current_chunk += sentence + " "
            else:
                # Parágrafo de tamanho adequado
                if len(current_chunk) + len(paragraph) > chunk_size:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                        current_chunk = current_chunk[-overlap:] if overlap > 0 else ""
                current_chunk += paragraph + " "

        # Adiciona o último chunk restante
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Gera embeddings vetoriais para uma lista de textos.
        
        Args:
            texts: Lista de trechos de texto.
        
        Returns:
            Lista de embeddings (vetores numéricos).
        """
        return self.model.encode(texts).tolist()


    def add_document_to_vectordb(self, document_id: int, title: str, chunks: List[str]) -> List[str]:
        """
        Armazena os embeddings e metadados dos chunks de um documento na base vetorial.
        O texto de cada chunk é ENRIQUECIDO com o título do documento para melhorar a busca.
        """
        if not chunks:
            return []

        # Passo 1: Enriquecer cada chunk com o título do documento
        enriched_chunks = [f"Título da Página: {title}\n\nConteúdo: {chunk}" for chunk in chunks]

        # Passo 2: Gerar embeddings a partir dos chunks enriquecidos
        embeddings = self.generate_embeddings(enriched_chunks)
        
        embedding_ids = []
        metadatas = []

        for i in range(len(enriched_chunks)):
            embedding_id = str(uuid.uuid4())
            embedding_ids.append(embedding_id)
            metadatas.append({
                'document_id': document_id,
                'title': title,
                'chunk_index': i,
                'chunk_length': len(chunks[i]) # Armazenamos o tamanho do chunk original
            })

        # Passo 3: Adicionar os chunks ENRIQUECIDOS ao ChromaDB
        self.collection.add(
            embeddings=embeddings,
            documents=enriched_chunks, # Guardamos o texto completo que foi usado para o embedding
            metadatas=metadatas,
            ids=embedding_ids
        )

        return embedding_ids

    

    def search_similar_chunks(self, query: str, n_results: int = 5, keyword: str = None) -> List[dict]:
        """
        Busca Híbrida Final: Se houver keyword, encontra o melhor DOCUMENTO e retorna TODOS os seus chunks.
        """
        
        if keyword:
            print(f"Executando busca por keyword para encontrar o melhor documento: '{keyword}'")
            try:
                # 1. Pega todos os documentos do banco de dados para filtrar em Python
                all_docs = self.collection.get(include=['documents', 'metadatas'])
                
                # 2. Filtra para encontrar todos os chunks que contêm a keyword
                candidate_chunks = []
                for i in range(len(all_docs['documents'])):
                    doc_content = all_docs['documents'][i]
                    if keyword.lower() in doc_content.lower():
                        candidate_chunks.append({
                            'content': doc_content,
                            'metadata': all_docs['metadatas'][i]
                        })
                
                if not candidate_chunks:
                    return []

                # 3. Reordena os candidatos pela similaridade do TÍTULO com a pergunta
                for chunk in candidate_chunks:
                    chunk['rank_score'] = fuzz.partial_ratio(query.lower(), chunk['metadata']['title'].lower())
                candidate_chunks.sort(key=lambda x: x['rank_score'], reverse=True)

                # 4. Identifica o ID do melhor documento
                best_document_id = candidate_chunks[0]['metadata']['document_id']
                print(f"Melhor documento encontrado (ID: {best_document_id}). Reunindo todos os seus chunks.")

                # 5. Reúne TODOS os chunks que pertencem a esse melhor documento
                full_document_chunks = []
                for i in range(len(all_docs['documents'])):
                    if all_docs['metadatas'][i]['document_id'] == best_document_id:
                        full_document_chunks.append({
                            'content': all_docs['documents'][i],
                            'metadata': all_docs['metadatas'][i],
                            'similarity_score': 1.0 # Confiança máxima, pois encontramos o doc certo
                        })
                
                # 6. Ordena os chunks pela sua ordem original no documento
                full_document_chunks.sort(key=lambda x: x['metadata']['chunk_index'])
                
                return full_document_chunks

            except Exception as e:
                print(f"Erro durante a busca com fallback: {e}")
                return []

        else: # Busca semântica normal
            # ... (o código da busca semântica continua igual)
            print("Executando busca semântica padrão.")
            query_embedding = self.model.encode([query]).tolist()[0]
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )
            
            formatted = []
            if results and results.get('documents') and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    formatted.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'similarity_score': round(1 / (1 + results['distances'][0][i]), 2)
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
