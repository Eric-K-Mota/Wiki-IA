from flask import Blueprint, request, jsonify
from src.models.wiki import db, WikiDocument, WikiChunk
from src.services.wiki_extractor import MediaWikiExtractor
from src.services.embedding_service import EmbeddingService
from src.services.qa_service import QAService
import re

wiki_bp = Blueprint('wiki', __name__)

# Inicializar serviços
embedding_service = None
qa_service = QAService()

def get_embedding_service():
    """Lazy loading do serviço de embeddings"""
    global embedding_service
    if embedding_service is None:
        embedding_service = EmbeddingService()
    return embedding_service

# Dentro do teu ficheiro de rotas da API

@wiki_bp.route('/extract', methods=['POST'])
def extract_wiki_content():
    """
    Extrai conteúdo da Wiki com logging de micro-depuração para cada etapa.
    """
    try:
        data = request.get_json()
        wiki_url = data.get('wiki_url')
        username = 'Eric'
        password = 'Erickaw3-'
        
        if not wiki_url:
            return jsonify({'error': 'URL da Wiki é obrigatória'}), 400
        
        print("\n--- INICIANDO PROCESSO DE EXTRAÇÃO E INDEXAÇÃO ---")
        extractor = MediaWikiExtractor(wiki_url)
        
        if username and password:
            if not extractor.login(username, password):
                return jsonify({'error': 'Falha ao autenticar com a Wiki'}), 401
        
        print("Limpando bases de dados...")
        WikiChunk.query.delete()
        WikiDocument.query.delete()
        db.session.commit()
        embedding_svc = get_embedding_service()
        embedding_svc.clear_vectordb()
        
        wiki_content = extractor.extract_all_content()
        if not wiki_content:
            return jsonify({'error': 'Nenhum conteúdo encontrado na Wiki'}), 404
        
        print("\n--- PROCESSANDO E INDEXANDO PÁGINAS INDIVIDUALMENTE ---")
        processed_docs = 0
        total_chunks = 0
        
        for i, content in enumerate(wiki_content, 1):
            page_title = content.get('title', 'Título Desconhecido')
            print(f"\n({i}/{len(wiki_content)}) Processando página: '{page_title}'") 
            
            if content and content.get('content', '').strip():
                try:
                    
                    doc = WikiDocument(
                        title=content['title'],
                        content=content['content'],
                        url=content['url']
                    )
                    db.session.add(doc)
                    db.session.flush()
                    
                    chunks = embedding_svc.chunk_text(content['content'])
                    
                    if chunks:
                        embedding_svc.add_document_to_vectordb(
                            doc.id, content['title'], chunks
                        )
        
                    if chunks:
                        for chunk_index, chunk_text in enumerate(chunks):
                            chunk = WikiChunk(
                                document_id=doc.id,
                                chunk_text=chunk_text,
                                chunk_index=chunk_index
                            )
                            db.session.add(chunk)
                        total_chunks += len(chunks)
                    
                    processed_docs += 1
                    print(f"  ✅ SUCESSO: Página '{page_title}' processada.")

                except Exception as e:
                    print(f"  ❌ ERRO: Ocorreu um erro ao processar a página '{page_title}': {e}")
                    import traceback
                    traceback.print_exc()
                    db.session.rollback() # Desfaz qualquer alteração desta página no banco

            else:
                print(f"  ⚠️ AVISO: Página '{page_title}' ignorada (conteúdo vazio).")
        
        print("\nCommit final ao banco de dados...")
        db.session.commit()
        
        print("\n--- PROCESSO CONCLUÍDO ---")
        return jsonify({
            'message': 'Conteúdo extraído e processado com sucesso',
            'documents_processed': processed_docs,
            'total_chunks_created': total_chunks,
            'total_pages_found': len(wiki_content)
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Ocorreu um erro inesperado: {str(e)}'}), 500
@wiki_bp.route('/ask', methods=['POST'])
def ask_question():
    """
    Responde uma pergunta baseada na base de conhecimento, usando busca híbrida.
    """
    try:
        data = request.get_json()
        question = data.get('question')
        
        if not question:
            return jsonify({'error': 'Pergunta é obrigária'}), 400
        
        keyword = None
        match = re.search(r'(\d{3,})', question)
        if match:
            keyword = match.group(1)
            
        embedding_svc = get_embedding_service()
        relevant_chunks = embedding_svc.search_similar_chunks(question, n_results=5, keyword=keyword)
        
        if not relevant_chunks:
             return jsonify({
                 'question': question,
                 'answer': "Não encontrei nenhum documento contendo os termos específicos da sua busca. Por favor, tente reformular a pergunta.",
                 'confidence': 0.1,
                 'sources': [],
                 'context_chunks_used': 0 
             })

        response = qa_service.generate_answer(question, relevant_chunks)
        
        # --- INÍCIO DA CORREÇÃO ---

        # 1. Pega a lista de DICIONÁRIOS de fontes que o seu serviço de QA retornou.
        sources_from_qa = response.get('sources', [])
        
        fontes_com_links = []
        if sources_from_qa:
            # 2. (A CORREÇÃO ESTÁ AQUI) Extrai APENAS OS TÍTULOS para uma nova lista de strings.
            titles_for_query = [source['title'] for source in sources_from_qa]
            
            # 3. Usa a lista de strings (titles_for_query) na consulta ao banco.
            documentos = db.session.query(WikiDocument).filter(WikiDocument.title.in_(titles_for_query)).all()
            
            # 4. Cria o mapa de "título -> url".
            url_map = {doc.title: doc.url for doc in documentos}
            
            # 5. Monta a lista final para o frontend, iterando sobre a lista original de dicionários.
            for source_info in sources_from_qa:
                title = source_info['title']
                fontes_com_links.append({
                    'title': title,
                    'url': url_map.get(title, '#')
                })
        
        # --- FIM DA CORREÇÃO ---
        
        return jsonify({
            'question': question,
            'answer': response['answer'],
            'confidence': response['confidence'],
            'sources': fontes_com_links,
            'context_chunks_used': len(relevant_chunks) 
        })
        
    except Exception as e:
        print(f"ERRO NA ROTA /ask: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao processar pergunta: {str(e)}'}), 500
    
@wiki_bp.route('/search', methods=['POST'])
def search_content():
    """
    Busca conteúdo similar na base de conhecimento
    
    Body JSON:
    {
        "query": "VPN conexão",
        "limit": 5
    }
    """
    try:
        data = request.get_json()
        query = data.get('query')
        limit = data.get('limit', 50)
        
        if not query:
            return jsonify({'error': 'Query é obrigatória'}), 400
        
        # Buscar chunks relevantes
        embedding_svc = get_embedding_service()
        relevant_chunks = embedding_svc.search_similar_chunks(query, n_results=50)
        
        return jsonify({
            'query': query,
            'results': relevant_chunks
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar conteúdo: {str(e)}'}), 500

@wiki_bp.route('/status', methods=['GET'])
def get_status():
    """Retorna status da base de conhecimento"""
    try:
        doc_count = WikiDocument.query.count()
        chunk_count = WikiChunk.query.count()
        
        return jsonify({
            'documents': doc_count,
            'chunks': chunk_count,
            'status': 'ready' if doc_count > 0 else 'empty'
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao obter status: {str(e)}'}), 500

@wiki_bp.route('/documents', methods=['GET'])
def list_documents():
    """Lista todos os documentos na base de conhecimento"""
    try:
        documents = WikiDocument.query.all()
        
        return jsonify({
            'documents': [doc.to_dict() for doc in documents]
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao listar documentos: {str(e)}'}), 500

