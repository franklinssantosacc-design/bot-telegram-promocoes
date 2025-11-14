import re
import logging
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class ParserPromocoes:
    def __init__(self):
        self.plataformas_jogos = ['Steam', 'Ubisoft Connect', 'Epic Games', 'Rockstar Launcher', 'Nuuvem']
    
    def processar_mensagem_completa(self, texto):
        """Processa a mensagem completa e retorna múltiplos produtos se existirem"""
        # Para mensagens simples, trata como produto único
        produtos = [texto]
        
        resultados = []
        for produto_texto in produtos:
            if self._eh_produto_valido(produto_texto):
                dados = self.extrair_dados(produto_texto)
                if dados['descricao'] and dados['descricao'] != '🔥[descrição do produto]':
                    resultados.append(dados)
        
        return resultados
    
    def _eh_produto_valido(self, texto):
        """Verifica se o texto parece ser um produto válido"""
        linhas = [linha.strip() for linha in texto.split('\n') if linha.strip()]
        
        # Tem pelo menos uma linha com conteúdo
        if len(linhas) < 2:
            return False
        
        # Tem preço ou cupom ou link
        tem_preco = any('R$' in linha for linha in linhas)
        tem_cupom = any('cupom' in linha.lower() or 'CUPOM' in linha for linha in linhas)
        tem_link = any(linha.startswith('http') for linha in linhas)
        
        return tem_preco or tem_cupom or tem_link
    
    def extrair_dados(self, texto):
        """Extrai informações de um único produto"""
        dados = {
            'descricao': '',
            'preco': '',
            'parcelamento': '',
            'cupom': '',
            'links': [],
        }
        
        # Extrair links PRIMEIRO
        links = re.findall(r'https?://[^\s]+', texto)
        dados['links'] = list(dict.fromkeys(links))
        
        linhas = [linha.strip() for linha in texto.split('\n') if linha.strip()]
        
        # 1. ENCONTRAR DESCRIÇÃO - CORREÇÃO AQUI
        dados['descricao'] = self._encontrar_descricao_correta(linhas, texto)
        
        # 2. ENCONTRAR PREÇO
        dados.update(self._extrair_preco_completo(texto, linhas))
        
        # 3. ENCONTRAR CUPOM
        dados['cupom'] = self._extrair_cupom_completo(texto, linhas)
        
        # 4. ENCONTRAR PARCELAMENTO
        if not dados['parcelamento']:
            dados['parcelamento'] = self._extrair_parcelamento(texto)
        
        return dados
    
    def _encontrar_descricao_correta(self, linhas, texto):
        """CORREÇÃO: Encontra a descrição mesmo sem 🔥 no início"""
        
        # CASO 1: Já começa com 🔥
        for linha in linhas:
            if linha.startswith('🔥') and len(linha) > 5:
                return self._processar_descricao(linha)
        
        # CASO 2: Linhas que claramente são descrições de produto (MELHORIA)
        for linha in linhas:
            # IGNORA linhas que NUNCA são descrição
            if self._eh_linha_nao_descricao(linha):
                continue
            
            # CORREÇÃO: Aceita linhas que começam com emojis como 🧟‍♂️, ✨➡️ desde que tenham nome de produto
            linha_limpa = self._limpar_descricao_basica(linha)
            
            # Verifica se parece uma descrição de produto após limpar
            if len(linha_limpa) > 10 and self._parece_descricao_produto(linha_limpa):
                return '🔥' + linha_limpa
        
        # CASO 3: Primeira linha que não é lixo (FALLBACK MELHORADO)
        for linha in linhas:
            if (not self._eh_linha_nao_descricao(linha) and 
                len(linha) > 8 and 
                not linha.startswith('http')):
                linha_limpa = self._limpar_descricao_basica(linha)
                if len(linha_limpa) > 5:
                    return '🔥' + linha_limpa
        
        # CASO 4: Busca por qualquer linha com nome de produto (ÚLTIMO RECURSO)
        for linha in linhas:
            if self._parece_descricao_produto(linha) and len(linha) > 15:
                linha_limpa = self._limpar_descricao_basica(linha)
                return '🔥' + linha_limpa
        
        return '🔥[descrição do produto]'
    
    def _eh_linha_nao_descricao(self, linha):
        """Verifica se a linha definitivamente NÃO é descrição"""
        padroes_nao_descricao = [
            r'^http', r'^🔗', r'^📍', r'^⭐️', r'^✍️', r'^🎟', r'^💵', r'^💸', 
            r'^📝', r'^✨', r'^POR:', r'^Valor:', r'^Cupom', r'^CUPOM', 
            r'^Oferta:', r'^Use o', r'^Ative por', r'^Vendido e entregue',
            r'^Parcelado', r'^Garantia', r'^Limitado', r'^OFF', r'^Origem do',
            r'^Por apenas:', r'^COMPREI', r'^Link de compra:', r'^🔗 Link',
            r'^Aqui estão', r'^Visite a página', r'^www\.', r'^\d+×',
            r'^❌', r'^✅', r'^⚠️',
        ]
        
        linha_lower = linha.lower()
        for padrao in padroes_nao_descricao:
            if re.match(padrao, linha, re.IGNORECASE):
                return True
        
        # Não considera linhas muito curtas como descrição
        if len(linha.strip()) < 10:
            return True
            
        return False
    
    def _parece_descricao_produto(self, linha):
        """Verifica se a linha parece uma descrição de produto"""
        termos_produto = [
            'teclado', 'mouse', 'monitor', 'processador', 'placa', 'notebook', 
            'game', 'power bank', 'combo', 'desodorante', 'ssd', 'headset', 
            'console', 'cooler', 'cadeira', 'fone', 'webcam', 'impressora',
            'tablet', 'smartphone', 'smartwatch', 'tv', 'som', 'caixa', 'fonte',
            'memória', 'hd', 'nvme', 'gamer', 'escritório', 'mesh', 'gabinete',
            'mancer', 'redragon', 'elg', 'intel', 'amd', 'rainbow'
        ]
        
        marcas = [
            'nike', 'alienware', 'dell', 'inno3d', 'acer', 'egeo', 'xfx', 'amd', 
            'nvidia', 'radeon', 'geforce', 'lg', 'ultragear', 'corsair', 'vgn', 
            'boyhom', 'redragon', 'irok', 'aula', 'elg', 'msi', 'asus', 'intel',
            'mancer'
        ]
        
        linha_lower = linha.lower()
        
        # Tem termos de produto ou marcas
        if any(termo in linha_lower for termo in termos_produto + marcas):
            return True
        
        # É uma linha com palavras em maiúsculo/minúsculo (nome de produto)
        palavras = linha.split()
        if len(palavras) >= 2:
            # Verifica se tem pelo menos 2 palavras que começam com maiúscula
            palavras_maiusculas = sum(1 for p in palavras if p and p[0].isupper())
            if palavras_maiusculas >= 2:
                return True
        
        return False
    
    def _extrair_preco_completo(self, texto, linhas):
        """Extrai preço de todas as formas possíveis"""
        resultado = {'preco': '', 'parcelamento': ''}
        
        # TODOS os padrões de preço em ordem de prioridade
        padroes_preco = [
            r'POR:\s*([\d\.,]+)(?:\s*REAIS)?',
            r'De\s*R\$\s*[\d\.,]+\s*por\s*R\$\s*([\d\.,]+)',
            r'Valor:\s*R\$\s*([\d\.,]+)',
            r'Por\s*apenas:\s*R\$\s*([\d\.,]+)',
            r'R\$\s*([\d\.,]+)\s*\(Cartão\)',
            r'R\$\s*([\d\.,]+)\s*NO\s*CARTÃO',
            r'R\$\s*([\d\.,]+)\s*NO\s*PIX',
            r'R\$\s*([\d\.,]+)\s*\(NO PIX\)',
            r'R\$\s*([\d\.,]+)\s*REAIS',
            r'💵R\$\s*([\d\.,]+)',
            r'💸\s*Valor:\s*R\$\s*([\d\.,]+)',
            r'R\$\s*([\d\.,]+)',
            r'por\s*R\$\s*([\d\.,]+)\s*com\s*ativação',
        ]
        
        for padrao in padroes_preco:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                resultado['preco'] = match.group(1)
                break
        
        # Busca em linhas individuais
        if not resultado['preco']:
            for linha in linhas:
                rs_match = re.search(r'R\$\s*([\d\.,]+)', linha)
                if rs_match and len(linha) < 100:
                    resultado['preco'] = rs_match.group(1)
                    break
        
        # Parcelamento
        parcelamento_match = re.search(r'(\d+x\s*sem\s*juros)', texto, re.IGNORECASE)
        if parcelamento_match:
            resultado['parcelamento'] = parcelamento_match.group(1)
        
        return resultado
    
    def _extrair_cupom_completo(self, texto, linhas):
        """Extrai cupom de todas as formas possíveis"""
        
        # 1. Padrão Shopee - Resgate
        for linha in linhas:
            resgate_match = re.search(r'RESGATE\s*(?:O)?\s*CUPOM\s*DE\s*R?\$?(\d+)\s*OFF', linha, re.IGNORECASE)
            if resgate_match:
                return f'Resgate cupom de R${resgate_match.group(1)} OFF'
            
            resgate_simples_match = re.search(r'Resgate\s*Cupom\s*(\d+)\s*Off\s*:', linha, re.IGNORECASE)
            if resgate_simples_match:
                return f'Resgate cupom de R${resgate_simples_match.group(1)} OFF'
        
        # 2. Padrão AliExpress complexo
        for linha in linhas:
            # Padrão: "3KT5RJCUDNC6 + LIVENA410 + 1090 moedas"
            ali_complexo = re.search(r'([A-Z0-9]+\s*\+\s*[A-Z0-9]+\s*\+\s*\d+\s*moedas?)', linha, re.IGNORECASE)
            if ali_complexo:
                return ali_complexo.group(1).strip()
            
            # Padrão: "AGORAC ou BRMEGA03 + Cupom da Loja + 1562 Moedas no APP"
            ali_multi = re.search(r'([A-Z0-9]+\s*(?:ou|/)\s*[A-Z0-9]+\s*(?:\+[^+]*)*\+?\s*\d+\s*Moedas?\s*(?:no\s*APP)?)', linha, re.IGNORECASE)
            if ali_multi:
                return ali_multi.group(1).strip()
        
        # 3. Cupom com emoji específico
        for linha in linhas:
            if '🎟' in linha or '📝' in linha:
                cupom_texto = re.sub(r'^[🎟📝]\s*', '', linha)
                cupom_texto = re.sub(r'^Cupom[:\s]*', '', cupom_texto, flags=re.IGNORECASE)
                return self._limpar_cupom(cupom_texto)
        
        # 4. Padrão tradicional
        for linha in linhas:
            # "-Cupom: X"
            cupom_traco = re.search(r'-\s*Cupom[:\s]*([^\n]+)', linha, re.IGNORECASE)
            if cupom_traco:
                return self._limpar_cupom(cupom_traco.group(1))
            
            # "Cupom: X"
            cupom_normal = re.search(r'Cupom[:\s]*([^\n]+)', linha, re.IGNORECASE)
            if cupom_normal:
                return self._limpar_cupom(cupom_normal.group(1))
            
            # "Cupom X" (sem dois pontos)
            cupom_sem_pontos = re.search(r'Cupom\s+([A-Z0-9]+)', linha, re.IGNORECASE)
            if cupom_sem_pontos:
                return cupom_sem_pontos.group(1)
        
        # 5. Cupom solto
        for linha in linhas:
            if (re.match(r'^[A-Z0-9]+$', linha) and 
                5 <= len(linha) <= 20 and 
                not linha.startswith('http')):
                return linha
        
        return ''
    
    def _extrair_parcelamento(self, texto):
        """Extrai informações de parcelamento"""
        parcelamento_match = re.search(r'(\d+x\s*sem\s*juros)', texto, re.IGNORECASE)
        if parcelamento_match:
            return parcelamento_match.group(1)
        return ''
    
    def _processar_descricao(self, texto):
        """Processa a descrição removendo elementos indesejados"""
        texto_limpo = texto
        
        # Remove múltiplos 🔥 mas mantém um
        texto_limpo = re.sub(r'^🔥+', '🔥', texto_limpo)
        
        # Remove emojis problemáticos
        texto_limpo = re.sub(r'[🧟‍♂️⚡️✨️✔️⚠️✅⭐️🇧🇷✍️💸📝✨➡️]', '', texto_limpo)
        
        # Remove padrões indesejados
        padroes_remover = [
            r'[💵💰]?\s*R\$\s*[\d\.,]+',
            r'-?\s*R\$\s*[\d\.,]+',
            r'\(Cartão\)',
            r'\s*por\s*R\$\s*[\d,]+\s*com\s*ativação[^\.]*\.?',
            r'\s*na[^\.]*loja[^\.]*\.?',
            r'\* \d+×',  # Remove " * 1×"
            r'Aqui estão[^🔥]*—',  # Remove texto introdutório
        ]
        
        for padrao in padroes_remover:
            texto_limpo = re.sub(padrao, '', texto_limpo)
        
        texto_limpo = texto_limpo.strip()
        
        if not texto_limpo.startswith('🔥'):
            texto_limpo = '🔥' + texto_limpo
            
        return texto_limpo
    
    def _limpar_descricao_basica(self, texto):
        """Limpeza básica para descrições sem 🔥"""
        texto_limpo = re.sub(r'[🧟‍♂️⚡️✨️✔️⚠️✅⭐️🇧🇷✍️💸📝✨➡️]', '', texto)
        texto_limpo = re.sub(r'\s*-\s*R\$\s*[\d\.,]+$', '', texto_limpo)
        texto_limpo = re.sub(r'\s*\(Cartão\)$', '', texto_limpo)
        texto_limpo = re.sub(r'\* \d+×', '', texto_limpo)  # Remove " * 1×"
        return texto_limpo.strip()
    
    def _limpar_cupom(self, texto):
        """Limpa e formata o texto do cupom"""
        texto = texto.strip()
        
        # Remove "para atingir o valor"
        texto = re.sub(r'\s*para\s*atingir.*$', '', texto, flags=re.IGNORECASE)
        
        # Remove "AQUI: http"
        texto = re.sub(r'AQUI:?\s*http.*$', '', texto, flags=re.IGNORECASE)
        
        # Remove espaços extras mas mantém estrutura
        texto = re.sub(r'\s+', ' ', texto)
        
        return texto.strip()

class FormatadorSaida:
    def __init__(self):
        pass
    
    def formatar(self, dados):
        """Formata no padrão exato"""
        partes = []
        
        partes.append(dados['descricao'])
        partes.append('')
        
        if dados['preco']:
            linha_preco = f"💵R${dados['preco']}"
            if dados['parcelamento']:
                linha_preco += f" em {dados['parcelamento']}"
            partes.append(linha_preco)
        else:
            partes.append("💵R$[preço]")
        
        if dados['cupom']:
            if dados['cupom'].startswith('Resgate'):
                partes.append(f"🎟{dados['cupom']}")
            else:
                partes.append(f"🎟Cupom: {dados['cupom']}")
        
        for i, link in enumerate(dados['links']):
            if i == 0:
                partes.append(f"🔗{link}")
            else:
                partes.append("📍Produto")
                partes.append(f"🔗{link}")
        
        return '\n'.join(partes)

# Instâncias globais
parser = ParserPromocoes()
formatador = FormatadorSaida()

async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa as mensagens recebidas"""
    try:
        texto_original = update.message.text
        
        # Processa a mensagem completa
        produtos = parser.processar_mensagem_completa(texto_original)
        
        if not produtos:
            await update.message.reply_text("❌ Não consegui identificar produtos válidos na mensagem.")
            return
        
        # Envia cada produto formatado
        for produto in produtos:
            mensagem_formatada = formatador.formatar(produto)
            await update.message.reply_text(mensagem_formatada)
        
    except Exception as e:
        logging.error(f"Erro: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao processar a mensagem.")

def main():
    # MUDANÇA AQUI: Só usa variável de ambiente, sem valor padrão
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        logging.error("❌ Token do bot não encontrado! Configure a variável BOT_TOKEN.")
        return
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))
    
    print("🤖 Bot Preguiça SUPER OTIMIZADO Iniciado!")
    application.run_polling()

if __name__ == '__main__':
    main()
