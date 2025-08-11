import requests
import re
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional

class MediaWikiExtractor:
    """Classe para extrair conteúdo de uma Wiki MediaWiki"""
    
    def __init__(self, base_url: str):
        """
        Inicializa o extrator com a URL base da Wiki
        
        Args:
            base_url: URL base da Wiki MediaWiki (ex: https://wiki.empresa.com)
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api.php"
        self.session = requests.Session()




    def login(self, username: str, password: str) -> bool:
        """
        Realiza login na Wiki usando o método antigo (para versões antigas do MediaWiki)
        
        Args:
            username: Nome de usuário da Wiki
            password: Senha do usuário
        
        Returns:
            True se o login for bem-sucedido, False caso contrário
        """
        try:
            response = self.session.post(self.api_url, data={
                'action': 'login',
                'lgname': username,
                'lgpassword': password,
                'format': 'json'
            })
            response.raise_for_status()
            data = response.json()
            
            if data.get('login', {}).get('result') == 'Success':
                print("Login bem-sucedido")
                return True
            else:
                print(f"Falha no login: {data}")
                return False
        except Exception as e:
            print(f"Erro no login: {e}")
            return False
            
    def get_all_pages(self) -> List[Dict]:
        """
        Obtém lista de todas as páginas da Wiki, incluindo agora namespaces adicionais.
        """
        pages = []
        apcontinue = None
        
        while True:
            params = {
                'action': 'query',
                'list': 'allpages',
                'aplimit': 5000,  # Usar um limite seguro, o máximo pode ser 500 ou 5000 dependendo da versão
                'format': 'json',
                'apfilterredir': 'nonredirects' # NOVO: Ignora redirecionamentos
            }
            
            if apcontinue:
                params['apcontinue'] = apcontinue
            
            try:
                response = self.session.get(self.api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'query' in data and 'allpages' in data['query']:
                    pages.extend(data['query']['allpages'])
                
                if 'continue' in data:
                    apcontinue = data['continue']['apcontinue']
                else:
                    break
            except Exception as e:
                print(f"Erro ao obter lista de páginas: {e}")
                break
        
        # --- NOVO: PRINT DE DIAGNÓSTICO ---
        print("\n--- DIAGNÓSTICO DE EXTRAÇÃO ---")
        print(f"A API da Wiki retornou um total de {len(pages)} páginas.")
        print("Amostra dos primeiros 20 títulos encontrados:")
        for i, page in enumerate(pages[:20], 1):
            print(f"  {i}. {page.get('title')}")
        print("--- FIM DO DIAGNÓSTICO ---\n")
        # --- FIM DO PRINT DE DIAGNÓSTICO ---

        return pages
    
    def get_page_content(self, page_title: str) -> Optional[Dict]:
        """
        Obtém o conteúdo de uma página específica
        
        Args:
            page_title: Título da página
            
        Returns:
            Dicionário com título, conteúdo e URL da página
        """
        params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'revisions',
            'rvprop': 'content',
            'format': 'json'
        }
        
        try:
            response = self.session.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'query' in data and 'pages' in data['query']:
                pages = data['query']['pages']
                page_id = list(pages.keys())[0]
                
                if page_id != '-1':  # Página existe
                    page_data = pages[page_id]
                    if 'revisions' in page_data:
                        wikitext = page_data['revisions'][0]['*']
                        clean_content = self._clean_wikitext(wikitext)
                        
                        return {
                            'title': page_data['title'],
                            'content': clean_content,
                            'url': f"{self.base_url}/index.php?title={page_title.replace(' ', '_')}"
                        }
                        
        except Exception as e:
            print(f"Erro ao obter conteúdo da página '{page_title}': {e}")
            
        return None
    
    def _clean_wikitext(self, wikitext: str) -> str:
        """
        Versão final da limpeza de texto, otimizada para templates com campos.
        """
        # Converte <br> em quebras de linha
        text = re.sub(r'<br\s*/?>', '\n', wikitext, flags=re.IGNORECASE)

        # Remove a definição do template e as chaves finais, mantendo o conteúdo
        text = re.sub(r'\{\{FAQ erros', '', text, flags=re.IGNORECASE)
        text = text.replace('}}', '')

        # Converte o pipe | (separador de campos) em uma quebra de linha, para isolar cada campo
        text = text.replace('|', '\n')
        
        # Remove links internos mas mantém o texto
        text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
        
        # Remove links externos, mantendo o texto
        text = re.sub(r'\[http[^\s\]]*\s*([^\]]*)\]', r'\1', text)

        # Remove formatação
        text = re.sub(r"'''|''", "", text)
        
        # Remove cabeçalhos
        text = re.sub(r'=+\s*(.*?)\s*=+_?', r'\1', text, flags=re.MULTILINE)
        
        # Remove tags HTML restantes
        text = re.sub(r'<[^>]*>', '', text)
        
        # Remove tags de Categoria
        text = re.sub(r'\[\[Categoria:[^\]]*\]\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Categoria:[^\n\r]*', '', text, flags=re.IGNORECASE)

        # Limpeza final de espaços e linhas
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
        
        return text
    
    def extract_all_content(self) -> List[Dict]:
        """
        Extrai todo o conteúdo da Wiki com logging detalhado para cada página.
        """
        print("Obtendo lista de todas as páginas...")
        pages = self.get_all_pages()
        print(f"Encontradas {len(pages)} páginas na lista inicial.")
        
        content_list = []
        
        print("\n--- INICIANDO EXTRAÇÃO DE CONTEÚDO PÁGINA A PÁGINA ---")
        for i, page in enumerate(pages, 1):
            page_title = page.get('title', 'TÍTULO DESCONHECIDO')
            print(f"\n({i}/{len(pages)}) Processando: '{page_title}'")

            # Etapa 1: Tentar obter o conteúdo da página
            content = self.get_page_content(page_title)
            
            if content:
                print(f"  [ETAPA A] Conteúdo bruto obtido com sucesso.")
                
                # Etapa 2: Verificar se o conteúdo não está vazio APÓS a limpeza
                cleaned_content = content.get('content', '').strip()
                if cleaned_content:
                    print(f"  [ETAPA B] Conteúdo não está vazio após a limpeza (tamanho: {len(cleaned_content)}).")
                    content_list.append(content)
                    print(f"  ✅ SUCESSO: Página '{page_title}' adicionada à lista final.")
                else:
                    print(f"  ❌ FALHA: Página '{page_title}' IGNORADA pois o conteúdo ficou VAZIO após a limpeza.")
            else:
                print(f"  ❌ FALHA: Não foi possível obter o conteúdo da API para a página '{page_title}'.")
                
        print(f"\n--- EXTRAÇÃO CONCLUÍDA ---")
        print(f"Total de páginas na lista inicial: {len(pages)}")
        print(f"Total de páginas com conteúdo válido extraído: {len(content_list)}")
        return content_list

